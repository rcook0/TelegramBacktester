from src.reconcile.deal_knit import knit_deals

def test_knit_wap_and_qty():
    aligned = [
        {"deal": {"execution_ts":"2026-01-01T00:00:00+00:00","symbol":"EURUSD","side":"BUY","execution_px":1.1000,"filled_volume_lots":1.0},
         "depth_wap_est": 1.1001},
        {"deal": {"execution_ts":"2026-01-01T00:00:01+00:00","symbol":"EURUSD","side":"BUY","execution_px":1.1002,"filled_volume_lots":3.0},
         "depth_wap_est": 1.1003},
    ]
    ex = knit_deals(aligned, max_gap_sec=3.0, bucket_ms=5000)
    assert len(ex) == 1
    e = ex[0]
    assert abs(e["total_qty_lots"] - 4.0) < 1e-12
    assert abs(e["wap_px"] - 1.10015) < 1e-12
    assert abs(e["depth_wap_est_wavg"] - 1.10025) < 1e-12
