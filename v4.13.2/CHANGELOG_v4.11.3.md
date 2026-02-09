# Changelog — v4.11.3
- Added **real** cTrader Open API capture using Spotware-maintained OpenApiPy (`ctrader-open-api`).
- Connects to official Open API proxies (live/demo) on port 5035 and subscribes to spots (+ optional depth).
- Normalizes spot prices by dividing by 100000 and rounding to digits.
- Runner updated: `--mode openapi|poll` (poll retained as legacy scaffold).
