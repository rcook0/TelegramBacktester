from src.pricing.pips import PipEngine, Contract

def engine():
    sm = {'XAUUSD.i':'XAUUSD'}
    cmap = {
        'EURUSD': Contract(100000, 0.0001, 0.00001, 5, 0.01, 0.01, 'USD'),
        'GBPJPY': Contract(100000, 0.01,   0.001,   3, 0.01, 0.01, 'JPY'),
        'XAUUSD': Contract(100,    0.1,    0.01,    2, 0.01, 0.01, 'USD')
    }
    return PipEngine(sm, cmap)

def test_eurusd_pip_10usd_per_lot():
    pe = engine()
    assert abs(pe.pip_value('EURUSD', 1.0, 'USD', fx_rates={}) - 10.0) < 1e-9

def test_gbpjpy_pip_usd_with_usdjpy_150():
    pe = engine()
    # JPY -> USD conversion via USDJPY=150 -> 1000 JPY pip ≈ 6.666... USD
    v = pe.pip_value('GBPJPY', 1.0, 'USD', fx_rates={'USDJPY':150.0})
    assert 6.60 < v < 6.80

def test_xauusd_pip_10usd_per_lot():
    pe = engine()
    assert abs(pe.pip_value('XAUUSD', 1.0, 'USD', fx_rates={}) - 10.0) < 1e-9
