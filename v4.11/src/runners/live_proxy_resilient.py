from __future__ import annotations
import argparse, os, time
from datetime import datetime, timezone
from ..storage.sqlite_store import Store
from ..replay.idempotency import signal_idem_key
from ..net.rate_limiter import TokenBucket
from ..risk.risk_gate import RiskGate, GateConfig
from ..execution.trade_executor import ExecConfig, CTraderExecutor

def parse_args():
    p=argparse.ArgumentParser(description='Resilient live proxy (idempotent + persistent)')
    p.add_argument('--db', required=True)
    p.add_argument('--channel', required=True)
    p.add_argument('--exec-mode', choices=['dry','live'], default='dry')
    p.add_argument('--max-rps', type=float, default=5.0)
    p.add_argument('--burst', type=int, default=10)
    p.add_argument('--spread-ceil', type=float, default=0.0)
    p.add_argument('--max-adverse-wap-pct', type=float, default=0.0)
    p.add_argument('--max-sym-risk', type=float, default=0.02)
    p.add_argument('--max-total-risk', type=float, default=0.05)
    p.add_argument('--session', type=str, default='')
    p.add_argument('--whitelist', type=str, default='')
    return p.parse_args()

def main():
    args=parse_args(); os.makedirs(os.path.dirname(args.db), exist_ok=True)
    store=Store(args.db); run_id=store.new_run({'channel':args.channel,'exec_mode':args.exec_mode}); print('Run',run_id,'DB=',args.db)
    limiter=TokenBucket(rate_per_sec=args.max_rps, burst=args.burst)
    gate=RiskGate(GateConfig(spread_ceil_pips=args.spread_ceil, max_adverse_wap_pct=args.max_adverse_wap_pct,
                             max_sym_risk=args.max_sym_risk, max_total_risk=args.max_total_risk,
                             whitelist=[s.strip() for s in args.whitelist.split(',') if s.strip()] or None,
                             sessions=[s.strip() for s in args.session.split(',') if s.strip()] or None),
                   CTraderExecutor(ExecConfig(exec_mode=args.exec_mode)))
    sample=[dict(channel=args.channel, ts=datetime.now(timezone.utc).isoformat(), symbol='XAUUSD', side='LONG', lot=0.1,
                 entry_px=2375.2, sl_px=2373.8, intended_wap=2375.25, spread_pips=0.8, pip_value_usd=10.0, tps=[2376.0,2376.5])]
    for sig in sample:
        while not limiter.take(): time.sleep(0.01)
        idem=signal_idem_key(dict(channel=sig['channel'], minute=sig['ts'][:16], side=sig['side'], symbol=sig['symbol'], entry=round(sig['entry_px'],3), sl=round(sig['sl_px'],3), tps=[round(x,3) for x in sig.get('tps',[])]))
        sid=store.upsert_signal(idem, sig['ts'], sig['channel'], sig)
        d=gate.decide(symbol=sig['symbol'], side=sig['side'], lot=sig['lot'], entry_px=sig['entry_px'], sl_px=sig['sl_px'], intended_wap=sig['intended_wap'], spread_pips=sig['spread_pips'], pip_value_usd=sig['pip_value_usd'])
        store.add_decision(sid, d.allow, d.reasons)
        if not d.allow: print('BLOCKED:', d.reasons); continue
        if args.exec_mode=='live':
            oid=CTraderExecutor(ExecConfig(exec_mode='live')).submit_market(sig['symbol'], sig['side'], sig['lot'], sl=sig['sl_px'], tps=sig.get('tps',[]))
            store.add_order(sid, oid, sig['side'], sig['symbol'], sig['lot'], sig['sl_px'], sig.get('tps',[])); print('Submitted', oid)
        else:
            print('Dry-run OK:', sig['symbol'], sig['side'])

if __name__=='__main__': main()
