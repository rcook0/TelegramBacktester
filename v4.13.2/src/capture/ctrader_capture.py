from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, Any, List, Optional
import time

from net.rate_limiter import TokenBucket

@dataclass
class CTraderCaptureConfig:
    base_url: str = ""          # your gateway base URL (broker-specific)
    access_token: str = ""      # pass at runtime, never commit
    host: str = "LIVE"          # LIVE|DEMO (metadata only)
    symbols: Optional[List[str]] = None
    poll_interval_sec: float = 0.5
    max_rps: float = 5.0
    burst: int = 10
    timeout_sec: float = 10.0

class CTraderCapture:
    """Read-only capture for shadow parity.
    Endpoints are intentionally placeholders: each broker's cTrader gateway differs.
    Wire your gateway paths inside fetch_quote/fetch_depth.
    """

    def __init__(self, cfg: CTraderCaptureConfig):
        self.cfg = cfg
        self.cfg.symbols = self.cfg.symbols or []
        self.limiter = TokenBucket(rate_per_sec=cfg.max_rps, burst=cfg.burst)

    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        """Return standardized quote payload: ts,symbol,bid,ask,mid,spread_pips,source."""
        while not self.limiter.take():
            time.sleep(0.01)
        now = datetime.now(timezone.utc).isoformat()
        # TODO: call your gateway and map fields:
        # bid = ...
        # ask = ...
        bid = 0.0
        ask = 0.0
        mid = (bid + ask) / 2.0 if (bid and ask) else 0.0
        spread_pips = 0.0
        return dict(ts=now, symbol=symbol, bid=bid, ask=ask, mid=mid, spread_pips=spread_pips, source="ctrader")

    def fetch_depth(self, symbol: str) -> Dict[str, Any]:
        """Return standardized depth payload: ts,symbol,bids[],asks[],source."""
        while not self.limiter.take():
            time.sleep(0.01)
        now = datetime.now(timezone.utc).isoformat()
        return dict(ts=now, symbol=symbol, bids=[], asks=[], source="ctrader")

    def run_poll_loop(
        self,
        on_quote: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_depth: Optional[Callable[[Dict[str, Any]], None]] = None,
        stop_after_sec: Optional[float] = None,
    ) -> None:
        start = time.time()
        while True:
            for sym in self.cfg.symbols:
                q = self.fetch_quote(sym)
                if on_quote:
                    on_quote(q)
                if on_depth:
                    d = self.fetch_depth(sym)
                    on_depth(d)
            time.sleep(self.cfg.poll_interval_sec)
            if stop_after_sec is not None and (time.time() - start) >= stop_after_sec:
                break
