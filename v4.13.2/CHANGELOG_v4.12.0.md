# Changelog — v4.12.0

- Added `runners/ctrader_deallist_fills.py` to capture execution deals via cTrader Open API DealList.
- Persists executions into `shadow_snapshots` as `kind='deal'`, with `deal_list_meta` and `deal_list_done` markers.
- DealList capture can reuse the existing `capture_window` snapshot from quote/depth capture.
