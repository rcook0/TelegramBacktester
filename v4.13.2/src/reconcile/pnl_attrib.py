from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from ..capture.window import parse_iso

@dataclass
class SymbolContract:
    symbol: str
    base_ccy: str
    quote_ccy: str
    lot_size: float
    pip_size: float

def _safe_float(x) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None

def parse_symbol_contract(symbol: str, meta: dict) -> Optional[SymbolContract]:
    if not isinstance(meta, dict):
        return None
    base = (meta.get("baseAsset") or meta.get("baseCurrency") or meta.get("base") or "").upper()
    quote = (meta.get("quoteAsset") or meta.get("quoteCurrency") or meta.get("quote") or "").upper()
    lot_size = _safe_float(meta.get("lotSize") or meta.get("contractSize") or 0.0) or 0.0

    pip_size = _safe_float(meta.get("pipSize") or meta.get("pip_size"))
    if pip_size is None:
        pp = meta.get("pipPosition") or meta.get("pip_position")
        try:
            pip_size = 10.0 ** (-int(pp))
        except Exception:
            pip_size = None

    if not base or not quote or lot_size <= 0 or (pip_size is None or pip_size <= 0):
        return None
    return SymbolContract(symbol=symbol, base_ccy=base, quote_ccy=quote, lot_size=lot_size, pip_size=pip_size)

def _mid_from_quote_payload(q: dict) -> Optional[float]:
    for k in ("mid", "mid_px", "price", "last", "bidAskMid", "bidAskMidPx"):
        v = q.get(k)
        fv = _safe_float(v)
        if fv is not None:
            return fv
    bid = _safe_float(q.get("bid"))
    ask = _safe_float(q.get("ask"))
    if bid is not None and ask is not None:
        return (bid + ask) / 2.0
    return None

def build_rate_graph(pairs: Dict[str, float]):
    g: Dict[str, Dict[str, float]] = {}
    for pair, px in pairs.items():
        if not pair or len(pair) < 6:
            continue
        base = pair[:3].upper()
        quote = pair[3:6].upper()
        px = float(px)
        g.setdefault(base, {})[quote] = px
        if px != 0:
            g.setdefault(quote, {})[base] = 1.0 / px
    return g

def find_fx_rate(pairs: Dict[str, float], from_ccy: str, to_ccy: str) -> Optional[float]:
    from_ccy = from_ccy.upper(); to_ccy = to_ccy.upper()
    if from_ccy == to_ccy:
        return 1.0
    g = build_rate_graph(pairs)
    from collections import deque
    q = deque([(from_ccy, 1.0)])
    seen = {from_ccy}
    while q:
        ccy, mul = q.popleft()
        for nxt, rate in g.get(ccy, {}).items():
            if nxt in seen:
                continue
            n_mul = mul * rate
            if nxt == to_ccy:
                return n_mul
            seen.add(nxt)
            q.append((nxt, n_mul))
    return None

def compute_trade_pnl_quote(side: str, entry_wap: float, exit_wap: float, qty_lots: float, contract: SymbolContract) -> Tuple[float, float]:
    side = side.upper()
    sign = 1.0 if side in ("LONG","BUY") else -1.0
    delta = (exit_wap - entry_wap) * sign
    pnl_quote = delta * (contract.lot_size * qty_lots)
    pnl_pips = delta / contract.pip_size
    return pnl_quote, pnl_pips

def attrib_trade_link(store, link_id: int, account_ccy: str = "USD", rates: Dict[str, float] | None = None, rate_window_sec: float = 300.0) -> dict:
    rates = dict(rates or {})
    cur = store.conn.cursor()
    cur.execute("SELECT symbol, side, entry_ts, exit_ts, entry_wap, exit_wap, qty_lots FROM trade_links WHERE id=?", (int(link_id),))
    row = cur.fetchone()
    if not row:
        return {"ok": False, "reason": "missing trade_link", "link_id": link_id}
    symbol, side, entry_ts, exit_ts, entry_wap, exit_wap, qty_lots = row
    if entry_wap is None or exit_wap is None or qty_lots is None:
        return {"ok": False, "reason": "missing wap/qty", "link_id": link_id}

    meta = store.get_symbol_meta(symbol)
    contract = parse_symbol_contract(symbol, meta or {})
    if contract is None:
        return {"ok": False, "reason": "missing/invalid symbol_meta", "symbol": symbol, "link_id": link_id}

    pnl_quote, pnl_pips = compute_trade_pnl_quote(str(side), float(entry_wap), float(exit_wap), float(qty_lots), contract)

    # augment rates from quote snapshots near exit time (best-effort)
    ts_anchor = exit_ts or entry_ts
    try:
        t0 = parse_iso(ts_anchor).timestamp() if ts_anchor else None
    except Exception:
        t0 = None

    if t0 is not None:
        lo = t0 - float(rate_window_sec)
        hi = t0 + float(rate_window_sec)
        cur.execute("SELECT payload FROM shadow_snapshots WHERE kind='quote'")
        for (ps,) in cur.fetchall():
            try:
                q = json.loads(ps)
            except Exception:
                continue
            sym = str(q.get("symbol") or q.get("symbol_name") or q.get("instrument") or "")
            if len(sym) < 6:
                continue
            ts = q.get("ts") or q.get("time") or q.get("timestamp") or q.get("at")
            if not ts:
                continue
            try:
                tt = parse_iso(ts).timestamp()
            except Exception:
                continue
            if tt < lo or tt > hi:
                continue
            mid = _mid_from_quote_payload(q)
            if mid is None:
                continue
            rates[sym.upper()] = float(mid)

    # include traded symbol as a rate if FX-like
    if symbol and len(symbol) >= 6 and symbol.upper() not in rates and contract.base_ccy.isalpha() and contract.quote_ccy.isalpha():
        rates[symbol.upper()] = (float(entry_wap) + float(exit_wap)) / 2.0

    fx_rate = find_fx_rate(rates, contract.quote_ccy, account_ccy.upper())
    pnl_account = pnl_quote * fx_rate if fx_rate is not None else None

    return {
        "ok": True,
        "link_id": link_id,
        "symbol": symbol,
        "side": side,
        "quote_ccy": contract.quote_ccy,
        "account_ccy": account_ccy.upper(),
        "entry_wap": float(entry_wap),
        "exit_wap": float(exit_wap),
        "qty_lots": float(qty_lots),
        "lot_size": float(contract.lot_size),
        "pip_size": float(contract.pip_size),
        "pnl_quote_ccy": float(pnl_quote),
        "pnl_pips": float(pnl_pips),
        "fx_rate_quote_to_account": float(fx_rate) if fx_rate is not None else None,
        "pnl_account_ccy": float(pnl_account) if pnl_account is not None else None,
        "rates_used_count": len(rates),
        "source": "pnl_attrib_v4.12.5",
        "note": None if fx_rate is not None else "No FX conversion path found; pass --rates-json or capture conversion pairs as quote snapshots.",
    }
