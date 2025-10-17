"""
Resample tick parquet into OHLCV CSV for a given timeframe.
"""
import os, argparse, pandas as pd

def resample_ticks(df_ticks: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    df = df_ticks.copy()
    df["time"] = pd.to_datetime(df["time"], utc=True)
    piv = df.pivot_table(index="time", columns="side", values="price", aggfunc="last")
    piv["mid"] = piv.mean(axis=1)
    rule = {"M1":"1min","M5":"5min","M15":"15min","H1":"1H"}[timeframe]
    o = piv["mid"].resample(rule).first()
    h = piv["mid"].resample(rule).max()
    l = piv["mid"].resample(rule).min()
    c = piv["mid"].resample(rule).last()
    v = piv["mid"].resample(rule).count()
    out = pd.DataFrame({"time": o.index, "open": o.values, "high": h.values, "low": l.values, "close": c.values, "volume": v.values})
    return out.dropna().reset_index(drop=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks", required=True, help="Dir of tick parquet files")
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--timeframe", choices=["M1","M5","M15","H1"], default="M1")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    path = os.path.join(args.ticks, f"{args.symbol}.parquet")
    if not os.path.exists(path):
        raise SystemExit(f"Ticks not found: {path}")
    df = pd.read_parquet(path)
    candles = resample_ticks(df, args.timeframe)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    candles.to_csv(args.out, index=False)
    print(f"Wrote {args.out} ({len(candles)} bars)")

if __name__ == "__main__":
    main()
