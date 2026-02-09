from __future__ import annotations
from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple
from datetime import datetime
from .depth.depth_provider import DepthProvider, DepthSnapshot

Side = Literal['LONG','SHORT']

@dataclass
class DepthConfig:
    side: Side
    lots: float
    sl_px: float
    tps_px: List[float]
    weights: List[float]
    impact_k: float  # extra slip per lot when book insufficient
    ioc: bool

@dataclass
class DepthFill:
    time: datetime
    kind: Literal['ENTRY','TP','SL']
    px: float
    qty_lots: float
    note: str = ''

def _consume(levels: List[Tuple[float, float]], need: float) -> Tuple[float, float]:
    remain = need
    notional = 0.0
    filled = 0.0
    for price, qty in levels:
        if remain <= 0: break
        if qty <= 0: continue
        take = min(qty, remain)
        notional += price * take
        filled += take
        remain -= take
    if filled <= 0:
        return (float('nan'), 0.0)
    return (notional / filled, filled)

class DepthExecutor:
    def __init__(self, provider: DepthProvider, impact_k: float = 0.0):
        self.provider = provider
        self.impact_k = float(impact_k or 0.0)

    def _entry_levels(self, snap: DepthSnapshot, side: Side) -> List[Tuple[float,float]]:
        return snap.asks if side == 'LONG' else snap.bids

    def _exit_levels_for(self, snap: DepthSnapshot, side: Side, kind: str, level_px: float) -> List[Tuple[float,float]]:
        if kind == 'TP':
            if side == 'LONG':
                return [(px, q) for px,q in snap.bids if px >= level_px]
            else:
                return [(px, q) for px,q in snap.asks if px <= level_px]
        else:
            if side == 'LONG':
                return [(px, q) for px,q in snap.bids if px <= level_px]
            else:
                return [(px, q) for px,q in snap.asks if px >= level_px]

    def entry(self, symbol: str, ts: datetime, side: Side, lots: float) -> DepthFill:
        snap = self.provider.snapshot(symbol, ts)
        if not snap:
            return DepthFill(ts, 'ENTRY', float('nan'), 0.0, 'no depth')
        levels = self._entry_levels(snap, side)
        wap, filled = _consume(levels, lots)
        if filled < lots and self.impact_k > 0.0:
            remain = max(0.0, lots - filled)
            adj = self.impact_k * remain
            wap = wap + (adj if side=='LONG' else -adj)
        return DepthFill(ts, 'ENTRY', wap, filled, 'entry wap')

    def exit_partial(self, symbol: str, ts: datetime, side: Side, level_px: float, lots: float, kind: str) -> List[DepthFill]:
        """Return zero, one or multiple fills to satisfy `lots` using book; partials allowed."""
        snap = self.provider.snapshot(symbol, ts)
        if not snap:
            return [DepthFill(ts, kind, level_px, 0.0, 'no depth')]
        levels = self._exit_levels_for(snap, side, kind, level_px)
        fills: List[DepthFill] = []
        remain = lots
        for px, qty in levels:
            if remain <= 0: break
            take = min(qty, remain)
            if take <= 0: continue
            fills.append(DepthFill(ts, kind, px, take, f'{kind.lower()} level'))
            remain -= take
        if remain > 0 and self.impact_k > 0.0:
            # model adverse continuation to complete remaining at adjusted price
            adj_px = (level_px + self.impact_k * remain) if (kind=='SL' and side=='LONG') else                      (level_px - self.impact_k * remain) if (kind=='SL' and side=='SHORT') else                      (level_px - self.impact_k * remain) if (kind=='TP' and side=='LONG') else                      (level_px + self.impact_k * remain)
            fills.append(DepthFill(ts, kind, adj_px, remain, 'impact remainder'))
            remain = 0.0
        return fills
