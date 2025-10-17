from src.backtester import split_symbol, pip_size, default_contract_size

def test_pip_value_scaling_usd_major():
    ps = pip_size("EURUSD", 1.12345)      # 0.0001
    cs = default_contract_size("EURUSD")  # 100k
    assert abs(cs * ps - 10.0) < 1e-9     # $10 / pip / 1 lot

def test_pip_size_jpy_pair():
    ps = pip_size("USDJPY", 147.12)       # 0.01
    assert ps == 0.01
