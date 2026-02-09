# Changelog — v4.12.3
- Added knitting engine: `src/reconcile/deal_knit.py`
- Added runner: `src/runners/ctrader_knit_exec.py`
- Persists stitched executions as `shadow_snapshots(kind='exec_knit')`
- Reconciler now prefers `exec_knit` for broker WAP before deal_aligned/raw deals/depth/quote mid.
- Added mechanisms doc: `docs/MECHANISMS_v4.12.3_knitting.md`
