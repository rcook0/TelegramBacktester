from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import numpy as np
import pandas as pd
def split_symbol(sym: str):
    if len(sym) >= 6: return sym[:3].upper(), sym[3:6].upper()
    return sym.upper(), "USD"
PIP_DECIMALS = {"USDJPY": 0.01}
def pip_size(symbol: str, price_hint: float) -> float:
    if symbol in PIP_DECIMALS: return PIP_DECIMALS[symbol]
    s=str(price_hint); return 0.01 if len(s.split(".")[-1])<=2 else 0.0001
def default_contract_size(symbol: str) -> float:
    base,_=split_symbol(symbol); return 100.0 if base in ("XAU","XAG") else 100_000.0
@dataclass
class TradeResult:
    symbol: str; side: str; entry_time: datetime; entry_price: float; exit_time: datetime; exit_price: float; hit: str
    lot: float; pnl_pips: float; pnl_account_ccy: float; pnl_quote_ccy: float; commission: float; margin_used: float; equity_after: float
class Backtester:
    def __init__(self, provider, default_lot: float, deposit: float, leverage: int, account_ccy: str,
                 symbol_map: Dict[str,str], contract_map: Dict[str,float], conv_map: Dict[str,str],
                 exit_rule: str="multi_tp", tp_weights: Optional[List[float]]=None, risk_pct: Optional[float]=None,
                 spread_pips: float=0.0, slippage_pips: float=0.0, commission_per_lot: float=0.0,
                 time_stop_min: Optional[int]=None, timeframe: str="M1"):
        self.provider=provider; self.default_lot=default_lot; self.deposit=deposit; self.leverage=leverage
        self.account_ccy=(account_ccy or "USD").upper(); self.symbol_map=symbol_map or {}; self.contract_map=contract_map or {}; self.conv_map=conv_map or {}
        self.exit_rule=exit_rule; self.tp_weights=tp_weights; self.risk_pct=risk_pct; self.spread_pips=spread_pips; self.slippage_pips=slippage_pips
        self.commission_per_lot=commission_per_lot; self.time_stop_min=time_stop_min; self.timeframe=timeframe
    def run(self, signals, since: datetime, until: datetime):
        trades=[]; equity=self.deposit
        for sig in signals:
            if not (since<=sig.dt<=until): continue
            sym=self.symbol_map.get(sig.symbol, sig.symbol)
            df=self.provider.candles(sym, since, until, timeframe=self.timeframe)
            if df is None or df.empty: continue
            first=df[df["time"]>=sig.dt].head(1); if first.empty: continue
            ps=pip_size(sig.symbol, float(first.iloc[0].get("open", first.iloc[0]["close"])))
            cs=self.contract_map.get(sig.symbol, default_contract_size(sig.symbol))
            entry_time=pd.to_datetime(first.iloc[0]["time"]).to_pydatetime()
            entry_mid=float(first.iloc[0].get("open", first.iloc[0]["close"])); slip=self.slippage_pips*ps
            entry_price=entry_mid+slip if sig.side=="BUY" else entry_mid-slip
            lot=self._lot(sig, entry_price, ps, equity, cs)
            hit, xt, xp, pnl_pips=self._path(sig, df[df["time"]>=entry_time], ps, entry_price)
            base, quote=split_symbol(sig.symbol); pip_per_lot_quote=cs*ps
            pnl_quote=pnl_pips*pip_per_lot_quote*lot; rate=self._fx(quote, self.account_ccy, xt); pnl_acct=pnl_quote*rate
            comm=self.commission_per_lot*lot; pnl_net=pnl_acct-comm; margin=self._margin(sig, entry_price, lot, cs); equity+=pnl_net
            trades.append(TradeResult(sym, sig.side, entry_time, entry_price, xt, xp, hit, float(f"{lot:.3f}"), float(pnl_pips),
                                      float(pnl_acct), float(pnl_quote), float(comm), float(margin), float(equity)))
        dftr=pd.DataFrame([t.__dict__ for t in trades]); return {"trades": dftr, "summary": self._sum(dftr, since, until, self.deposit)}
    def _lot(self, sig, entry, ps, equity, cs):
        if not self.risk_pct: return self.default_lot
        risk=equity*(self.risk_pct/100.0); dist=abs(entry-sig.sl)/ps; 
        if dist<=0: return self.default_lot
        pip_per_lot_quote=cs*ps; base,quote=split_symbol(sig.symbol); rate=self._fx(quote, self.account_ccy, None)
        pip_per_lot_acct=pip_per_lot_quote*rate; lot=risk/(dist*pip_per_lot_acct); return max(0.01, lot)
    def _path(self, sig, df, ps, entry_price):
        tps=sig.tps; sl=sig.sl; hits=[]
        if sig.side=="BUY":
            for i,tp in enumerate(tps,1):
                r=df[df["high"]>=tp].head(1); 
                if not r.empty: r=r.iloc[0]; hits.append((f"TP{i}", r["time"], float(r["close"])))
            r=df[df["low"]<=sl].head(1); 
            if not r.empty: r=r.iloc[0]; hits.append(("SL", r["time"], float(r["close"])))
        else:
            for i,tp in enumerate(tps,1):
                r=df[df["low"]<=tp].head(1); 
                if not r.empty: r=r.iloc[0]; hits.append((f"TP{i}", r["time"], float(r["close"])))
            r=df[df["high"]>=sl].head(1); 
            if not r.empty: r=r.iloc[0]; hits.append(("SL", r["time"], float(r["close"])))
        if self.time_stop_min:
            t0=pd.to_datetime(df["time"].iloc[0]); ts=df[df["time"]>=t0+pd.Timedelta(minutes=self.time_stop_min)].head(1)
            if not ts.empty: r=ts.iloc[0]; hits.append(("TIME", r["time"], float(r["close"])))
        if not hits:
            last=df.tail(1).iloc[0]; pnl=(1 if sig.side=="BUY" else -1)*(float(last["close"])-entry_price)/ps
            return ("EOD", pd.to_datetime(last["time"]).to_pydatetime(), float(last["close"]), float(pnl))
        hits.sort(key=lambda x: x[1])
        if self.exit_rule=="first_target" or hits[0][0]=="SL":
            lab,t,px=hits[0]; pnl=(1 if sig.side=="BUY" else -1)*(px-entry_price)/ps; return (lab, pd.to_datetime(t).to_pydatetime(), px, float(pnl))
        last_tp=None; barrier=None
        for lab,t,px in hits:
            if lab.startswith("TP"): last_tp=(lab,t,px)
            else: barrier=t; break
        if last_tp is None:
            lab,t,px=hits[0]; pnl=(1 if sig.side=="BUY" else -1)*(px-entry_price)/ps; return (lab, pd.to_datetime(t).to_pydatetime(), px, float(pnl))
        if self.exit_rule=="multi_tp":
            lab,t,px=last_tp; pnl=(1 if sig.side=="BUY" else -1)*(px-entry_price)/ps; return (lab, pd.to_datetime(t).to_pydatetime(), px, float(pnl))
        reached=[h for h in hits if h[0].startswith("TP")]
        weights=self.tp_weights or [1.0/len(reached)]*len(reached); weights=weights[:len(reached)]; s=sum(weights) or 1.0; weights=[w/s for w in weights]
        avg_px=sum(px*w for (_,_,px),w in zip(reached,weights)); last_t=reached[-1][1]
        pnl=(1 if sig.side=="BUY" else -1)*(avg_px-entry_price)/ps
        return ("SCALED_TP", pd.to_datetime(last_t).to_pydatetime(), avg_px, float(pnl))
    def _fx(self, f, t, when):
        if f==t: return 1.0
        direct=f+t; rev=t+f
        for sym in (direct, rev):
            try:
                end=when or datetime.now(timezone.utc); start=end-pd.Timedelta(days=2)
                df=self.provider.candles(sym, start, end, timeframe=self.timeframe)
                if df is not None and not df.empty:
                    px=float(df.tail(1).iloc[0].get("close", df.tail(1).iloc[0]["open"]))
                    return px if sym==direct else 1.0/px
            except Exception: pass
        key=f"{f}->{t}"
        return 1.0
    def _margin(self, sig, price, lot, cs):
        base, quote=split_symbol(sig.symbol); notion=cs*lot*price; rate=self._fx(quote, self.account_ccy, None)
        return float((notion*rate)/self.leverage)
    def _sum(self, df, start, end, start_equity):
        if df.empty: return {"trades":0,"win_rate":0,"profit_factor":0,"net_pnl_account":0,"net_pnl_pips":0,"max_dd":0,"final_equity":start_equity}
        wins=df[df["pnl_account_ccy"]>0]; losses=df[df["pnl_account_ccy"]<=0]
        gp=wins["pnl_account_ccy"].sum(); gl=-losses["pnl_account_ccy"].sum(); pf=(gp/gl) if gl!=0 else float("inf")
        eq=df["equity_after"].values; peak=np.maximum.accumulate(eq); dd=(eq-peak)/np.where(peak==0,1,peak); mx=dd.min() if len(dd) else 0
        return {"period_start":start.isoformat(),"period_end":end.isoformat(),"trades":int(len(df)),
                "win_rate":float(len(wins)/len(df)) if len(df) else 0.0,"profit_factor":float(pf),
                "net_pnl_account":float(df["pnl_account_ccy"].sum()),"net_pnl_pips":float(df["pnl_pips"].sum()),
                "max_dd":float(mx),"final_equity":float(df["equity_after"].iloc[-1]) if len(df) else start_equity,
                "commissions":float(df["commission"].sum())}
