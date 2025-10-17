"""
Run the cTrader live spread recorder and flush to CSV on an interval.
"""
#!/usr/bin/env python
import argparse, time
from src.tools.ctrader_spreads import CTraderSpreadsRecorder

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", required=True, help="Comma-separated cTrader symbols")
    ap.add_argument("--mode", choices=["top","weighted"], default="top")
    ap.add_argument("--out", required=True, help="Dir for spread CSVs")
    # runtime auth (no env)
    ap.add_argument("--ctrader-client-id", required=True)
    ap.add_argument("--ctrader-client-secret", required=True)
    ap.add_argument("--ctrader-access-token", required=True)
    ap.add_argument("--ctrader-account-id", type=int, required=True)
    ap.add_argument("--ctrader-host", choices=["LIVE","DEMO"], default="LIVE")
    ap.add_argument("--flush-sec", type=int, default=30)
    args = ap.parse_args()

    rec = CTraderSpreadsRecorder(
        symbols=[s.strip() for s in args.symbols.split(",") if s.strip()],
        mode=args.mode,
        client_id=args.ctrader_client_id,
        client_secret=args.ctrader_client_secret,
        access_token=args.ctrader_access_token,
        account_id=args.ctrader_account_id,
        host=args.ctrader_host,
    )
    try:
        while True:
            time.sleep(max(args.flush_sec, 10))
            rec.flush_minute(args.out)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
