from __future__ import annotations
import json, math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

def _safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

def _pct(n: float, d: float) -> float:
    return 0.0 if d == 0 else (100.0 * n / d)

def _quantile(xs: List[float], q: float) -> Optional[float]:
    xs = [float(x) for x in xs if x is not None]
    if not xs:
        return None
    xs.sort()
    if q <= 0: return xs[0]
    if q >= 1: return xs[-1]
    i = (len(xs)-1) * q
    lo = int(math.floor(i))
    hi = int(math.ceil(i))
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi-i) + xs[hi] * (i-lo)

@dataclass
class ReportConfig:
    pack_name: str = "shadow_gate_v1"
    pack_version: str = "1.0"
    since_ts: Optional[str] = None
    until_ts: Optional[str] = None
    channel: Optional[str] = None
    symbol: Optional[str] = None

def fetch_rows(store, cfg: ReportConfig) -> List[dict]:
    cur = store.conn.cursor()
    where = []
    params: List[Any] = []
    if cfg.since_ts:
        where.append("s.ts >= ?"); params.append(cfg.since_ts)
    if cfg.until_ts:
        where.append("s.ts <= ?"); params.append(cfg.until_ts)
    if cfg.channel:
        where.append("s.channel = ?"); params.append(cfg.channel)

    q = f"""
    SELECT
      s.id AS signal_id,
      s.idem_key,
      s.ts AS signal_ts,
      s.channel,
      tl.id AS trade_link_id,
      tl.symbol AS symbol,
      tl.side AS side,
      tl.pnl_pips AS pnl_pips,
      tl.pnl_ccy AS pnl_ccy,
      rr.id AS recon_id,
      rr.total_slip_pips AS slip_pips,
      rr.latency_entry_sec AS lat_entry_sec,
      rr.latency_exit_sec AS lat_exit_sec,
      ev.id AS eval_id,
      ev.status AS gate_status,
      ev.score AS gate_score,
      ev.violations AS gate_violations_json
    FROM signals s
    LEFT JOIN trade_links tl ON tl.id = (
      SELECT id FROM trade_links WHERE signal_id=s.id ORDER BY id DESC LIMIT 1
    )
    LEFT JOIN trade_recon_v3 rr ON rr.id = (
      SELECT id FROM trade_recon_v3 WHERE signal_id=s.id ORDER BY id DESC LIMIT 1
    )
    LEFT JOIN threshold_packs pk ON pk.id = (
      SELECT id FROM threshold_packs WHERE name=? AND version=? ORDER BY id DESC LIMIT 1
    )
    LEFT JOIN signal_threshold_eval ev ON ev.id = (
      SELECT id FROM signal_threshold_eval WHERE signal_id=s.id AND pack_id=pk.id ORDER BY id DESC LIMIT 1
    )
    {("WHERE " + " AND ".join(where)) if where else ""}
    ORDER BY s.ts ASC
    """
    cur.execute(q, [cfg.pack_name, cfg.pack_version] + params)
    rows = []
    for r in cur.fetchall():
        (signal_id, idem_key, signal_ts, channel, trade_link_id, symbol, side,
         pnl_pips, pnl_ccy, recon_id, slip_pips, lat_entry_sec, lat_exit_sec,
         eval_id, gate_status, gate_score, gate_violations_json) = r
        if cfg.symbol and symbol and symbol != cfg.symbol:
            continue
        try:
            vio = json.loads(gate_violations_json) if gate_violations_json else []
        except Exception:
            vio = []
        rows.append({
            "signal_id": signal_id,
            "idem_key": idem_key,
            "signal_ts": signal_ts,
            "channel": channel,
            "trade_link_id": trade_link_id,
            "symbol": symbol,
            "side": side,
            "pnl_pips": _safe_float(pnl_pips),
            "pnl_ccy": _safe_float(pnl_ccy),
            "recon_id": recon_id,
            "slip_pips": _safe_float(slip_pips),
            "lat_entry_sec": _safe_float(lat_entry_sec),
            "lat_exit_sec": _safe_float(lat_exit_sec),
            "eval_id": eval_id,
            "gate_status": gate_status,
            "gate_score": _safe_float(gate_score),
            "gate_violations": vio,
        })
    return rows

def summarize(rows: List[dict]) -> dict:
    total = len(rows)
    with_link = sum(1 for r in rows if r.get("trade_link_id") is not None)
    with_recon = sum(1 for r in rows if r.get("recon_id") is not None)
    with_gate = sum(1 for r in rows if r.get("eval_id") is not None)

    pnl_ccy = [r["pnl_ccy"] for r in rows if r.get("pnl_ccy") is not None]
    pnl_pips = [r["pnl_pips"] for r in rows if r.get("pnl_pips") is not None]
    slip = [r["slip_pips"] for r in rows if r.get("slip_pips") is not None]
    lat = [r["lat_entry_sec"] for r in rows if r.get("lat_entry_sec") is not None]
    gate_scores = [r["gate_score"] for r in rows if r.get("gate_score") is not None]
    passes = sum(1 for r in rows if r.get("gate_status") == "PASS")
    fails = sum(1 for r in rows if r.get("gate_status") == "FAIL")

    freq: Dict[str, int] = {}
    sev: Dict[str, int] = {"WARN":0,"ERROR":0}
    for r in rows:
        for v in (r.get("gate_violations") or []):
            rid = v.get("rule_id") or v.get("id") or "unknown"
            freq[rid] = freq.get(rid, 0) + 1
            s = (v.get("severity") or "").upper()
            if s in sev: sev[s] += 1

    top_rules = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:15]

    by_symbol: Dict[str, dict] = {}
    for r in rows:
        sym = r.get("symbol") or "UNKNOWN"
        d = by_symbol.setdefault(sym, {"n":0,"pnl_ccy_sum":0.0,"pnl_ccy_n":0,"pass":0,"fail":0})
        d["n"] += 1
        if r.get("pnl_ccy") is not None:
            d["pnl_ccy_sum"] += float(r["pnl_ccy"]); d["pnl_ccy_n"] += 1
        if r.get("gate_status") == "PASS": d["pass"] += 1
        if r.get("gate_status") == "FAIL": d["fail"] += 1

    by_symbol_list = []
    for sym, d in sorted(by_symbol.items(), key=lambda kv: (-kv[1]["n"], kv[0])):
        by_symbol_list.append({
            "symbol": sym,
            "n": d["n"],
            "pnl_ccy_sum": d["pnl_ccy_sum"] if d["pnl_ccy_n"] else None,
            "pass_rate": _pct(d["pass"], d["pass"]+d["fail"]) if (d["pass"]+d["fail"]) else None,
        })

    return {
        "n_signals": total,
        "coverage": {
            "with_trade_link": with_link,
            "with_recon": with_recon,
            "with_gate_eval": with_gate,
            "trade_link_coverage_pct": _pct(with_link, total),
            "recon_coverage_pct": _pct(with_recon, total),
            "gate_coverage_pct": _pct(with_gate, total),
        },
        "gate": {
            "pass": passes,
            "fail": fails,
            "pass_rate_pct": _pct(passes, passes+fails),
            "score_mean": (sum(gate_scores)/len(gate_scores)) if gate_scores else None,
            "score_p10": _quantile(gate_scores, 0.10),
            "score_p50": _quantile(gate_scores, 0.50),
            "score_p90": _quantile(gate_scores, 0.90),
            "violations_total": sev["WARN"] + sev["ERROR"],
            "violations_by_severity": sev,
            "top_rule_hits": [{"rule_id": rid, "count": c} for rid,c in top_rules],
        },
        "pnl": {
            "pnl_ccy_sum": sum(pnl_ccy) if pnl_ccy else None,
            "pnl_ccy_mean": (sum(pnl_ccy)/len(pnl_ccy)) if pnl_ccy else None,
            "pnl_pips_sum": sum(pnl_pips) if pnl_pips else None,
            "pnl_pips_mean": (sum(pnl_pips)/len(pnl_pips)) if pnl_pips else None,
        },
        "execution": {
            "slip_pips_p50": _quantile(slip, 0.50),
            "slip_pips_p90": _quantile(slip, 0.90),
            "lat_entry_sec_p50": _quantile(lat, 0.50),
            "lat_entry_sec_p90": _quantile(lat, 0.90),
        },
        "by_symbol": by_symbol_list,
    }

def build_report(store, cfg: ReportConfig) -> dict:
    rows = fetch_rows(store, cfg)
    summary = summarize(rows)
    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pack_name": cfg.pack_name,
            "pack_version": cfg.pack_version,
            "since_ts": cfg.since_ts,
            "until_ts": cfg.until_ts,
            "channel": cfg.channel,
            "symbol": cfg.symbol,
        },
        "summary": summary,
        "rows": rows,
        "schema": "report_pack_v4.12.8",
    }
