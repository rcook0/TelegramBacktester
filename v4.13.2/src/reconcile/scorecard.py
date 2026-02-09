from __future__ import annotations
from typing import Dict, Any, Tuple, List
import pandas as pd
from .thresholds import Thresholds

_METRIC_COLS = [
    "delta_wap_pips",
    "delta_spread_pips",
    "delta_latency_ms",
]

def _abs_series(df: pd.DataFrame, col: str) -> pd.Series:
    s = pd.to_numeric(df.get(col), errors="coerce").dropna()
    return s.abs()

def compute_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    out: Dict[str, Any] = {"n": int(len(df))}
    for col in _METRIC_COLS:
        if col not in df.columns:
            continue
        s = _abs_series(df, col)
        if len(s) == 0:
            continue
        out[col] = {
            "count": int(s.count()),
            "mean_abs": float(s.mean()),
            "median_abs": float(s.median()),
            "p95_abs": float(s.quantile(0.95)),
            "max_abs": float(s.max()),
        }
    return out

def evaluate_thresholds(metrics: Dict[str, Any], thr: Thresholds) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    n = metrics.get("n", 0)
    if n < thr.min_trades:
        reasons.append(f"insufficient_trades: n={n} < min_trades={thr.min_trades}")

    # helper
    def chk(col: str, key: str, limit: float, tag: str):
        m = metrics.get(col, {})
        if not m:
            reasons.append(f"missing_metric: {col}")
            return
        val = m.get(key)
        if val is None:
            reasons.append(f"missing_stat: {col}.{key}")
            return
        if float(val) > float(limit):
            reasons.append(f"{tag}: {col}.{key}={val:.4g} > {limit:.4g}")

    chk("delta_wap_pips", "median_abs", thr.max_abs_median_delta_wap_pips, "too_wide")
    chk("delta_wap_pips", "p95_abs", thr.max_abs_p95_delta_wap_pips, "tail_risk")
    chk("delta_spread_pips", "median_abs", thr.max_abs_median_delta_spread_pips, "spread_bias")
    chk("delta_spread_pips", "p95_abs", thr.max_abs_p95_delta_spread_pips, "spread_tail")
    chk("delta_latency_ms", "median_abs", thr.max_median_delta_latency_ms, "latency_bias")
    chk("delta_latency_ms", "p95_abs", thr.max_p95_delta_latency_ms, "latency_tail")

    ok = (len(reasons) == 0)
    return ok, reasons

def per_symbol_breakdown(df: pd.DataFrame, top_n: int = 10) -> Dict[str, Any]:
    if "symbol" not in df.columns:
        return {}
    out = {}
    for sym, g in df.groupby("symbol"):
        m = compute_metrics(g)
        out[sym] = m
    # sort by worst median wap (abs)
    def key(sym):
        m = out[sym].get("delta_wap_pips", {})
        return m.get("median_abs", 0.0)
    worst = sorted(out.keys(), key=key, reverse=True)[:top_n]
    return {"symbols": out, "worst_by_median_wap": worst}

def worst_offenders(df: pd.DataFrame, by: str="delta_wap_pips", n: int=25) -> pd.DataFrame:
    if by not in df.columns:
        return df.head(0)
    d = df.copy()
    d["_abs"] = pd.to_numeric(d[by], errors="coerce").abs()
    return d.sort_values("_abs", ascending=False).drop(columns=["_abs"]).head(n)
