#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from datetime import datetime, timezone

try:
    import yaml
except Exception as e:
    raise SystemExit("Missing dependency: pyyaml. Install via `pip install pyyaml`.") from e

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
TREE_PATH = DOCS / "FEATURE_TREE.yaml"
REL_DIR = DOCS / "releases"
TEMPLATE = REL_DIR / "_TEMPLATE.md"

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

def load_tree() -> dict:
    return yaml.safe_load(TREE_PATH.read_text(encoding="utf-8"))

def write_tree(tree: dict) -> None:
    TREE_PATH.write_text(yaml.safe_dump(tree, sort_keys=False, allow_unicode=True), encoding="utf-8")

def ensure_template() -> str:
    if not TEMPLATE.exists():
        raise SystemExit(f"Missing template: {TEMPLATE}")
    return TEMPLATE.read_text(encoding="utf-8")

def version_key(v: str):
    m = SEMVER_RE.match(v)
    if not m:
        return (9999, v)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))

def add_release(tree: dict, version: str, title: str, roadmap_line: str, release_doc: str, assistant_notes: dict|None):
    rels = tree.setdefault("releases", [])
    for r in rels:
        if str(r.get("version")) == version:
            raise SystemExit(f"Release already exists in FEATURE_TREE.yaml: v{version}")
    rec = {
        "version": version,
        "title": title,
        "roadmap_line": roadmap_line,
        "release_doc": release_doc,
    }
    if assistant_notes:
        rec["assistant_notes"] = assistant_notes
    rels.append(rec)
    # Keep sorted (helps long-term)
    rels.sort(key=lambda r: version_key(str(r.get("version","0.0.0"))))

def fill_template(tmpl: str, version: str, title: str, roadmap_line: str,
                  changed: list[str], mechanism: list[str],
                  run_cmds: list[str], snapshots: list[str], tables: list[str], files: list[str],
                  why: list[str], caveats: list[str], next_line: str) -> str:
    # Template is simple; we don't attempt to preserve formatting beyond sections.
    def bullets(items, default="-"):
        if not items:
            return "-"
        return "\n".join([f"- {x}" for x in items])

    run_block = "\n".join(run_cmds) if run_cmds else "# command(s)"
    artifacts_lines = []
    artifacts_lines.append("- snapshots: " + (", ".join(snapshots) if snapshots else ""))
    artifacts_lines.append("- tables: " + (", ".join(tables) if tables else ""))
    artifacts_lines.append("- files: " + (", ".join(files) if files else ""))
    artifacts = "\n".join(artifacts_lines)

    out = tmpl
    out = out.replace("vX.Y.Z", f"v{version}", 1)
    out = out.replace("<title>", title, 1)
    out = out.replace("<one line>", roadmap_line, 1)
    out = out.replace("## What changed\n-", "## What changed\n" + bullets(changed), 1)
    out = out.replace("## Mechanism (short)\n-", "## Mechanism (short)\n" + bullets(mechanism), 1)
    out = out.replace("# command(s)", run_block, 1)
    # replace artifacts block
    out = re.sub(r"## Artifacts \(what to expect\)[\s\S]*?## Why it matters",
                 "## Artifacts (what to expect)\n" + artifacts + "\n\n## Why it matters",
                 out, count=1)
    out = out.replace("## Why it matters\n-", "## Why it matters\n" + bullets(why), 1)
    out = out.replace("## Caveats\n-", "## Caveats\n" + bullets(caveats), 1)
    out = re.sub(r"## Next[\s\S]*$", "## Next\n- " + (next_line or "vX.Y.(Z+1) — ...") + "\n", out, count=1)
    return out

def main():
    ap = argparse.ArgumentParser(description="Create a new release note + register it in docs/FEATURE_TREE.yaml")
    ap.add_argument("version", help="Semver like 4.12.5")
    ap.add_argument("title", help="Release title")
    ap.add_argument("--roadmap-line", default="", help="One-line roadmap summary")
    ap.add_argument("--next", dest="next_line", default="", help="Next version hint (one line)")

    # assistant notes (short structured)
    ap.add_argument("--why", action="append", default=[], help="Why this exists (repeatable)")
    ap.add_argument("--unlocks", default="", help="Comma-separated list of what this unlocks")
    ap.add_argument("--caveat", action="append", default=[], help="Caveats (repeatable)")

    # release doc sections
    ap.add_argument("--changed", action="append", default=[], help="What changed (repeatable)")
    ap.add_argument("--mechanism", action="append", default=[], help="Mechanism bullets (repeatable)")
    ap.add_argument("--run", action="append", default=[], help="Run commands (repeatable lines)")

    ap.add_argument("--snapshots", default="", help="Comma-separated snapshot kinds")
    ap.add_argument("--tables", default="", help="Comma-separated table names")
    ap.add_argument("--files", default="", help="Comma-separated file artifacts")

    ap.add_argument("--force", action="store_true", help="Overwrite release doc if it already exists on disk")
    args = ap.parse_args()

    if not SEMVER_RE.match(args.version):
        raise SystemExit("version must be X.Y.Z (e.g., 4.12.5)")

    REL_DIR.mkdir(parents=True, exist_ok=True)
    rel_path = REL_DIR / f"v{args.version}.md"
    if rel_path.exists() and not args.force:
        raise SystemExit(f"Release doc already exists: {rel_path} (use --force to overwrite)")

    tmpl = ensure_template()
    snapshots = [s.strip() for s in args.snapshots.split(",") if s.strip()]
    tables = [s.strip() for s in args.tables.split(",") if s.strip()]
    files = [s.strip() for s in args.files.split(",") if s.strip()]

    unlocks = [s.strip() for s in args.unlocks.split(",") if s.strip()]
    assistant_notes = None
    if args.why or unlocks or args.caveat:
        assistant_notes = {}
        if args.why:
            assistant_notes["why"] = " ".join(args.why) if len(args.why) == 1 else args.why
        if unlocks:
            assistant_notes["unlocks"] = unlocks
        if args.caveat:
            assistant_notes["caveats"] = " ".join(args.caveat) if len(args.caveat) == 1 else args.caveat

    doc = fill_template(
        tmpl=tmpl,
        version=args.version,
        title=args.title,
        roadmap_line=args.roadmap_line or "-",
        changed=args.changed,
        mechanism=args.mechanism,
        run_cmds=args.run,
        snapshots=snapshots,
        tables=tables,
        files=files,
        why=args.why,
        caveats=args.caveat,
        next_line=args.next_line,
    )
    rel_path.write_text(doc, encoding="utf-8")

    tree = load_tree()
    add_release(tree, args.version, args.title, args.roadmap_line or "", f"docs/releases/v{args.version}.md", assistant_notes)
    write_tree(tree)

    print(f"created: {rel_path}")
    print("updated: docs/FEATURE_TREE.yaml")
    print("next: run `python tools/docs_build.py` to regenerate USER_MANUAL / TECHNICAL_GUIDE / VERSION_HISTORY")

if __name__ == "__main__":
    main()
