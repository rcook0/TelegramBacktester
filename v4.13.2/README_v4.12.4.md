# v4.12.4 — Linkage (execution lifecycle mapping)

This release links stitched broker executions (`exec_knit`) to the model trace ENTRY/EXIT lifecycle.

## New store + schema
- `src/storage/sqlite_store_linkage.py` adds:
  - `trade_links`
  - `trade_link_execs`

## New runner
```
python -m src.runners.ctrader_linkage --db ./journal/trader.db --signal-idem-key <KEY> --overwrite
```

## Mechanisms doc
See `docs/MECHANISMS_v4.12.4_linkage.md`.
