from __future__ import annotations
import json
from typing import Dict, Any, List, Optional, Tuple
from ..capture.window import parse_iso

def _pip_size_from_ctx(exec_payload: dict) -> Optional[float]:
    # Try quote_ctx then depth_ctx then deal metadata
    q = exec_payload.get("quote_ctx") if isinstance(exec_payload.get("quote_ctx"), dict) else None
    d = exec_payload.get("depth_ctx") if isinstance(exec_payload.get("depth_ctx"), dict) else None
    for obj in (q, d, exec_payload):
        if not isinstance(obj, dict):
            continue
        ps = obj.get("pip_size") or obj.get("pipSize")
        if ps is not None:
            try:
                return float(ps)
            except Exception:
                pass
        pp = obj.get("pip_position") or obj.get("pipPosition")
        if pp is not None:
            try:
                return 10.0 ** (-int(pp))
            except Exception:
                pass
    return None

def _wavg(items: List[Tuple[float,float]]) -> Optional[float]:
    num=0.0; den=0.0
    for px, qty in items:
        if qty <= 0: 
            continue
        num += px * qty
        den += qty
    return (num/den) if den>0 else None

def _extract_trace_window(trace_payload: dict) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    # returns (symbol, side, entry_ts, exit_ts)
    if not isinstance(trace_payload, dict):
        return (None, None, None, None)
    sym = trace_payload.get("symbol")
    side = (trace_payload.get("side") or "").upper()
    events = trace_payload.get("events") or []
    entry = None
    exit_ = None
    for ev in events:
        if not isinstance(ev, dict):
            continue
        k = (ev.get("kind") or "").upper()
        ts = ev.get("ts")
        if not ts:
            continue
        if k == "ENTRY" and entry is None:
            entry = ts
        if k in ("EXIT","SL","TP"):
            exit_ = ts
    return (sym, side, entry, exit_)

def link_execs_to_trace(store,
                        signal_id: int,
                        overwrite: bool = False,
                        entry_tolerance_sec: float = 180.0,
                        exit_tolerance_sec: float = 180.0) -> dict:
    """Create a trade_link by associating stitched executions (exec_knit) to model trace ENTRY/EXIT.

    Mechanism:
    - Fetch latest model trace for signal_id (if present) to get symbol/side and entry/exit timestamps
    - Load exec_knit snapshots for the signal (each is already stitched WAP+qty)
    - Classify each execution as ENTRY or EXIT:
      - if trace side is known: ENTRY matches trace side; EXIT is opposite
      - else: ENTRY are earlier execs; EXIT are later execs (heuristic)
    - Aggregate entry_wap/exit_wap via qty-weighted average across their respective exec sets
    - Compute pnl_pips if pip_size can be derived from context
    - Persist link as:
      - shadow_snapshots(kind='trade_link') for quick inspection
      - trade_links/trade_link_execs tables for structured queries
    """
    cur = store.conn.cursor()

    # overwrite prior
    if overwrite:
        cur.execute("DELETE FROM trade_link_execs WHERE link_id IN (SELECT id FROM trade_links WHERE signal_id=?)", (signal_id,))
        cur.execute("DELETE FROM trade_links WHERE signal_id=?", (signal_id,))
        cur.execute("DELETE FROM shadow_snapshots WHERE signal_id=? AND kind='trade_link'", (signal_id,))
        store.conn.commit()

    trace = store.latest_trace_for_signal(signal_id)
    trace_id = trace["trace_id"] if trace else None
    trace_payload = trace["payload"] if trace else None
    sym, side, entry_ts, exit_ts = _extract_trace_window(trace_payload or {})

    # fetch exec_knit snapshots with ids
    cur.execute("SELECT id, ts, payload FROM shadow_snapshots WHERE signal_id=? AND kind='exec_knit' ORDER BY id ASC", (signal_id,))
    rows = cur.fetchall()
    execs = []
    for sid, ts, payload_s in rows:
        ex = json.loads(payload_s)
        ex["_snapshot_id"] = int(sid)
        ex["_ts_row"] = ts
        execs.append(ex)

    if not execs:
        out = {"ok": False, "reason": "no exec_knit snapshots found", "signal_id": signal_id}
        store.add_shadow_snapshot(signal_id, "trade_link", out, ts=entry_ts or datetime.now(timezone.utc).isoformat())
        store.conn.commit()
        return out

    # derive side if missing
    if side not in ("LONG","SHORT"):
        side = execs[0].get("side") or "LONG"
        side = str(side).upper()
        if side == "BUY": side = "LONG"
        if side == "SELL": side = "SHORT"

    # derive entry/exit ts heuristically if missing
    if entry_ts is None:
        entry_ts = execs[0].get("ts_first") or execs[0].get("ts_last") or execs[0].get("_ts_row")
    if exit_ts is None and len(execs) > 1:
        exit_ts = execs[-1].get("ts_last") or execs[-1].get("ts_first") or execs[-1].get("_ts_row")

    t_entry = parse_iso(entry_ts).timestamp() if entry_ts else None
    t_exit = parse_iso(exit_ts).timestamp() if exit_ts else None

    def classify(ex: dict) -> str:
        ex_side = (ex.get("side") or "").upper()
        if ex_side == "BUY": ex_side = "LONG"
        if ex_side == "SELL": ex_side = "SHORT"
        ts0 = ex.get("ts_first") or ex.get("ts_last") or ex.get("_ts_row")
        try:
            t0 = parse_iso(ts0).timestamp()
        except Exception:
            t0 = None

        if side in ("LONG","SHORT") and ex_side in ("LONG","SHORT"):
            if ex_side == side:
                # near entry window? else treat as scale-in ENTRY still
                if t_entry is None or t0 is None or abs(t0 - t_entry) <= entry_tolerance_sec:
                    return "ENTRY"
                return "ENTRY"
            else:
                if t_exit is None or t0 is None or abs(t0 - t_exit) <= exit_tolerance_sec:
                    return "EXIT"
                return "EXIT"

        # fallback by time
        if t_entry is not None and t0 is not None and t0 <= (t_entry + entry_tolerance_sec):
            return "ENTRY"
        if t_exit is not None and t0 is not None and t0 >= (t_exit - exit_tolerance_sec):
            return "EXIT"
        return "UNKNOWN"

    entry_execs = []
    exit_execs = []
    unknown_execs = []
    for ex in execs:
        role = classify(ex)
        if role == "ENTRY":
            entry_execs.append(ex)
        elif role == "EXIT":
            exit_execs.append(ex)
        else:
            unknown_execs.append(ex)

    # If we got everything as ENTRY (single leg), keep exit empty.
    # If we got everything as EXIT, treat first as ENTRY.
    if entry_execs and not exit_execs and len(execs) > 1:
        # split by median time as heuristic
        mid = len(execs)//2
        entry_execs = execs[:mid]
        exit_execs = execs[mid:]
    if not entry_execs:
        entry_execs = [execs[0]]
        exit_execs = execs[1:]

    # aggregate
    def agg(exs: List[dict]) -> Tuple[Optional[float], float]:
        pairs=[]
        qty_sum=0.0
        for ex in exs:
            px = ex.get("wap_px")
            qty = ex.get("total_qty_lots")
            try:
                px = float(px) if px is not None else None
                qty = float(qty) if qty is not None else None
            except Exception:
                px = None; qty=None
            if px is None or qty is None or qty<=0:
                continue
            pairs.append((px, qty)); qty_sum += qty
        return (_wavg(pairs), qty_sum)

    entry_wap, entry_qty = agg(entry_execs)
    exit_wap, exit_qty = agg(exit_execs) if exit_execs else (None, 0.0)
    qty = min(entry_qty, exit_qty) if exit_qty > 0 else entry_qty

    # pip size for pnl calculation
    pip_size = None
    for ex in entry_execs + exit_execs:
        pip_size = _pip_size_from_ctx(ex)
        if pip_size:
            break

    pnl_pips = None
    if entry_wap is not None and exit_wap is not None and pip_size:
        if side == "LONG":
            pnl_pips = (exit_wap - entry_wap) / pip_size
        else:
            pnl_pips = (entry_wap - exit_wap) / pip_size

    # build exec rows
    exec_rows = []
    for ex in entry_execs:
        exec_rows.append({
            "exec_snapshot_id": ex["_snapshot_id"],
            "exec_id": ex.get("exec_id"),
            "role": "ENTRY",
            "ts_first": ex.get("ts_first"),
            "ts_last": ex.get("ts_last"),
            "qty_lots": ex.get("total_qty_lots"),
            "wap_px": ex.get("wap_px"),
        })
    for ex in exit_execs:
        exec_rows.append({
            "exec_snapshot_id": ex["_snapshot_id"],
            "exec_id": ex.get("exec_id"),
            "role": "EXIT",
            "ts_first": ex.get("ts_first"),
            "ts_last": ex.get("ts_last"),
            "qty_lots": ex.get("total_qty_lots"),
            "wap_px": ex.get("wap_px"),
        })

    summary = dict(
        ok=True,
        signal_id=signal_id,
        trace_id=trace_id,
        symbol=sym or (entry_execs[0].get("symbol") if entry_execs else None),
        side=side,
        entry_ts=entry_ts,
        exit_ts=exit_ts,
        entry_wap=entry_wap,
        exit_wap=exit_wap,
        qty_lots=qty,
        pip_size=pip_size,
        pnl_pips=pnl_pips,
        pnl_ccy=None,
        entry_exec_count=len(entry_execs),
        exit_exec_count=len(exit_execs),
        unknown_exec_count=len(unknown_execs),
        source="linkage_v4.12.4",
    )

    # Persist: structured table + snapshot
    link_id = store.add_trade_link(signal_id, trace_id, summary, exec_rows)
    summary["link_id"] = link_id
    store.add_shadow_snapshot(signal_id, "trade_link", dict(summary=summary, execs=exec_rows), ts=entry_ts or datetime.now(timezone.utc).isoformat())
    store.conn.commit()
    return summary
