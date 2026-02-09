import os
import pandas as pd
from datetime import datetime

try:
    import pyarrow  # noqa: F401
    PARQUET = True
except Exception:
    PARQUET = False

class CachedProvider:
    def __init__(self, provider, cache_dir):
        self.provider = provider
        self.cache_dir = cache_dir

    def _cache_path(self, symbol: str, timeframe: str):
        d = os.path.join(self.cache_dir, symbol, timeframe)
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "data.parquet")

    def candles(self, symbol: str, start: datetime, end: datetime, timeframe="M1"):
        path = self._cache_path(symbol, timeframe)
        if PARQUET and os.path.exists(path):
            df = pd.read_parquet(path)
        else:
            df = pd.DataFrame(columns=["time","open","high","low","close","volume"])

        in_cache = df[(df["time"] >= pd.Timestamp(start)) & (df["time"] <= pd.Timestamp(end))] if not df.empty else pd.DataFrame()

        if not in_cache.empty:
            return in_cache.sort_values("time").reset_index(drop=True)

        fresh = self.provider.candles(symbol, start, end, timeframe=timeframe)
        if fresh is None or fresh.empty:
            return fresh
        merged = pd.concat([df, fresh], ignore_index=True).drop_duplicates(subset=["time"]).sort_values("time")
        if PARQUET:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            merged.to_parquet(path, index=False)
        return merged[(merged["time"] >= pd.Timestamp(start)) & (merged["time"] <= pd.Timestamp(end))].reset_index(drop=True)
