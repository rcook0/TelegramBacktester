# v4.11.8 — Fills / depth WAP

Upgrades reconciliation WAP logic:
1) Prefer broker **fills** (shadow snapshots kind: `deal` / `fill`) to compute broker WAP.
2) Else estimate WAP by walking **depth** book levels (shadow kind: `depth`) for the model entry qty.
3) Else fallback to quote mid.

This enables meaningful WAP deltas once you ingest deals/fills or capture depth.

## Inputs expected
### Fills/deals (shadow kind `deal` / `fill`)
Each payload should include:
- `ts` (ISO)
- `symbol`
- `px` (or `price`)
- `qty` (or `volume`)

### Depth (shadow kind `depth`)
Payload should include either:
- `bids:[{px,qty},...]` and `asks:[{px,qty},...]`
or
- `bid:[[px,qty],...]` and `ask:[[px,qty],...]`

## Reconciliation output
`reconcile_diffs` now includes `wap_broker_source ∈ {fills, depth, quote_mid}`.

## Ingest fills from CSV (pragmatic)
```
python -m src.runners.ingest_deals_csv --db ./journal/trader.db --signal-idem-key <KEY> --csv fills.csv
```
