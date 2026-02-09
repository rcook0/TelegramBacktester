from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from ..capture.window import parse_iso

def _deal_ts(d: dict) -> Optional[str]:
    return d.get("execution_ts") or d.get("ts") or d.get("time") or d.get("timestamp")

def _deal_px(d: dict) -> Optional[float]:
    px = d.get("execution_px") or d.get("px") or d.get("price")
    try:
        return float(px) if px is not None else None
    except Exception:
        return None

def _deal_qty(d: dict) -> Optional[float]:
    qty = d.get("filled_volume_lots") or d.get("volume_lots") or d.get("qty") or d.get("volume")
    try:
        return float(qty) if qty is not None else None
    except Exception:
        return None

def _deal_side(d: dict) -> str:
    s = (d.get("side") or d.get("trade_side") or d.get("direction") or "").upper()
    if s in ("BUY","LONG"): return "LONG"
    if s in ("SELL","SHORT"): return "SHORT"
    return "LONG"

def _deal_symbol(d: dict) -> str:
    return str(d.get("symbol") or d.get("symbol_name") or d.get("instrument") or "")

def _deal_group_id(d: dict) -> Optional[str]:
    for k in ("position_id","positionId","order_id","orderId","trade_id","tradeId","execution_id","executionId","dealId","id"):
        v = d.get(k)
        if v is None:
            continue
        try:
            s = str(v).strip()
            if s and s != "0":
                return f"{k}:{s}"
        except Exception:
            pass
    return None

def _wavg(pairs: List[Tuple[float,float]]) -> Optional[float]:
    num = 0.0
    den = 0.0
    for px, qty in pairs:
        if qty <= 0:
            continue
        num += px * qty
        den += qty
    if den <= 0:
        return None
    return num / den

def knit_deals(aligned_deals: List[dict],
              max_gap_sec: float = 3.0,
              bucket_ms: int = 5000) -> List[dict]:
    """Stitch per-fill `deal_aligned` payloads into execution clusters (`exec_knit`)."""
    rows = []
    for a in aligned_deals:
        if not isinstance(a, dict):
            continue
        d = a.get("deal") if isinstance(a.get("deal"), dict) else None
        if not d:
            continue
        ts = _deal_ts(d)
        if not ts:
            continue
        try:
            t = parse_iso(ts).timestamp()
        except Exception:
            continue
        rows.append((t, ts, a, d))
    rows.sort(key=lambda x: x[0])

    groups: List[List[Tuple[float,str,dict,dict]]] = []
    current: List[Tuple[float,str,dict,dict]] = []
    current_key = None

    def key_for(t: float, d: dict) -> Tuple:
        gid = _deal_group_id(d)
        sym = _deal_symbol(d)
        side = _deal_side(d)
        if gid:
            return ("id", gid)
        b = int((t * 1000) // int(bucket_ms))
        return ("heur", sym, side, b)

    for t, ts, a, d in rows:
        k = key_for(t, d)
        if not current:
            current = [(t, ts, a, d)]
            current_key = k
            continue

        if current_key and current_key[0] == "id" and k == current_key:
            current.append((t, ts, a, d))
            continue

        if current_key and current_key[0] == "heur" and k[0] == "heur":
            if current_key[1] == k[1] and current_key[2] == k[2]:
                gap = t - current[-1][0]
                if gap <= float(max_gap_sec):
                    current.append((t, ts, a, d))
                    current_key = ("heur", current_key[1], current_key[2], k[3])
                    continue

        groups.append(current)
        current = [(t, ts, a, d)]
        current_key = k

    if current:
        groups.append(current)

    execs: List[dict] = []
    for idx, g in enumerate(groups):
        _, _, a0, d0 = g[0]
        sym = _deal_symbol(d0)
        side = _deal_side(d0)
        gid = _deal_group_id(d0) or f"heur:{sym}:{side}:{idx}"

        fills = []
        pairs = []
        qty_sum = 0.0
        depth_pairs = []
        commission_sum = 0.0
        realized_sum = 0.0
        have_commission = False
        have_realized = False

        for _, _, a, d in g:
            px = _deal_px(d)
            qty = _deal_qty(d)
            if px is None or qty is None or qty <= 0:
                continue
            qty_sum += qty
            pairs.append((px, qty))

            dwe = a.get("depth_wap_est")
            try:
                dwe = float(dwe) if dwe is not None else None
            except Exception:
                dwe = None
            if dwe is not None:
                depth_pairs.append((dwe, qty))

            cm = d.get("commission_ccy")
            if cm is None and isinstance(d.get("close_position_detail_norm"), dict):
                cm = d["close_position_detail_norm"].get("commission_ccy")
            if cm is not None:
                try:
                    commission_sum += float(cm)
                    have_commission = True
                except Exception:
                    pass

            rp = d.get("realized_pnl_ccy")
            if rp is not None:
                try:
                    realized_sum += float(rp)
                    have_realized = True
                except Exception:
                    pass

            fills.append({"ts": _deal_ts(d), "px": px, "qty_lots": qty, "raw": d})

        if qty_sum <= 0:
            continue

        wap = _wavg(pairs)
        depth_wap = _wavg(depth_pairs) if depth_pairs else None

        ts_first = fills[0]["ts"] if fills else None
        ts_last = fills[-1]["ts"] if fills else None

        execs.append({
            "exec_id": gid,
            "symbol": sym,
            "side": side,
            "ts_first": ts_first,
            "ts_last": ts_last,
            "total_qty_lots": qty_sum,
            "wap_px": wap,
            "fill_count": len(fills),
            "fills": fills,
            "quote_ctx": a0.get("quote_ctx"),
            "depth_ctx": a0.get("depth_ctx"),
            "depth_wap_est_wavg": depth_wap,
            "commission_ccy_sum": commission_sum if have_commission else None,
            "realized_pnl_ccy_sum": realized_sum if have_realized else None,
            "source": "deal_knit_v4.12.3",
        })

    return execs
