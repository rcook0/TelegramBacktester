# v4.12.4 Linkage — stitching executions into a trade lifecycle

“Knitting” (v4.12.3) gives you execution objects (`exec_knit`) but you still need *trade lifecycle linkage*:
which executions correspond to the model trace ENTRY and which correspond to EXIT?

This release adds a deterministic “linker” that produces `trade_links`.

## Inputs
- `model_traces` / `model_trace_events` (latest trace per signal)
  - provides `symbol`, `side`, and a sequence of events, including `ENTRY` and `EXIT/TP/SL`
- `shadow_snapshots(kind='exec_knit')`
  - stitched executions: WAP, qty, ts_first/ts_last, plus carried quote/depth context

## 1) Determine trade window
From the latest trace for this `signal_id`:
- entry_ts = first `ENTRY` event
- exit_ts = last of `EXIT/TP/SL` events (if present)

If either timestamp is missing, we fall back to exec timestamps:
- entry_ts = first execution ts
- exit_ts = last execution ts (if more than one exists)

## 2) Classify executions as ENTRY vs EXIT
If trace side exists (`LONG`/`SHORT`):
- ENTRY executions are those whose execution side matches trace side
- EXIT executions are the opposite side

We also apply tolerances (default 180s) to avoid weird mismatches; but in practice
side is the dominant discriminator.

If trace side is missing, we classify by time relative to entry/exit with the same tolerances.

## 3) Aggregate entry/exit WAP and quantity
Across ENTRY executions:
- entry_wap = qty-weighted average of their `wap_px`
- entry_qty = sum of their qty

Across EXIT executions:
- exit_wap / exit_qty similarly

The trade qty is conservatively `min(entry_qty, exit_qty)` when both exist.

## 4) Compute P&L in pips (if pip_size known)
We attempt to derive pip_size from:
- exec.quote_ctx.pip_size / pipPosition, then
- exec.depth_ctx.pip_size / pipPosition

Then:
- LONG pnl_pips = (exit_wap - entry_wap) / pip_size
- SHORT pnl_pips = (entry_wap - exit_wap) / pip_size

Base-currency P&L is left as `None` here because pip-value conversion depends on symbol contract
details and account CCY mapping; that’s pushed to v4.12.5.

## Output artifacts
### Structured tables
- `trade_links` (one row per linked trade lifecycle for the signal)
- `trade_link_execs` (ENTRY/EXIT execution rows attached to trade_links)

### Shadow snapshot
- `shadow_snapshots(kind='trade_link')` for quick inspection / export

## Command
```
python -m src.runners.ctrader_linkage --db ./journal/trader.db --signal-idem-key <KEY> --overwrite
```

## Why this matters
Once you have linked ENTRY and EXIT, you can:
- compute realized slippage vs model
- do per-trade thresholding (Shadow Gate) rather than per-fill noise
- support true dry-run “shadow execution” scoring before sending live orders
