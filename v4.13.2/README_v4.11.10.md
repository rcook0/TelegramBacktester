# v4.11.10 — Capture hardening

This release makes long-running cTrader capture survivable.

## Features
- **Poison pill guard**: malformed messages won't crash the capture loop.
- **Backpressure smoothing**: coalesces high-frequency quote/depth updates and flushes at a fixed interval.
  - Emits only the latest quote/depth per symbol each flush tick.
  - Throttles depth per symbol (default 5 Hz) to avoid DB/stdout bottlenecks.
- **Auto reconnect** (best-effort): on disconnect, attempts to restart capture with exponential backoff.
- **SQLite maintenance** runner: WAL checkpoint + optional VACUUM/ANALYZE.

## Flags (Open API capture)
```
--flush-interval-sec 0.2
--max-depth-hz-per-symbol 5
--drop-depth-under-pressure
--no-reconnect
--reconnect-backoff-sec 2
--max-reconnect-backoff-sec 30
```

## DB maintenance
```
python -m src.runners.db_maintenance --db ./journal/trader.db --wal-checkpoint TRUNCATE --vacuum --analyze
```
