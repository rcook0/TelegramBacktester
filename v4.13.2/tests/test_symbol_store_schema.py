from src.storage.sqlite_store_symbols import SymbolStore

def test_symbol_store_schema(tmp_path):
    db = tmp_path / "t.db"
    s = SymbolStore(str(db))
    s.upsert_symbol("ctrader-openapi", "123", "XAUUSD", "XAUUSD", 1, digits=2, pip_position=1, pip_size=0.1)
    got = s.get_symbol("ctrader-openapi", "123", "XAUUSD")
    assert got and got["symbol_id"] == 1
