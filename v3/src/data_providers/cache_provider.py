import os, pandas as pd
from datetime import datetime
try:
    import pyarrow; PARQUET=True
except Exception: PARQUET=False
class CachedProvider:
    def __init__(self, provider, cache_dir): self.provider=provider; self.cache_dir=cache_dir
    def _path(self, sym, tf):
        d=os.path.join(self.cache_dir, sym, tf); os.makedirs(d, exist_ok=True); return os.path.join(d,"data.parquet")
    def candles(self, symbol, start, end, timeframe="M1"):
        p=self._path(symbol, timeframe)
        if PARQUET and os.path.exists(p): df=pd.read_parquet(p)
        else: df=pd.DataFrame(columns=["time","open","high","low","close","volume"])
        in_cache = df[(df["time"]>=pd.Timestamp(start)) & (df["time"]<=pd.Timestamp(end))] if not df.empty else pd.DataFrame()
        if not in_cache.empty: return in_cache.sort_values("time").reset_index(drop=True)
        fresh=self.provider.candles(symbol,start,end,timeframe=timeframe)
        if fresh is None or fresh.empty: return fresh
        merged=pd.concat([df,fresh],ignore_index=True).drop_duplicates(subset=["time"]).sort_values("time")
        if PARQUET: os.makedirs(os.path.dirname(p),exist_ok=True); merged.to_parquet(p,index=False)
        return merged[(merged["time"]>=pd.Timestamp(start)) & (merged["time"]<=pd.Timestamp(end))].reset_index(drop=True)
