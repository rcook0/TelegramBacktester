# v4.12.7 Threshold Packs — Shadow Gate inputs

Policy layer on top of:
- v4.12.5 `pnl_attrib`
- v4.12.6 `recon_v3`

## Output contract
- status: PASS/FAIL
- score: 0..1
- violations[]: (rule_id, severity, metric, expected, actual, weight)

## Storage
- `threshold_packs` (versioned pack payloads)
- `signal_threshold_eval` (eval results)
- `shadow_snapshots(kind='threshold_eval')` (auditable JSON)

## Pack model
Rules are metric comparisons with severities and weights:
- metric path: e.g. `recon.total_slip_pips`
- op: <=, >=, <, >, ==, !=, exists
- optional when: `<path> exists`

Scoring: weighted penalty with warn/error penalties and pass_score.

## Runner
```bash
python -m src.runners.threshold_eval   --db ./journal/trader.db   --signal-idem-key <KEY>   --pack shadow_gate_v1   --pack-version 1.0   --overwrite
```
