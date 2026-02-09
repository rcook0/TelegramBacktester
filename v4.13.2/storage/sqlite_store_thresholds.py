from __future__ import annotations
import json
from datetime import datetime, timezone
from .sqlite_store_recon import ReconStore

THRESH_SCHEMA = '''
CREATE TABLE IF NOT EXISTS threshold_packs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS signal_threshold_eval (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id INTEGER NOT NULL,
  trade_link_id INTEGER,
  recon_id INTEGER,
  pack_id INTEGER NOT NULL,
  created_at TEXT NOT NULL,

  status TEXT NOT NULL,
  score REAL,
  violations TEXT,
  payload TEXT NOT NULL,

  FOREIGN KEY(pack_id) REFERENCES threshold_packs(id)
);

CREATE INDEX IF NOT EXISTS idx_signal_threshold_eval_signal_id ON signal_threshold_eval(signal_id);
CREATE INDEX IF NOT EXISTS idx_signal_threshold_eval_pack_id ON signal_threshold_eval(pack_id);
'''

class ThresholdStore(ReconStore):
    def __init__(self, path: str):
        super().__init__(path)
        self.conn.executescript(THRESH_SCHEMA)

    def upsert_threshold_pack(self, name: str, version: str, payload: dict) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM threshold_packs WHERE name=? AND version=? ORDER BY id DESC LIMIT 1", (name, version))
        row = cur.fetchone()
        if row:
            return int(row[0])
        cur.execute(
            "INSERT INTO threshold_packs(name, version, created_at, payload) VALUES(?,?,?,?)",
            (name, version, datetime.now(timezone.utc).isoformat(), json.dumps(payload))
        )
        return int(cur.lastrowid)

    def add_signal_eval(self, rec: dict) -> int:
        cur = self.conn.cursor()
        cur.execute('''
          INSERT INTO signal_threshold_eval(
            signal_id, trade_link_id, recon_id, pack_id, created_at,
            status, score, violations, payload
          ) VALUES (?,?,?,?,?,?,?,?,?)
        ''', (
          int(rec["signal_id"]),
          int(rec["trade_link_id"]) if rec.get("trade_link_id") is not None else None,
          int(rec["recon_id"]) if rec.get("recon_id") is not None else None,
          int(rec["pack_id"]),
          rec.get("created_at") or datetime.now(timezone.utc).isoformat(),
          rec.get("status"),
          rec.get("score"),
          json.dumps(rec.get("violations") or []),
          json.dumps(rec),
        ))
        return int(cur.lastrowid)
