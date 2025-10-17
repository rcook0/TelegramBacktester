from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Optional
import numpy as np
import pandas as pd

from .signal_parser import Signal

PIP_DECIMALS = {
    "USDJPY": 0.01,
}

def pip_size(symbol: str, price_hint: float) -> float:
    if symbol in PIP_DECIMALS:
        return PIP_DECIMALS[symbol]
    s = str(price_hint)
    if len(s.split(".")[-1]) <= 2:
        return 0.01
    return 0.0001

def contract_size(symbol: str) -> float:
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
    hit: str
    lot: float
    pnl_pips: float
    pnl_ccy: float
    commission: float
    margin_used: float
    equity_after: float

class Backtester:
    def __init__(self, provider, default_lot: float, deposit: float, leverage: int,
                 symbol_map: Dict[str,str], exit_rule: str = "multi_tp",
                 tp_weights: Optional[List[float]] = None, risk_pct: Optional[float] = None,
                 spread_pips: float = 0.0, slippage_pips: float = 0.0, commission_per_lot: float = 0.0,
                 time_stop_min: Optional[int] = None, timeframe: str = "M1"):
        self.provider = provider
        self.default_lot = default_lot
        self.deposit = deposit
        self.leverage = leverage
        self.symbol_map = symbol_map or {}
        self.exit_rule = exit_rule
        self.tp_weights = tp_weights
        self.risk_pct = risk_pct
        self.spread_pips = spread_pips
        self.slippage_pips = slippage_pips
        self.commission_per_lot = commission_per_lot
        self.time_stop_min = time_stop_min
        self.timeframe = timeframe

    def run(self, signals: List[Signal], since: datetime, until: datetime):
        trades: List[TradeResult] = []
        equity = self.deposit
        for sig in signals:
            if not (since <= sig.dt <= until):
                continue
            broker_symbol = self.symbol_map.get(sig.symbol, sig.symbol)
            df = self.provider.candles(broker_symbol, sig.dt, until, timeframe=self.timeframe)
            if df is None or df.empty:
                continue
            first = df[df["time"] >= sig.dt].head(1)
            if first.empty:
                continue

            ps = pip_size(sig.symbol, float(first.iloc[0]["open"]))
            entry_time = pd.to_datetime(first.iloc[0]["time"]).to_pydatetime()
            entry_mid = float(first.iloc[0]["open"])
            slip = self.slippage_pips * ps
            entry_price = entry_mid + slip if sig.side == "BUY" else entry_mid - slip

            lot = self._compute_lot(sig, entry_price, ps, equity)

            hit_label, exit_time, exit_price, pnl_pips = self._simulate_path(sig, df[df["time"] >= entry_time], ps, entry_price)

            pnl_ccy = self._pnl_ccy(sig, pnl_pips, lot, ps, sig.symbol)
            commission = self.commission_per_lot * lot
            pnl_ccy_net = pnl_ccy - commission
            margin_used = self._margin(sig, entry_price, lot)

            equity += pnl_ccy_net
            trades.append(TradeResult(
                symbol=broker_symbol, side=sig.side, entry_time=entry_time, entry_price=entry_price,
                exit_time=exit_time, exit_price=exit_price, hit=hit_label, lot=float(f"{lot:.3f}"),
                pnl_pips=pnl_pips, pnl_ccy=pnl_ccy_net, commission=commission, margin_used=margin_used,
                equity_after=equity
            ))
        trades_df = pd.DataFrame([t.__dict__ for t in trades])
        summary = self._summarize(trades_df, start=since, end=until, start_equity=self.deposit)
        return {"trades": trades_df, "summary": summary}

    def _compute_lot(self, sig: Signal, entry: float, ps: float, equity: float) -> float:
        if not self.risk_pct:
            return self.default_lot
        risk_ccy = equity * (self.risk_pct / 100.0)
        dist = abs(entry - sig.sl) / ps
        if dist <= 0:
            return self.default_lot
        pip_value_per_lot = contract_size(sig.symbol) * ps
        lot = risk_ccy / (dist * pip_value_per_lot)
        return max(0.01, lot)

    def _apply_spread_to_levels(self, sig: Signal, ps: float):
        half_spread = (self.spread_pips * ps) / 2.0
        if sig.side == "BUY":
            tps = [tp + half_spread for tp in sig.tps]
            sl = sig.sl - half_spread
        else:
            tps = [tp - half_spread for tp in sig.tps]
            sl = sig.sl + half_spread
        return sl, tps

    def _simulate_path(self, sig: Signal, df: pd.DataFrame, ps: float, entry_price: float) -> Tuple[str, datetime, float, float]:
        adj_sl, adj_tps = self._apply_spread_to_levels(sig, ps)

        time_limit = None
        if self.time_stop_min:
            time_limit = df["time"].iloc[0] + pd.Timedelta(minutes=self.time_stop_min)

        hit_times = {}
        for i, tp in enumerate(adj_tps, start=1):
            if sig.side == "BUY":
                hitdf = df[df["high"] >= tp].head(1)
            else:
                hitdf = df[df["low"] <= tp].head(1)
            if not hitdf.empty:
                hit_times[f"TP{i}"] = hitdf.iloc[0]

        if sig.side == "BUY":
            sl_hitdf = df[df["low"] <= adj_sl].head(1)
        else:
            sl_hitdf = df[df["high"] >= adj_sl].head(1)
        sl_row = sl_hitdf.iloc[0] if not sl_hitdf.empty else None

        candidates = []
        for label, row in hit_times.items():
            candidates.append((label, row["time"], float(row["close"])))
        if sl_row is not None:
            candidates.append(("SL", sl_row["time"], float(sl_row["close"])))

        if time_limit is not None:
            ts_row = df[df["time"] >= time_limit].head(1)
            if not ts_row.empty:
                candidates.append(("TIME", ts_row.iloc[0]["time"], float(ts_row.iloc[0]["close"])))

        if len(candidates) == 0:
            last = df.tail(1).iloc[0]
            pnl_pips = (1 if sig.side=="BUY" else -1) * (float(last["close"]) - entry_price) / ps
            return ("EOD", pd.to_datetime(last["time"]).to_pydatetime(), float(last["close"]), float(pnl_pips))

        candidates.sort(key=lambda x: x[1])

        if self.exit_rule == "first_target":
            label, t, px = candidates[0]
            pnl_pips = (1 if sig.side=="BUY" else -1) * (px - entry_price) / ps
            return (label, pd.to_datetime(t).to_pydatetime(), px, float(pnl_pips))

        if candidates[0][0] == "SL":
            label, t, px = candidates[0]
            pnl_pips = (1 if sig.side=="BUY" else -1) * (px - entry_price) / ps
            return (label, pd.to_datetime(t).to_pydatetime(), px, float(pnl_pips))

        last_tp = None
        barrier_time = None
        for label, t, px in candidates:
            if label.startswith("TP"):
                last_tp = (label, t, px)
            else:
                barrier_time = t
                break

        if last_tp is None:
            label, t, px = candidates[0]
            pnl_pips = (1 if sig.side=="BUY" else -1) * (px - entry_price) / ps
            return (label, pd.to_datetime(t).to_pydatetime(), px, float(pnl_pips))

        if self.exit_rule == "multi_tp":
            label, t, px = last_tp
            pnl_pips = (1 if sig.side=="BUY" else -1) * (px - entry_price) / ps
            return (label, pd.to_datetime(t).to_pydatetime(), px, float(pnl_pips))

        reached = []
        for i in range(1, 1 + len(sig.tps)):
            k = f"TP{i}"
            if k in hit_times:
                trow = hit_times[k]
                if barrier_time is None or trow["time"] <= barrier_time:
                    reached.append((k, float(trow["close"])))
        if not reached:
            label, t, px = last_tp
            pnl_pips = (1 if sig.side=="BUY" else -1) * (px - entry_price) / ps
            return (label, pd.to_datetime(t).to_pydatetime(), px, float(pnl_pips))

        weights = self.tp_weights or [1.0/len(reached)]*len(reached)
        weights = weights[:len(reached)]
        s = sum(weights)
        weights = [w/s for w in weights]

        avg_px = 0.0
        for (k, px), w in zip(reached, weights):
            avg_px += px * w
        pnl_pips = (1 if sig.side=="BUY" else -1) * (avg_px - entry_price) / ps
        last_t = max([hit_times[k]["time"] for k,_ in reached])
        return ("SCALED_TP", pd.to_datetime(last_t).to_pydatetime(), avg_px, float(pnl_pips))

    def _pnl_ccy(self, sig: Signal, pnl_pips: float, lot: float, ps: float, symbol: str) -> float:
        pip_usd_per_lot = contract_size(symbol) * ps
        return float(pnl_pips * pip_usd_per_lot * lot)

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
        dd = (equity_curve - peak) / np.where(peak==0, 1, peak)
        max_dd = dd.min() if len(dd) else 0
        return {
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "trades": int(len(trades_df)),
            "win_rate": float(len(wins) / len(trades_df)) if len(trades_df) else 0.0,
            "profit_factor": float(profit_factor),
            "net_pnl": float(trades_df["pnl_ccy"].sum()),
            "max_dd": float(max_dd),
            "final_equity": float(trades_df["equity_after"].iloc[-1]) if len(trades_df) else start_equity,
            "commissions": float(trades_df["commission"].sum()) if "commission" in trades_df else 0.0
        }
