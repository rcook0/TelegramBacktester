from __future__ import annotations
import argparse
from ..risk.risk_gate import RiskGate, GateConfig
from ..execution.trade_executor import ExecConfig, CTraderExecutor

def parse_args():
    p = argparse.ArgumentParser(description='Telegram→RiskGate→(Executor) live proxy')
    p.add_argument('--channel', required=True)
    p.add_argument('--exec-mode', choices=['dry','live'], default='dry')
    p.add_argument('--spread-ceil', type=float, default=0.0)
    p.add_argument('--max-adverse-wap-pct', type=float, default=0.0)
    p.add_argument('--max-sym-risk', type=float, default=0.02)
    p.add_argument('--max-total-risk', type=float, default=0.05)
    p.add_argument('--session', type=str, default='')
    p.add_argument('--whitelist', type=str, default='')
    p.add_argument('--ctrader-client-id')
    p.add_argument('--ctrader-client-secret')
    p.add_argument('--ctrader-access-token')
    p.add_argument('--ctrader-account-id', type=int)
    p.add_argument('--ctrader-host', choices=['LIVE','DEMO'], default='LIVE')
    return p.parse_args()

def build_gate(args):
    sessions = [s.strip() for s in args.session.split(',') if s.strip()]
    wl = [s.strip() for s in args.whitelist.split(',') if s.strip()] or None
    gcfg = GateConfig(spread_ceil_pips=args.spread_ceil, max_adverse_wap_pct=args.max_adverse_wap_pct,
                      max_sym_risk=args.max_sym_risk, max_total_risk=args.max_total_risk,
                      whitelist=wl, sessions=sessions or None)
    ecfg = ExecConfig(exec_mode=args.exec_mode, account_id=args.ctrader_account_id,
                      client_id=args.ctrader_client_id, client_secret=args.ctrader_client_secret,
                      access_token=args.ctrader_access_token, host=args.ctrader_host)
    exe = CTraderExecutor(ecfg)
    return RiskGate(gcfg, exe), exe

def main():
    args = parse_args()
    gate, exe = build_gate(args)
    # Example signal (replace with TG feed)
    sig = dict(symbol='XAUUSD', side='LONG', lot=0.10, entry_px=2375.2, sl_px=2373.8,
               intended_wap=2375.3, spread_pips=1.0, pip_value_usd=10.0)
    d = gate.decide(**sig)
    print('Decision:', d.allow, d.reasons)
    if d.allow and args.exec_mode == 'live':
        oid = exe.submit_market(sig['symbol'], sig['side'], sig['lot'], sl=sig['sl_px'])
        print('Submitted', oid)
    else:
        print('Dry-run or blocked; no order sent')

if __name__ == '__main__':
    main()
