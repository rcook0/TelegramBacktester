from __future__ import annotations
import argparse
import sqlite3
import time

def parse_args():
    p = argparse.ArgumentParser(description="SQLite maintenance (WAL checkpoint, vacuum)")
    p.add_argument("--db", required=True)
    p.add_argument("--wal-checkpoint", choices=["PASSIVE","FULL","RESTART","TRUNCATE"], default="TRUNCATE")
    p.add_argument("--vacuum", action="store_true")
    p.add_argument("--analyze", action="store_true")
    return p.parse_args()

def main():
    a = parse_args()
    con = sqlite3.connect(a.db)
    cur = con.cursor()

    # checkpoint WAL
    mode = a.wal_checkpoint.upper()
    cur.execute(f"PRAGMA wal_checkpoint({mode});")
    res = cur.fetchall()
    print("wal_checkpoint", mode, res)

    if a.analyze:
        cur.execute("ANALYZE;")
        print("ANALYZE ok")

    if a.vacuum:
        # VACUUM can be slow but compacts the DB if you delete many rows.
        cur.execute("VACUUM;")
        print("VACUUM ok")

    con.commit()
    con.close()

if __name__ == "__main__":
    main()
