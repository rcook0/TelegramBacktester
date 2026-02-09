# v4.11.6 — Persist model traces

Adds DB persistence for model execution traces so reconciliation can compare:
- model event timeline vs broker snapshots/fills
- WAP/spread/latency deltas later (v4.11.7+)

## New DB tables
- `model_traces(signal_id, created_at, payload)`
- `model_trace_events(trace_id, ts, kind, px, qty, payload)`

## APIs
- `src/reconcile/trace_schema.py` defines `ModelTraceDoc` and `TraceEvent`.
- `src/reconcile/trace_persist.py` provides `persist_trace(store, signal_id, doc)`.
- `src/storage/sqlite_store_traces.py` adds `TraceStore` (extends SymbolStore).

## Demo
```
python -m src.runners.persist_trace_demo --db ./journal/trader.db --signal-idem-key <KEY>
```
