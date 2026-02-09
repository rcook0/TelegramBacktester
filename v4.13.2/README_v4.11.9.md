# v4.11.8 + v4.11.9 — Report generation + thresholds (Shadow Gate)

This release adds two operator-facing tools:

## v4.11.8 — Report generation (Plus)
`reconcile_report_plus` generates:
- full per-signal CSV
- JSON report including:
  - aggregate metrics (mean/median/p95/max of |deltas|)
  - per-symbol breakdown
  - worst offenders tables (by WAP/spread/latency)

Run:
```
python -m src.runners.reconcile_report_plus --db ./journal/trader.db --from ISO --to ISO
```

## v4.11.9 — Threshold scorecard (Shadow Gate)
`reconcile_thresholds` evaluates your reconciliation results against policy thresholds.

Outputs:
- ok/pass boolean
- reasons list (violations)
- thresholds + computed metrics
- per-symbol breakdown

Run with defaults:
```
python -m src.runners.reconcile_thresholds --db ./journal/trader.db --from ISO --to ISO
```

Override thresholds via JSON:
```
python -m src.runners.reconcile_thresholds --db ./journal/trader.db --from ISO --to ISO \
  --thresholds-json '{"max_abs_median_delta_wap_pips":0.6,"min_trades":50}'
```

Persist scorecard into DB:
```
python -m src.runners.reconcile_thresholds --db ./journal/trader.db --from ISO --to ISO --persist
```
