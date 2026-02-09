#!/usr/bin/env python3
from __future__ import annotations
import argparse, re
from pathlib import Path

try:
  import yaml
except Exception as e:
  raise SystemExit("Missing dependency: pyyaml. Install via `pip install pyyaml`.") from e

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

def load_tree():
  return yaml.safe_load((DOCS / "FEATURE_TREE.yaml").read_text(encoding="utf-8"))

def write(path: Path, content: str):
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(content, encoding="utf-8")

def build_user_manual(tree: dict) -> str:
  lines=[]
  lines.append("# User Manual\n")
  lines.append("Operator/runbook view.\n")
  pipe = tree.get("pipelines", {}).get("shadow_parity", {})
  lines.append(f"## {pipe.get('title','Pipeline')}\n")
  for step in pipe.get("steps", []):
    lines.append(f"### {step.get('title','(unnamed)')}\n")
    eps = step.get("entrypoints", [])
    if eps:
      lines.append("**Run:**")
      for ep in eps:
        lines.append(f"- `{ep}`")
      lines.append("")
    arts = step.get("artifacts", {})
    snaps = arts.get("snapshots", [])
    tbls = arts.get("tables", [])
    if snaps or tbls:
      lines.append("**Artifacts:**")
      if snaps: lines.append(f"- snapshots: {', '.join(snaps)}")
      if tbls: lines.append(f"- tables: {', '.join(tbls)}")
      lines.append("")
  lines.append("## Releases\n")
  for r in tree.get("releases", []):
    lines.append(f"- v{r.get('version')} — {r.get('title','')} ({r.get('roadmap_line','')}) → {r.get('release_doc','')}")
  lines.append("")
  return "\n".join(lines)

def build_tech_guide(tree: dict) -> str:
  lines=[]
  lines.append("# Technical Guide\n")
  lines.append("Developer view: architecture + extension points.\n")
  lines.append("## Source of truth\n- `docs/FEATURE_TREE.yaml`\n")
  lines.append("## Release notes\n- `docs/releases/`\n")
  return "\n".join(lines)

def build_version_history(tree: dict) -> str:
  lines=[]
  lines.append("# Version History\n")
  rels = list(tree.get("releases", []))
  def key(r):
    parts = re.split(r"[.-]", str(r.get("version","0")))
    out=[]
    for p in parts:
      try: out.append(int(p))
      except: out.append(p)
    return out
  rels.sort(key=key)
  for r in rels:
    lines.append(f"- v{r.get('version')} — {r.get('title','')} — {r.get('roadmap_line','')} ({r.get('release_doc','')})")
  lines.append("")
  return "\n".join(lines)

def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--check", action="store_true")
  a = ap.parse_args()
  tree = load_tree()
  targets = {
    DOCS / "USER_MANUAL.md": build_user_manual(tree),
    DOCS / "TECHNICAL_GUIDE.md": build_tech_guide(tree),
    DOCS / "VERSION_HISTORY.md": build_version_history(tree),
  }
  changed=[]
  for p, content in targets.items():
    old = p.read_text(encoding="utf-8") if p.exists() else None
    if old != content:
      changed.append(str(p.relative_to(ROOT)))
      if not a.check:
        write(p, content)
  if a.check and changed:
    raise SystemExit("Docs out of date: " + ", ".join(changed))
  print("ok" if not changed else "updated: " + ", ".join(changed))

if __name__ == "__main__":
  main()
