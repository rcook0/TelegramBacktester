from __future__ import annotations
import argparse, json
import pandas as pd

from storage.sqlite_store_scorecard import ScorecardStore
from reconcile.reconciler import reconcile_range
from reconcile.thresholds import Thresholds
from reconcile.scorecard import compute_metrics, evaluate_thresholds, per_symbol_breakdown

def parse_args():
    p = argparse.ArgumentParser(description="Reconciliation thresholds scorecard")
    p.add_argument("--db", required=True)
    p.add_argument("--from", dest="ts_from", required=True)
    p.add_argument("--to", dest="ts_to", required=True)
    p.add_argument("--thresholds-json", default="", help="Inline JSON string for Thresholds")
    p.add_argument("--thresholds-file", default="", help="Path to thresholds JSON")
    p.add_argument("--out-json", default="reconcile_scorecard.json")
    p.add_argument("--persist", action="store_true", help="Persist scorecard into DB table reconcile_scorecards")
    return p.parse_args()

def main():
    a = parse_args()
    store = ScorecardStore(a.db)

    if a.thresholds_file:
        thr = Thresholds.from_file(a.thresholds_file)
    elif a.thresholds_json:
        thr = Thresholds.from_json(a.thresholds_json)
    else:
        thr = Thresholds()

    diffs = reconcile_range(store, a.ts_from, a.ts_to)
    df = pd.DataFrame(diffs)

    metrics = compute_metrics(df) if len(df) else {"n": 0}
    ok, reasons = evaluate_thresholds(metrics, thr)

    payload = {
        "from": a.ts_from,
        "to": a.ts_to,
        "ok": bool(ok),
        "reasons": reasons,
        "thresholds": thr.to_dict(),
        "metrics": metrics,
        "per_symbol": per_symbol_breakdown(df) if len(df) else {},
    }

    with open(a.out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    if a.persist:
        sid = store.add_scorecard(a.ts_from, a.ts_to, payload)
        print("persisted scorecard id=", sid)

    print("ok=", ok, "reasons=", len(reasons))
    print("wrote", a.out_json)

if __name__ == "__main__":
    main()
