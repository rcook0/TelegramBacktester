from __future__ import annotations
import argparse, json, os
from datetime import datetime, timezone

def parse_args():
    p = argparse.ArgumentParser(description="Dash status tab (optional). Requires: pip install -e '.[dash]'")
    p.add_argument("--reports-dir", default="./reports")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8050)
    p.add_argument("--debug", action="store_true")
    return p.parse_args()

def load_status(path: str) -> dict:
    if not os.path.exists(path):
        return {"status":"MISSING","summary_line":"status_latest.json not found", "generated_at": datetime.now(timezone.utc).isoformat()}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"status":"ERROR","summary_line":f"failed to parse status_latest.json: {e}"}

def main():
    a = parse_args()
    try:
        import dash
        from dash import html, dcc
    except Exception as e:
        raise SystemExit("Dash not installed. Install extras: pip install -e '.[dash]'") from e

    app = dash.Dash(__name__)
    status_path = os.path.join(a.reports_dir, "status_latest.json")

    def layout():
        s = load_status(status_path)
        return html.Div([
            html.H2("Weekly Ops Status"),
            html.Div([
                html.Span(s.get("status","OK"), style={"border":"1px solid #bbb","padding":"4px 10px","borderRadius":"999px","fontWeight":"600"}),
            ], style={"marginBottom":"12px"}),
            html.Pre(s.get("summary_line",""), style={"whiteSpace":"pre-wrap","fontSize":"16px"}),
            html.H4("Details"),
            dcc.Markdown(f"""
- updated: `{s.get('generated_at','')}`
- ops_run_id: `{s.get('ops_run_id','')}`
- report_html: `{s.get('report_html','')}`
"""),
            html.H4("Raw status_latest.json"),
            html.Pre(json.dumps(s, indent=2), style={"whiteSpace":"pre-wrap","fontSize":"12px"}),
        ], style={"maxWidth":"980px","margin":"24px auto","padding":"16px","fontFamily":"system-ui"})
    app.layout = layout

    app.run(host=a.host, port=a.port, debug=a.debug)

if __name__ == "__main__":
    main()
