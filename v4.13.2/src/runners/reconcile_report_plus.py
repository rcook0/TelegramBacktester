from __future__ import annotations
import argparse, json
import pandas as pd

from storage.sqlite_store_traces import TraceStore
from reconcile.reconciler import reconcile_range
from reconcile.scorecard import compute_metrics, per_symbol_breakdown, worst_offenders

def parse_args():
    p = argparse.ArgumentParser(description="Reconciliation report (plus)")
    p.add_argument("--db", required=True)
    p.add_argument("--from", dest="ts_from", required=True)
    p.add_argument("--to", dest="ts_to", required=True)
    p.add_argument("--out-csv", default="reconcile_trades.csv")
    p.add_argument("--out-json", default="reconcile_report.json")
    p.add_argument("--worst-n", type=int, default=25)
    return p.parse_args()

def main():
    a = parse_args()
    store = TraceStore(a.db)
    diffs = reconcile_range(store, a.ts_from, a.ts_to)
    df = pd.DataFrame(diffs)
    df.to_csv(a.out_csv, index=False)

    report = {
        "from": a.ts_from,
        "to": a.ts_to,
        "n": int(len(df)),
        "metrics": compute_metrics(df) if len(df) else {"n": 0},
        "per_symbol": per_symbol_breakdown(df) if len(df) else {},
        "worst": {
            "by_delta_wap_pips": worst_offenders(df, "delta_wap_pips", a.worst_n).to_dict(orient="records") if len(df) else [],
            "by_delta_spread_pips": worst_offenders(df, "delta_spread_pips", a.worst_n).to_dict(orient="records") if len(df) else [],
            "by_delta_latency_ms": worst_offenders(df, "delta_latency_ms", a.worst_n).to_dict(orient="records") if len(df) else [],
        }
    }

    with open(a.out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("wrote", a.out_csv, a.out_json, "n=", len(df))

if __name__ == "__main__":
    main()
