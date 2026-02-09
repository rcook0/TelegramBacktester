from __future__ import annotations
import argparse, json
from storage.sqlite_store_traces import TraceStore
from reconcile.reconciler import reconcile_signal, reconcile_range

def parse_args():
    p = argparse.ArgumentParser(description="Run reconciliation (v4.11.7)")
    p.add_argument("--db", required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--signal-idem-key", help="Reconcile one signal by idempotency key")
    g.add_argument("--range", help="Reconcile signals in range: ISO_FROM,ISO_TO")
    p.add_argument("--export-json", default="", help="Optional path to write diffs as JSON list")
    return p.parse_args()

def main():
    a = parse_args()
    store = TraceStore(a.db)

    diffs = []
    if a.signal_idem_key:
        cur = store.conn.cursor()
        cur.execute("SELECT id FROM signals WHERE idem_key=?", (a.signal_idem_key,))
        r = cur.fetchone()
        if not r:
            raise SystemExit("No signal for idem_key.")
        d = reconcile_signal(store, int(r[0]))
        if d: diffs = [d]
    else:
        ts_from, ts_to = [x.strip() for x in a.range.split(",")]
        diffs = reconcile_range(store, ts_from, ts_to)

    print(f"reconciled={len(diffs)}")
    if diffs:
        # print a compact summary line per diff
        for d in diffs[:50]:
            print(d.get("symbol"), d.get("delta_wap_pips"), d.get("delta_spread_pips"), d.get("delta_latency_ms"))

    if a.export_json:
        with open(a.export_json, "w", encoding="utf-8") as f:
            json.dump(diffs, f, indent=2)

if __name__ == "__main__":
    main()
