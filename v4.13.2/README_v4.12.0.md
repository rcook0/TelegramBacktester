# v4.12.0 — DealList fills capture

Adds `src/runners/ctrader_deallist_fills.py` to pull DealList executions from cTrader Open API and persist them into `shadow_snapshots` as `kind='deal'`.

## Run
Recommended: reuse the capture window from `ctrader_shadow_capture.py`.

```bash
PYTHONPATH=src python -m runners.ctrader_deallist_fills \
  --db ./db/shadow.sqlite \
  --signal-idem-key <IDEM_KEY> \
  --use-capture-window \
  --env LIVE \
  --client-id <CLIENT_ID> \
  --client-secret <CLIENT_SECRET> \
  --access-token <ACCESS_TOKEN> \
  --account-id <CTID_TRADER_ACCOUNT_ID>
```

If you want an explicit window instead of the stored `capture_window` snapshot:

```bash
PYTHONPATH=src python -m runners.ctrader_deallist_fills \
  --db ./db/shadow.sqlite \
  --signal-idem-key <IDEM_KEY> \
  --from 2026-01-30T07:00:00Z \
  --to   2026-01-30T07:01:00Z \
  --env LIVE \
  --client-id <CLIENT_ID> \
  --client-secret <CLIENT_SECRET> \
  --access-token <ACCESS_TOKEN> \
  --account-id <CTID_TRADER_ACCOUNT_ID>
```
