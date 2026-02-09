from __future__ import annotations

"""Depth-of-market book builder for cTrader Open API.

Open API depth updates arrive as :class:`ProtoOADepthEvent` with:

- ``newQuotes``: repeated :class:`ProtoOADepthQuote` (id, size, bid|ask)
- ``deletedQuotes``: repeated uint64 (quote ids)

We maintain an in-memory book keyed by quote id and can emit a price-level snapshot.

Important protocol details:
* ``ProtoOADepthQuote.size`` is *in cents* (0.01 units). See model messages.
* Depth prices (``bid``/``ask`` fields in depth quotes) are represented as the same
  relative integer scale as spot prices (divide by 100000). Spotware docs are explicit
  for spot prices; depth uses the same integer fields in practice. If your broker
  uses a different scaling for certain symbols, correct it in the capture layer.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


def price_from_relative(rel: int, digits: int) -> float:
    px = rel / 100000.0
    return round(px, int(digits))


def size_units_from_cents(size_cents: int) -> float:
    return float(size_cents) / 100.0


@dataclass
class BookLevel:
    px: float
    qty: float


class DepthBookBuilder:
    """Maintains per-symbol L2 book from incremental depth events."""

    def __init__(self, digits: int):
        self.digits = int(digits)
        # quote_id -> (price_rel:int, size_cents:int)
        self._bids: Dict[int, Tuple[int, int]] = {}
        self._asks: Dict[int, Tuple[int, int]] = {}

    def reset(self) -> None:
        self._bids.clear()
        self._asks.clear()

    def apply_event(self, new_quotes: List[object], deleted_quote_ids: List[int]) -> None:
        """Apply ProtoOADepthEvent.

        Parameters
        ----------
        new_quotes:
            Iterable of ProtoOADepthQuote. Each quote has id, size, and either bid or ask set.
        deleted_quote_ids:
            Quote IDs to delete.
        """
        for qid in deleted_quote_ids:
            self._bids.pop(int(qid), None)
            self._asks.pop(int(qid), None)

        for q in new_quotes:
            qid = int(getattr(q, "id", 0))
            if not qid:
                continue
            size = int(getattr(q, "size", 0))
            bid = int(getattr(q, "bid", 0) or 0)
            ask = int(getattr(q, "ask", 0) or 0)

            # Quote is either bid-side or ask-side.
            if bid:
                self._bids[qid] = (bid, size)
                # Defensive: if quote flips sides, remove from the other.
                self._asks.pop(qid, None)
            elif ask:
                self._asks[qid] = (ask, size)
                self._bids.pop(qid, None)

    def snapshot(self, top_n: int = 10) -> Tuple[List[BookLevel], List[BookLevel]]:
        """Return aggregated price-level snapshot (top N)."""

        bid_by_px: Dict[int, int] = {}
        ask_by_px: Dict[int, int] = {}

        for px_rel, size_cents in self._bids.values():
            bid_by_px[px_rel] = bid_by_px.get(px_rel, 0) + int(size_cents)
        for px_rel, size_cents in self._asks.values():
            ask_by_px[px_rel] = ask_by_px.get(px_rel, 0) + int(size_cents)

        bid_levels = [
            BookLevel(px=price_from_relative(px_rel, self.digits), qty=size_units_from_cents(sz))
            for px_rel, sz in sorted(bid_by_px.items(), key=lambda kv: kv[0], reverse=True)[:top_n]
        ]
        ask_levels = [
            BookLevel(px=price_from_relative(px_rel, self.digits), qty=size_units_from_cents(sz))
            for px_rel, sz in sorted(ask_by_px.items(), key=lambda kv: kv[0])[:top_n]
        ]

        return bid_levels, ask_levels

    def best(self) -> Tuple[Optional[float], Optional[float]]:
        """Return (best_bid, best_ask) in price units."""
        best_bid_rel = max((px for px, _ in self._bids.values()), default=None)
        best_ask_rel = min((px for px, _ in self._asks.values()), default=None)
        best_bid = price_from_relative(best_bid_rel, self.digits) if best_bid_rel else None
        best_ask = price_from_relative(best_ask_rel, self.digits) if best_ask_rel else None
        return best_bid, best_ask

    def wap(self, side: str, qty_units: float) -> Optional[float]:
        """Compute a simple depth-weighted average price for buying/selling `qty_units`.

        - For a BUY, we consume asks from best upwards.
        - For a SELL, we consume bids from best downwards.
        Returns None if book does not have enough size.
        """
        side_u = side.upper()
        if qty_units <= 0:
            return None

        bids, asks = self.snapshot(top_n=200)  # coarse cap
        levels = asks if side_u == "BUY" else bids
        if not levels:
            return None

        remaining = float(qty_units)
        cost = 0.0
        filled = 0.0
        for lvl in levels:
            take = min(remaining, lvl.qty)
            if take <= 0:
                break
            cost += take * lvl.px
            filled += take
            remaining -= take
            if remaining <= 0:
                break

        if filled <= 0 or remaining > 1e-12:
            return None
        return cost / filled
