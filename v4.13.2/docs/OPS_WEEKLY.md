# Weekly Ops (v4.13.0)

The goal: **one command** that you can schedule weekly, producing an auditable report bundle.

## Command
```bash
python -m src.runners.weekly_ops   --db ./journal/trader.db   --channel MySignals   --weeks 1   --pack shadow_gate_v1 --pack-version 1.0   --out-dir ./reports   --retention-days 60
```

## What it does
1. Rotates old `./reports/*.csv|json|html|log` into `./reports/archive/<YYYY-Www>/`.
2. Runs:
   - `reconcile_batch_v3`
   - `threshold_batch_eval`
   - `report_pack`
3. Writes run summaries + artifacts into `ops_runs` + `ops_artifacts` in SQLite.

## Outputs
- `reports/<prefix>.(csv|json|html)`
- `reports/<prefix>_reconcile_summary.json`
- `reports/<prefix>_threshold_summary.json`
- `reports/<prefix>_report_pack.log`
- DB tables: `ops_runs`, `ops_artifacts`

## Scheduling

### Linux (cron)
Run every Monday at 08:00:
```
0 8 * * 1  cd /path/to/project && /usr/bin/python -m src.runners.weekly_ops --db ./journal/trader.db --channel MySignals --weeks 1 --out-dir ./reports >> ./reports/cron.log 2>&1
```

### Windows (Task Scheduler)
- Program: `python`
- Arguments: `-m src.runners.weekly_ops --db .\journal\trader.db --channel MySignals --weeks 1 --out-dir .\reports`
- Start in: project folder

## Notes
- `--overwrite` forces regeneration of recon + thresholds for the window.
- Prefix defaults to: `weekly_<since>_<until>` (UTC dates).
