from __future__ import annotations
import json
from datetime import datetime, timezone
from .sqlite_store_symbols import SymbolStore

TRACE_SCHEMA = '''
CREATE TABLE IF NOT EXISTS model_traces (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  payload TEXT NOT NULL,
  FOREIGN KEY(signal_id) REFERENCES signals(id)
);

CREATE TABLE IF NOT EXISTS model_trace_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trace_id INTEGER NOT NULL,
  ts TEXT NOT NULL,
  kind TEXT NOT NULL,
  px REAL,
  qty REAL,
  payload TEXT,
  FOREIGN KEY(trace_id) REFERENCES model_traces(id)
);
'''

class TraceStore(SymbolStore):
    def __init__(self, path: str):
        super().__init__(path)
        self.conn.executescript(TRACE_SCHEMA)

    def add_model_trace(self, signal_id: int, payload: dict) -> int:
        ts = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        cur.execute("INSERT INTO model_traces(signal_id,created_at,payload) VALUES(?,?,?)",
                    (signal_id, ts, json.dumps(payload)))
        return int(cur.lastrowid)

    def add_model_event(self, trace_id: int, ts: str, kind: str, px: float|None, qty: float|None, payload: dict|None=None):
        self.conn.execute("INSERT INTO model_trace_events(trace_id,ts,kind,px,qty,payload) VALUES(?,?,?,?,?,?)",
                          (trace_id, ts, kind, px, qty, json.dumps(payload or {})))

    def latest_trace_for_signal(self, signal_id: int):
        cur = self.conn.cursor()
        cur.execute("SELECT id, created_at, payload FROM model_traces WHERE signal_id=? ORDER BY id DESC LIMIT 1", (signal_id,))
        row = cur.fetchone()
        if not row:
            return None
        return dict(trace_id=int(row[0]), created_at=row[1], payload=json.loads(row[2]))
