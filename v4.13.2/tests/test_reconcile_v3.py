import json
from src.storage.sqlite_store_recon import ReconStore
from src.reconcile.reconcile_v3 import reconcile_signal

def test_reconcile_slippage_sign_long(tmp_path):
    db = tmp_path / "t.db"
    store = ReconStore(str(db))
    sid = store.upsert_signal("k", "2026-01-01T00:00:00+00:00", "chan", {"x":1})

    store.add_model_trace(sid, {"symbol":"EURUSD","side":"LONG","events":[
        {"ts":"2026-01-01T00:00:00+00:00","kind":"ENTRY","px":1.1000},
        {"ts":"2026-01-01T00:10:00+00:00","kind":"EXIT","px":1.1010},
    ]})

    store.conn.execute("INSERT INTO symbol_meta(symbol,payload) VALUES(?,?)", ("EURUSD", json.dumps({
        "baseAsset":"EUR","quoteAsset":"USD","lotSize":100000,"pipPosition":4
    })))
    store.conn.commit()

    store.add_trade_link(sid, None, {
        "symbol":"EURUSD","side":"LONG",
        "entry_ts":"2026-01-01T00:00:01+00:00","exit_ts":"2026-01-01T00:10:01+00:00",
        "entry_wap":1.1002,"exit_wap":1.1008,"qty_lots":1.0
    }, exec_rows=[])
    store.conn.commit()

    rec = reconcile_signal(store, sid, slip_warn_pips=0.0, slip_error_pips=9999.0)
    assert abs(rec["entry_slip_pips"] - 2.0) < 1e-9
    assert abs(rec["exit_slip_pips"] - 2.0) < 1e-9
    assert abs(rec["total_slip_pips"] - 4.0) < 1e-9
