import argparse
from src.main import get_data_provider

class Args:
    data_source="csv"
    ctrader_client_id=None; ctrader_client_secret=None; ctrader_access_token=None; ctrader_account_id=None; ctrader_host="LIVE"
    fix_cfg=None; fix_symbols=None

def test_csv_provider_factory():
    args = Args()
    prov = get_data_provider(args)
    assert hasattr(prov, "candles")

def test_ctrader_missing_params_raises():
    args = Args(); args.data_source="ctrader"
    try:
        get_data_provider(args)
        assert False, "Should raise on missing ctrader params"
    except RuntimeError:
        assert True
