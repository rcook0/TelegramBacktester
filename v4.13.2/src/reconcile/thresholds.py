from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, Optional
import json

@dataclass
class Thresholds:
    # pips deltas
    max_abs_median_delta_wap_pips: float = 0.8
    max_abs_p95_delta_wap_pips: float = 2.5
    max_abs_median_delta_spread_pips: float = 0.5
    max_abs_p95_delta_spread_pips: float = 1.5

    # latency (proxy) deltas
    max_median_delta_latency_ms: float = 150.0
    max_p95_delta_latency_ms: float = 400.0

    # coverage
    min_trades: int = 20

    # optional allowlist gating
    per_symbol_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_json(s: str) -> "Thresholds":
        d = json.loads(s)
        return Thresholds(**d)

    @staticmethod
    def from_file(path: str) -> "Thresholds":
        with open(path, "r", encoding="utf-8") as f:
            txt = f.read()
        # allow raw json
        return Thresholds.from_json(txt)
