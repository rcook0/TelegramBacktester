#!/usr/bin/env python3
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT / "docs" / "releases"
VER_RE = re.compile(r"v(\d+\.\d+\.\d+)", re.I)

def main():
  rels = sorted([p for p in REL.glob("v*.md") if p.is_file()])
  found=[]
  for p in rels:
    m = VER_RE.search(p.stem)
    if m: found.append(m.group(1))
  print("found:", ", ".join(found) if found else "(none)")
  print("tip: keep one release note per shipped version under docs/releases/")

if __name__ == "__main__":
  main()
