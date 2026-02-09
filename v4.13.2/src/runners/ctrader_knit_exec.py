from __future__ import annotations
import argparse, json
from storage.sqlite_store_symbols import SymbolStore
from reconcile.deal_knit import knit_deals

def parse_args():
    p = argparse.ArgumentParser(description="Knit aligned deal fills into stitched executions")
    p.add_argument("--db", required=True)
    p.add_argument("--signal-idem-key", required=True)
    p.add_argument("--max-gap-sec", type=float, default=3.0)
    p.add_argument("--bucket-ms", type=int, default=5000)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--export-json", default="")
    return p.parse_args()

def main():
    a = parse_args()
    store = SymbolStore(a.db)
    cur = store.conn.cursor()
    cur.execute("SELECT id FROM signals WHERE idem_key=?", (a.signal_idem_key,))
    row = cur.fetchone()
    if not row:
        raise SystemExit("No signal for idem_key")
    sid = int(row[0])

    if a.overwrite:
        cur.execute("DELETE FROM shadow_snapshots WHERE signal_id=? AND kind='exec_knit'", (sid,))
        store.conn.commit()

    cur.execute("SELECT payload FROM shadow_snapshots WHERE signal_id=? AND kind='deal_aligned' ORDER BY id ASC", (sid,))
    aligned = [json.loads(p[0]) for p in cur.fetchall()]

    execs = knit_deals(aligned, max_gap_sec=float(a.max_gap_sec), bucket_ms=int(a.bucket_ms))

    for ex in execs:
        ts = ex.get("ts_first") or ex.get("ts_last")
        store.add_shadow_snapshot(sid, "exec_knit", ex, ts=ts)

    store.conn.commit()
    print("exec_knit=", len(execs))

    if a.export_json:
        with open(a.export_json, "w", encoding="utf-8") as f:
            json.dump(execs, f, indent=2)

if __name__ == "__main__":
    main()
