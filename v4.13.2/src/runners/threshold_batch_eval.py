from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from storage.sqlite_store_thresholds import ThresholdStore
from thresholds.packs import DEFAULT_PACKS
from thresholds.evaluator import evaluate_pack

def parse_args():
    p = argparse.ArgumentParser(description="Batch threshold eval over a time window (signals -> signal_threshold_eval).")
    p.add_argument("--db", required=True)
    p.add_argument("--since", default="")
    p.add_argument("--until", default="")
    p.add_argument("--channel", default="")
    p.add_argument("--symbol", default="")
    p.add_argument("--pack", default="shadow_gate_v1")
    p.add_argument("--pack-version", default="1.0")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--emit-json", default="", help="Write a JSON summary to this file path.")
    return p.parse_args()

def _now():
    return datetime.now(timezone.utc).isoformat()

def main():
    a = parse_args()
    store = ThresholdStore(a.db)
    cur = store.conn.cursor()

    pack = DEFAULT_PACKS.get(a.pack)
    if not pack:
        raise SystemExit(f"Unknown pack: {a.pack}")
    if str(pack.get("version")) != str(a.pack_version):
        raise SystemExit(f"Pack version mismatch: requested {a.pack_version}, available {pack.get('version')}")

    pack_id = store.upsert_threshold_pack(a.pack, a.pack_version, pack)
    store.conn.commit()

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
        "pack": {"name": a.pack, "version": a.pack_version, "pack_id": pack_id},
        "counts": {"signals": 0, "skipped_existing": 0, "evaluated": 0, "pass": 0, "fail": 0, "errors": 0},
        "examples": {"fails": [], "errors": []},
    }

    for (sid, idem_key, ts, chan) in signals:
        stats["counts"]["signals"] += 1

        if a.symbol:
            cur.execute("SELECT symbol FROM trade_links WHERE signal_id=? ORDER BY id DESC LIMIT 1", (sid,))
            row = cur.fetchone()
            if not row or row[0] != a.symbol:
                continue

        if not a.overwrite:
            cur.execute("SELECT id FROM signal_threshold_eval WHERE signal_id=? AND pack_id=? ORDER BY id DESC LIMIT 1", (sid, pack_id))
            if cur.fetchone():
                stats["counts"]["skipped_existing"] += 1
                continue
        else:
            cur.execute("DELETE FROM signal_threshold_eval WHERE signal_id=? AND pack_id=?", (sid, pack_id))
            cur.execute("DELETE FROM shadow_snapshots WHERE signal_id=? AND kind='threshold_eval' AND payload LIKE ?", (sid, f'%"pack_id": {pack_id}%'))
            store.conn.commit()

        cur.execute("SELECT id, pnl_ccy, pnl_pips FROM trade_links WHERE signal_id=? ORDER BY id DESC LIMIT 1", (sid,))
        tl = cur.fetchone()
        if not tl:
            stats["counts"]["errors"] += 1
            if len(stats["examples"]["errors"]) < 20:
                stats["examples"]["errors"].append({"idem_key": idem_key, "code": "MISSING_TRADE_LINK"})
            continue
        trade_link_id, pnl_ccy, pnl_pips = tl

        cur.execute("SELECT id, payload FROM trade_recon_v3 WHERE signal_id=? ORDER BY id DESC LIMIT 1", (sid,))
        rr = cur.fetchone()
        if not rr:
            stats["counts"]["errors"] += 1
            if len(stats["examples"]["errors"]) < 20:
                stats["examples"]["errors"].append({"idem_key": idem_key, "code": "MISSING_RECON"})
            continue
        recon_id, recon_payload = rr
        try:
            recon = json.loads(recon_payload) if recon_payload else {}
        except Exception:
            recon = {}

        ctx = {
            "recon": recon,
            "pnl": {"pnl_ccy": pnl_ccy, "pnl_pips": pnl_pips},
            "trade_link_id": trade_link_id,
            "recon_id": recon_id,
            "signal_id": sid,
        }

        try:
            out = evaluate_pack(pack, ctx)
            rec = {
                "signal_id": int(sid),
                "trade_link_id": int(trade_link_id),
                "recon_id": int(recon_id),
                "pack_id": int(pack_id),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": out["status"],
                "score": out["score"],
                "violations": out["violations"],
                "ctx": ctx,
                "pack_name": a.pack,
                "pack_version": a.pack_version,
                "source": "threshold_batch_eval_v4.12.9",
            }
            eid = store.add_signal_eval(rec)
            rec["eval_id"] = eid
            store.add_shadow_snapshot(int(sid), "threshold_eval", rec, ts=recon.get("actual_exit_ts") or recon.get("actual_entry_ts") or ts)
            store.conn.commit()

            stats["counts"]["evaluated"] += 1
            if out["status"] == "PASS":
                stats["counts"]["pass"] += 1
            else:
                stats["counts"]["fail"] += 1
                if len(stats["examples"]["fails"]) < 20:
                    stats["examples"]["fails"].append({"idem_key": idem_key, "score": out["score"], "violations": (out["violations"][:2] if out["violations"] else [])})
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
