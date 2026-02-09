# v4.12.2 Deal ↔ Signal Alignment — Mechanisms

This document explains *how* we attach real broker executions (deals/fills) to a Telegram signal / model run.

## What exists in the DB (recap)
All signal-centric artifacts are stored under the same `signal_id`:
- `signals` — canonical signal record (`idem_key`, `ts`, channel, raw payload)
- `shadow_snapshots` — time series artifacts tied to a signal
  - `quote` — sampled quote snapshots during the capture window
  - `depth` / `depth_book` — depth snapshots/book state during the window
  - `deal` — raw DealList row (authoritative)
  - `deal_norm` — normalized deal view (moneyDigits scaling, volume cents→lots)
  - `capture_window` — optional stored window boundaries for this signal
  - **`deal_aligned` (new)** — enriched deal_norm with nearest context snapshots

## Why alignment is needed
A Telegram “signal” is not an execution. The broker may:
- fill later (latency / routing)
- fill in multiple parts (partial fills)
- fill at prices different from the quote mid (spread + adverse selection)

To reconcile *expected vs actual* we need to map:
- model “ENTRY” event time
- broker executions from DealList (fills)
- market context (quote/depth) at that time

## Alignment algorithm (v4.12.2)
Given a `signal_id`:

### 1) Determine the window `[from,to]`
We choose (in order):
1. If `shadow_snapshots.kind='capture_window'` exists and `--use-capture-window` is enabled, use its boundaries.
2. Else fallback to `signal.ts ± (pre_sec, post_sec)` (defaults: 2s before, 120s after).

### 2) Select candidate executions
We scan `shadow_snapshots.kind='deal_norm'` and keep rows with `execution_ts ∈ [from,to]`.

This handles:
- delayed fills inside the window
- multi-part fills inside the window

### 3) Attach nearest context snapshots
For each candidate deal at time `t_exec`:
- choose nearest `quote` snapshot by timestamp (within `max_gap_ms`, default 5000ms)
- choose nearest `depth/depth_book` snapshot by timestamp (same max gap)

If the nearest snapshot is outside `max_gap_ms`, it is discarded (set to `null`) to avoid misleading context.

### 4) Depth-WAP estimate (optional)
If a depth snapshot exists and deal quantity is known, we compute a *book-walk WAP*:
- LONG (buy) consumes asks
- SHORT (sell) consumes bids

This yields `depth_wap_est` which is a first-order proxy for “what the book would have given” at that moment.
(Important: unit calibration for depth quantities is refined later; this version provides the plumbing.)

### 5) Persist `deal_aligned`
We write `shadow_snapshots(kind='deal_aligned')` with:
- the deal_norm payload (`deal`)
- `quote_ctx`, `depth_ctx`
- `depth_wap_est`
- chosen window boundaries and `max_gap_ms`

## How it’s used downstream
- **Reconciliation WAP**: reconciler now prefers aligned deals first, then raw deals, then depth, then quote mid.
- **Reporting**: report generators can pivot on `deal_aligned` to show slippage under different spread/latency regimes.

## Operational knobs
- `--pre-sec / --post-sec`: widen/narrow the window
- `--max-gap-ms`: how strict we are about matching context snapshots
- `--overwrite`: rebuild alignment idempotently

## Typical workflow
1) capture quote/depth around signal (`ctrader_shadow_capture`)
2) capture fills (`ctrader_deallist_fills`)
3) normalize deals (optional now automatic in 4.12.1)
4) align (`ctrader_align_deals`)
5) reconcile/report/threshold gate

---
If you want “hard mode”: the next increment (4.12.3) is stitching partial fills into *order-level executions* and computing realized P&L in account currency with fees and conversion.
