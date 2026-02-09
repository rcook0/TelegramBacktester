from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from storage.sqlite_store_recon import ReconStore
from reconcile.reconcile_v3 import reconcile_signal

def parse_args():
    p = argparse.ArgumentParser(description="Batch reconciliation v3 over a time window (signals -> trade_recon_v3).")
    p.add_argument("--db", required=True)
    p.add_argument("--since", default="")
    p.add_argument("--until", default="")
    p.add_argument("--channel", default="")
    p.add_argument("--symbol", default="")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--slip-warn-pips", type=float, default=1.0)
    p.add_argument("--slip-error-pips", type=float, default=5.0)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--emit-json", default="", help="Write a JSON summary to this file path.")
    return p.parse_args()

def _now():
    return datetime.now(timezone.utc).isoformat()

def main():
    a = parse_args()
    store = ReconStore(a.db)
    cur = store.conn.cursor()

    where = []
    params = []
    if a.since:
        where.append("ts >= ?"); params.append(a.since)
    if a.until:
        where.append("ts <= ?"); params.append(a.until)
    if a.channel:
        where.append("channel = ?"); params.append(a.channel)

    q = "SELECT id, idem_key, ts, channel FROM signals"
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY ts ASC"
    if a.limit and a.limit > 0:
        q += f" LIMIT {int(a.limit)}"

    cur.execute(q, params)
    signals = cur.fetchall()

    stats = {
        "generated_at": _now(),
        "since": a.since or None,
        "until": a.until or None,
        "channel": a.channel or None,
        "symbol": a.symbol or None,
        "limit": a.limit or None,
        "counts": {"signals": 0, "skipped_existing": 0, "reconciled": 0, "errors": 0, "warns": 0},
        "examples": {"errors": [], "warns": []},
    }

    for (sid, idem_key, ts, chan) in signals:
        stats["counts"]["signals"] += 1

        if a.symbol:
            cur.execute("SELECT symbol FROM trade_links WHERE signal_id=? ORDER BY id DESC LIMIT 1", (sid,))
            row = cur.fetchone()
            if not row or row[0] != a.symbol:
                continue

        if not a.overwrite:
            cur.execute("SELECT id FROM trade_recon_v3 WHERE signal_id=? ORDER BY id DESC LIMIT 1", (sid,))
            if cur.fetchone():
                stats["counts"]["skipped_existing"] += 1
                continue
        else:
            cur.execute("DELETE FROM trade_recon_v3 WHERE signal_id=?", (sid,))
            cur.execute("DELETE FROM shadow_snapshots WHERE signal_id=? AND kind='recon_v3'", (sid,))
            store.conn.commit()

        try:
            rec = reconcile_signal(store, int(sid), slip_warn_pips=a.slip_warn_pips, slip_error_pips=a.slip_error_pips)
            rid = store.add_trade_recon(rec)
            rec["recon_id"] = rid
            store.add_shadow_snapshot(int(sid), "recon_v3", rec, ts=rec.get("actual_exit_ts") or rec.get("actual_entry_ts") or ts)
            store.conn.commit()

            stats["counts"]["reconciled"] += 1
            if rec.get("status") == "WARN":
                stats["counts"]["warns"] += 1
                if len(stats["examples"]["warns"]) < 20:
                    stats["examples"]["warns"].append({"idem_key": idem_key, "code": rec.get("code"), "total_slip_pips": rec.get("total_slip_pips")})
            if rec.get("status") == "ERROR":
                stats["counts"]["errors"] += 1
                if len(stats["examples"]["errors"]) < 20:
                    stats["examples"]["errors"].append({"idem_key": idem_key, "code": rec.get("code")})
        except Exception as e:
            stats["counts"]["errors"] += 1
            if len(stats["examples"]["errors"]) < 20:
                stats["examples"]["errors"].append({"idem_key": idem_key, "code": "EXCEPTION", "err": str(e)})

    print(json.dumps(stats, indent=2))
    if a.emit_json:
        with open(a.emit_json, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)

if __name__ == "__main__":
    main()
