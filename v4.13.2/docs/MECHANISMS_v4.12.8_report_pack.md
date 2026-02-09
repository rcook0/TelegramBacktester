# v4.12.8 Report Pack — batch summaries

Turns the shadow pipeline into portable artifacts:
- CSV (per-signal rows)
- JSON (summary + rows)
- HTML (static report)

## Runner
```bash
python -m src.runners.report_pack   --db ./journal/trader.db   --since 2026-01-01T00:00:00+00:00   --until 2026-02-01T00:00:00+00:00   --pack shadow_gate_v1 --pack-version 1.0   --out-dir ./reports --out-prefix jan
```
