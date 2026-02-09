# Changelog — v4.11.8
- Added `src/reconcile/wap.py`:
  - `wap_from_fills()`
  - `wap_from_depth()` (consumes book levels to estimate WAP)
- Reconciliation now prefers:
  1) fills/deals → broker WAP
  2) depth book → estimated WAP for model qty
  3) quote mid fallback
- Added `ingest_deals_csv` runner to load fills into `shadow_snapshots` for reconciliation.
