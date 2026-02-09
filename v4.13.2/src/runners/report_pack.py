from __future__ import annotations
import argparse, json, os
from storage.sqlite_store_thresholds import ThresholdStore
from reporting.report_pack import ReportConfig, build_report
from reporting.csv_export import write_rows_csv
from reporting.html import render_report_html

def parse_args():
    p = argparse.ArgumentParser(description="Report pack v4.12.8: batch summaries over recon + thresholds + pnl.")
    p.add_argument("--db", required=True)
    p.add_argument("--since", default="")
    p.add_argument("--until", default="")
    p.add_argument("--channel", default="")
    p.add_argument("--symbol", default="")
    p.add_argument("--pack", default="shadow_gate_v1")
    p.add_argument("--pack-version", default="1.0")
    p.add_argument("--out-dir", default="./reports")
    p.add_argument("--out-prefix", default="report")
    p.add_argument("--emit-json", action="store_true")
    p.add_argument("--emit-csv", action="store_true")
    p.add_argument("--emit-html", action="store_true")
    p.add_argument("--max-rows", type=int, default=0)
    return p.parse_args()

def main():
    a = parse_args()
    store = ThresholdStore(a.db)
    cfg = ReportConfig(
        pack_name=a.pack,
        pack_version=a.pack_version,
        since_ts=a.since or None,
        until_ts=a.until or None,
        channel=a.channel or None,
        symbol=a.symbol or None,
    )
    report = build_report(store, cfg)

    os.makedirs(a.out_dir, exist_ok=True)
    base = os.path.join(a.out_dir, a.out_prefix)

    if not (a.emit_json or a.emit_csv or a.emit_html):
        a.emit_json = a.emit_csv = a.emit_html = True

    if a.emit_csv:
        write_rows_csv(base + ".csv", report["rows"])
        print("Wrote", base + ".csv")

    if a.emit_html:
        html = render_report_html(report)
        with open(base + ".html", "w", encoding="utf-8") as f:
            f.write(html)
        print("Wrote", base + ".html")

    if a.emit_json:
        out = dict(report)
        if a.max_rows and a.max_rows > 0:
            out["rows"] = out["rows"][:a.max_rows]
        with open(base + ".json", "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print("Wrote", base + ".json")

    print("\nSummary keys:", list(report["summary"].keys()))

if __name__ == "__main__":
    main()
