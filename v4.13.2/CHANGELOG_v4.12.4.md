# Changelog — v4.12.4
- Added trade linkage engine: `src/reconcile/linkage.py`
- Added LinkageStore + schema: `src/storage/sqlite_store_linkage.py` (trade_links, trade_link_execs)
- Added runner: `src/runners/ctrader_linkage.py`
- Persists linkage summary as `shadow_snapshots(kind='trade_link')`
- Added mechanisms doc: `docs/MECHANISMS_v4.12.4_linkage.md`
