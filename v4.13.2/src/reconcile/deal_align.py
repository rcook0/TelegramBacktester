from __future__ import annotations
import json
from typing import Dict, Any, List, Optional, Tuple
from ..capture.window import parse_iso, nearest_by_ts
from ..reconcile.wap import wap_from_depth

def _pick_window(store, signal_id: int, use_capture_window: bool, pre_sec: float, post_sec: float) -> Tuple[str, str]:
    cur = store.conn.cursor()
    cur.execute("SELECT ts FROM signals WHERE id=?", (signal_id,))
    r = cur.fetchone()
    if not r:
        raise RuntimeError("signal_id not found")
    sig_ts = r[0]

    if use_capture_window:
        cur.execute("SELECT payload FROM shadow_snapshots WHERE signal_id=? AND kind='capture_window' ORDER BY id DESC LIMIT 1", (signal_id,))
        cw = cur.fetchone()
        if cw:
            try:
                payload = json.loads(cw[0])
                ts_from = payload.get("from") or payload.get("ts_from") or payload.get("start")
                ts_to = payload.get("to") or payload.get("ts_to") or payload.get("end")
                if ts_from and ts_to:
                    return ts_from, ts_to
            except Exception:
                pass

    # fallback: sig_ts +/- pre/post
    t0 = parse_iso(sig_ts).timestamp()
    ts_from = parse_iso(sig_ts)
    ts_to = parse_iso(sig_ts)
    ts_from = ts_from.fromtimestamp(t0 - float(pre_sec), tz=ts_from.tzinfo).isoformat()
    ts_to = ts_to.fromtimestamp(t0 + float(post_sec), tz=ts_to.tzinfo).isoformat()
    return ts_from, ts_to

def align_deals_for_signal(store,
                           signal_id: int,
                           use_capture_window: bool = True,
                           pre_sec: float = 2.0,
                           post_sec: float = 120.0,
                           max_gap_ms: float = 5000.0,
                           overwrite: bool = False) -> List[dict]:
    """Align deal_norm rows to a signal and enrich with nearest quote/depth context.

    Output is persisted as shadow_snapshots(kind='deal_aligned') per aligned deal.
    Returns list of aligned payloads.

    Mechanism:
    - Determine a time window (capture_window if present, else signal_ts +/- {pre_sec, post_sec})
    - Load deal_norm rows whose execution_ts falls inside [from,to]
    - For each deal, attach nearest quote snapshot and nearest depth snapshot within max_gap_ms
    - If depth exists, compute an estimated depth-WAP for the executed qty (lots)
    """
    cur = store.conn.cursor()
    if overwrite:
        cur.execute("DELETE FROM shadow_snapshots WHERE signal_id=? AND kind='deal_aligned'", (signal_id,))
        store.conn.commit()

    ts_from, ts_to = _pick_window(store, signal_id, use_capture_window, pre_sec, post_sec)

    # Fetch candidate deals
    cur.execute("""
      SELECT ts, payload FROM shadow_snapshots
      WHERE signal_id=? AND kind='deal_norm'
      ORDER BY id ASC
    """, (signal_id,))
    deals = [(ts, json.loads(p)) for ts, p in cur.fetchall()]

    # Fetch context snapshots
    cur.execute("""SELECT ts, payload FROM shadow_snapshots WHERE signal_id=? AND kind='quote' ORDER BY id ASC""", (signal_id,))
    quotes = [json.loads(p) for _, p in cur.fetchall()]
    cur.execute("""SELECT ts, payload FROM shadow_snapshots WHERE signal_id=? AND kind IN ('depth','depth_book') ORDER BY id ASC""", (signal_id,))
    depths = [json.loads(p) for _, p in cur.fetchall()]

    t_from = parse_iso(ts_from).timestamp()
    t_to = parse_iso(ts_to).timestamp()

    aligned: List[dict] = []
    for fallback_ts, d in deals:
        ex_ts = d.get("execution_ts") or d.get("ts") or fallback_ts
        try:
            t_ex = parse_iso(ex_ts).timestamp()
        except Exception:
            continue
        if t_ex < t_from or t_ex > t_to:
            continue

        q = nearest_by_ts(quotes, ex_ts) if quotes else None
        dep = nearest_by_ts(depths, ex_ts) if depths else None

        # enforce max_gap_ms
        def within(obj):
            if not obj or not obj.get("ts"):
                return False
            try:
                return abs(parse_iso(obj["ts"]).timestamp() - t_ex) * 1000.0 <= float(max_gap_ms)
            except Exception:
                return False

        q_used = q if within(q) else None
        d_used = dep if within(dep) else None

        qty_lots = d.get("filled_volume_lots") or d.get("volume_lots") or d.get("qty_lots")
        try:
            qty_lots = float(qty_lots) if qty_lots is not None else None
        except Exception:
            qty_lots = None

        side = (d.get("side") or d.get("trade_side") or "").upper()
        if side not in ("LONG","SHORT"):
            # cTrader uses BUY/SELL sometimes
            if str(d.get("side") or "").upper() == "BUY":
                side = "LONG"
            elif str(d.get("side") or "").upper() == "SELL":
                side = "SHORT"
            else:
                side = "LONG"

        depth_wap = None
        if d_used is not None and qty_lots is not None:
            # NOTE: depth quantities are in "units" native to cTrader snapshot; many feeds are in lots-ish.
            # We treat qty_lots as the same unit for now; calibration happens in later versions.
            try:
                depth_wap = wap_from_depth(d_used, qty_lots, side)
            except Exception:
                depth_wap = None

        payload = {
            "execution_ts": ex_ts,
            "window_from": ts_from,
            "window_to": ts_to,
            "deal": d,
            "quote_ctx": q_used,
            "depth_ctx": d_used,
            "depth_wap_est": depth_wap,
            "max_gap_ms": float(max_gap_ms),
            "source": "deal_align_v4.12.2",
        }
        store.add_shadow_snapshot(signal_id, "deal_aligned", payload, ts=ex_ts)
        aligned.append(payload)

    store.conn.commit()
    return aligned
