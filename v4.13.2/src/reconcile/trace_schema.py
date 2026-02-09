from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

KINDS = {
  "ENTRY", "PARTIAL_FILL", "TP", "SL", "EXIT", "BE_MOVE", "TRAIL_MOVE", "NOTE"
}

@dataclass
class TraceEvent:
    ts: str
    kind: str
    px: Optional[float] = None
    qty: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class ModelTraceDoc:
    idem_key: str
    symbol: str
    side: str
    timeframe: str = "M1"
    events: List[TraceEvent] = field(default_factory=list)
    assumptions: Dict[str, Any] = field(default_factory=dict)  # spread/slippage/latency model used
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "idem_key": self.idem_key,
            "symbol": self.symbol,
            "side": self.side,
            "timeframe": self.timeframe,
            "assumptions": self.assumptions,
            "meta": self.meta,
            "events": [e.to_dict() for e in self.events],
        }

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
