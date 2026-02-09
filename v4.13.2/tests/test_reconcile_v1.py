from src.storage.sqlite_store_traces import TraceStore
from src.reconcile.trace_schema import ModelTraceDoc, TraceEvent
from src.reconcile.trace_persist import persist_trace
from src.reconcile.reconciler import reconcile_signal

def test_reconcile_signal(tmp_path):
    db = tmp_path / "t.db"
    store = TraceStore(str(db))
    sid = store.upsert_signal("k", "2026-01-01T00:00:00+00:00", "chan", {"x":1})
    # shadow quote snapshot at +1s
    store.add_shadow_snapshot(sid, "quote", {
        "ts": "2026-01-01T00:00:01+00:00",
        "symbol": "XAUUSD",
        "mid": 100.05,
        "spread_pips": 2.0,
        "pip_size": 0.1,
        "source": "ctrader-openapi"
    }, ts="2026-01-01T00:00:01+00:00")

    doc = ModelTraceDoc(idem_key="k", symbol="XAUUSD", side="LONG",
                        assumptions={"spread_pips": 1.5, "latency_ms": 100, "pip_size": 0.1},
                        events=[TraceEvent(ts="2026-01-01T00:00:00+00:00", kind="ENTRY", px=100.0, qty=1.0, meta={"intended_wap":100.0})])
    persist_trace(store, sid, doc)

    diff = reconcile_signal(store, sid)
    assert diff is not None
    assert diff["delta_entry_pips"] is not None
    # delta entry = (100.05-100.0)/0.1 = 0.5 pips
    assert abs(diff["delta_entry_pips"] - 0.5) < 1e-9
