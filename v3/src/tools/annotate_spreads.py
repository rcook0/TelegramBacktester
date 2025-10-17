"""
Merge recorded per-minute spreads into an OHLC CSV as a `spread_pips` column.
"""
import os, argparse, pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candles", required=True, help="Path to candles CSV (time,open,high,low,close,volume)")
    ap.add_argument("--spreads", required=True, help="Path to spreads CSV (bucket,spread_pips)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    c = pd.read_csv(args.candles, parse_dates=["time"])
    s = pd.read_csv(args.spreads, parse_dates=["bucket"])
    s = s.rename(columns={"bucket":"time"})
    out = c.merge(s, on="time", how="left")
    out.to_csv(args.out, index=False)
    print(f"Wrote {args.out}")

if __name__ == "__main__":
    main()
