"""
Record live ticks from Vantage FIX to Parquet files per symbol.
"""
import os, argparse, time, pandas as pd
from src.data_providers.fix_provider import VantageFIXProvider

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=True, help="Path to FIX .cfg")
    ap.add_argument("--symbols", required=True, help="Comma-separated symbols (EURUSD,XAUUSD,...)")
    ap.add_argument("--out", required=True, help="Output dir for tick parquet")
    ap.add_argument("--flush-sec", type=int, default=5)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    prov = VantageFIXProvider(cfg_path=args.cfg, symbols=symbols)

    try:
        while True:
            ticks = prov.drain_ticks()
            if ticks:
                df = pd.DataFrame(ticks)
                for sym, g in df.groupby("symbol"):
                    path = os.path.join(args.out, f"{sym}.parquet")
                    if os.path.exists(path):
                        old = pd.read_parquet(path)
                        dfw = pd.concat([old, g], ignore_index=True)
                    else:
                        dfw = g
                    dfw.to_parquet(path, index=False)
            time.sleep(args.flush_sec)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
