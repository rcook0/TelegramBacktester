from __future__ import annotations
import argparse, json
from storage.sqlite_store_linkage import LinkageStore
from reconcile.linkage import link_execs_to_trace

def parse_args():
    p = argparse.ArgumentParser(description="Link stitched executions (exec_knit) to model trace ENTRY/EXIT")
    p.add_argument("--db", required=True)
    p.add_argument("--signal-idem-key", required=True)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--entry-tolerance-sec", type=float, default=180.0)
    p.add_argument("--exit-tolerance-sec", type=float, default=180.0)
    p.add_argument("--export-json", default="")
    return p.parse_args()

def main():
    a = parse_args()
    store = LinkageStore(a.db)
    cur = store.conn.cursor()
    cur.execute("SELECT id FROM signals WHERE idem_key=?", (a.signal_idem_key,))
    row = cur.fetchone()
    if not row:
        raise SystemExit("No signal for idem_key")
    sid = int(row[0])

    out = link_execs_to_trace(store, sid, overwrite=bool(a.overwrite),
                             entry_tolerance_sec=float(a.entry_tolerance_sec),
                             exit_tolerance_sec=float(a.exit_tolerance_sec))
    print(json.dumps(out, indent=2))
    if a.export_json:
        with open(a.export_json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)

if __name__ == "__main__":
    main()
