from __future__ import annotations
import json
from datetime import datetime, timezone
from .sqlite_store_traces import TraceStore

SCORECARD_SCHEMA = '''
CREATE TABLE IF NOT EXISTS reconcile_scorecards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_from TEXT NOT NULL,
  ts_to TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload TEXT NOT NULL
);
'''

class ScorecardStore(TraceStore):
    def __init__(self, path: str):
        super().__init__(path)
        self.conn.executescript(SCORECARD_SCHEMA)

    def add_scorecard(self, ts_from: str, ts_to: str, payload: dict) -> int:
        ts = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        cur.execute("INSERT INTO reconcile_scorecards(ts_from,ts_to,created_at,payload) VALUES(?,?,?,?)",
                    (ts_from, ts_to, ts, json.dumps(payload)))
        return int(cur.lastrowid)
