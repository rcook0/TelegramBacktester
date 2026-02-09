# v4.11.2 — cTrader capture (read-only)

Adds a **read-only capture scaffold** that persists broker quotes (and optionally depth) into `shadow_snapshots`.

## Typical workflow
1) Ingest Telegram signals into the SQLite DB (creates `signals.idem_key`).
2) Capture around a specific signal:
```bash
python -m src.runners.ctrader_shadow_capture       --db ./journal/trader.db       --signal-idem-key <KEY>       --symbols XAUUSD,GBPJPY       --access-token $CTRADER_ACCESS_TOKEN       --base-url https://<your-gateway>       --duration-sec 20       --capture-depth
```

## Wiring note
`CTraderCapture.fetch_quote()` and `fetch_depth()` are placeholders. You map your broker's cTrader gateway endpoints into the standardized payloads stored in SQLite.
