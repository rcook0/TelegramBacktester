# v4.11.4 + v4.11.5 — Capture window alignment + symbol normalization

## v4.11.4 — Capture window
The capture runner now persists a `capture_window` snapshot into `shadow_snapshots` so later reconciliation can align:
- start/end timestamps
- pre/post milliseconds
- signal timestamp used

Use:
- `--signal-ts` (optional; defaults to DB signal ts)
- `--pre-ms`, `--post-ms`

## v4.11.5 — Symbol normalization + ID mapping cache
Adds `symbol_resolution` table and `SymbolStore`.
- caches broker `symbolName <-> symbolId` and digits/pipPosition/pipSize where present
- supports alias map via `--symbol-map-json` (JSON string alias->brokerSymbolName)

Example:
```
python -m src.runners.ctrader_shadow_capture \
  --db ./journal/trader.db \
  --signal-idem-key <KEY> \
  --symbols XAUUSD,GBPJPY \
  --symbol-map-json '{"XAUUSD":"XAUUSD.i","GBPJPY":"GBPJPY"}' \
  --mode openapi --env LIVE \
  --client-id ... --client-secret ... --access-token ... --account-id ... \
  --pre-ms 2000 --post-ms 30000 --duration-sec 20 --capture-depth
```
