from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Tuple
import numpy as np
import pandas as pd

from .signal_parser import Signal

PIP_DECIMALS = {
    # Default pip decimal places (can be overridden by broker tick size)
    # EURUSD: 0.0001 -> 1 pip = 0.0001
    "USDJPY": 0.01,
}

def pip_size(symbol: str, price: float) -> float:
    if symbol in PIP_DECIMALS:
        return PIP_DECIMALS[symbol]
    # Heuristic: 2 dp -> JPY-style, else 4 dp
    s = str(price)
    if len(s.split(".")[-1]) <= 2:
        return 0.01
    return 0.0001

def contract_size(symbol: str) -> float:
    # 1 standard lot = 100,000 for FX majors, 100 for metals like XAUUSD (varies by broker)
    if symbol.startswith("XAU"):
        return 100.0
    return 100_000.0

@dataclass
class TradeResult:
    symbol: str
    side: str
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    hit: str  # TP1/TP2/.../SL
    lot: float
    pnl_pips: float
    pnl_ccy: float
    margin_used: float
    equity_after: float

class Backtester:
    def __init__(self, provider, default_lot: float, deposit: float, leverage: int,
                 symbol_map: Dict[str,str], exit_rule: str = "multi_tp"):
        self.provider = provider
        self.default_lot = default_lot
        self.deposit = deposit
        self.leverage = leverage
        self.symbol_map = symbol_map or {}
        self.exit_rule = exit_rule

    def run(self, signals: List[Signal], since: datetime, until: datetime):
        trades: List[TradeResult] = []
        equity = self.deposit
        for sig in signals:
            if not (since <= sig.dt <= until):
                continue
            broker_symbol = self.symbol_map.get(sig.symbol, sig.symbol)
            # Pull 1D window around signal for exit logic
            df = self.provider.candles(broker_symbol, sig.dt, until, timeframe="M1")
            if df.empty:
                continue
            # entry at next candle open after signal time
            first = df[df["time"] >= sig.dt].head(1)
            if first.empty:
                continue
            entry_time = pd.to_datetime(first.iloc[0]["time"]).to_pydatetime()
            entry_price = float(first.iloc[0]["open"])  # conservative
            # simulate path for SL/TP hits
            hit_label, exit_time, exit_price = self._simulate_path(sig, df[df["time"] >= entry_time])
            pnl_pips, pnl_ccy = self._pnl(sig, entry_price, exit_price, lot=self.default_lot)
            margin_used = self._margin(sig, entry_price, lot=self.default_lot)
            equity += pnl_ccy
            trades.append(TradeResult(
                symbol=broker_symbol, side=sig.side, entry_time=entry_time, entry_price=entry_price,
                exit_time=exit_time, exit_price=exit_price, hit=hit_label, lot=self.default_lot,
                pnl_pips=pnl_pips, pnl_ccy=pnl_ccy, margin_used=margin_used, equity_after=equity
            ))
        trades_df = pd.DataFrame([t.__dict__ for t in trades])
        summary = self._summarize(trades_df, start=since, end=until, start_equity=self.deposit)
        return {"trades": trades_df, "summary": summary}

    def _simulate_path(self, sig: Signal, df: pd.DataFrame) -> Tuple[str, datetime, float]:
        # For each minute, check if SL or any TP is hit. If multi_tp: exit at final TP if sequence hits monotonically.
        tps = sig.tps
        if sig.side == "BUY":
            sl_hit = df[df["low"] <= sig.sl]
            tp_hits = [df[df["high"] >= tp].head(1) for tp in tps]
        else:
            sl_hit = df[df["high"] >= sig.sl]
            tp_hits = [df[df["low"] <= tp].head(1) for tp in tps]

        # Determine first time each level is reached
        levels = []
        for i,hitdf in enumerate(tp_hits, start=1):
            if not hitdf.empty:
                levels.append(("TP"+str(i), hitdf.iloc[0]["time"], hitdf.iloc[0]["close"]))
        if not sl_hit.empty:
            levels.append(("SL", sl_hit.iloc[0]["time"], sl_hit.iloc[0]["close"]))

        if len(levels)==0:
            # no exit -> close at last candle
            last = df.tail(1).iloc[0]
            return ("EOD", pd.to_datetime(last["time"]).to_pydatetime(), float(last["close"]))

        # Sort by time
        levels.sort(key=lambda x: x[1])
        if self.exit_rule == "first_target":
            label, t, px = levels[0]
            return (label, pd.to_datetime(t).to_pydatetime(), float(px))
        else:
            # multi_tp: if SL hits before any TP -> SL
            if levels[0][0] == "SL":
                label, t, px = levels[0]
                return (label, pd.to_datetime(t).to_pydatetime(), float(px))
            # else exit at last TP that is hit before SL
            last_tp = levels[0]
            for label, t, px in levels:
                if label.startswith("TP"):
                    last_tp = (label, t, px)
                else:
                    # SL hit after some TPs; take last TP before SL
                    break
            label, t, px = last_tp
            return (label, pd.to_datetime(t).to_pydatetime(), float(px))

    def _pnl(self, sig: Signal, entry: float, exitp: float, lot: float) -> Tuple[float, float]:
        ps = pip_size(sig.symbol, entry)
        direction = 1 if sig.side == "BUY" else -1
        pip_move = direction * (exitp - entry) / ps
        # pip value approximation in account currency USD; for cross pairs require conversion (omitted for MVP)
        # For simplicity assume pip value per lot: FX majors ~ $10 per pip for 1.0 lot; metals differ
        cs = contract_size(sig.symbol)
        # value per pip = contract_size * pip_size
        pip_usd_per_lot = cs * ps
        pnl_ccy = pip_move * pip_usd_per_lot * lot
        return float(pip_move), float(pnl_ccy)

    def _margin(self, sig: Signal, price: float, lot: float) -> float:
        cs = contract_size(sig.symbol)
        notional = cs * lot * price
        margin = notional / self.leverage
        return float(margin)

    def _summarize(self, trades_df: pd.DataFrame, start: datetime, end: datetime, start_equity: float) -> Dict:
        if trades_df.empty:
            return {"trades": 0, "win_rate": 0, "profit_factor": 0, "net_pnl": 0, "max_dd": 0}
        wins = trades_df[trades_df["pnl_ccy"] > 0]
        losses = trades_df[trades_df["pnl_ccy"] <= 0]
        gross_profit = wins["pnl_ccy"].sum()
        gross_loss = -losses["pnl_ccy"].sum()
        profit_factor = (gross_profit / gross_loss) if gross_loss != 0 else np.inf
        equity_curve = trades_df["equity_after"].values
        peak = np.maximum.accumulate(equity_curve)
        dd = (equity_curve - peak) / peak
        max_dd = dd.min() if len(dd) else 0
        return {
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "trades": int(len(trades_df)),
            "win_rate": float(len(wins) / len(trades_df)) if len(trades_df) else 0.0,
            "profit_factor": float(profit_factor),
            "net_pnl": float(trades_df["pnl_ccy"].sum()),
            "max_dd": float(max_dd),
            "final_equity": float(trades_df["equity_after"].iloc[-1]),
        }
