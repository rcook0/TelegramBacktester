from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from storage.sqlite_store_thresholds import ThresholdStore
from thresholds.packs import DEFAULT_PACKS
from thresholds.evaluator import evaluate_pack

def parse_args():
    p = argparse.ArgumentParser(description="Evaluate a threshold pack (Shadow Gate) for a signal.")
    p.add_argument("--db", required=True)
    p.add_argument("--signal-idem-key", required=True)
    p.add_argument("--pack", default="shadow_gate_v1")
    p.add_argument("--pack-version", default="1.0")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--export-json", default="")
    return p.parse_args()

def main():
    a = parse_args()
    store = ThresholdStore(a.db)
    cur = store.conn.cursor()

    cur.execute("SELECT id FROM signals WHERE idem_key=?", (a.signal_idem_key,))
    r = cur.fetchone()
    if not r:
        raise SystemExit("No signal for idem_key")
    sid = int(r[0])

    cur.execute("SELECT id, pnl_ccy, pnl_pips, payload FROM trade_links WHERE signal_id=? ORDER BY id DESC LIMIT 1", (sid,))
    tl = cur.fetchone()
    if not tl:
        raise SystemExit("No trade_links; run linkage first.")
    trade_link_id, pnl_ccy, pnl_pips, tl_payload = tl

    cur.execute("SELECT id, payload FROM trade_recon_v3 WHERE signal_id=? ORDER BY id DESC LIMIT 1", (sid,))
    rr = cur.fetchone()
    if not rr:
        raise SystemExit("No trade_recon_v3; run reconcile_v3 first.")
    recon_id, recon_payload = rr
    recon = json.loads(recon_payload) if recon_payload else {}

    ctx = {
        "recon": recon,
        "pnl": {"pnl_ccy": pnl_ccy, "pnl_pips": pnl_pips},
        "trade_link_id": trade_link_id,
        "recon_id": recon_id,
        "signal_id": sid,
    }

    pack = DEFAULT_PACKS.get(a.pack)
    if not pack:
        raise SystemExit(f"Unknown pack: {a.pack}")
    if str(pack.get("version")) != str(a.pack_version):
        raise SystemExit(f"Pack version mismatch: requested {a.pack_version}, available {pack.get('version')}")

    pack_id = store.upsert_threshold_pack(a.pack, a.pack_version, pack)

    if a.overwrite:
        cur.execute("DELETE FROM signal_threshold_eval WHERE signal_id=? AND pack_id=?", (sid, pack_id))
        store.conn.commit()

    out = evaluate_pack(pack, ctx)
    rec = {
        "signal_id": sid,
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
        "source": "threshold_eval_v4.12.7",
    }
    eid = store.add_signal_eval(rec)
    rec["eval_id"] = eid
    store.add_shadow_snapshot(sid, "threshold_eval", rec, ts=recon.get("actual_exit_ts") or recon.get("actual_entry_ts"))
    store.conn.commit()

    print(json.dumps(rec, indent=2))
    if a.export_json:
        with open(a.export_json, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=2)

if __name__ == "__main__":
    main()
