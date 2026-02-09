from __future__ import annotations
import json
from datetime import datetime, timezone
from .sqlite_store import Store

SHADOW_SCHEMA='''
CREATE TABLE IF NOT EXISTS shadow_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, signal_id INTEGER NOT NULL, kind TEXT NOT NULL, ts TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reconcile_diffs (id INTEGER PRIMARY KEY AUTOINCREMENT, signal_id INTEGER NOT NULL, ts TEXT NOT NULL, payload TEXT NOT NULL);
'''

class ShadowStore(Store):
  def __init__(self, path: str):
    super().__init__(path); self.conn.executescript(SHADOW_SCHEMA)
  def add_shadow_snapshot(self, signal_id: int, kind: str, payload: dict, ts: str|None=None):
    ts=ts or datetime.now(timezone.utc).isoformat();
    self.conn.execute('INSERT INTO shadow_snapshots(signal_id,kind,ts,payload) VALUES(?,?,?,?)',(signal_id, kind, ts, json.dumps(payload)))
  def add_reconcile_diff(self, signal_id: int, payload: dict, ts: str|None=None):
    ts=ts or datetime.now(timezone.utc).isoformat();
    self.conn.execute('INSERT INTO reconcile_diffs(signal_id,ts,payload) VALUES(?,?,?)',(signal_id, ts, json.dumps(payload)))
