# Changelog — v4.11.7
- Added `src/reconcile/reconciler.py` to compute reconciliation diffs and persist into `reconcile_diffs`.
- Added runners:
  - `reconcile_run` (single or range)
  - `reconcile_report` (CSV + JSON summary)
- Uses capture-window alignment helper (`nearest_by_ts`) for quote selection.
