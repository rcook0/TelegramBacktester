from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Optional
import numpy as np
import pandas as pd

def split_symbol(sym: str):
    if len(sym) >= 6:
        return sym[:3].upper(), sym[3:6].upper()
    return sym.upper(), "USD"

PIP_DECIMALS = {"USDJPY": 0.01}
def pip_size(symbol: str, price_hint: float) -> float:
    if symbol in PIP_DECIMALS:
        return PIP_DECIMALS[symbol]
    s = str(price_hint)
    if len(s.split(".")[-1]) <= 2:
        return 0.01
    return 0.0001

def default_contract_size(symbol: str) -> float:
    base, quote = split_symbol(symbol)
    if base in ("XAU","XAG"):
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
                 account_ccy: str,
                 symbol_map: Dict[str,str], contract_map: Dict[str,float], conv_map: Dict[str,str],
                 exit_rule: str = "multi_tp",
                 tp_weights: Optional[List[float]] = None, risk_pct: Optional[float] = None,
                 spread_pips: Optional[float] = None, spread_map: Optional[Dict[str,float]] = None,
                 slippage_pips: float = 0.0, commission_per_lot: float = 0.0,
                 time_stop_min: Optional[int] = None, timeframe: str = "M1"):
        self.provider = provider
        self.default_lot = default_lot
        self.deposit = deposit
        self.leverage = leverage
        self.account_ccy = (account_ccy or "USD").upper()
        self.symbol_map = symbol_map or {}
        self.contract_map = contract_map or {}
        self.conv_map = conv_map or {}
        self.exit_rule = exit_rule
        self.tp_weights = tp_weights
        self.risk_pct = risk_pct
        self.spread_pips = spread_pips
        self.spread_map = spread_map or {}
        self.slippage_pips = slippage_pips
        self.commission_per_lot = commission_per_lot
        self.time_stop_min = time_stop_min
        self.timeframe = timeframe

    def run(self, signals, since: datetime, until: datetime):
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

            price_hint = float(first.iloc[0].get("open", first.iloc[0].get("bid_open", 0.0)))
            ps = pip_size(sig.symbol, price_hint)
            cs = self.contract_map.get(sig.symbol, default_contract_size(sig.symbol))

            entry_time = pd.to_datetime(first.iloc[0]["time"]).to_pydatetime()
            entry_bid, entry_ask = self._row_bid_ask(first.iloc[0], ps, sig.symbol)
            slip = self.slippage_pips * ps
            entry_price = (entry_ask + slip) if sig.side == "BUY" else (entry_bid - slip)

            lot = self._compute_lot(sig, entry_price, ps, equity, cs)

            hit_label, exit_time, exit_price, pnl_pips = self._simulate_path(sig, df[df["time"] >= entry_time], ps, entry_price)

            pnl_ccy = self._pnl_account(sig, pnl_pips, lot, ps, cs, when=exit_time)
            commission = self.commission_per_lot * lot
            pnl_net = pnl_ccy - commission

            margin_used = self._margin(sig, entry_price, lot, cs)
            equity += pnl_net

            trades.append(TradeResult(
                symbol=broker_symbol, side=sig.side, entry_time=entry_time, entry_price=entry_price,
                exit_time=exit_time, exit_price=exit_price, hit=hit_label, lot=float(f"{lot:.3f}"),
                pnl_pips=pnl_pips, pnl_ccy=pnl_net, commission=commission, margin_used=margin_used,
                equity_after=equity
            ))
        trades_df = pd.DataFrame([t.__dict__ for t in trades])
        summary = self._summarize(trades_df, start=since, end=until, start_equity=self.deposit)
        return {"trades": trades_df, "summary": summary}

    def _compute_lot(self, sig, entry: float, ps: float, equity: float, cs: float) -> float:
        if not self.risk_pct:
            return self.default_lot
        risk_ccy = equity * (self.risk_pct / 100.0)
        dist_pips = abs(entry - sig.sl) / ps
        if dist_pips <= 0:
            return self.default_lot
        base, quote = split_symbol(sig.symbol)
        pip_per_lot_quote = cs * ps  # e.g., 100k * 0.0001 = 10 quote-ccy
        rate = self._conversion_rate(quote, self.account_ccy, when=None)
        pip_per_lot_acct = pip_per_lot_quote * rate
        lot = risk_ccy / (dist_pips * pip_per_lot_acct)
        return max(0.01, lot)

    def _row_bid_ask(self, row, ps: float, symbol: str):
        cols = set(row.index) if hasattr(row, "index") else set()
        if {"bid_open","ask_open"} <= cols:
            return float(row["bid_open"]), float(row["ask_open"])
        mid = float(row.get("open", row.get("close", 0.0)))
        sp = row.get("spread_pips", np.nan)
        if pd.isna(sp):
            sp = self.spread_map.get(symbol, self.spread_pips or 0.0)
        half = (sp * ps) / 2.0
        return mid - half, mid + half

    def _simulate_path(self, sig, df: pd.DataFrame, ps: float, entry_price: float):
        use_ba = {"bid_high","bid_low","ask_high","ask_low"} <= set(df.columns)
        if not use_ba:
            sp_series = df.get("spread_pips", pd.Series([self.spread_map.get(sig.symbol, self.spread_pips or 0.0)]*len(df)))
            bid_high = df["high"] - (sp_series.values * ps)/2.0
            bid_low  = df["low"]  - (sp_series.values * ps)/2.0
            ask_high = df["high"] + (sp_series.values * ps)/2.0
            ask_low  = df["low"]  + (sp_series.values * ps)/2.0
            bid_close = df["close"] - (sp_series.values * ps)/2.0
            ask_close = df["close"] + (sp_series.values * ps)/2.0
        else:
            bid_high = df["bid_high"].astype(float).values
            bid_low  = df["bid_low"].astype(float).values
            ask_high = df["ask_high"].astype(float).values
            ask_low  = df["ask_low"].astype(float).values
            bid_close = df.get("bid_close", df["close"]).astype(float).values
            ask_close = df.get("ask_close", df["close"]).astype(float).values

        times = pd.to_datetime(df["time"]).values
        tps = sig.tps; sl = sig.sl
        hits = []

        if sig.side == "BUY":
            for i, tp in enumerate(tps, start=1):
                idx = np.where(ask_high >= tp)[0]
                if len(idx):
                    j = idx[0]; hits.append((f"TP{i}", times[j], float(ask_close[j])))
            idx_sl = np.where(bid_low <= sl)[0]
            if len(idx_sl):
                j = idx_sl[0]; hits.append(("SL", times[j], float(bid_close[j])))
        else:
            for i, tp in enumerate(tps, start=1):
                idx = np.where(bid_low <= tp)[0]
                if len(idx):
                    j = idx[0]; hits.append((f"TP{i}", times[j], float(bid_close[j])))
            idx_sl = np.where(ask_high >= sl)[0]
            if len(idx_sl):
                j = idx_sl[0]; hits.append(("SL", times[j], float(ask_close[j])))

        if self.time_stop_min:
            limit_time = pd.to_datetime(df["time"].iloc[0]) + pd.Timedelta(minutes=self.time_stop_min)
            ts_idx = np.where(times >= np.datetime64(limit_time))[0]
            if len(ts_idx):
                j = ts_idx[0]; hits.append(("TIME", times[j], float(df.iloc[j]["close"])))

        if not hits:
            last = df.tail(1).iloc[0]
            last_px = float((last.get("ask_close") if sig.side=="BUY" else last.get("bid_close")) or last["close"])
            pnl_pips = (1 if sig.side=="BUY" else -1) * (last_px - entry_price) / ps
            return ("EOD", pd.to_datetime(last["time"]).to_pydatetime(), last_px, float(pnl_pips))

        hits.sort(key=lambda x: x[1])

        if self.exit_rule == "first_target":
            label, t, px = hits[0]
            pnl_pips = (1 if sig.side=="BUY" else -1) * (px - entry_price) / ps
            return (label, pd.to_datetime(t).to_pydatetime(), px, float(pnl_pips))

        if hits[0][0] == "SL":
            label, t, px = hits[0]
            pnl_pips = (1 if sig.side=="BUY" else -1) * (px - entry_price) / ps
            return (label, pd.to_datetime(t).to_pydatetime(), px, float(pnl_pips))

        last_tp = None
        for label, t, px in hits:
            if label.startswith("TP"):
                last_tp = (label, t, px)
            else:
                break

        if last_tp is None:
            label, t, px = hits[0]
            pnl_pips = (1 if sig.side=="BUY" else -1) * (px - entry_price) / ps
            return (label, pd.to_datetime(t).to_pydatetime(), px, float(pnl_pips))

        if self.exit_rule == "multi_tp":
            label, t, px = last_tp
            pnl_pips = (1 if sig.side=="BUY" else -1) * (px - entry_price) / ps
            return (label, pd.to_datetime(t).to_pydatetime(), px, float(pnl_pips))

        reached = [h for h in hits if h[0].startswith("TP")]
        if self.exit_rule == "multi_tp_scaled" and reached:
            weights = self.tp_weights or [1.0/len(reached)]*len(reached)
            weights = weights[:len(reached)]
            s = sum(weights) or 1.0
            weights = [w/s for w in weights]
            avg_px = sum(px*w for (_,_,px), w in zip(reached, weights))
            last_t = reached[-1][1]
            pnl_pips = (1 if sig.side=="BUY" else -1) * (avg_px - entry_price) / ps
            return ("SCALED_TP", pd.to_datetime(last_t).to_pydatetime(), avg_px, float(pnl_pips))

        label, t, px = last_tp
        pnl_pips = (1 if sig.side=="BUY" else -1) * (px - entry_price) / ps
        return (label, pd.to_datetime(t).to_pydatetime(), px, float(pnl_pips))

    def _conversion_rate(self, from_ccy: str, to_ccy: str, when: Optional[datetime]) -> float:
        from_ccy = from_ccy.upper(); to_ccy = to_ccy.upper()
        if from_ccy == to_ccy:
            return 1.0
        key = f"{from_ccy}->{to_ccy}"
        if key in self.conv_map:
            sym = self.conv_map[key]
            rate = self._mid_at(sym, when)
            if rate is not None:
                if sym.upper().endswith(to_ccy):
                    return float(rate)
                else:
                    return float(1.0 / rate)
        direct = f"{from_ccy}{to_ccy}"; reverse = f"{to_ccy}{from_ccy}"
        for sym in (direct, reverse):
            rate = self._mid_at(sym, when)
            if rate is not None:
                return float(rate if sym == direct else 1.0 / rate)
        return 1.0

    def _mid_at(self, symbol: str, when: Optional[datetime]) -> Optional[float]:
        try:
            end = when or datetime.now(timezone.utc)
            start = end - timedelta(days=2)
            df = self.provider.candles(symbol, start, end, timeframe=self.timeframe)
            if df is None or df.empty:
                return None
            row = df.tail(1).iloc[0]
            if "close" in df.columns:
                return float(row["close"])
            if "bid_close" in df.columns and "ask_close" in df.columns:
                return float((row["bid_close"] + row["ask_close"]) / 2.0)
        except Exception:
            return None
        return None

    def _pnl_account(self, sig, pnl_pips: float, lot: float, ps: float, cs: float, when: Optional[datetime]) -> float:
        base, quote = split_symbol(sig.symbol)
        pip_per_lot_quote = cs * ps
        rate = self._conversion_rate(quote, self.account_ccy, when)
        pip_per_lot_acct = pip_per_lot_quote * rate
        return float(pnl_pips * pip_per_lot_acct * lot)

    def _margin(self, sig, price: float, lot: float, cs: float) -> float:
        base, quote = split_symbol(sig.symbol)
        notional_quote = cs * lot * price
        rate = self._conversion_rate(quote, self.account_ccy, when=None)
        notional_acct = notional_quote * rate
        return float(notional_acct / self.leverage)

    def _summarize(self, trades_df: pd.DataFrame, start: datetime, end: datetime, start_equity: float) -> Dict:
        if trades_df.empty:
            return {"trades": 0, "win_rate": 0, "profit_factor": 0, "net_pnl": 0, "max_dd": 0, "final_equity": start_equity}
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
