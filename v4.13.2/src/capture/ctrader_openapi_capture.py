from __future__ import annotations
"""cTrader Open API (Spotware) capture: quotes + depth.

This is the "real" wiring for cTrader market data capture:
- Connect to Spotware Open API proxies (demo/live) over Protobuf (TCP/TLS).
- Authenticate application + trading account session.
- Resolve symbolIds via SymbolsList.
- Subscribe to spot quotes + depth quotes.
- Persist into our shadow tables via callbacks (runner handles persistence).

Docs:
- Endpoints: live/demo on ports 5035 (Protobuf) / 5036 (JSON) and TCP or WS. 5035 is used here. 
- Spot price scaling: bid/ask values are relative; divide by 100000 and round to symbol digits.

Implementation uses Spotware-maintained OpenApiPy package: `pip install ctrader-open-api`.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, Callable, Optional, List, Tuple
import math

from .buffered_emitter import BufferedEmitter, BufferedEmitterConfig
from .depth_book_builder import DepthBookBuilder


try:
    from ctrader_open_api import Client, TcpProtocol, EndPoints, Protobuf
    from ctrader_open_api.messages.OpenApiMessages_pb2 import (
        ProtoOAApplicationAuthReq, ProtoOAAccountAuthReq,
        ProtoOASubscribeSpotsReq, ProtoOASubscribeDepthQuotesReq,
        ProtoOASymbolsListReq
    )
    CTRADER_OPENAPI_AVAILABLE = True
except Exception:
    CTRADER_OPENAPI_AVAILABLE = False


@dataclass
class OpenApiCaptureConfig:
    env: str  # LIVE|DEMO
    client_id: str
    client_secret: str
    access_token: str
    ctid_trader_account_id: int
    symbols: List[str]
    subscribe_depth: bool = False
    symbol_alias_map: Dict[str,str] | None = None  # alias->broker symbol name

    # v4.11.10 hardening
    flush_interval_sec: float = 0.2
    max_depth_hz_per_symbol: float = 5.0
    drop_depth_under_pressure: bool = True
    reconnect: bool = True
    reconnect_backoff_sec: float = 2.0
    max_reconnect_backoff_sec: float = 30.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _price_from_relative(rel: int, digits: int) -> float:
    # Open API docs: divide by 100000 and round to symbol digits.
    # See: help.ctrader.com/open-api/symbol-data/ (SpotEvent)
    px = rel / 100000.0
    return round(px, int(digits))


def _pip_size_from_symbol(digits: int, pip_position: int) -> float:
    # pipPosition is the index on digits; pip size is 10^(-pipPosition)
    # Example: EURUSD digits=5 pipPosition=4 => 1e-4
    # Gold often digits=2 pipPosition=1 => 1e-1
    return 10.0 ** (-int(pip_position))


class CTraderOpenApiCapture:
    def __init__(self, cfg: OpenApiCaptureConfig):
        if not CTRADER_OPENAPI_AVAILABLE:
            raise RuntimeError("ctrader-open-api (OpenApiPy) is not installed. Install: pip install ctrader-open-api")
        self.cfg = cfg
        self.cfg.symbol_alias_map = self.cfg.symbol_alias_map or {}
        # Normalize requested symbols to broker symbol names if alias map provided
        self.cfg.symbols = [self.cfg.symbol_alias_map.get(s, s) for s in self.cfg.symbols]
        env = cfg.env.upper()
        if env not in ("LIVE", "DEMO"):
            raise ValueError("env must be LIVE or DEMO")
        host = EndPoints.PROTOBUF_LIVE_HOST if env == "LIVE" else EndPoints.PROTOBUF_DEMO_HOST
        self.client = Client(host, EndPoints.PROTOBUF_PORT, TcpProtocol)
        self._symbols_by_name: Dict[str, Tuple[int,int,int]] = {}  # name -> (symbolId,digits,pipPosition)
        self._book_by_symbol: Dict[str, DepthBookBuilder] = {}
        self._ready = False
        self.emitter = BufferedEmitter(BufferedEmitterConfig(
            flush_interval_sec=float(getattr(self.cfg,'flush_interval_sec',0.2)),
            max_depth_hz_per_symbol=float(getattr(self.cfg,'max_depth_hz_per_symbol',5.0)),
            drop_depth_under_pressure=bool(getattr(self.cfg,'drop_depth_under_pressure',True)),
        ))
        self._on_quote = None
        self._on_depth = None
        self._reconnect_backoff = float(getattr(self.cfg,'reconnect_backoff_sec',2.0))


    def start(self,
              on_quote: Callable[[Dict[str, Any]], None],
              on_depth: Optional[Callable[[Dict[str, Any]], None]] = None,
              stop_after_sec: Optional[float] = None):
        from twisted.internet import reactor
        from twisted.internet.task import LoopingCall
        # Store callbacks (poison-pill safe emission happens in BufferedEmitter.flush)
        self._on_quote = on_quote
        self._on_depth = on_depth

        # Flush loop: coalesce high-frequency events
        lc = LoopingCall(lambda: self.emitter.flush(on_quote=self._on_quote, on_depth=self._on_depth))
        lc.start(float(getattr(self.cfg,'flush_interval_sec',0.2)), now=False)


        def on_error(failure):
            # Keep short; caller can log more.
            print("OpenAPI error:", failure)

        def connected(client):
            # 1) App auth
            req = ProtoOAApplicationAuthReq()
            req.clientId = self.cfg.client_id
            req.clientSecret = self.cfg.client_secret
            d = client.send(req)
            d.addErrback(on_error)

        def disconnected(client, reason):
            print("Disconnected:", reason)
            if getattr(self.cfg,'reconnect',True):
                try:
                    from twisted.internet import reactor
                    backoff = min(self._reconnect_backoff, float(getattr(self.cfg,'max_reconnect_backoff_sec',30.0)))
                    print(f"Reconnecting in {backoff:.1f}s...")
                    reactor.callLater(backoff, client.startService)
                    self._reconnect_backoff = min(self._reconnect_backoff * 1.8, float(getattr(self.cfg,'max_reconnect_backoff_sec',30.0)))
                except Exception:
                    pass

        def _send_account_auth():
            req = ProtoOAAccountAuthReq()
            req.ctidTraderAccountId = int(self.cfg.ctid_trader_account_id)
            req.accessToken = self.cfg.access_token
            d = self.client.send(req); d.addErrback(on_error)

        def _request_symbols():
            req = ProtoOASymbolsListReq()
            req.ctidTraderAccountId = int(self.cfg.ctid_trader_account_id)
            d = self.client.send(req); d.addErrback(on_error)

        def _subscribe():
            # Subscribe spots
            sym_ids = [self._symbols_by_name[s][0] for s in self.cfg.symbols if s in self._symbols_by_name]
            if not sym_ids:
                raise RuntimeError("No symbols resolved. Ensure your broker uses the same symbol names (e.g., XAUUSD).")
            sreq = ProtoOASubscribeSpotsReq()
            sreq.ctidTraderAccountId = int(self.cfg.ctid_trader_account_id)
            sreq.symbolId.extend(sym_ids)
            d = self.client.send(sreq); d.addErrback(on_error)

            if self.cfg.subscribe_depth and on_depth:
                dreq = ProtoOASubscribeDepthQuotesReq()
                dreq.ctidTraderAccountId = int(self.cfg.ctid_trader_account_id)
                dreq.symbolId.extend(sym_ids)
                d2 = self.client.send(dreq); d2.addErrback(on_error)

            self._ready = True

        def on_message(client, message):
            try:
                m = Protobuf.extract(message)
                name = m.DESCRIPTOR.name

                if name == "ProtoOAApplicationAuthRes":
                    _send_account_auth()
                    return

                if name == "ProtoOAAccountAuthRes":
                    _request_symbols()
                    return

                if name == "ProtoOASymbolsListRes":
                    # Build mapping
                    self._symbols_by_name.clear()
                    self._book_by_symbol.clear()
                    for ls in getattr(m, "symbol", []):
                        # Light symbols include symbolId, digits, pipPosition, and name.
                        sym_name = getattr(ls, "symbolName", None) or getattr(ls, "name", None)
                        if not sym_name:
                            continue
                        digits = int(getattr(ls, "digits", 5))
                        self._symbols_by_name[sym_name] = (int(ls.symbolId), digits, int(ls.pipPosition))
                        self._book_by_symbol[sym_name] = DepthBookBuilder(digits=digits)
                    _subscribe()
                    return

                if name == "ProtoOASpotEvent":
                    # Find symbol meta by id
                    sid = int(getattr(m, "symbolId", 0))
                    # reverse lookup (small set; ok)
                    sym_name = None
                    digits = 5
                    pip_pos = 4
                    for k, (id_, d, p) in self._symbols_by_name.items():
                        if id_ == sid:
                            sym_name, digits, pip_pos = k, d, p
                            break
                    if not sym_name:
                        return

                    bid_rel = int(getattr(m, "bid", 0))
                    ask_rel = int(getattr(m, "ask", 0))
                    bid = _price_from_relative(bid_rel, digits) if bid_rel else 0.0
                    ask = _price_from_relative(ask_rel, digits) if ask_rel else 0.0
                    mid = (bid + ask) / 2.0 if (bid and ask) else 0.0
                    pip_size = _pip_size_from_symbol(digits, pip_pos)
                    spread_pips = ((ask - bid) / pip_size) if (pip_size and bid and ask) else 0.0

                    q_payload = dict(
                        ts=_now_iso(),
                        symbol=sym_name,
                        symbol_id=sid,
                        bid=bid,
                        ask=ask,
                        mid=mid,
                        digits=digits,
                        pip_position=pip_pos,
                        pip_size=pip_size,
                        spread_pips=spread_pips,
                        source="ctrader-openapi",
                    )
                    self.emitter.update_quote(sym_name, q_payload)
                    return

                if name == "ProtoOADepthEvent" and self.cfg.subscribe_depth and on_depth:
                    sid = int(getattr(m, "symbolId", 0))
                    sym_name = None; digits = 5; pip_pos = 4
                    for k,(id_,d,p) in self._symbols_by_name.items():
                        if id_ == sid:
                            sym_name, digits, pip_pos = k, d, p
                            break
                    if not sym_name:
                        return

                    book = self._book_by_symbol.get(sym_name)
                    if not book:
                        book = DepthBookBuilder(digits=digits)
                        self._book_by_symbol[sym_name] = book

                    # Depth event is incremental: apply adds/updates + deletions.
                    new_quotes = list(getattr(m, "newQuotes", []))
                    deleted = [int(x) for x in list(getattr(m, "deletedQuotes", []))]
                    book.apply_event(new_quotes=new_quotes, deleted_quote_ids=deleted)

                    bid_lvls, ask_lvls = book.snapshot(top_n=10)
                    best_bid, best_ask = book.best()
                    pip_size = _pip_size_from_symbol(digits, pip_pos)
                    spread_pips = ((best_ask - best_bid) / pip_size) if (pip_size and best_bid and best_ask) else 0.0

                    d_payload = dict(
                        ts=_now_iso(),
                        symbol=sym_name,
                        symbol_id=sid,
                        bids=[{"px": b.px, "qty": b.qty} for b in bid_lvls],
                        asks=[{"px": a.px, "qty": a.qty} for a in ask_lvls],
                        best_bid=best_bid,
                        best_ask=best_ask,
                        spread_pips=spread_pips,
                        source="ctrader-openapi",
                        depth_event_stats={
                            "new_quotes": len(new_quotes),
                            "deleted_quotes": len(deleted),
                        },
                    )

                    # Drop depth updates under pressure if configured (simple heuristic)
                    if not getattr(self.cfg,'drop_depth_under_pressure',True) or self.emitter.pressure < 1000:
                        self.emitter.update_depth(sym_name, d_payload)
                    return

            except Exception as e:
                # poison pill guard: log minimal and keep running
                print('OpenAPI message handler error:', type(e).__name__)
                return

        # Wire callbacks and connect
        self.client.setConnectedCallback(connected)
        self.client.setDisconnectedCallback(disconnected)
        self.client.setMessageReceivedCallback(on_message)

        if stop_after_sec is not None and stop_after_sec > 0:
            reactor.callLater(float(stop_after_sec), reactor.stop)

        self.client.startService()
        reactor.run()
