from __future__ import annotations
from typing import Iterable, Optional, Tuple, List, Dict

def wap_from_fills(fills: List[dict], px_key: str="px", qty_key: str="qty") -> Optional[float]:
    """Volume-weighted average price from fills.
    Expected fill dict keys: px/qty (configurable).
    """
    num = 0.0
    den = 0.0
    for f in fills:
        try:
            px = float(f.get(px_key))
            qty = float(f.get(qty_key))
        except Exception:
            continue
        if qty <= 0:
            continue
        num += px * qty
        den += qty
    if den <= 0:
        return None
    return num / den

def _normalize_depth(depth: dict) -> Tuple[List[Tuple[float,float]], List[Tuple[float,float]]]:
    """Return (bids, asks) as sorted lists of (px, qty). Robust to common payload shapes."""
    bids = []
    asks = []

    # common shapes: {"bids":[{"px":..,"qty":..}], "asks":[...]}
    if isinstance(depth.get("bids"), list):
        for lv in depth["bids"]:
            try:
                bids.append((float(lv.get("px") or lv.get("price")), float(lv.get("qty") or lv.get("volume"))))
            except Exception:
                pass
    if isinstance(depth.get("asks"), list):
        for lv in depth["asks"]:
            try:
                asks.append((float(lv.get("px") or lv.get("price")), float(lv.get("qty") or lv.get("volume"))))
            except Exception:
                pass

    # alternative: {"bid":[[px,qty],...], "ask":[[px,qty],...]}
    if not bids and isinstance(depth.get("bid"), list):
        for lv in depth["bid"]:
            try:
                bids.append((float(lv[0]), float(lv[1])))
            except Exception:
                pass
    if not asks and isinstance(depth.get("ask"), list):
        for lv in depth["ask"]:
            try:
                asks.append((float(lv[0]), float(lv[1])))
            except Exception:
                pass

    # if payload stored as ProtoOADepthEvent deltas, caller must aggregate elsewhere
    bids.sort(key=lambda x: x[0], reverse=True)
    asks.sort(key=lambda x: x[0])
    return bids, asks

def wap_from_depth(depth: dict, qty: float, side: str) -> Optional[float]:
    """Compute the *book* WAP to execute qty immediately against current depth.
    Assumes depth is L2/L3-ish aggregated levels (price, available qty).
    For LONG (buy) consume asks; for SHORT (sell) consume bids.
    Returns None if insufficient depth.
    """
    if qty is None:
        return None
    try:
        qty = float(qty)
    except Exception:
        return None
    if qty <= 0:
        return None

    bids, asks = _normalize_depth(depth)
    book = asks if side.upper() == "LONG" else bids
    if not book:
        return None

    rem = qty
    num = 0.0
    for px, avail in book:
        if avail <= 0:
            continue
        take = avail if avail < rem else rem
        num += px * take
        rem -= take
        if rem <= 1e-12:
            return num / qty
    return None
