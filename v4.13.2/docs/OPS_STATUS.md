# Ops Status (v4.13.1)

You wanted a **single summary line** that works in:
- Browser tab (static HTML)
- Dash tab (optional)
- Terminal script (fast)

## Generate status_latest bundle
Run weekly ops with:
```bash
python -m src.runners.weekly_ops   --db ./journal/trader.db   --channel MySignals   --weeks 1   --out-dir ./reports   --write-status-latest
```

This writes:
- `reports/status_latest.json`
- `reports/status_latest.txt`
- `reports/status_latest.html`

## Terminal (glance)
```bash
python -m src.runners.ops_status --db ./journal/trader.db
python -m src.runners.ops_status --db ./journal/trader.db --open
python -m src.runners.ops_status --db ./journal/trader.db --history 10
```

## Dash tab (optional)
Install extras:
```bash
pip install -e ".[dash]"
```
Run:
```bash
python -m src.ui.dash_status_app --reports-dir ./reports
```
Then open: http://127.0.0.1:8050

## Policy knobs
- `--min-pass-rate-pct <float>` (WARN if pass rate drops below)
- `--max-missing-recon <int>` (WARN if missing recon exceeds)

Example:
```bash
python -m src.runners.weekly_ops --db ./journal/trader.db --channel MySignals --weeks 1 --out-dir ./reports --write-status-latest --min-pass-rate-pct 70 --max-missing-recon 5
```
