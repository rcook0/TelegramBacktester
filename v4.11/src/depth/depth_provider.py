from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional
from datetime import datetime
import os, pandas as pd

@dataclass
class DepthSnapshot:
    symbol: str
    time: datetime
    bids: List[Tuple[float, float]]
    asks: List[Tuple[float, float]]

class DepthProvider:
    def snapshot(self, symbol: str, ts: datetime) -> Optional[DepthSnapshot]:
        raise NotImplementedError

class CSVDepthProvider(DepthProvider):
    def __init__(self, depth_dir: str):
        self.depth_dir = depth_dir
        self.cache = {}

    def _load(self, symbol: str) -> pd.DataFrame:
        path = os.path.join(self.depth_dir, f"{symbol}.csv")
        if path in self.cache:
            return self.cache[path]
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        df = pd.read_csv(path)
        df['time'] = pd.to_datetime(df['time'], utc=True)
        self.cache[path] = df
        return df

    def snapshot(self, symbol: str, ts: datetime) -> Optional[DepthSnapshot]:
        df = self._load(symbol)
        t = pd.Timestamp(ts, tz='UTC').floor('1min')
        snap = df[df['time'] == t]
        if snap.empty: return None
        bids = snap[snap['side']=='bid'].sort_values('price', ascending=False)
        asks = snap[snap['side']=='ask'].sort_values('price', ascending=True)
        return DepthSnapshot(
            symbol=symbol, time=t.to_pydatetime(),
            bids=[(float(p), float(q)) for p,q in zip(bids['price'], bids['qty'])],
            asks=[(float(p), float(q)) for p,q in zip(asks['price'], asks['qty'])],
        )
