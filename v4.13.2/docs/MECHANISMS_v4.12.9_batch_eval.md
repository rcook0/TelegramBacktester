# v4.12.9 Batch eval (reconcile + thresholds)

Adds windowed execution so you can run weeks/months of data without per-signal commands.

## Entrypoints
- `python -m src.runners.reconcile_batch_v3 ...`
- `python -m src.runners.threshold_batch_eval ...`
- `python -m src.runners.shadow_batch_pipeline ...`

## Idempotency
- Skips signals that already have outputs unless `--overwrite`.
- Emits a JSON run summary to stdout; optionally `--emit-json <path>`.

## Typical flow
```bash
python -m src.runners.reconcile_batch_v3 --db ./journal/trader.db --since ... --until ... --channel ...
python -m src.runners.threshold_batch_eval --db ./journal/trader.db --since ... --until ... --channel ...
python -m src.runners.report_pack --db ./journal/trader.db --since ... --until ... --channel ... --out-dir ./reports --out-prefix window
```

Or one-shot:
```bash
python -m src.runners.shadow_batch_pipeline --db ./journal/trader.db --since ... --until ... --channel ... --out-dir ./reports --out-prefix window
```
