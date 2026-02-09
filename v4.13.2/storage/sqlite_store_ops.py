from __future__ import annotations
import json
from datetime import datetime, timezone
from .sqlite_store_thresholds import ThresholdStore

OPS_SCHEMA = '''
CREATE TABLE IF NOT EXISTS ops_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,                 -- weekly_ops, adhoc_ops
  created_at TEXT NOT NULL,
  window_since TEXT,
  window_until TEXT,
  channel TEXT,
  symbol TEXT,
  pack_name TEXT,
  pack_version TEXT,
  status TEXT NOT NULL,               -- OK/ERROR
  summary_line TEXT,
  summary_json TEXT,
  error TEXT
);

CREATE TABLE IF NOT EXISTS ops_artifacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ops_run_id INTEGER NOT NULL,
  kind TEXT NOT NULL,                 -- report_csv, report_json, report_html, recon_summary, threshold_summary
  path TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(ops_run_id) REFERENCES ops_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_ops_runs_kind_created ON ops_runs(kind, created_at);
CREATE INDEX IF NOT EXISTS idx_ops_artifacts_ops_run ON ops_artifacts(ops_run_id);
'''

class OpsStore(ThresholdStore):
    def __init__(self, path: str):
        super().__init__(path)
        self.conn.executescript(OPS_SCHEMA)
        # lightweight migrations
        try:
            self.conn.execute('ALTER TABLE ops_runs ADD COLUMN summary_line TEXT')
        except Exception:
            pass


    def add_ops_run(self, rec: dict) -> int:
        cur = self.conn.cursor()
        cur.execute('''
          INSERT INTO ops_runs(
            kind, created_at, window_since, window_until, channel, symbol, pack_name, pack_version,
            status, summary_line, summary_json, error
          ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ''', (
          rec.get("kind","weekly_ops"),
          rec.get("created_at") or datetime.now(timezone.utc).isoformat(),
          rec.get("window_since"),
          rec.get("window_until"),
          rec.get("channel"),
          rec.get("symbol"),
          rec.get("pack_name"),
          rec.get("pack_version"),
          rec.get("status","OK"),
          rec.get("summary_line"),
          json.dumps(rec.get("summary") or {}),
          rec.get("error"),
        ))
        return int(cur.lastrowid)

    def add_artifact(self, ops_run_id: int, kind: str, path: str) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO ops_artifacts(ops_run_id, kind, path, created_at) VALUES(?,?,?,?)",
            (int(ops_run_id), kind, path, datetime.now(timezone.utc).isoformat())
        )
        return int(cur.lastrowid)
