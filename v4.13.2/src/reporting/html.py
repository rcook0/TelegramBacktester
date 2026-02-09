from __future__ import annotations
import html
from typing import Any, Dict, List

def _h(x: Any) -> str:
    return html.escape("" if x is None else str(x))

def _table(headers: List[str], rows: List[List[Any]]) -> str:
    th = "".join(f"<th>{_h(h)}</th>" for h in headers)
    trs = []
    for r in rows:
        tds = "".join(f"<td>{_h(v)}</td>" for v in r)
        trs.append(f"<tr>{tds}</tr>")
    return f"<table border='1' cellpadding='6' cellspacing='0'><thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table>"

def render_report_html(report: Dict[str, Any]) -> str:
    meta = report.get("meta", {})
    s = report.get("summary", {})
    cov = s.get("coverage", {})
    gate = s.get("gate", {})
    pnl = s.get("pnl", {})
    exe = s.get("execution", {})
    by_sym = s.get("by_symbol", [])
    top_rules = gate.get("top_rule_hits", [])

    parts = []
    parts.append("<html><head><meta charset='utf-8'><title>FX Backtester Report</title></head><body>")
    parts.append("<h1>FX Backtester Report (v4.12.8)</h1>")
    parts.append("<h2>Meta</h2>")
    parts.append(_table(["key","value"], [[k,v] for k,v in meta.items()]))
    parts.append("<h2>Coverage</h2>")
    parts.append(_table(["metric","value"], [[k,v] for k,v in cov.items()]))
    parts.append("<h2>Gate</h2>")
    parts.append(_table(["metric","value"], [[k,v] for k,v in gate.items() if k not in ("top_rule_hits","violations_by_severity")]))

    parts.append("<h3>Violations by severity</h3>")
    vbs = gate.get("violations_by_severity", {})
    parts.append(_table(["severity","count"], [[k,v] for k,v in vbs.items()]))
    parts.append("<h3>Top rule hits</h3>")
    parts.append(_table(["rule_id","count"], [[r.get("rule_id"), r.get("count")] for r in top_rules]))

    parts.append("<h2>P&L</h2>")
    parts.append(_table(["metric","value"], [[k,v] for k,v in pnl.items()]))
    parts.append("<h2>Execution</h2>")
    parts.append(_table(["metric","value"], [[k,v] for k,v in exe.items()]))
    parts.append("<h2>By symbol</h2>")
    parts.append(_table(["symbol","n","pnl_ccy_sum","pass_rate"], [[r.get("symbol"), r.get("n"), r.get("pnl_ccy_sum"), r.get("pass_rate")] for r in by_sym]))

    parts.append("<h2>Rows (first 200)</h2>")
    rows = report.get("rows", [])[:200]
    headers = ["signal_ts","channel","symbol","side","pnl_ccy","pnl_pips","slip_pips","lat_entry_sec","gate_status","gate_score","idem_key"]
    parts.append(_table(headers, [[
        r.get("signal_ts"), r.get("channel"), r.get("symbol"), r.get("side"),
        r.get("pnl_ccy"), r.get("pnl_pips"), r.get("slip_pips"),
        r.get("lat_entry_sec"), r.get("gate_status"), r.get("gate_score"),
        r.get("idem_key")
    ] for r in rows]))
    parts.append("</body></html>")
    return "".join(parts)
