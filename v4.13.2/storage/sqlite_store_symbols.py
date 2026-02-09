from __future__ import annotations
import json
from datetime import datetime, timezone
from .sqlite_store_shadow import ShadowStore

SYMBOL_SCHEMA = '''
CREATE TABLE IF NOT EXISTS symbol_resolution (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  broker TEXT NOT NULL,           -- e.g. ctrader-openapi
  account_id TEXT,                -- optional scope
  symbol_input TEXT NOT NULL,     -- your canonical symbol or alias
  symbol_name TEXT NOT NULL,      -- broker symbol name (as returned)
  symbol_id INTEGER NOT NULL,
  digits INTEGER,
  pip_position INTEGER,
  pip_size REAL,
  updated_at TEXT NOT NULL,
  UNIQUE(broker, account_id, symbol_input)
);

-- v4.12.1: richer per-symbol metadata cache, keyed by broker+account+symbol_id.
CREATE TABLE IF NOT EXISTS symbol_meta (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  broker TEXT NOT NULL,
  account_id TEXT,
  symbol_id INTEGER NOT NULL,
  symbol_name TEXT NOT NULL,
  digits INTEGER,
  pip_position INTEGER,
  pip_size REAL,
  lot_size_cents INTEGER,
  min_volume_cents INTEGER,
  max_volume_cents INTEGER,
  step_volume_cents INTEGER,
  measurement_units TEXT,
  updated_at TEXT NOT NULL,
  UNIQUE(broker, account_id, symbol_id)
);
'''


class SymbolStore(ShadowStore):
    def __init__(self, path: str):
        super().__init__(path)
        self.conn.executescript(SYMBOL_SCHEMA)

    def upsert_symbol(self, broker: str, account_id: str|None, symbol_input: str, symbol_name: str, symbol_id: int,
                      digits: int|None=None, pip_position: int|None=None, pip_size: float|None=None):
        ts = datetime.now(timezone.utc).isoformat()
        self.conn.execute('''
          INSERT INTO symbol_resolution(broker,account_id,symbol_input,symbol_name,symbol_id,digits,pip_position,pip_size,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?)
          ON CONFLICT(broker,account_id,symbol_input) DO UPDATE SET
            symbol_name=excluded.symbol_name,
            symbol_id=excluded.symbol_id,
            digits=excluded.digits,
            pip_position=excluded.pip_position,
            pip_size=excluded.pip_size,
            updated_at=excluded.updated_at
        ''', (broker, account_id, symbol_input, symbol_name, int(symbol_id),
              digits, pip_position, pip_size, ts))

    def get_symbol(self, broker: str, account_id: str|None, symbol_input: str):
        cur = self.conn.cursor()
        cur.execute('''SELECT symbol_name,symbol_id,digits,pip_position,pip_size FROM symbol_resolution
                       WHERE broker=? AND account_id IS ? AND symbol_input=?''', (broker, account_id, symbol_input))
        row = cur.fetchone()
        if not row:
            return None
        return dict(symbol_name=row[0], symbol_id=int(row[1]), digits=row[2], pip_position=row[3], pip_size=row[4])


    def upsert_symbol_meta(self, broker: str, account_id: str|None, symbol_id: int, symbol_name: str,
                          digits: int|None=None, pip_position: int|None=None, pip_size: float|None=None,
                          lot_size_cents: int|None=None, min_volume_cents: int|None=None, max_volume_cents: int|None=None,
                          step_volume_cents: int|None=None, measurement_units: str|None=None):
        ts = datetime.now(timezone.utc).isoformat()
        self.conn.execute('''
          INSERT INTO symbol_meta(broker,account_id,symbol_id,symbol_name,digits,pip_position,pip_size,
                                 lot_size_cents,min_volume_cents,max_volume_cents,step_volume_cents,measurement_units,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(broker,account_id,symbol_id) DO UPDATE SET
            symbol_name=excluded.symbol_name,
            digits=excluded.digits,
            pip_position=excluded.pip_position,
            pip_size=excluded.pip_size,
            lot_size_cents=excluded.lot_size_cents,
            min_volume_cents=excluded.min_volume_cents,
            max_volume_cents=excluded.max_volume_cents,
            step_volume_cents=excluded.step_volume_cents,
            measurement_units=excluded.measurement_units,
            updated_at=excluded.updated_at
        ''', (broker, account_id, int(symbol_id), symbol_name, digits, pip_position, pip_size,
              lot_size_cents, min_volume_cents, max_volume_cents, step_volume_cents, measurement_units, ts))

    def get_symbol_meta(self, broker: str, account_id: str|None, symbol_id: int):
        cur = self.conn.cursor()
        cur.execute('''SELECT symbol_name,digits,pip_position,pip_size,lot_size_cents,min_volume_cents,max_volume_cents,step_volume_cents,measurement_units
                       FROM symbol_meta WHERE broker=? AND account_id IS ? AND symbol_id=?''', (broker, account_id, int(symbol_id)))
        row = cur.fetchone()
        if not row:
            return None
        return dict(
            symbol_name=row[0], digits=row[1], pip_position=row[2], pip_size=row[3],
            lot_size_cents=row[4], min_volume_cents=row[5], max_volume_cents=row[6], step_volume_cents=row[7],
            measurement_units=row[8],
        )
