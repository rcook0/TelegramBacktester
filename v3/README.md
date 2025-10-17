# Adapters Pack (Full): Vantage FIX + cTrader Live Spreads

This pack replaces the stubs with **working implementations**:

1) **Vantage FIX Market Data provider** (QuickFIX, FIX 4.4) that:
   - logs on using Username/Password on Logon
   - subscribes via **MarketDataRequest (V)** for **BID/OFFER**
   - parses **Snapshot/Incremental** into ticks
   - exposes a Python API to drain ticks
   - includes a **recorder** to write per-symbol Parquet
   - includes a **candle builder** to resample ticks → OHLCV CSV

2) **cTrader Live Spread recorder** (Spotware Open API):
   - authenticates app + account
   - subscribes to spots
   - computes **spread in pips** and aggregates per-minute
   - provides an **annotator** to merge spreads into existing OHLC CSVs

> You’ll need `quickfix` and `ctrader-open-api` installed in your runtime.
