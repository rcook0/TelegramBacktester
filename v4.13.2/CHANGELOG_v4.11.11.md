# v4.11.11 — Depth book builder (cTrader Open API)

- Added `DepthBookBuilder` to maintain an incremental L2 book from `ProtoOADepthEvent` (`newQuotes` / `deletedQuotes`).
- `ctrader_openapi_capture.py` now builds a top-of-book snapshot (bids/asks, best bid/ask, spread in pips) instead of relying on non-existent `bid[]/ask[]` fields.
- Fixed the `on_message` handler indentation so the capture module is importable/runable.

Notes:
- `ProtoOADepthQuote.size` is in cents (0.01 units). Prices are treated with the standard Open API 1e5 scaling (same as spot quotes).