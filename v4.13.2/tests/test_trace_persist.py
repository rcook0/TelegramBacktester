from src.storage.sqlite_store_traces import TraceStore
from src.reconcile.trace_schema import ModelTraceDoc, TraceEvent
from src.reconcile.trace_persist import persist_trace

def test_persist_trace(tmp_path):
    db = tmp_path / "t.db"
    store = TraceStore(str(db))
    sid = store.upsert_signal("k", "2026-01-01T00:00:00+00:00", "chan", {"x":1})
    doc = ModelTraceDoc(idem_key="k", symbol="XAUUSD", side="LONG",
                        events=[TraceEvent(ts="2026-01-01T00:00:00+00:00", kind="ENTRY", px=1.0, qty=1.0)])
    tid = persist_trace(store, sid, doc)
    assert tid > 0
    got = store.latest_trace_for_signal(sid)
    assert got and got["trace_id"] == tid
