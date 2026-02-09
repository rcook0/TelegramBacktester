# Changelog — v4.12.1
- Added `symbol_meta` cache table + upsert/get helpers in SymbolStore.
- Added deal normalization module:
  - moneyDigits scaling
  - volume cents -> lots
  - realized_pnl_ccy convenience
- Updated DealList fills capture to persist normalized `deal_norm` alongside raw `deal`.
- Added batch normalization runner.
