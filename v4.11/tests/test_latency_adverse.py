from src.execution.latency_guard import LatencyModel, AdverseWAPGuard

def test_latency_to_bars():
    lm = LatencyModel(latency_ms=150)
    assert lm.delay_bars(50) == 3

def test_adverse_wap_guard():
    g = AdverseWAPGuard(max_pct=0.2)
    assert g.allowed(100.0, 100.1) is True   # +0.1%
    assert g.allowed(100.0, 100.5) is False  # +0.5% > 0.2%
