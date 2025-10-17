# src/connectors/base.py
from typing import Iterable, Optional, Literal, Dict
from dataclasses import dataclass
from datetime import datetime

BarTF = Literal["M1","M5","M15","H1","H4","D1"]

@dataclass
class Candle:  # normalized OHLCV
    time: datetime; open: float; high: float; low: float; close: float; volume: float

@dataclass
class Tick:    # normalized tick
    time: datetime; bid: Optional[float]; ask: Optional[float]; last: Optional[float]; size: Optional[float]

@dataclass
class Capabilities:
    candles: bool; ticks: bool; depth: bool; spreads: bool
    place_orders: bool; modify_orders: bool; positions: bool

class Connector:
    name: str
    caps: Capabilities

    # ---- Market data
    def candles(self, symbol: str, start: datetime, end: datetime, timeframe: BarTF) -> Iterable[Candle]:
        raise NotImplementedError
    def stream_ticks(self, symbols: list[str]) -> Iterable[Tick]:
        raise NotImplementedError
    def stream_spreads(self, symbols: list[str]) -> Iterable[Dict]:  # {time, symbol, spread_pips}
        raise NotImplementedError

    # ---- Trading (optional)
    def place_order(self, **kwargs) -> Dict: ...
    def amend_order(self, **kwargs) -> Dict: ...
    def cancel_order(self, **kwargs) -> Dict: ...
    def positions(self) -> Iterable[Dict]: ...

    # ---- Bookkeeping
    def close(self): ...
