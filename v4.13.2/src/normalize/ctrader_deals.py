from __future__ import annotations
from typing import Any, Dict, Optional
import math

def _scale_money(val: int, money_digits: Optional[int]) -> Optional[float]:
    if val is None:
        return None
    try:
        v = int(val)
    except Exception:
        return None
    if money_digits is None:
        # keep raw as float
        return float(v)
    try:
        md = int(money_digits)
    except Exception:
        return float(v)
    return float(v) / (10.0 ** md)

def _pip_size_from_pip_position(pip_position: Optional[int]) -> Optional[float]:
    if pip_position is None:
        return None
    try:
        pp = int(pip_position)
    except Exception:
        return None
    return 10.0 ** (-pp)

def normalize_deal_payload(payload: Dict[str, Any], symbol_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Normalize a DealList 'deal' payload to consistent units.

    - volumes: cTrader Open API uses volume fields in *cents* (1/100 of a unit of volume, typically lots).
      So `volume_lots = volume_cents / 100`.
    - money: deal/closePositionDetail monetary values are scaled by `moneyDigits` exponent.
    """
    out = dict(payload)  # shallow copy

    # Symbol metadata
    if symbol_meta:
        out.setdefault("symbol", symbol_meta.get("symbol_name"))
        out.setdefault("digits", symbol_meta.get("digits"))
        out.setdefault("pip_position", symbol_meta.get("pip_position"))
        out.setdefault("pip_size", symbol_meta.get("pip_size") or _pip_size_from_pip_position(symbol_meta.get("pip_position")))
        out.setdefault("lot_size_cents", symbol_meta.get("lot_size_cents"))
        out.setdefault("min_volume_cents", symbol_meta.get("min_volume_cents"))
        out.setdefault("step_volume_cents", symbol_meta.get("step_volume_cents"))
        out.setdefault("max_volume_cents", symbol_meta.get("max_volume_cents"))
        out.setdefault("measurement_units", symbol_meta.get("measurement_units"))

    # Volume normalization
    vc = out.get("volume_cents")
    fvc = out.get("filled_volume_cents")
    try:
        if vc is not None:
            out["volume_lots"] = float(vc) / 100.0
        if fvc is not None:
            out["filled_volume_lots"] = float(fvc) / 100.0
    except Exception:
        pass

    # Money normalization (deal-level commission can exist)
    md = out.get("money_digits")
    if out.get("commission") is not None:
        out["commission_ccy"] = _scale_money(out.get("commission"), md)

    # Close position detail normalization (gross_profit/swap/commission/balance/fee)
    cpd = out.get("close_position_detail") or None
    if isinstance(cpd, dict):
        md2 = cpd.get("money_digits") if cpd.get("money_digits") is not None else md
        # copy normalized fields
        cpd_norm = dict(cpd)
        for k in ("gross_profit", "swap", "commission", "balance", "pnl_conversion_fee"):
            if k in cpd_norm:
                cpd_norm[f"{k}_ccy"] = _scale_money(cpd_norm.get(k), md2)
        out["close_position_detail_norm"] = cpd_norm

    # convenience: realized pnl (gross - commission + swap - fees) if close detail present
    if isinstance(out.get("close_position_detail_norm"), dict):
        c = out["close_position_detail_norm"]
        gp = c.get("gross_profit_ccy")
        sw = c.get("swap_ccy")
        cm = c.get("commission_ccy")
        fee = c.get("pnl_conversion_fee_ccy")
        if all(v is not None for v in (gp, sw, cm, fee)):
            out["realized_pnl_ccy"] = float(gp) + float(sw) - float(cm) - float(fee)

    return out
