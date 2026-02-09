# v4.12.2 — Deal ↔ Signal alignment (fills contextualization)

This release aligns broker executions to the signal window and enriches each execution with market context
(quote/depth nearest-neighbor) so reconciliation can do real “expected vs actual”.

## New artifacts
- `shadow_snapshots(kind='deal_aligned')`: deal_norm + nearest quote/depth + optional depth-WAP estimate

## New runner
```
python -m src.runners.ctrader_align_deals --db ./journal/trader.db --signal-idem-key <KEY> --use-capture-window --overwrite
```

Flags:
- `--pre-sec`, `--post-sec`: fallback window around signal.ts if capture_window is absent
- `--max-gap-ms`: reject quote/depth context if too far from execution_ts
- `--export-json`: export the aligned list for inspection

## Mechanisms doc
See: `docs/MECHANISMS_v4.12.2_deal_alignment.md`
