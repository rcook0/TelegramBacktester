# Patch to support --data-source ctrader via adapters/brokers
import argparse, json, os
from datetime import datetime, timezone
from dotenv import load_dotenv
import pandas as pd

def get_provider(source: str):
    if source == "ctrader":
        from .data_providers.ctrader_provider import CTraderProvider
        from .brokers import vantage_adapter, fpmarkets_adapter
        broker = (os.getenv("BROKER","").upper())
        if broker == "VANTAGE":
            creds = vantage_adapter.load_from_env()
        elif broker == "FPMARKETS":
            creds = fpmarkets_adapter.load_from_env()
        else:
            # Try Vantage first, else FP
            creds = vantage_adapter.load_from_env(optional=True) or fpmarkets_adapter.load_from_env(optional=True)
            if not creds:
                raise RuntimeError("No cTrader credentials found. Set BROKER and env vars (see .env.example).")
        return CTraderProvider(**creds)
    elif source == "mt5":
        from .data_providers.mt5_provider import MT5Provider, MT5_AVAILABLE
        if not MT5_AVAILABLE: raise RuntimeError("MetaTrader5 not available on this platform.")
        return MT5Provider()
    else:
        class CSVProvider:
            def candles(self, symbol, start, end, timeframe="M1"):
                path = os.path.join(os.path.dirname(__file__), "data", f"{symbol}.csv")
                if not os.path.exists(path): raise FileNotFoundError(f"CSV not found: {path}")
                df = pd.read_csv(path, parse_dates=["time"])
                df = df[(df["time"] >= pd.Timestamp(start)) & (df["time"] <= pd.Timestamp(end))]
                return df.sort_values("time").reset_index(drop=True)
        return CSVProvider()
