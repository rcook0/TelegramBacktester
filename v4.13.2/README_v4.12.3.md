# v4.12.3 — Knitting (partial-fill stitching)

Adds execution-level stitching by converting fill-level `deal_aligned` into `exec_knit`.

## Run
```
python -m src.runners.ctrader_knit_exec --db ./journal/trader.db --signal-idem-key <KEY> --overwrite
```

## Mechanisms
See `docs/MECHANISMS_v4.12.3_knitting.md`
