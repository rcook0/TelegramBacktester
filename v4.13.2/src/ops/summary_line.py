from __future__ import annotations
import json
from typing import Any, Dict, Optional

def _fmt_pct(x: Any) -> str:
    try:
        if x is None: return "n/a"
        return f"{float(x):.1f}%"
    except Exception:
        return "n/a"

def _fmt_num(x: Any, dp: int = 0) -> str:
    try:
        if x is None: return "n/a"
        xf = float(x)
        if dp == 0: return f"{xf:.0f}"
        return f"{xf:.{dp}f}"
    except Exception:
        return "n/a"

def compute_summary_line(report_json: Dict[str, Any], *, label: str = "WEEK") -> str:
    s = report_json.get("summary", {})
    cov = s.get("coverage", {})
    gate = s.get("gate", {})
    pnl = s.get("pnl", {})
    exe = s.get("execution", {})

    n = s.get("n_signals", 0) or 0
    with_recon = cov.get("with_recon", 0) or 0
    with_link = cov.get("with_trade_link", 0) or 0

    missing_recon = (n - with_recon) if n else 0
    missing_link = (n - with_link) if n else 0

    pass_rate = gate.get("pass_rate_pct", None)
    pnl_ccy_sum = pnl.get("pnl_ccy_sum", None)
    pnl_pips_sum = pnl.get("pnl_pips_sum", None)
    slip_p90 = exe.get("slip_pips_p90", None)

    parts = [
        f"{label}",
        f"{int(n)} signals",
        f"gate pass {_fmt_pct(pass_rate)}",
        f"P&L {_fmt_num(pnl_ccy_sum, 2)} ccy ({_fmt_num(pnl_pips_sum, 0)} pips)",
        f"slip p90 {_fmt_num(slip_p90, 2)} pips",
    ]
    if missing_recon or missing_link:
        parts.append(f"missing recon {int(missing_recon)} / link {int(missing_link)}")
    return " | ".join(parts)

def classify_status(report_json: Dict[str, Any], *, min_pass_rate_pct: Optional[float] = None, max_missing_recon: Optional[int] = None) -> str:
    """Return OK/WARN/ERROR based on light policy knobs."""
    s = report_json.get("summary", {})
    cov = s.get("coverage", {})
    gate = s.get("gate", {})
    n = int(s.get("n_signals", 0) or 0)
    with_recon = int(cov.get("with_recon", 0) or 0)
    missing_recon = (n - with_recon) if n else 0

    pr = gate.get("pass_rate_pct", None)
    try:
        prf = float(pr) if pr is not None else None
    except Exception:
        prf = None

    status = "OK"
    if max_missing_recon is not None and missing_recon > int(max_missing_recon):
        status = "WARN"
    if min_pass_rate_pct is not None and prf is not None and prf < float(min_pass_rate_pct):
        status = "WARN"
    # If *zero* recon in a non-empty run, treat as ERROR
    if n > 0 and with_recon == 0:
        status = "ERROR"
    return status

def extract_key_metrics(report_json: Dict[str, Any]) -> Dict[str, Any]:
    s = report_json.get("summary", {})
    cov = s.get("coverage", {})
    gate = s.get("gate", {})
    pnl = s.get("pnl", {})
    exe = s.get("execution", {})

    n = int(s.get("n_signals", 0) or 0)
    with_recon = int(cov.get("with_recon", 0) or 0)
    with_link = int(cov.get("with_trade_link", 0) or 0)
    missing_recon = (n - with_recon) if n else 0
    missing_link = (n - with_link) if n else 0

    return {
        "n_signals": n,
        "with_recon": with_recon,
        "with_trade_link": with_link,
        "missing_recon": missing_recon,
        "missing_link": missing_link,
        "pass_rate_pct": gate.get("pass_rate_pct", None),
        "pnl_ccy_sum": pnl.get("pnl_ccy_sum", None),
        "pnl_pips_sum": pnl.get("pnl_pips_sum", None),
        "slip_p90_pips": exe.get("slip_pips_p90", None),
        "slip_p50_pips": exe.get("slip_pips_p50", None),
        "lat_entry_p90_sec": exe.get("lat_entry_sec_p90", None),
        "lat_entry_p50_sec": exe.get("lat_entry_sec_p50", None),
    }

def evaluate_policy(report_json: Dict[str, Any], *, min_pass_rate_pct: Optional[float] = None, max_missing_recon: Optional[int] = None) -> Dict[str, Any]:
    m = extract_key_metrics(report_json)
    reasons = []
    status = "OK"

    # hard error: non-empty but no recon coverage
    if m["n_signals"] > 0 and m["with_recon"] == 0:
        status = "ERROR"
        reasons.append({"rule": "recon_coverage", "severity": "ERROR", "detail": "n_signals>0 but with_recon==0"})

    # missing recon threshold
    if max_missing_recon is not None:
        thr = int(max_missing_recon)
        if m["missing_recon"] > thr:
            if status == "OK": status = "WARN"
            reasons.append({"rule": "missing_recon", "severity": "WARN", "detail": f"missing_recon={m['missing_recon']} > {thr}"})

    # pass rate threshold
    if min_pass_rate_pct is not None:
        try:
            pr = float(m["pass_rate_pct"]) if m["pass_rate_pct"] is not None else None
        except Exception:
            pr = None
        if pr is not None and pr < float(min_pass_rate_pct):
            if status == "OK": status = "WARN"
            reasons.append({"rule": "pass_rate", "severity": "WARN", "detail": f"pass_rate_pct={pr:.2f} < {float(min_pass_rate_pct):.2f}"})
        elif pr is None and m["n_signals"] > 0:
            if status == "OK": status = "WARN"
            reasons.append({"rule": "pass_rate", "severity": "WARN", "detail": "pass_rate_pct missing"})

    return {
        "status": status,
        "thresholds": {"min_pass_rate_pct": min_pass_rate_pct, "max_missing_recon": max_missing_recon},
        "metrics": m,
        "reasons": reasons,
    }
