from __future__ import annotations
import json
from datetime import datetime, timezone
from .sqlite_store_traces import TraceStore

LINKAGE_SCHEMA = '''
CREATE TABLE IF NOT EXISTS trade_links (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id INTEGER NOT NULL,
  trace_id INTEGER,
  created_at TEXT NOT NULL,
  symbol TEXT,
  side TEXT,
  entry_ts TEXT,
  exit_ts TEXT,
  entry_wap REAL,
  exit_wap REAL,
  qty_lots REAL,
  pnl_pips REAL,
  pnl_ccy REAL,
  payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trade_link_execs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  link_id INTEGER NOT NULL,
  exec_snapshot_id INTEGER NOT NULL,
  exec_id TEXT,
  role TEXT NOT NULL, -- ENTRY or EXIT
  ts_first TEXT,
  ts_last TEXT,
  qty_lots REAL,
  wap_px REAL,
  payload TEXT NOT NULL,
  FOREIGN KEY(link_id) REFERENCES trade_links(id)
);
'''

class LinkageStore(TraceStore):
    def __init__(self, path: str):
        super().__init__(path)
        self.conn.executescript(LINKAGE_SCHEMA)

    def add_trade_link(self, signal_id: int, trace_id: int|None, summary: dict, exec_rows: list[dict]) -> int:
        ts = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        cur.execute('''
          INSERT INTO trade_links(signal_id,trace_id,created_at,symbol,side,entry_ts,exit_ts,entry_wap,exit_wap,qty_lots,pnl_pips,pnl_ccy,payload)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
          int(signal_id),
          int(trace_id) if trace_id is not None else None,
          ts,
          summary.get("symbol"),
          summary.get("side"),
          summary.get("entry_ts"),
          summary.get("exit_ts"),
          summary.get("entry_wap"),
          summary.get("exit_wap"),
          summary.get("qty_lots"),
          summary.get("pnl_pips"),
          summary.get("pnl_ccy"),
          json.dumps(summary),
        ))
        link_id = int(cur.lastrowid)
        for er in exec_rows:
            cur.execute('''
              INSERT INTO trade_link_execs(link_id,exec_snapshot_id,exec_id,role,ts_first,ts_last,qty_lots,wap_px,payload)
              VALUES(?,?,?,?,?,?,?,?,?)
            ''', (
              link_id,
              int(er["exec_snapshot_id"]),
              er.get("exec_id"),
              er.get("role"),
              er.get("ts_first"),
              er.get("ts_last"),
              er.get("qty_lots"),
              er.get("wap_px"),
              json.dumps(er),
            ))
        return link_id

def get_symbol_meta(self, symbol: str) -> dict|None:
    """Fetch cached symbol metadata for a given symbol name."""
    cur = self.conn.cursor()
    try:
        cur.execute("SELECT payload FROM symbol_meta WHERE symbol=? ORDER BY id DESC LIMIT 1", (str(symbol),))
        row = cur.fetchone()
        if row and row[0]:
            return json.loads(row[0])
    except Exception:
        return None
    return None

def update_trade_link_pnl(self, link_id: int, pnl_pips: float|None, pnl_ccy: float|None, payload_patch: dict|None=None) -> None:
    cur = self.conn.cursor()
    cur.execute("SELECT payload FROM trade_links WHERE id=?", (int(link_id),))
    row = cur.fetchone()
    payload = {}
    if row and row[0]:
        try:
            payload = json.loads(row[0])
        except Exception:
            payload = {}
    if payload_patch:
        payload.update(payload_patch)
    cur.execute(
        "UPDATE trade_links SET pnl_pips=?, pnl_ccy=?, payload=? WHERE id=?",
        (pnl_pips, pnl_ccy, json.dumps(payload), int(link_id))
    )
