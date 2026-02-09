# v4.11.7 — Reconciliation v1

This release computes and persists reconciliation diffs between:
- broker shadow snapshots (quotes today; fills later)
- model traces (persisted in v4.11.6)

## What it computes (v1)
Per signal:
- entry delta (pips): nearest broker quote mid vs model entry px
- WAP delta (pips): nearest broker quote mid vs model intended_wap (or entry px)
- spread delta (pips): broker spread_pips vs model assumption spread_pips
- latency delta (ms): proxy |entry_ts - nearest_quote_ts| vs model assumption latency_ms

Notes:
- Broker WAP is approximated using quote mid until real fills/vwap are wired.
- Observed latency is a proxy for time alignment, not true venue latency.

## Run for one signal
```
python -m src.runners.reconcile_run --db ./journal/trader.db --signal-idem-key <KEY>
```

## Run for a range and export a report
```
python -m src.runners.reconcile_report --db ./journal/trader.db --from 2026-01-01T00:00:00+00:00 --to 2026-01-31T23:59:59+00:00
```
