from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Optional, Tuple
from ..capture.window import parse_iso

TAXONOMY = {
  "OK": "reconciled",
  "MISSING_TRACE": "no model trace for signal",
  "MISSING_TRADE_LINK": "no trade link for signal",
  "MISSING_EXPECTED_PX": "trace missing expected entry/exit price",
  "MISSING_ACTUAL_WAP": "trade_link missing entry/exit WAP",
  "MISSING_PIP_SIZE": "no pip_size available",
  "SIDE_MISMATCH": "trace side vs trade_link side mismatch",
  "SLIP_WARN": "slippage above warn threshold",
  "SLIP_TOO_LARGE": "slippage above error threshold",
}

def _safe_float(x) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None

def _event_px(ev: dict) -> Optional[float]:
    if not isinstance(ev, dict):
        return None
    for k in ("px","price","entry","exit","fill_px"):
        v = _safe_float(ev.get(k))
        if v is not None:
            return v
    return None

def _extract_trace_expectations(trace_payload: dict) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[float], Optional[float]]:
    if not isinstance(trace_payload, dict):
        return (None, None, None, None, None, None)
    sym = trace_payload.get("symbol")
    side = (trace_payload.get("side") or "").upper()
    events = trace_payload.get("events") or []
    entry_ts=None; exit_ts=None; entry_px=None; exit_px=None
    for ev in events:
        if not isinstance(ev, dict):
            continue
        k = (ev.get("kind") or "").upper()
        ts = ev.get("ts")
        if k == "ENTRY" and entry_ts is None:
            entry_ts = ts
            entry_px = _event_px(ev)
        if k in ("EXIT","TP","SL"):
            exit_ts = ts
            px = _event_px(ev)
            if px is not None:
                exit_px = px
    return (sym, side, entry_ts, exit_ts, entry_px, exit_px)

def _slippage_pips(side: str, expected_px: float, actual_px: float, pip_size: float, leg: str) -> float:
    side = side.upper()
    if side in ("LONG","BUY"):
        return (actual_px - expected_px)/pip_size if leg=="ENTRY" else (expected_px - actual_px)/pip_size
    else:
        return (expected_px - actual_px)/pip_size if leg=="ENTRY" else (actual_px - expected_px)/pip_size

def _latency_sec(expected_ts: Optional[str], actual_ts: Optional[str]) -> Optional[float]:
    if not expected_ts or not actual_ts:
        return None
    try:
        return parse_iso(actual_ts).timestamp() - parse_iso(expected_ts).timestamp()
    except Exception:
        return None

def _mk_error(signal_id: int, link_id: Optional[int], status: str, code: str, trace_id: Optional[int]=None) -> dict:
    return {
        "trade_link_id": link_id,
        "signal_id": int(signal_id),
        "trace_id": trace_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "code": code,
        "symbol": None,
        "side": None,
        "pip_size": None,
        "taxonomy": TAXONOMY,
        "source": "reconcile_v3_v4.12.6",
        "note": TAXONOMY.get(code),
    }

def reconcile_signal(store, signal_id: int, overwrite: bool=False, slip_warn_pips: float=1.0, slip_error_pips: float=5.0) -> dict:
    cur = store.conn.cursor()
    cur.execute("SELECT id, symbol, side, entry_ts, exit_ts, entry_wap, exit_wap, pnl_pips, pnl_ccy, payload FROM trade_links WHERE signal_id=? ORDER BY id DESC LIMIT 1", (signal_id,))
    tl = cur.fetchone()
    if not tl:
        return _mk_error(signal_id, None, "ERROR", "MISSING_TRADE_LINK")
    link_id, sym_a, side_a, a_entry_ts, a_exit_ts, a_entry_wap, a_exit_wap, pnl_pips, pnl_ccy, tl_payload = tl

    trace = store.latest_trace_for_signal(signal_id)
    if not trace:
        rec = _mk_error(signal_id, int(link_id), "ERROR", "MISSING_TRACE")
        rec.update({"symbol": sym_a, "side": side_a})
        return rec

    trace_id = trace.get("trace_id")
    tp = trace.get("payload") or {}
    sym_e, side_e, e_entry_ts, e_exit_ts, e_entry_px, e_exit_px = _extract_trace_expectations(tp)

    status="OK"; code="OK"
    if side_e and side_a and str(side_e).upper() != str(side_a).upper():
        status="WARN"; code="SIDE_MISMATCH"

    # pip size
    pip_size=None
    try:
        payload = json.loads(tl_payload) if tl_payload else {}
    except Exception:
        payload = {}
    pip_size = _safe_float(payload.get("pip_size"))
    if pip_size is None:
        meta = store.get_symbol_meta(sym_a)
        if isinstance(meta, dict):
            pip_size = _safe_float(meta.get("pipSize") or meta.get("pip_size"))
            if pip_size is None and meta.get("pipPosition") is not None:
                try:
                    pip_size = 10.0 ** (-int(meta.get("pipPosition")))
                except Exception:
                    pip_size = None

    if e_entry_px is None or e_exit_px is None:
        rec=_mk_error(signal_id, int(link_id), "ERROR", "MISSING_EXPECTED_PX", trace_id=trace_id)
        rec.update({"symbol": sym_a, "side": side_a, "expected_entry_ts": e_entry_ts, "expected_exit_ts": e_exit_ts})
        return rec
    if a_entry_wap is None or a_exit_wap is None:
        rec=_mk_error(signal_id, int(link_id), "ERROR", "MISSING_ACTUAL_WAP", trace_id=trace_id)
        rec.update({"symbol": sym_a, "side": side_a})
        return rec
    if pip_size is None or pip_size <= 0:
        rec=_mk_error(signal_id, int(link_id), "ERROR", "MISSING_PIP_SIZE", trace_id=trace_id)
        rec.update({"symbol": sym_a, "side": side_a})
        return rec

    entry_slip=_slippage_pips(side_a, float(e_entry_px), float(a_entry_wap), float(pip_size), "ENTRY")
    exit_slip=_slippage_pips(side_a, float(e_exit_px), float(a_exit_wap), float(pip_size), "EXIT")
    total_slip=entry_slip+exit_slip

    abs_total=abs(total_slip)
    if abs_total >= slip_error_pips:
        status="ERROR"; code="SLIP_TOO_LARGE"
    elif abs_total >= slip_warn_pips and status=="OK":
        status="WARN"; code="SLIP_WARN"

    return {
        "trade_link_id": int(link_id),
        "signal_id": int(signal_id),
        "trace_id": int(trace_id) if trace_id is not None else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "code": code,
        "symbol": sym_a or sym_e,
        "side": str(side_a).upper() if side_a else (side_e or None),
        "pip_size": float(pip_size),
        "expected_entry_ts": e_entry_ts,
        "expected_exit_ts": e_exit_ts,
        "expected_entry_px": float(e_entry_px),
        "expected_exit_px": float(e_exit_px),
        "actual_entry_ts": a_entry_ts,
        "actual_exit_ts": a_exit_ts,
        "actual_entry_wap": float(a_entry_wap),
        "actual_exit_wap": float(a_exit_wap),
        "entry_slip_pips": float(entry_slip),
        "exit_slip_pips": float(exit_slip),
        "total_slip_pips": float(total_slip),
        "latency_entry_sec": _latency_sec(e_entry_ts, a_entry_ts),
        "latency_exit_sec": _latency_sec(e_exit_ts, a_exit_ts),
        "pnl_pips": float(pnl_pips) if pnl_pips is not None else None,
        "pnl_ccy": float(pnl_ccy) if pnl_ccy is not None else None,
        "taxonomy": TAXONOMY,
        "source": "reconcile_v3_v4.12.6",
    }
