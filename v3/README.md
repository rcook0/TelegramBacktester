# cTrader adapters for Vantage & FP Markets

This patch adds a **cTrader Open API** market-data provider, and broker facades for **Vantage** and **FP Markets**.

- Uses Spotware's official Python SDK (`ctrader-open-api`) to pull **historical candles (trendbars)**.
- Normalizes to the backtester schema: `time, open, high, low, close, volume` (UTC).
- Works for *any* broker account that supports cTrader (Vantage, FP Markets, etc.).
- Falls back gracefully if the SDK or credentials are missing.

> Get SDK + docs: `pip install ctrader-open-api` and see https://spotware.github.io/OpenApiPy/ .

## Configure

Copy `.env.example` → `.env` and fill **either** Vantage or FP Markets block (or both).

Required for each broker:
- `*_CTRADER_CLIENT_ID` and `*_CTRADER_CLIENT_SECRET` (register an app with cTrader Open API)
- `*_CTRADER_ACCESS_TOKEN` (OAuth token for the cTID user)
- `*_CTRADER_ACCOUNT_ID` (numeric account id at the broker)
- `*_CTRADER_HOST` = `LIVE` or `DEMO`

## Use

### MT5 unchanged (works today)
```
python -m src.main --data-source mt5 ...
```

### cTrader (Vantage example)
```
python -m src.main   --channel "<channel>"   --since "2024-01-01" --until "2025-10-09"   --data-source ctrader --timeframe M1   --account-ccy USD --deposit 1000 --leverage 500 --lot 0.1   --symbol-map '{"XAU":"XAUUSD"}'   --export results.csv
```

### cTrader (FP Markets example)
```
python -m src.main   --channel "<channel>"   --since "2024-01-01" --until "2025-10-09"   --data-source ctrader --timeframe M5   --account-ccy USD --lot 0.1   --export results_fp.csv
```

## Notes
- The SDK is asynchronous (Twisted). The adapter runs the reactor in a background thread and waits for responses per request.
- cTrader returns trendbars in **relative format**; the adapter reconstructs absolute OHLC using the official formula.
- If you prefer one broker at a time, set `BROKER=VANTAGE` or `BROKER=FPMARKETS` in env and the adapter will pick that block.

