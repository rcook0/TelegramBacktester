from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, Any, Optional, List
from time import monotonic

@dataclass
class BufferedEmitterConfig:
    flush_interval_sec: float = 0.2
    # If depth events arrive too fast, we can drop them aggressively.
    max_depth_hz_per_symbol: float = 5.0
    # If enabled, depth will be dropped first under pressure.
    drop_depth_under_pressure: bool = True

class BufferedEmitter:
    """Coalesces high-frequency quote/depth updates into a stable stream.
    - Keeps only the *latest* quote per symbol between flush ticks.
    - Optionally keeps only the latest depth per symbol with throttling.
    This prevents backtest DB writes or stdout from becoming the bottleneck.
    """
    def __init__(self, cfg: BufferedEmitterConfig):
        self.cfg = cfg
        self.latest_quote: Dict[str, Dict[str, Any]] = {}
        self.latest_depth: Dict[str, Dict[str, Any]] = {}
        self._last_depth_emit_ts: Dict[str, float] = {}
        self._pressure = 0  # simple counter for diagnostics

    def update_quote(self, symbol: str, payload: Dict[str, Any]):
        self.latest_quote[symbol] = payload

    def update_depth(self, symbol: str, payload: Dict[str, Any]):
        self.latest_depth[symbol] = payload

    def flush(self,
              on_quote: Optional[Callable[[Dict[str, Any]], None]] = None,
              on_depth: Optional[Callable[[Dict[str, Any]], None]] = None):
        # emit latest quotes
        if on_quote:
            for sym, q in list(self.latest_quote.items()):
                try:
                    on_quote(q)
                except Exception:
                    # poison pill guard
                    self._pressure += 1
            self.latest_quote.clear()

        # emit latest depth with per-symbol throttling
        if on_depth:
            now = monotonic()
            min_dt = 1.0 / max(self.cfg.max_depth_hz_per_symbol, 0.0001)
            for sym, d in list(self.latest_depth.items()):
                last = self._last_depth_emit_ts.get(sym, 0.0)
                if (now - last) < min_dt:
                    continue
                try:
                    on_depth(d)
                    self._last_depth_emit_ts[sym] = now
                except Exception:
                    self._pressure += 1
            self.latest_depth.clear()

    @property
    def pressure(self) -> int:
        return self._pressure
