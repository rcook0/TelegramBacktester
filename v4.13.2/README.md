# Telegram FX Backtester — v4.12.0

This workspace contains the v4.11+ **shadow parity & reconciliation** tooling plus the v4.12 **DealList fills capture** runner.

Start here:
- `README_v4.12.0.md` (DealList runner + examples)

Versioned notes:
- `CHANGELOG_v4.12.0.md`


## v4.12.4 linkage
- Link stitched executions to model trace lifecycle:
  - `python -m src.runners.ctrader_linkage --db ./journal/trader.db --signal-idem-key <KEY> --overwrite`

## Documentation (generated manuals)
- Source of truth: `docs/FEATURE_TREE.yaml`
- Release notes: `docs/releases/vX.Y.Z.md`
- Build manuals: `python tools/docs_build.py` (requires `pyyaml`)

- Release helper: `python tools/release_new.py X.Y.Z "title" --roadmap-line "..."`

## v4.12.5 P&L attribution
- `python -m src.runners.pnl_attrib --db ./journal/trader.db --signal-idem-key <KEY> --account-ccy USD --rates-json '{"EURUSD":1.08}' --overwrite`

## v4.12.6 Reconciliation v3
- `python -m src.runners.reconcile_v3 --db ./journal/trader.db --signal-idem-key <KEY> --overwrite`

## v4.12.7 Threshold packs (Shadow Gate)
- `python -m src.runners.threshold_eval --db ./journal/trader.db --signal-idem-key <KEY> --pack shadow_gate_v1 --pack-version 1.0 --overwrite`

## v4.12.8 Report pack
- `python -m src.runners.report_pack --db ./journal/trader.db --since ... --until ... --out-dir ./reports --out-prefix report`

## v4.12.9 Batch eval
- `python -m src.runners.shadow_batch_pipeline --db ./journal/trader.db --since ... --until ... --channel ... --out-dir ./reports --out-prefix window`

## v4.13.0 Weekly ops
- `python -m src.runners.weekly_ops --db ./journal/trader.db --channel <NAME> --weeks 1 --out-dir ./reports`
- see `docs/OPS_WEEKLY.md`

## v4.13.1 Ops status line
- Generate: `python -m src.runners.weekly_ops --db ./journal/trader.db --channel <NAME> --weeks 1 --out-dir ./reports --write-status-latest`
- Glance: `python -m src.runners.ops_status --db ./journal/trader.db --open`
- Docs: `docs/OPS_STATUS.md`

## v4.13.2 Ops policy polish
- `python -m src.runners.weekly_ops --db ./journal/trader.db --channel <NAME> --weeks 1 --out-dir ./reports --write-status-latest --min-pass-rate-pct 70 --max-missing-recon 5`
