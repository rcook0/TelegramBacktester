from __future__ import annotations
import json
from typing import Any, Dict, Optional, Tuple, List
from datetime import datetime, timezone

from storage.sqlite_store_traces import TraceStore
from capture.window import parse_iso, nearest_by_ts
from .wap import wap_from_fills, wap_from_depth

def _fetch_shadow_payloads(store: TraceStore, signal_id: int) -> Dict[str, List[dict]]:
    cur = store.conn.cursor()
    cur.execute("SELECT kind, payload FROM shadow_snapshots WHERE signal_id=? ORDER BY ts ASC", (signal_id,))
    out: Dict[str, List[dict]] = {}
    for kind, payload in cur.fetchall():
        out.setdefault(kind, []).append(json.loads(payload))
    return out

def _fetch_latest_trace(store: TraceStore, signal_id: int) -> Optional[dict]:
    t = store.latest_trace_for_signal(signal_id)
    if not t:
        return None
    return t["payload"]

def _first_event(trace_doc: dict, kind: str) -> Optional[dict]:
    for ev in trace_doc.get("events", []):
        if str(ev.get("kind", "")).upper() == kind.upper():
            return ev
    return None

def _pip_size_from_quote(q: dict) -> Optional[float]:
    ps = q.get("pip_size")
    if ps is None:
        return None
    try:
        return float(ps)
    except Exception:
        return None

def _delta_pips(side: str, broker_px: float, model_px: float, pip_size: float) -> float:
    if pip_size <= 0:
        return 0.0
    side = side.upper()
    if side == "LONG":
        return (broker_px - model_px) / pip_size
    return (model_px - broker_px) / pip_size

def reconcile_signal(store: TraceStore, signal_id: int) -> Optional[dict]:
    """Compute reconciliation diff for one signal_id and persist into reconcile_diffs.
    Returns diff payload dict, or None if not enough data.
    """
    shadow = _fetch_shadow_payloads(store, signal_id)
    trace = _fetch_latest_trace(store, signal_id)
    if not trace:
        return None

    entry_ev = _first_event(trace, "ENTRY")
    if not entry_ev:
        return None

    entry_ts = entry_ev.get("ts")
    if not entry_ts:
        return None

    quotes = shadow.get("quote", [])
    nearest_q = nearest_by_ts(quotes, entry_ts) if quotes else None
    if not nearest_q:
        return None

    side = str(trace.get("side", "LONG")).upper()
    symbol = str(trace.get("symbol", nearest_q.get("symbol", "")))

    entry_px_model = float(entry_ev.get("px")) if entry_ev.get("px") is not None else None
    entry_px_broker = float(nearest_q.get("mid") or 0.0)
    spread_broker_pips = float(nearest_q.get("spread_pips") or 0.0)

    assumptions = trace.get("assumptions", {}) or {}
    spread_model_pips = assumptions.get("spread_pips")
    latency_ms_model = assumptions.get("latency_ms")

    pip_size = _pip_size_from_quote(nearest_q) or assumptions.get("pip_size")
    if pip_size is None:
        # fallback: infer from pip_position/digits if present, else 0.0
        pip_pos = nearest_q.get("pip_position")
        if pip_pos is not None:
            try:
                pip_size = 10.0 ** (-int(pip_pos))
            except Exception:
                pip_size = 0.0
        else:
            pip_size = 0.0

    # WAP: if simulator recorded intended_wap, use it; otherwise use entry px
    wap_model = None
    try:
        if isinstance(entry_ev.get("meta", {}), dict) and entry_ev["meta"].get("intended_wap") is not None:
            wap_model = float(entry_ev["meta"]["intended_wap"])
    except Exception:
        pass
    if wap_model is None and entry_px_model is not None:
        wap_model = float(entry_px_model)

    wap_broker = None
    wap_broker_source = None

    # 1) Prefer aligned deals (shadow kind: 'deal_aligned') if present near entry.
    for da in shadow.get('deal_aligned', []):
        dd = (da.get('deal') if isinstance(da, dict) else None)
        if not isinstance(dd, dict):
            continue
        sym_ok = (str(dd.get('symbol','')) == symbol) if dd.get('symbol') else True
        if not sym_ok:
            continue
        try:
            dt = abs(parse_iso(dd.get('execution_ts', entry_ts)).timestamp() - parse_iso(entry_ts).timestamp())
            if dt > 120:
                continue
        except Exception:
            pass
        px = dd.get('execution_px') or dd.get('px') or dd.get('price')
        qty = dd.get('filled_volume_lots') or dd.get('volume_lots') or dd.get('qty')
        if px is None or qty is None:
            continue
        fills.append({'px': px, 'qty': qty, 'ts': dd.get('execution_ts')})

    # 2) Prefer real fills (shadow kind: 'deal' or 'fill') if present near entry.
    fills = []
    for k in ("deal", "fill", "fills"):
        for f in shadow.get(k, []):
            # normalize to {px, qty, ts, symbol}
            sym_ok = (str(f.get('symbol','')) == symbol) if f.get('symbol') else True
            if not sym_ok:
                continue
            # time window: +/- 120s around entry
            try:
                dt = abs(parse_iso(f.get('ts', entry_ts)).timestamp() - parse_iso(entry_ts).timestamp())
                if dt > 120:
                    continue
            except Exception:
                pass
            px = f.get('px') or f.get('price')
            qty = f.get('qty') or f.get('volume') or f.get('filled_qty')
            if px is None or qty is None:
                continue
            fills.append({'px': px, 'qty': qty, 'ts': f.get('ts')})

    wap = wap_from_fills(fills)
    if wap is not None:
        wap_broker = float(wap)
        wap_broker_source = 'fills'

    # 2) Else use depth book to estimate WAP for the model entry qty.
    if wap_broker is None:
        depth_items = shadow.get('depth', [])
        nearest_depth = nearest_by_ts(depth_items, entry_ts) if depth_items else None
        qty_model = entry_ev.get('qty')
        try:
            qty_model = float(qty_model) if qty_model is not None else None
        except Exception:
            qty_model = None
        if nearest_depth is not None and qty_model is not None:
            wapd = wap_from_depth(nearest_depth, qty_model, side)
            if wapd is not None:
                wap_broker = float(wapd)
                wap_broker_source = 'depth'

    # 3) Fallback: quote mid
    if wap_broker is None:
        wap_broker = float(entry_px_broker)
        wap_broker_source = 'quote_mid'

    delta_entry_pips = None
    delta_wap_pips = None
    if entry_px_model is not None and pip_size and pip_size > 0:
        delta_entry_pips = _delta_pips(side, entry_px_broker, float(entry_px_model), float(pip_size))
    if wap_model is not None and pip_size and pip_size > 0:
        delta_wap_pips = _delta_pips(side, float(wap_broker), float(wap_model), float(pip_size))

    # Observed latency proxy: time distance between entry event ts and nearest quote ts
    latency_ms_obs = None
    delta_latency_ms = None
    try:
        t_entry = parse_iso(entry_ts).timestamp()
        t_quote = parse_iso(nearest_q.get("ts")).timestamp()
        latency_ms_obs = abs(t_quote - t_entry) * 1000.0
        if latency_ms_model is not None:
            delta_latency_ms = float(latency_ms_obs) - float(latency_ms_model)
    except Exception:
        pass

    diff = {
        "idem_key": trace.get("idem_key"),
        "symbol": symbol,
        "side": side,
        "entry_ts": entry_ts,
        "entry_px_model": entry_px_model,
        "entry_px_broker": entry_px_broker,
        "delta_entry_pips": delta_entry_pips,
        "wap_model": wap_model,
        "wap_broker": wap_broker,
        "delta_wap_pips": delta_wap_pips,
        "spread_model_pips": spread_model_pips,
        "spread_broker_pips": spread_broker_pips,
        "delta_spread_pips": (float(spread_broker_pips) - float(spread_model_pips)) if spread_model_pips is not None else None,
        "latency_ms_model": latency_ms_model,
        "latency_ms_obs": latency_ms_obs,
        "delta_latency_ms": delta_latency_ms,
        "quote_used_ts": nearest_q.get("ts"),
        "quote_used_mid": nearest_q.get("mid"),
        "source": "reconcile-v1",
        "notes": [
            "Broker WAP approximated by nearest quote mid (fills not yet wired).",
            "Latency observed is proxy: |entry_ts - nearest_quote_ts|."
        ]
    }

    store.add_reconcile_diff(signal_id, diff, ts=entry_ts)
    return diff

def reconcile_range(store: TraceStore, ts_from: str, ts_to: str) -> List[dict]:
    cur = store.conn.cursor()
    cur.execute("SELECT id FROM signals WHERE ts >= ? AND ts <= ? ORDER BY ts ASC", (ts_from, ts_to))
    out = []
    for (sid,) in cur.fetchall():
        d = reconcile_signal(store, int(sid))
        if d: out.append(d)
    return out
