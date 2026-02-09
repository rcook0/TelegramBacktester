# v4.12.3 “Knitting” — Partial-fill stitching mechanisms

## Problem
Orders can fill in multiple parts across price levels and time. Fill-level reconciliation is noisy.
We “knit” fills into an execution-level object so later steps can compare expected vs actual cleanly.

## Inputs
We knit from `shadow_snapshots(kind='deal_aligned')` which already has:
- normalized deal payload (`deal`)
- nearest quote/depth context (`quote_ctx`, `depth_ctx`)
- optional `depth_wap_est` per fill

## Grouping rules (deterministic)
1) **Explicit IDs** (preferred): group by the first present of
   `position_id / order_id / trade_id / execution_id / dealId / id`.
2) **Heuristic clustering** (fallback): cluster by `(symbol, side)` using:
   - a loose time bucket (`bucket_ms`, default 5000ms)
   - merge adjacent fills when the gap between fills ≤ `max_gap_sec` (default 3s)

## Aggregation
For fills i=1..n:
- total_qty = Σ qty_i
- wap_px = (Σ px_i * qty_i) / total_qty
- depth_wap_est_wavg = (Σ depth_wap_est_i * qty_i) / total_qty (when available)

Fees / PnL (when present):
- commission_ccy_sum = Σ commission_ccy
- realized_pnl_ccy_sum = Σ realized_pnl_ccy

## Output
We write `shadow_snapshots(kind='exec_knit')` with:
- `exec_id`, symbol, side
- ts_first/ts_last
- total_qty_lots, wap_px
- fill_count + fills[]
- carried quote/depth context from first fill
- optional aggregates

## Usage
```
python -m src.runners.ctrader_knit_exec --db ./journal/trader.db --signal-idem-key <KEY> --overwrite
```
