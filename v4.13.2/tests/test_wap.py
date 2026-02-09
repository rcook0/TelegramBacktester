from src.reconcile.wap import wap_from_fills, wap_from_depth

def test_wap_from_fills():
    fills = [{"px": 100.0, "qty": 1}, {"px": 101.0, "qty": 3}]
    assert abs(wap_from_fills(fills) - 100.75) < 1e-12

def test_wap_from_depth_buy():
    depth = {"asks":[{"px":100.0,"qty":1},{"px":101.0,"qty":2}]}
    # buy 2 -> 1@100 + 1@101 => 100.5
    assert abs(wap_from_depth(depth, 2, "LONG") - 100.5) < 1e-12

def test_wap_from_depth_sell():
    depth = {"bids":[{"px":100.0,"qty":1},{"px":99.0,"qty":2}]}
    # sell 2 -> 1@100 + 1@99 => 99.5
    assert abs(wap_from_depth(depth, 2, "SHORT") - 99.5) < 1e-12
