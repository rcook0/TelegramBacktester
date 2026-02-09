from __future__ import annotations
import argparse, json
from storage.sqlite_store_linkage import LinkageStore
from reconcile.pnl_attrib import attrib_trade_link

def parse_args():
    p = argparse.ArgumentParser(description="Compute trade P&L in account currency for the latest trade_link of a signal.")
    p.add_argument("--db", required=True)
    p.add_argument("--signal-idem-key", required=True)
    p.add_argument("--account-ccy", default="USD")
    p.add_argument("--rates-json", default="{}")
    p.add_argument("--rate-window-sec", type=float, default=300.0)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--export-json", default="")
    return p.parse_args()

def main():
    a = parse_args()
    store = LinkageStore(a.db)
    cur = store.conn.cursor()
    cur.execute("SELECT id FROM signals WHERE idem_key=?", (a.signal_idem_key,))
    r = cur.fetchone()
    if not r:
        raise SystemExit("No signal for idem_key")
    sid = int(r[0])

    cur.execute("SELECT id, pnl_ccy FROM trade_links WHERE signal_id=? ORDER BY id DESC LIMIT 1", (sid,))
    tl = cur.fetchone()
    if not tl:
        raise SystemExit("No trade_links for signal; run linkage first.")
    link_id = int(tl[0])
    pnl_ccy = tl[1]

    if pnl_ccy is not None and not a.overwrite:
        print("pnl_ccy already set; use --overwrite to recompute")
        return

    rates = json.loads(a.rates_json) if a.rates_json else {}
    out = attrib_trade_link(store, link_id, account_ccy=a.account_ccy, rates=rates, rate_window_sec=a.rate_window_sec)

    if out.get("ok"):
        store.update_trade_link_pnl(link_id, out.get("pnl_pips"), out.get("pnl_account_ccy"), payload_patch={"pnl_attrib": out})
        store.add_shadow_snapshot(sid, "pnl_attrib", out, ts=None)
        store.conn.commit()

    print(json.dumps(out, indent=2))
    if a.export_json:
        with open(a.export_json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)

if __name__ == "__main__":
    main()
