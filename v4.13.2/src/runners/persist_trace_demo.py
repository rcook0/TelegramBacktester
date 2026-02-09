from __future__ import annotations
import argparse
from storage.sqlite_store_traces import TraceStore
from reconcile.trace_schema import ModelTraceDoc, TraceEvent, now_iso
from reconcile.trace_persist import persist_trace

def parse_args():
    p = argparse.ArgumentParser(description="Persist a model trace (demo)")
    p.add_argument("--db", required=True)
    p.add_argument("--signal-idem-key", required=True)
    return p.parse_args()

def main():
    a = parse_args()
    store = TraceStore(a.db)
    cur = store.conn.cursor()
    cur.execute("SELECT id, payload FROM signals WHERE idem_key=?", (a.signal_idem_key,))
    row = cur.fetchone()
    if not row:
        raise SystemExit("No signal found for idem_key.")
    signal_id = int(row[0])
    payload = row[1]

    doc = ModelTraceDoc(
        idem_key=a.signal_idem_key,
        symbol="XAUUSD",
        side="LONG",
        timeframe="M1",
        assumptions={"spread_pips": 0.8, "slippage_pips": 0.2, "latency_ms": 150},
        events=[
            TraceEvent(ts=now_iso(), kind="ENTRY", px=2375.25, qty=1.0, meta={"intended_wap": 2375.25}),
            TraceEvent(ts=now_iso(), kind="TP", px=2376.0, qty=0.5, meta={"tp_index": 1}),
            TraceEvent(ts=now_iso(), kind="TRAIL_MOVE", px=2375.8, qty=None, meta={"reason": "equity_adaptive"}),
            TraceEvent(ts=now_iso(), kind="EXIT", px=2376.1, qty=1.0, meta={"net_usd": 12.3}),
        ],
        meta={"source": "demo"}
    )
    tid = persist_trace(store, signal_id, doc)
    print("trace_id", tid)

if __name__ == "__main__":
    main()
