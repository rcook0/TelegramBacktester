import json
from src.storage.sqlite_store_symbols import SymbolStore
from src.reconcile.deal_align import align_deals_for_signal

def test_align_attaches_quote_and_depth(tmp_path):
    db = tmp_path / "t.db"
    store = SymbolStore(str(db))
    sid = store.upsert_signal("k", "2026-01-01T00:00:00+00:00", "chan", {"x":1})

    store.add_shadow_snapshot(sid, "capture_window", {"from":"2026-01-01T00:00:00+00:00","to":"2026-01-01T00:02:00+00:00"}, ts="2026-01-01T00:00:00+00:00")
    store.add_shadow_snapshot(sid, "quote", {"ts":"2026-01-01T00:00:10+00:00","symbol":"XAUUSD","mid":100.0,"pip_size":0.1}, ts="2026-01-01T00:00:10+00:00")
    store.add_shadow_snapshot(sid, "depth_book", {"ts":"2026-01-01T00:00:10+00:00","symbol":"XAUUSD","asks":[{"px":100.0,"qty":1},{"px":100.2,"qty":1}], "bids":[{"px":99.8,"qty":2}]}, ts="2026-01-01T00:00:10+00:00")
    store.add_shadow_snapshot(sid, "deal_norm", {"execution_ts":"2026-01-01T00:00:11+00:00","symbol":"XAUUSD","execution_px":100.1,"filled_volume_lots":2.0, "side":"BUY"}, ts="2026-01-01T00:00:11+00:00")

    aligned = align_deals_for_signal(store, sid, use_capture_window=True, overwrite=True)
    assert len(aligned) == 1
    a = aligned[0]
    assert a["quote_ctx"] is not None
    assert a["depth_ctx"] is not None
    assert abs(a["depth_wap_est"] - 100.1) < 1e-12
