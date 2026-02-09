from __future__ import annotations
import json
from datetime import datetime, timezone
from .sqlite_store_linkage import LinkageStore

RECON_SCHEMA = '''
CREATE TABLE IF NOT EXISTS trade_recon_v3 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trade_link_id INTEGER NOT NULL,
  signal_id INTEGER NOT NULL,
  trace_id INTEGER,
  created_at TEXT NOT NULL,

  status TEXT NOT NULL,
  code TEXT NOT NULL,

  symbol TEXT,
  side TEXT,
  pip_size REAL,

  expected_entry_ts TEXT,
  expected_exit_ts TEXT,
  expected_entry_px REAL,
  expected_exit_px REAL,

  actual_entry_ts TEXT,
  actual_exit_ts TEXT,
  actual_entry_wap REAL,
  actual_exit_wap REAL,

  entry_slip_pips REAL,
  exit_slip_pips REAL,
  total_slip_pips REAL,

  latency_entry_sec REAL,
  latency_exit_sec REAL,

  pnl_pips REAL,
  pnl_ccy REAL,

  payload TEXT NOT NULL,

  FOREIGN KEY(trade_link_id) REFERENCES trade_links(id)
);

CREATE INDEX IF NOT EXISTS idx_trade_recon_v3_signal_id ON trade_recon_v3(signal_id);
CREATE INDEX IF NOT EXISTS idx_trade_recon_v3_trade_link_id ON trade_recon_v3(trade_link_id);
'''

class ReconStore(LinkageStore):
    def __init__(self, path: str):
        super().__init__(path)
        self.conn.executescript(RECON_SCHEMA)

    def add_trade_recon(self, rec: dict) -> int:
        cur = self.conn.cursor()
        cur.execute('''
          INSERT INTO trade_recon_v3(
            trade_link_id, signal_id, trace_id, created_at,
            status, code, symbol, side, pip_size,
            expected_entry_ts, expected_exit_ts, expected_entry_px, expected_exit_px,
            actual_entry_ts, actual_exit_ts, actual_entry_wap, actual_exit_wap,
            entry_slip_pips, exit_slip_pips, total_slip_pips,
            latency_entry_sec, latency_exit_sec,
            pnl_pips, pnl_ccy,
            payload
          ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
          int(rec["trade_link_id"]) if rec.get("trade_link_id") is not None else None,
          int(rec["signal_id"]),
          int(rec["trace_id"]) if rec.get("trace_id") is not None else None,
          rec.get("created_at") or datetime.now(timezone.utc).isoformat(),

          rec.get("status"),
          rec.get("code"),
          rec.get("symbol"),
          rec.get("side"),
          rec.get("pip_size"),

          rec.get("expected_entry_ts"),
          rec.get("expected_exit_ts"),
          rec.get("expected_entry_px"),
          rec.get("expected_exit_px"),

          rec.get("actual_entry_ts"),
          rec.get("actual_exit_ts"),
          rec.get("actual_entry_wap"),
          rec.get("actual_exit_wap"),

          rec.get("entry_slip_pips"),
          rec.get("exit_slip_pips"),
          rec.get("total_slip_pips"),

          rec.get("latency_entry_sec"),
          rec.get("latency_exit_sec"),

          rec.get("pnl_pips"),
          rec.get("pnl_ccy"),

          json.dumps(rec),
        ))
        return int(cur.lastrowid)
