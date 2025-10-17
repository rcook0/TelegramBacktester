# Telegram FX Signal Backtester (v2)

Operational blueprint to ingest Telegram messages, parse FX signals, pull market data from a broker or CSV, and backtest with leverage & margin analytics.

## Core Features
- Telethon login and channel history fetch (name or ID).
- Signal parser for `BUY/SELL <SYMBOL> @ <entry> SL <price> TP1 <price> TP2 <price> ...`.
- Backtest engine:
  - Entry at next candle open; slippage configurable.
  - Exit modes: `first_target`, `multi_tp`, `multi_tp_scaled` (weighted), optional time stop via `--time-stop-min`.
  - Spread-aware level-touch logic.
  - Fixed-lot or **risk-%** position sizing from SL distance.
  - P&L in pips and account currency; commission per lot; margin usage from lot/leverage.
- Data adapters:
  - **MetaTrader 5** (requires installed MT5 and logged-in account; e.g., Vantage, FP Markets).
  - **CSV** fallback (`data/SYMBOL.csv`).
  - **Parquet cache** to accelerate repeated runs.

## Install
1. Python 3.10+
2. `pip install -r requirements.txt`
3. Create Telegram API credentials at https://my.telegram.org and fill `.env` (copy from `.env.example`).

## Run
```
python -m src.main   --channel "<channel_name_or_id>"   --since "2024-01-01" --until "2025-10-09"   --data-source mt5 --timeframe M1 --cache   --risk-pct 1.0 --leverage 500 --deposit 1000   --exit multi_tp_scaled --tp-weights "0.5,0.3,0.2"   --spread-pips 1.5 --slippage-pips 0.2 --commission-per-lot 7   --symbol-map '{"GOLD":"XAUUSD","US30":"US30"}'
```
If you prefer CSV, place `data/EURUSD.csv` etc. with columns: `time,open,high,low,close,volume` (UTC ISO8601).

## Notes
- **Risk-% sizing**: computes lot from (equity * risk%) / (SL distance × pip value per lot).
- **Spread**: Applied as half-spread to TP/SL checks assuming mid candles.
- **Commissions**: Deducted per lot from P&L.
- **Mac ARM**: MT5 Python may be unavailable; use CSV.
