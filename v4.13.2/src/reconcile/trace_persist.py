from __future__ import annotations
from typing import Optional
from storage.sqlite_store_traces import TraceStore
from .trace_schema import ModelTraceDoc

def persist_trace(store: TraceStore, signal_id: int, doc: ModelTraceDoc) -> int:
    trace_id = store.add_model_trace(signal_id, doc.to_dict())
    for ev in doc.events:
        store.add_model_event(trace_id, ev.ts, ev.kind, ev.px, ev.qty, ev.meta)
    return trace_id
