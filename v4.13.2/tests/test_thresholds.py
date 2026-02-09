import pandas as pd
from src.reconcile.thresholds import Thresholds
from src.reconcile.scorecard import compute_metrics, evaluate_thresholds

def test_thresholds_pass_fail():
    df = pd.DataFrame([
        {"delta_wap_pips": 0.1, "delta_spread_pips": 0.1, "delta_latency_ms": 50},
        {"delta_wap_pips": 0.2, "delta_spread_pips": 0.2, "delta_latency_ms": 80},
    ])
    thr = Thresholds(min_trades=1, max_abs_median_delta_wap_pips=0.5, max_abs_p95_delta_wap_pips=1.0,
                     max_abs_median_delta_spread_pips=0.5, max_abs_p95_delta_spread_pips=1.0,
                     max_median_delta_latency_ms=200, max_p95_delta_latency_ms=400)
    metrics = compute_metrics(df)
    ok, reasons = evaluate_thresholds(metrics, thr)
    assert ok and reasons == []

    thr2 = Thresholds(min_trades=1, max_abs_median_delta_wap_pips=0.05)
    ok2, reasons2 = evaluate_thresholds(metrics, thr2)
    assert (not ok2) and any("too_wide" in r or "delta_wap_pips.median_abs" in r for r in reasons2)
