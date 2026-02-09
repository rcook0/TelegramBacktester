from __future__ import annotations
import argparse, json
import pandas as pd
from storage.sqlite_store_traces import TraceStore
from reconcile.reconciler import reconcile_range

def parse_args():
    p = argparse.ArgumentParser(description="Generate reconciliation report (csv+json)")
    p.add_argument("--db", required=True)
    p.add_argument("--from", dest="ts_from", required=True)
    p.add_argument("--to", dest="ts_to", required=True)
    p.add_argument("--out-csv", default="reconcile_trades.csv")
    p.add_argument("--out-json", default="reconcile_summary.json")
    return p.parse_args()

def main():
    a = parse_args()
    store = TraceStore(a.db)
    diffs = reconcile_range(store, a.ts_from, a.ts_to)
    df = pd.DataFrame(diffs)
    df.to_csv(a.out_csv, index=False)

    summary = {}
    if len(df) > 0:
        for col in ["delta_entry_pips","delta_wap_pips","delta_spread_pips","delta_latency_ms"]:
            if col in df.columns:
                series = pd.to_numeric(df[col], errors="coerce").dropna()
                if len(series):
                    summary[col] = {
                        "count": int(series.count()),
                        "mean": float(series.mean()),
                        "median": float(series.median()),
                        "p95": float(series.quantile(0.95)),
                        "max": float(series.max()),
                    }

    with open(a.out_json, "w", encoding="utf-8") as f:
        json.dump({"from": a.ts_from, "to": a.ts_to, "n": int(len(df)), "summary": summary}, f, indent=2)

    print("wrote", a.out_csv, a.out_json, "n=", len(df))

if __name__ == "__main__":
    main()
