from __future__ import annotations
import argparse, json, os, webbrowser
from datetime import datetime, timezone
from storage.sqlite_store_ops import OpsStore

def parse_args():
    p = argparse.ArgumentParser(description="Show latest Weekly Ops status line (and optionally open browser).")
    p.add_argument("--db", required=True)
    p.add_argument("--json", action="store_true", help="Print latest ops summary_json as JSON.")
    p.add_argument("--history", type=int, default=0, help="Print N recent runs (summary_line + status).")
    p.add_argument("--open", action="store_true", help="Open reports/status_latest.html in browser if present.")
    p.add_argument("--reports-dir", default="./reports")
    return p.parse_args()

def main():
    a = parse_args()
    store = OpsStore(a.db)
    cur = store.conn.cursor()

    cur.execute("SELECT id, created_at, status, summary_line, summary_json FROM ops_runs ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        print("No ops_runs found.")
        raise SystemExit(1)
    run_id, created_at, status, summary_line, summary_json = row

    if a.history and a.history > 0:
        cur.execute("SELECT id, created_at, status, summary_line FROM ops_runs ORDER BY id DESC LIMIT ?", (int(a.history),))
        for rid, cat, st, line in cur.fetchall():
            print(f"{rid} | {cat} | {st} | {line}")
        return

    if a.json:
        try:
            obj = json.loads(summary_json) if summary_json else {}
        except Exception:
            obj = {"raw": summary_json}
        obj["ops_run_id"] = run_id
        obj["created_at"] = created_at
        obj["status"] = status
        if summary_line:
            obj["summary_line"] = summary_line
        print(json.dumps(obj, indent=2))
    else:
        print(summary_line or f"{status} | ops_run_id={run_id} | created_at={created_at}")

    if a.open:
        html_path = os.path.join(a.reports_dir, "status_latest.html")
        if os.path.exists(html_path):
            webbrowser.open("file://" + os.path.abspath(html_path))
        else:
            print("No status_latest.html found at", html_path)

if __name__ == "__main__":
    main()
