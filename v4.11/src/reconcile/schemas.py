from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

@dataclass
class QuoteSnapshot:
  ts: datetime; symbol: str; bid: float; ask: float; mid: float; spread_pips: float; source: str='broker'

@dataclass
class ModelEvent:
  ts: datetime; kind: str; px: float; qty: float; note: str=''

@dataclass
class ModelTrace:
  idem_key: str; symbol: str; side: str; events: List[ModelEvent]=field(default_factory=list); meta: Dict[str,Any]=field(default_factory=dict)

@dataclass
class ShadowRecord:
  idem_key: str; channel: str; signal_ts: datetime; symbol: str; side: str
  quotes: List[QuoteSnapshot]=field(default_factory=list)
  depths: list=field(default_factory=list)
  fills: list=field(default_factory=list)
  meta: Dict[str,Any]=field(default_factory=dict)

@dataclass
class ReconcileDiff:
  idem_key: str; symbol: str; side: str
  entry_px_model: Optional[float]=None
  entry_px_broker: Optional[float]=None
  delta_entry_pips: Optional[float]=None
  notes: List[str]=field(default_factory=list)
