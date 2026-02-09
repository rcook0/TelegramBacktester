from __future__ import annotations
import argparse, csv, json
from datetime import datetime, timezone
from storage.sqlite_store_traces import TraceStore

def parse_args():
    p = argparse.ArgumentParser(description="Ingest broker deal/fill CSV as shadow snapshots")
    p.add_argument("--db", required=True)
    p.add_argument("--signal-idem-key", required=True)
    p.add_argument("--csv", required=True, help="Path to CSV containing fills/deals")
    p.add_argument("--symbol-col", default="Symbol")
    p.add_argument("--time-col", default="Time")
    p.add_argument("--price-col", default="Price")
    p.add_argument("--qty-col", default="Volume")
    p.add_argument("--kind", default="deal", choices=["deal","fill"])
    p.add_argument("--time-format", default="", help="Optional datetime.strptime format; otherwise ISO parse")
    return p.parse_args()

def _parse_time(s: str, fmt: str) -> str:
    s = s.strip()
    if not fmt:
        # try ISO
        try:
            if s.endswith("Z"): s = s.replace("Z","+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except Exception:
            pass
    dt = datetime.strptime(s, fmt) if fmt else datetime.fromisoformat(s)
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()

def main():
    a = parse_args()
    store = TraceStore(a.db)
    cur = store.conn.cursor()
    cur.execute("SELECT id FROM signals WHERE idem_key=?", (a.signal_idem_key,))
    r = cur.fetchone()
    if not r:
        raise SystemExit("No signal for idem_key.")
    sid = int(r[0])

    n = 0
    with open(a.csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = _parse_time(row[a.time_col], a.time_format)
            payload = {
                "ts": ts,
                "symbol": row.get(a.symbol_col),
                "px": float(row[a.price_col]),
                "qty": float(row[a.qty_col]),
                "raw": row,
                "source": "csv",
            }
            store.add_shadow_snapshot(sid, a.kind, payload, ts=ts)
            n += 1
    print("ingested", n, "rows")

if __name__ == "__main__":
    main()
