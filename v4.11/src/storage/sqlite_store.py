from __future__ import annotations
import sqlite3, os, json
from datetime import datetime, timezone
SCHEMA='''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS signals (id INTEGER PRIMARY KEY AUTOINCREMENT, idem_key TEXT UNIQUE NOT NULL, ts TEXT NOT NULL, channel TEXT, payload TEXT);
'''
class Store:
  def __init__(self, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    self.conn=sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    self.conn.executescript(SCHEMA)
  def upsert_signal(self, idem_key: str, ts: str, channel: str, payload: dict) -> int:
    cur=self.conn.cursor(); cur.execute('SELECT id FROM signals WHERE idem_key=?',(idem_key,)); r=cur.fetchone();
    if r: return r[0]
    cur.execute('INSERT INTO signals(idem_key,ts,channel,payload) VALUES(?,?,?,?)',(idem_key, ts, channel, json.dumps(payload))); return cur.lastrowid
