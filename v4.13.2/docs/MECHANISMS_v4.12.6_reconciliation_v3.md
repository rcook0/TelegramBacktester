# v4.12.6 Reconciliation v3 — expected vs actual at trade-link level

This step produces a **deterministic diff** between:
- **Model intent** (trace events)
- **Execution reality** (trade_links, i.e. stitched+linked broker executions)

## Outputs
- `trade_recon_v3` table row
- `shadow_snapshots(kind='recon_v3')` JSON

## Slippage sign convention
Positive slippage = **adverse**.

LONG:
- entry_slip = (actual_entry_wap - expected_entry_px) / pip_size
- exit_slip  = (expected_exit_px - actual_exit_wap) / pip_size

SHORT:
- entry_slip = (expected_entry_px - actual_entry_wap) / pip_size
- exit_slip  = (actual_exit_wap - expected_exit_px) / pip_size

total_slip = entry_slip + exit_slip

## Taxonomy
status: OK / WARN / ERROR
code: OK, SIDE_MISMATCH, SLIP_WARN, SLIP_TOO_LARGE, MISSING_TRACE, MISSING_TRADE_LINK, MISSING_EXPECTED_PX, MISSING_ACTUAL_WAP, MISSING_PIP_SIZE

Thresholding policy is v4.12.7; v4.12.6 computes + classifies.

## Runner
```bash
python -m src.runners.reconcile_v3   --db ./journal/trader.db   --signal-idem-key <KEY>   --slip-warn-pips 1   --slip-error-pips 5   --overwrite
```
