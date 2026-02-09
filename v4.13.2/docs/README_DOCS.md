# Docs system

## What it is
- `docs/FEATURE_TREE.yaml` is the source of truth (pipelines + releases).
- `docs/releases/` holds per-version notes (including “why/mechanism/unlocks/caveats”).
- `tools/docs_build.py` generates:
  - `docs/USER_MANUAL.md`
  - `docs/TECHNICAL_GUIDE.md`
  - `docs/VERSION_HISTORY.md`

## Dependency
- `pyyaml` for the generator: `pip install pyyaml`

## Workflow
1) Update `docs/FEATURE_TREE.yaml`
2) Add/update `docs/releases/vX.Y.Z.md`
3) Run: `python tools/docs_build.py`
4) Optional check: `python tools/docs_build.py --check`

## Release helper
- Create a new release note + register it in the feature tree:
  - `python tools/release_new.py X.Y.Z "title" --roadmap-line "..."`
