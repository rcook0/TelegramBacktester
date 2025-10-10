# Telegram FX Signal Backtester (MVP)

Operational blueprint to ingest Telegram channel messages, parse FX trading signals, pull market data from a preferred broker or CSV, and backtest P&L with leverage & margin analytics.

## Features
- Login to Telegram via **Telethon** (API ID/HASH + local session file).
- Target a channel by name or ID; fetch history in a date range.
- Parse common signal formats (BUY/SELL, entry, SL, TP1..TP4).
- Configurable **lot size**, **deposit**, **leverage**, and symbol mapping.
- Broker data adapters:
  - **MetaTrader 5** (optional, requires installed MT5 terminal + logged account).
  - **CSV** fallback (drop candles in `data/`).
- Backtest engine:
  - Entry at signal price (or first market candle after signal time).
  - Exit at first hit among TP levels or SL; supports multiple TPs (partial scaling) or single target mode.
  - Per-trade P&L in pips and account currency.
  - Margin used given leverage & contract size.
  - Equity curve, drawdown, win rate, profit factor, and exposure stats.
- Export to CSV; plots (equity curve).

## Quickstart
1. **Python 3.10+** recommended.
2. `pip install -r requirements.txt`
3. Get Telegram credentials:
   - Create app at https://my.telegram.org -> API ID + API HASH.
4. Copy `.env.example` to `.env` and fill values.
5. Put your CSV data (if not using MT5) in `data/` as `{SYMBOL}.csv` with columns:
   `time,open,high,low,close,volume` (UTC ISO8601). Example: `EURUSD.csv`.
6. Run:  
   `python -m src.main --channel "your_channel_name" --since "2024-01-01" --until "2025-10-09" --lot 0.1 --deposit 1000 --leverage 500 --exit multi_tp`

## Notes
- **Security:** Your Telegram session is stored locally as `telegram.session`. Keep it private.
- **Leverage:** Affects required margin, **not** raw P&L. We still report both.
- **MT5:** Install terminal + logged-in broker account (e.g., Vantage, FP Markets).

## CLI
```
python -m src.main   --channel "channel_name_or_id"   --since "2024-01-01" --until "2025-10-09"   --lot 0.1 --deposit 1000 --leverage 500   --exit multi_tp   --symbol-map '{"XAUUSD":"XAUUSD"}'   --data-source mt5  # or csv
```
