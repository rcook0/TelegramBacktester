import json
from src.storage.sqlite_store_linkage import LinkageStore
from src.reconcile.linkage import link_execs_to_trace

def test_linkage_basic(tmp_path):
    db = tmp_path / "t.db"
    store = LinkageStore(str(db))
    sid = store.upsert_signal("k", "2026-01-01T00:00:00+00:00", "chan", {"x":1})

    # trace with entry/exit
    tid = store.add_model_trace(sid, {
        "idem_key":"k","symbol":"EURUSD","side":"LONG","events":[
            {"ts":"2026-01-01T00:00:00+00:00","kind":"ENTRY","px":1.1},
            {"ts":"2026-01-01T00:10:00+00:00","kind":"EXIT","px":1.101},
        ]
    })

    store.add_shadow_snapshot(sid, "exec_knit", {
        "exec_id":"id:1","symbol":"EURUSD","side":"LONG","ts_first":"2026-01-01T00:00:01+00:00","ts_last":"2026-01-01T00:00:01+00:00",
        "total_qty_lots":1.0,"wap_px":1.1000,"quote_ctx":{"pip_size":0.0001}
    }, ts="2026-01-01T00:00:01+00:00")
    store.add_shadow_snapshot(sid, "exec_knit", {
        "exec_id":"id:2","symbol":"EURUSD","side":"SHORT","ts_first":"2026-01-01T00:10:01+00:00","ts_last":"2026-01-01T00:10:01+00:00",
        "total_qty_lots":1.0,"wap_px":1.1010,"quote_ctx":{"pip_size":0.0001}
    }, ts="2026-01-01T00:10:01+00:00")

    out = link_execs_to_trace(store, sid, overwrite=True)
    assert out["ok"] is True
    assert abs(out["pnl_pips"] - 10.0) < 1e-9
