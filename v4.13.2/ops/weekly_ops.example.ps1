$DB = ".\journal\trader.db"
$CHANNEL = "MySignals"
$OUT = ".\reports"

python -m src.runners.weekly_ops `
  --db $DB `
  --channel $CHANNEL `
  --weeks 1 `
  --pack shadow_gate_v1 --pack-version 1.0 `
  --out-dir $OUT `
  --retention-days 60
