# v4.12.1 — Deal normalization + symbol metadata caching

This release turns raw DealList rows into *usable numbers* and avoids re-fetching symbol metadata repeatedly.

## What’s new
### 1) Symbol metadata caching
`SymbolStore` now includes a `symbol_meta` table keyed by `(broker, account_id, symbol_id)`.
We cache (when available from `ProtoOASymbolsListRes`):
- digits, pipPosition, pipSize
- lotSize/minVolume/maxVolume/stepVolume (in cents)
- measurementUnits

### 2) Deal normalization
New module: `src/normalize/ctrader_deals.py`
- `volume_cents → volume_lots` via `/100`
- monetary values scaled via `moneyDigits`:
  - `commission_ccy`
  - `close_position_detail_norm.*_ccy`
  - `realized_pnl_ccy` convenience

### 3) DealList capture persists both:
- `shadow_snapshots(kind='deal')` raw authoritative payload
- `shadow_snapshots(kind='deal_norm')` normalized view

## Batch normalize existing data
If you captured deals before this version:
```
python -m src.runners.ctrader_normalize_deals --db ./journal/trader.db --signal-idem-key <KEY> --overwrite
```
