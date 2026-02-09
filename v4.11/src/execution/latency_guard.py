from __future__ import annotations
from dataclasses import dataclass

@dataclass
class LatencyModel:
    latency_ms: float = 0.0
    def delay_bars(self, ms_per_bar: float) -> int:
        if ms_per_bar <= 0: return 0
        b = int(self.latency_ms / ms_per_bar)
        return max(0, b)

@dataclass
class AdverseWAPGuard:
    max_pct: float = 0.0  # percent; 0 disables
    def allowed(self, intended_px: float, wap_px: float) -> bool:
        if self.max_pct <= 0: return True
        if intended_px <= 0: return True
        dev = abs(wap_px - intended_px) / intended_px * 100.0
        return dev <= self.max_pct
