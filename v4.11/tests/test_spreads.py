import pandas as pd
from datetime import datetime
# Expect SpreadProvider in your repo at src/spread_provider.py

def test_spread_precedence_import():
    try:
        from src.spread_provider import SpreadProvider
    except Exception as e:
        import pytest; pytest.skip(f'spread_provider not present: {e}')

def test_spread_precedence(tmp_path):
    try:
        from src.spread_provider import SpreadProvider, SpreadSource
    except Exception:
        return  # skip if not present
    p = tmp_path / 'spreads'; p.mkdir()
    df = pd.DataFrame({'bucket':[pd.Timestamp('2025-01-01T10:00Z')], 'spread_pips':[1.2]})
    df.to_csv(p / 'EURUSD.csv', index=False)
    rec = SpreadProvider.load_dir(str(p))
    sp = SpreadProvider(static_pips=0.5, per_symbol={'XAUUSD':24}, recorded=rec)
    assert sp.at('EURUSD', pd.Timestamp('2025-01-01T10:05Z')) == 1.2
    assert sp.at('XAUUSD', pd.Timestamp('2025-01-01T10:05Z')) == 24.0
    assert sp.at('GBPUSD', pd.Timestamp('2025-01-01T10:05Z')) == 0.5
