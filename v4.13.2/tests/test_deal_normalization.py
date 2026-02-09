from src.normalize.ctrader_deals import normalize_deal_payload

def test_money_scaling_and_volume():
    payload = {
        "volume_cents": 250,
        "filled_volume_cents": 100,
        "commission": 123000000,   # moneyDigits=8 => 1.23
        "money_digits": 8,
        "close_position_detail": {
            "gross_profit": 10053099944,
            "swap": 100000000,
            "commission": 200000000,
            "pnl_conversion_fee": 0,
            "money_digits": 8
        }
    }
    out = normalize_deal_payload(payload, symbol_meta={"symbol_name":"EURUSD","pip_position":4,"pip_size":0.0001})
    assert abs(out["volume_lots"] - 2.5) < 1e-12
    assert abs(out["filled_volume_lots"] - 1.0) < 1e-12
    assert abs(out["commission_ccy"] - 1.23) < 1e-12
    c = out["close_position_detail_norm"]
    assert abs(c["gross_profit_ccy"] - 100.53099944) < 1e-12
    assert "realized_pnl_ccy" in out
