from __future__ import annotations
import csv
from typing import List

DEFAULT_COLUMNS = [
  "signal_id","idem_key","signal_ts","channel","trade_link_id","symbol","side",
  "pnl_ccy","pnl_pips","recon_id","slip_pips","lat_entry_sec","lat_exit_sec",
  "eval_id","gate_status","gate_score"
]

def write_rows_csv(path: str, rows: List[dict], columns: List[str] | None = None) -> None:
    cols = columns or DEFAULT_COLUMNS
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
