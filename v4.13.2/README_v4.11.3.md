# v4.11.3 — Wire real cTrader Open API endpoints

This release replaces the fake "REST-ish" capture assumption with **real cTrader Open API** wiring:

- Uses Spotware Open API **Protobuf over TCP/TLS** on port **5035**.
- Endpoints (global): `live.ctraderapi.com:5035` and `demo.ctraderapi.com:5035`.
- Auth flow: Application Auth -> Account Auth -> Symbols List -> Subscribe spots/depth.
- Quote scaling: `ProtoOASpotEvent.bid/ask` are relative; **divide by 100000** and round to symbol digits.

## Install deps (optional)
The Open API capture path is optional and only required for live capture:
```
pip install ctrader-open-api twisted
```

## Run capture (real Open API)
```
python -m src.runners.ctrader_shadow_capture \
  --db ./journal/trader.db \
  --signal-idem-key <KEY> \
  --symbols XAUUSD,GBPJPY \
  --mode openapi \
  --env LIVE \
  --client-id  <APP_CLIENT_ID> \
  --client-secret <APP_SECRET> \
  --access-token <ACCESS_TOKEN> \
  --account-id <CTID_TRADER_ACCOUNT_ID> \
  --duration-sec 20 \
  --capture-depth
```

### Where these come from
- You register an Open API app and obtain client-id/secret.
- You obtain accessToken + accountId from Spotware Open API portal/playground.
- For demo accounts, use `--env DEMO` and demo credentials.

## Code
- `src/capture/ctrader_openapi_capture.py` — real Open API capture implementation.
- `src/runners/ctrader_shadow_capture.py` — unified runner with `--mode openapi|poll`.
