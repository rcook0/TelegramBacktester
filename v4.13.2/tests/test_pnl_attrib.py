import json
from src.storage.sqlite_store_linkage import LinkageStore
from src.reconcile.pnl_attrib import attrib_trade_link

def test_pnl_attrib_fx_direct(tmp_path):
    db = tmp_path / "t.db"
    store = LinkageStore(str(db))
    sid = store.upsert_signal("k", "2026-01-01T00:00:00+00:00", "chan", {"x":1})

    store.conn.execute("INSERT INTO symbol_meta(symbol,payload) VALUES(?,?)", ("EURUSD", json.dumps({
        "baseAsset":"EUR","quoteAsset":"USD","lotSize":100000,"pipPosition":4
    })))
    store.conn.commit()

    link_id = store.add_trade_link(sid, None, {
        "symbol":"EURUSD","side":"LONG","entry_ts":"2026-01-01T00:00:00+00:00","exit_ts":"2026-01-01T00:10:00+00:00",
        "entry_wap":1.1000,"exit_wap":1.1010,"qty_lots":0.5
    }, exec_rows=[])
    store.conn.commit()

    out = attrib_trade_link(store, link_id, account_ccy="USD", rates={"EURUSD":1.1005})
    assert out["ok"] is True
    assert abs(out["pnl_account_ccy"] - 50.0) < 1e-6
