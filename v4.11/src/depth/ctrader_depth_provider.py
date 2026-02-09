from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timezone
import threading
from .depth_provider import DepthProvider, DepthSnapshot

@dataclass
class _BookSide:
    levels: Dict[float, float] = field(default_factory=dict)
    def sorted(self, is_bid: bool) -> List[Tuple[float,float]]:
        return sorted(self.levels.items(), key=lambda x:x[0], reverse=is_bid)

class CTraderDepthProvider(DepthProvider):
    def __init__(self):
        self._lock = threading.Lock()
        self._books: Dict[str, Dict[str,_BookSide]] = {}
    def _ensure(self, sym:str):
        if sym not in self._books:
            self._books[sym] = {'bid': _BookSide(), 'ask': _BookSide()}
    def on_depth(self, symbol: str, time: datetime, side: str, price: float, qty: float, action: str='set'):
        if time.tzinfo is None: time = time.replace(tzinfo=timezone.utc)
        with self._lock:
            self._ensure(symbol)
            side_obj = self._books[symbol]['bid' if side.lower()=='bid' else 'ask']
            if action=='del' or qty<=0:
                side_obj.levels.pop(float(price), None)
            else:
                side_obj.levels[float(price)] = float(qty)
    def snapshot(self, symbol: str, ts: datetime) -> Optional[DepthSnapshot]:
        if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)
        with self._lock:
            self._ensure(symbol)
            bid = self._books[symbol]['bid'].sorted(True)
            ask = self._books[symbol]['ask'].sorted(False)
            if not bid and not ask: return None
            return DepthSnapshot(symbol=symbol, time=ts.replace(second=0, microsecond=0), bids=bid, asks=ask)
