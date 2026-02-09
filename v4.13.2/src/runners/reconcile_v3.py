from __future__ import annotations
import argparse, json
from storage.sqlite_store_recon import ReconStore
from reconcile.reconcile_v3 import reconcile_signal

def parse_args():
    p = argparse.ArgumentParser(description="Reconciliation v3: expected(trace) vs actual(trade_link) at trade level.")
    p.add_argument("--db", required=True)
    p.add_argument("--signal-idem-key", required=True)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--slip-warn-pips", type=float, default=1.0)
    p.add_argument("--slip-error-pips", type=float, default=5.0)
    p.add_argument("--export-json", default="")
    return p.parse_args()

def main():
    a = parse_args()
    store = ReconStore(a.db)
    cur = store.conn.cursor()
    cur.execute("SELECT id FROM signals WHERE idem_key=?", (a.signal_idem_key,))
    row = cur.fetchone()
    if not row:
        raise SystemExit("No signal for idem_key")
    sid = int(row[0])

    if a.overwrite:
        cur.execute("DELETE FROM trade_recon_v3 WHERE signal_id=?", (sid,))
        cur.execute("DELETE FROM shadow_snapshots WHERE signal_id=? AND kind='recon_v3'", (sid,))
        store.conn.commit()

    rec = reconcile_signal(store, sid, slip_warn_pips=a.slip_warn_pips, slip_error_pips=a.slip_error_pips)
    rid = store.add_trade_recon(rec)
    rec["recon_id"] = rid
    store.add_shadow_snapshot(sid, "recon_v3", rec, ts=rec.get("actual_exit_ts") or rec.get("actual_entry_ts"))
    store.conn.commit()

    print(json.dumps(rec, indent=2))
    if a.export_json:
        with open(a.export_json, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=2)

if __name__ == "__main__":
    main()
