from __future__ import annotations
import argparse, json, os
from datetime import datetime, timezone, timedelta

from storage.sqlite_store_ops import OpsStore
from ops.summary_line import compute_summary_line, classify_status, evaluate_policy
from ops.status_artifacts import write_status_bundle

from ops.exec import run_module, ensure_ok
from ops.rotation import rotate_reports

def parse_args():
    p = argparse.ArgumentParser(description="Weekly Ops: run reconcile+threshold+report for a rolling window and persist ops metadata.")
    p.add_argument("--db", required=True)
    p.add_argument("--channel", default="")
    p.add_argument("--symbol", default="")
    p.add_argument("--pack", default="shadow_gate_v1")
    p.add_argument("--pack-version", default="1.0")
    p.add_argument("--weeks", type=int, default=1, help="Window size in weeks (default 1).")
    p.add_argument("--until", default="", help="ISO timestamp for window end (default now UTC).")
    p.add_argument("--out-dir", default="./reports")
    p.add_argument("--prefix", default="", help="If empty, auto: weekly_YYYY-MM-DD")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--retention-days", type=int, default=30)
    p.add_argument("--emit-ops-json", default="", help="Optional: write ops summary json to this path")
    p.add_argument("--min-pass-rate-pct", type=float, default=None)
    p.add_argument("--max-missing-recon", type=int, default=None)
    p.add_argument("--write-status-latest", action="store_true", help="Write reports/status_latest.(json|txt|html)")

    return p.parse_args()

def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()

def main():
    a = parse_args()
    store = OpsStore(a.db)

    until = datetime.now(timezone.utc) if not a.until else datetime.fromisoformat(a.until)
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    since = until - timedelta(days=7*max(1, int(a.weeks)))

    out_dir = a.out_dir
    os.makedirs(out_dir, exist_ok=True)
    prefix = a.prefix or f"weekly_{since.date().isoformat()}_{until.date().isoformat()}"

    common = ["--since", _iso(since), "--until", _iso(until)]
    if a.channel:
        common += ["--channel", a.channel]
    if a.symbol:
        common += ["--symbol", a.symbol]

    ops_summary = {
        "kind": "weekly_ops",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "window_since": _iso(since),
        "window_until": _iso(until),
        "channel": a.channel or None,
        "symbol": a.symbol or None,
        "pack_name": a.pack,
        "pack_version": a.pack_version,
                "policy": policy,
        "status": "OK",
        "steps": [],
        "artifacts": {},
    }

    try:
        # rotate old stuff first
        moved = rotate_reports(out_dir, retention_days=int(a.retention_days))
        ops_summary["rotation"] = {"moved": moved, "retention_days": int(a.retention_days)}

        # reconcile batch
        rec_args = ["--db", a.db] + common
        if a.overwrite: rec_args.append("--overwrite")
        code, out = run_module("src.runners.reconcile_batch_v3", rec_args, capture=True)
        ensure_ok(code, out, "reconcile_batch_v3")
        rec_path = os.path.join(out_dir, prefix + "_reconcile_summary.json")
        with open(rec_path, "w", encoding="utf-8") as f:
            f.write(out)
        ops_summary["steps"].append({"step": "reconcile_batch_v3", "ok": True, "summary_path": rec_path})

        # threshold batch
        thr_args = ["--db", a.db] + common + ["--pack", a.pack, "--pack-version", a.pack_version]
        if a.overwrite: thr_args.append("--overwrite")
        code, out = run_module("src.runners.threshold_batch_eval", thr_args, capture=True)
        ensure_ok(code, out, "threshold_batch_eval")
        thr_path = os.path.join(out_dir, prefix + "_threshold_summary.json")
        with open(thr_path, "w", encoding="utf-8") as f:
            f.write(out)
        ops_summary["steps"].append({"step": "threshold_batch_eval", "ok": True, "summary_path": thr_path})

        # report pack
        rep_args = ["--db", a.db] + common + ["--pack", a.pack, "--pack-version", a.pack_version, "--out-dir", out_dir, "--out-prefix", prefix]
        code, out = run_module("src.runners.report_pack", rep_args, capture=True)
        ensure_ok(code, out, "report_pack")
        rep_log = os.path.join(out_dir, prefix + "_report_pack.log")
        with open(rep_log, "w", encoding="utf-8") as f:
            f.write(out)
        ops_summary["steps"].append({"step": "report_pack", "ok": True, "log_path": rep_log})

        ops_summary["artifacts"] = {
            "reconcile_summary_json": rec_path,
            "threshold_summary_json": thr_path,
            "report_csv": os.path.join(out_dir, prefix + ".csv"),
            "report_json": os.path.join(out_dir, prefix + ".json"),
            "report_html": os.path.join(out_dir, prefix + ".html"),
            "report_log": rep_log,
# compute summary line from report JSON
rep_json_path = os.path.join(out_dir, prefix + ".json")
report_obj = {}
try:
    with open(rep_json_path, "r", encoding="utf-8") as f:
        report_obj = json.load(f)
except Exception:
    report_obj = {}

summary_line = compute_summary_line(report_obj, label="WEEK")
ops_summary["summary_line"] = summary_line

# classify status (light knobs)
ops_status = classify_status(report_obj, min_pass_rate_pct=a.min_pass_rate_pct, max_missing_recon=a.max_missing_recon)
if ops_summary.get("status") == "OK" and ops_status != "OK":
    ops_summary["status"] = ops_status

# status_latest bundle (for browser/Dash/terminal)
if a.write_status_latest:
    status_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": ops_summary.get("status","OK"),
        "summary_line": summary_line,
        "ops_run_id": None,  # filled after DB insert
        "db": a.db,
        "window_since": ops_summary.get("window_since"),
        "window_until": ops_summary.get("window_until"),
        "channel": ops_summary.get("channel"),
        "symbol": ops_summary.get("symbol"),
        "pack_name": a.pack,
        "pack_version": a.pack_version,
                "policy": policy,
        "report_csv": os.path.join(out_dir, prefix + ".csv"),
        "report_json": rep_json_path,
        "report_html": os.path.join(out_dir, prefix + ".html"),
    }
    paths = write_status_bundle(out_dir, status_payload)
    ops_summary["artifacts"]["status_latest_json"] = paths["json"]
    ops_summary["artifacts"]["status_latest_txt"] = paths["txt"]
    ops_summary["artifacts"]["status_latest_html"] = paths["html"]
        }

    except Exception as e:
        ops_summary["status"] = "ERROR"
        ops_summary["error"] = str(e)

    run_id = store.add_ops_run(ops_summary)
    for k, path in (ops_summary.get("artifacts") or {}).items():
        store.add_artifact(run_id, k, path)
    store.conn.commit()

    ops_summary["ops_run_id"] = run_id
    # fill ops_run_id into status_latest.json if present
    try:
        import json as _json
        sj = os.path.join(a.out_dir, "status_latest.json")
        if os.path.exists(sj):
            obj = _json.loads(open(sj,"r",encoding="utf-8").read())
            obj["ops_run_id"] = run_id
            open(sj,"w",encoding="utf-8").write(_json.dumps(obj, indent=2))
    except Exception:
        pass

    print(json.dumps(ops_summary, indent=2))
    if a.emit_ops_json:
        with open(a.emit_ops_json, "w", encoding="utf-8") as f:
            json.dump(ops_summary, f, indent=2)

    if ops_summary["status"] != "OK":
        raise SystemExit(2)

if __name__ == "__main__":
    main()
