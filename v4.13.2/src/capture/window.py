from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

@dataclass(frozen=True)
class CaptureWindow:
    pre_ms: int = 2000
    post_ms: int = 30000

    def start_end(self, signal_ts: datetime) -> tuple[datetime, datetime]:
        if signal_ts.tzinfo is None:
            signal_ts = signal_ts.replace(tzinfo=timezone.utc)
        start = signal_ts - timedelta(milliseconds=int(self.pre_ms))
        end = signal_ts + timedelta(milliseconds=int(self.post_ms))
        return start, end

def parse_iso(ts: str) -> datetime:
    # Accept 'Z' suffix and naive ISO; normalize to UTC tz-aware
    ts = ts.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def nearest_by_ts(items: list[dict], target_iso: str, ts_key: str="ts") -> Optional[dict]:
    if not items:
        return None
    target = parse_iso(target_iso).timestamp()
    best = None
    best_d = 1e18
    for it in items:
        t = parse_iso(it.get(ts_key, "")).timestamp()
        d = abs(t - target)
        if d < best_d:
            best_d = d
            best = it
    return best
