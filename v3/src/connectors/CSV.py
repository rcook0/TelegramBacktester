# src/connectors/csv_provider.py
from datetime import datetime
import os
import pandas as pd

class CSVConnector:
    """
    Read-only candle source for backtests.
    Expects CSVs at: <repo>/src/data/<SYMBOL>.csv with columns:
    time,open,high,low,close,volume  (time = ISO8601, UTC)
    """
    def __init__(self, data_dir=None):
        # default to src/data so existing datasets keep working
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "..", "data")

    def candles(self, symbol: str, start: datetime, end: datetime, timeframe="M1"):
        path = os.path.join(self.data_dir, f"{symbol}.csv")
        if not os.path.exists(path):
            raise FileNotFoundError(f"CSV not found: {path}")
        df = pd.read_csv(path, parse_dates=["time"])
        df = df[(df["time"] >= pd.Timestamp(start)) & (df["time"] <= pd.Timestamp(end))]
        return df.sort_values("time").reset_index(drop=True)
