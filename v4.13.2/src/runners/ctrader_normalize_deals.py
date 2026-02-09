from __future__ import annotations
import argparse, json
from typing import Optional
from storage.sqlite_store_symbols import SymbolStore
from normalize.ctrader_deals import normalize_deal_payload

def parse_args():
    p = argparse.ArgumentParser(description="Normalize ctrader deals already stored in DB")
    p.add_argument("--db", required=True)
    p.add_argument("--signal-idem-key", required=True)
    p.add_argument("--broker", default="ctrader-openapi")
    p.add_argument("--account-id", default="")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing deal_norm rows for the signal")
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
        cur.execute("DELETE FROM shadow_snapshots WHERE signal_id=? AND kind='deal_norm'", (sid,))
        store.conn.commit()

    cur.execute("SELECT ts, payload FROM shadow_snapshots WHERE signal_id=? AND kind='deal' ORDER BY id ASC", (sid,))
    deals = cur.fetchall()

    n = 0
    for ts, payload_s in deals:
        payload = json.loads(payload_s)
        sym_id = payload.get("symbol_id")
        meta = None
        if sym_id is not None:
            meta = store.get_symbol_meta(a.broker, a.account_id or None, int(sym_id))
        norm = normalize_deal_payload(payload, symbol_meta=meta)
        store.add_shadow_snapshot(sid, "deal_norm", norm, ts=payload.get("execution_ts") or ts)
        n += 1

    store.conn.commit()
    print("normalized", n, "deals -> deal_norm")

if __name__ == "__main__":
    main()
