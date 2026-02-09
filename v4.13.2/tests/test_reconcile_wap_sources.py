from src.storage.sqlite_store_traces import TraceStore
from src.reconcile.trace_schema import ModelTraceDoc, TraceEvent
from src.reconcile.trace_persist import persist_trace
from src.reconcile.reconciler import reconcile_signal

def test_reconcile_prefers_fills(tmp_path):
    db = tmp_path / "t.db"
    store = TraceStore(str(db))
    sid = store.upsert_signal("k", "2026-01-01T00:00:00+00:00", "chan", {"x":1})

    store.add_shadow_snapshot(sid, "quote", {
        "ts": "2026-01-01T00:00:00+00:00",
        "symbol": "XAUUSD",
        "mid": 100.0,
        "spread_pips": 1.0,
        "pip_size": 0.1,
    }, ts="2026-01-01T00:00:00+00:00")

    # two fills -> WAP = (100.0*1 + 100.2*1)/2 = 100.1
    store.add_shadow_snapshot(sid, "deal", {"ts":"2026-01-01T00:00:01+00:00","symbol":"XAUUSD","px":100.0,"qty":1.0}, ts="2026-01-01T00:00:01+00:00")
    store.add_shadow_snapshot(sid, "deal", {"ts":"2026-01-01T00:00:02+00:00","symbol":"XAUUSD","px":100.2,"qty":1.0}, ts="2026-01-01T00:00:02+00:00")

    doc = ModelTraceDoc(idem_key="k", symbol="XAUUSD", side="LONG",
                        assumptions={"pip_size":0.1},
                        events=[TraceEvent(ts="2026-01-01T00:00:00+00:00", kind="ENTRY", px=100.0, qty=2.0, meta={"intended_wap":100.0})])
    persist_trace(store, sid, doc)
    diff = reconcile_signal(store, sid)
    assert diff["wap_broker_source"] == "fills"
    assert abs(diff["wap_broker"] - 100.1) < 1e-12

def test_reconcile_uses_depth_when_no_fills(tmp_path):
    db = tmp_path / "t.db"
    store = TraceStore(str(db))
    sid = store.upsert_signal("k2", "2026-01-01T00:00:00+00:00", "chan", {"x":1})

    store.add_shadow_snapshot(sid, "quote", {
        "ts": "2026-01-01T00:00:00+00:00",
        "symbol": "XAUUSD",
        "mid": 100.0,
        "spread_pips": 1.0,
        "pip_size": 0.1,
    }, ts="2026-01-01T00:00:00+00:00")

    store.add_shadow_snapshot(sid, "depth", {
        "ts": "2026-01-01T00:00:00+00:00",
        "symbol": "XAUUSD",
        "asks":[{"px":100.0,"qty":1.0},{"px":100.2,"qty":1.0}],
        "bids":[{"px":99.8,"qty":2.0}],
        "pip_size": 0.1,
    }, ts="2026-01-01T00:00:00+00:00")

    doc = ModelTraceDoc(idem_key="k2", symbol="XAUUSD", side="LONG",
                        assumptions={"pip_size":0.1},
                        events=[TraceEvent(ts="2026-01-01T00:00:00+00:00", kind="ENTRY", px=100.0, qty=2.0, meta={"intended_wap":100.0})])
    persist_trace(store, sid, doc)
    diff = reconcile_signal(store, sid)
    assert diff["wap_broker_source"] == "depth"
    # buy 2 -> wap 100.1
    assert abs(diff["wap_broker"] - 100.1) < 1e-12
