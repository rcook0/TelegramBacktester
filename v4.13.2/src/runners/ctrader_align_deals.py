from __future__ import annotations
import argparse, json
from storage.sqlite_store_symbols import SymbolStore
from reconcile.deal_align import align_deals_for_signal

def parse_args():
    p = argparse.ArgumentParser(description="Align deal_norm to signal window + attach quote/depth context")
    p.add_argument("--db", required=True)
    p.add_argument("--signal-idem-key", required=True)
    p.add_argument("--use-capture-window", action="store_true")
    p.add_argument("--pre-sec", type=float, default=2.0)
    p.add_argument("--post-sec", type=float, default=120.0)
    p.add_argument("--max-gap-ms", type=float, default=5000.0)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--export-json", default="", help="Optional export aligned payloads (list)")
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

    aligned = align_deals_for_signal(
        store, sid,
        use_capture_window=bool(a.use_capture_window),
        pre_sec=float(a.pre_sec),
        post_sec=float(a.post_sec),
        max_gap_ms=float(a.max_gap_ms),
        overwrite=bool(a.overwrite)
    )
    print("aligned_deals=", len(aligned))
    if a.export_json:
        with open(a.export_json, "w", encoding="utf-8") as f:
            json.dump(aligned, f, indent=2)

if __name__ == "__main__":
    main()
