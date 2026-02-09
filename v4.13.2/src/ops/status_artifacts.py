from __future__ import annotations
import json, os
from typing import Any, Dict

def _h(x: Any) -> str:
    s = "" if x is None else str(x)
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def write_status_bundle(out_dir: str, status: Dict[str, Any]) -> Dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    paths = {}

    # JSON
    jp = os.path.join(out_dir, "status_latest.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)
    paths["json"] = jp

    # TXT
    tp = os.path.join(out_dir, "status_latest.txt")
    with open(tp, "w", encoding="utf-8") as f:
        f.write(status.get("summary_line","") + "\n")
    paths["txt"] = tp

    # HTML
    hp = os.path.join(out_dir, "status_latest.html")
    badge = status.get("status","OK")

    policy = status.get("policy", {}) or {}
    thresholds = policy.get("thresholds", {}) or {}
    reasons = policy.get("reasons", []) or []
    metrics = policy.get("metrics", {}) or {}

    css = "font-family:ui-sans-serif,system-ui,-apple-system;max-width:980px;margin:32px auto;padding:16px;border:1px solid #ddd;border-radius:12px;"
    badge_css = "display:inline-block;padding:4px 10px;border-radius:999px;border:1px solid #bbb;font-weight:600;"
    small = "font-size:12px;opacity:0.75;"
    hr = "<hr style='margin:16px 0;border:none;border-top:1px solid #eee;'>"

    reasons_html = "<em>none</em>" if not reasons else "<ul style='margin:6px 0 0 18px;'>" + "".join(
        f"<li><b>{_h(r.get('severity',''))}</b> {_h(r.get('rule',''))}: {_h(r.get('detail',''))}</li>" for r in reasons
    ) + "</ul>"

    thr_html = "<em>none</em>" if not thresholds else "<ul style='margin:6px 0 0 18px;'>" + "".join(
        f"<li>{_h(k)}: <code>{_h(v)}</code></li>" for k,v in thresholds.items()
    ) + "</ul>"

    keep = ("n_signals","missing_recon","missing_link","pass_rate_pct","slip_p90_pips","lat_entry_p90_sec")
    met_html = "<ul style='margin:6px 0 0 18px;'>" + "".join(
        f"<li>{_h(k)}: <code>{_h(v)}</code></li>" for k,v in metrics.items() if k in keep
    ) + "</ul>"

    body = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Status</title></head>
<body>
<div style="{css}">
  <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;">
    <h2 style="margin:0;">Weekly Ops Status</h2>
    <span style="{badge_css}">{_h(badge)}</span>
  </div>
  <p style="margin:12px 0 6px 0;font-size:16px;line-height:1.4;">{_h(status.get("summary_line",""))}</p>
  <div style="{small}">updated: {_h(status.get("generated_at",""))}</div>

  {hr}
  <h3 style="margin:0 0 6px 0;">Policy</h3>
  <div><b>thresholds</b>{thr_html}</div>
  <div style="margin-top:10px;"><b>metrics</b>{met_html}</div>
  <div style="margin-top:10px;"><b>reasons</b>{reasons_html}</div>

  {hr}
  <h3 style="margin:0 0 6px 0;">Links</h3>
  <div style="font-size:13px;">
    <div><b>report_html:</b> {_h(status.get("report_html",""))}</div>
    <div><b>report_json:</b> {_h(status.get("report_json",""))}</div>
    <div><b>db:</b> {_h(status.get("db",""))}</div>
    <div><b>ops_run_id:</b> {_h(status.get("ops_run_id",""))}</div>
  </div>
</div>
</body></html>"""

    with open(hp, "w", encoding="utf-8") as f:
        f.write(body)
    paths["html"] = hp
    return paths
