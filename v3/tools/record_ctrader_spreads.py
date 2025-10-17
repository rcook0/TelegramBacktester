"""
Run the cTrader live spread recorder and flush to CSV on an interval.
"""
import argparse, time
from src.tools.ctrader_spreads import CTraderSpreadsRecorder

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", required=True, help="Comma-separated symbols (cTrader names)")
    ap.add_argument("--out", required=True, help="Dir for spread CSVs")
    ap.add_argument("--flush-sec", type=int, default=30)
    args = ap.parse_args()
    rec = CTraderSpreadsRecorder([s.strip() for s in args.symbols.split(",") if s.strip()])
    try:
        while True:
            time.sleep(max(args.flush_sec, 10))
            rec.flush_minute(args.out)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
