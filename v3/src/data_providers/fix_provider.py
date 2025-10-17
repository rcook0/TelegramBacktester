"""
Vantage FIX Market Data provider: QuickFIX client that subscribes to BID/OFFER and exposes a tick queue.
"""
import os, time, threading, queue, logging
from datetime import datetime, timezone
from typing import List, Dict, Optional
import pandas as pd
from dotenv import load_dotenv

import quickfix as fix
import quickfix44 as fix44

log = logging.getLogger("fix_provider")
log.setLevel(logging.INFO)

# ---------------- Tick bus ----------------
class TickBus:
    def __init__(self, maxsize: int = 500_000):
        self.q = queue.Queue(maxsize=maxsize)
    def put(self, x: Dict):
        try: self.q.put_nowait(x)
        except queue.Full: pass
    def drain(self, max_items: int = 100_000):
        out = []
        while len(out) < max_items:
            try: out.append(self.q.get_nowait())
            except queue.Empty: break
        return out

# ---------------- FIX App ----------------
class MDApp(fix.Application):
    def __init__(self, bus: TickBus, symbols: List[str]):
        super().__init__()
        self.sessionID: Optional[fix.SessionID] = None
        self.bus = bus
        self.symbols = symbols

    def onCreate(self, sessionID): self.sessionID = sessionID
    def onLogon(self, sessionID):
        log.info("FIX Logon: %s", sessionID.toString())
        self.sessionID = sessionID
        self._subscribe()
    def onLogout(self, sessionID):
        log.warning("FIX Logout: %s", sessionID.toString())
    def toAdmin(self, message, sessionID):
        msgtype = fix.MsgType()
        message.getHeader().getField(msgtype)
        if msgtype.getValue() == fix.MsgType_Logon:
            load_dotenv()
            u = os.getenv("FIX_USERNAME", "")
            p = os.getenv("FIX_PASSWORD", "")
            if u: message.setField(fix.Username(u))
            if p: message.setField(fix.Password(p))
    def fromAdmin(self, message, sessionID): pass
    def toApp(self, message, sessionID): pass
    def fromApp(self, message, sessionID):
        msgtype = fix.MsgType()
        message.getHeader().getField(msgtype)
        if msgtype.getValue() in (fix.MsgType_MarketDataSnapshotFullRefresh, fix.MsgType_MarketDataIncrementalRefresh):
            self._handle_md(message)

    def _subscribe(self):
        req = fix44.MarketDataRequest(
            fix.MDReqID("MD-REQ-1"),
            fix.SubscriptionRequestType(fix.SubscriptionRequestType_SNAPSHOT_PLUS_UPDATES),
            fix.MarketDepth(1)
        )
        req.setField(fix.MDUpdateType(0))  # Full refresh
        req.setField(fix.AggregatedBook(True))

        # Types: BID(0), OFFER(1)
        for typ in (fix.MDEntryType_BID, fix.MDEntryType_OFFER):
            g = fix44.MarketDataRequest.NoMDEntryTypes()
            g.setField(fix.MDEntryType(typ))
            req.addGroup(g)
        # Symbols
        for sym in self.symbols:
            sg = fix44.MarketDataRequest.NoRelatedSym()
            sg.setField(fix.Symbol(sym))
            req.addGroup(sg)

        fix.Session.sendToTarget(req, self.sessionID)

    def _handle_md(self, message: fix.Message):
        # Snapshot handler
        entries = []
        try:
            count = fix.NoMDEntries()
            message.getField(count)
            n = count.getValue()
            for i in range(1, n + 1):
                grp = fix44.MarketDataSnapshotFullRefresh.NoMDEntries()
                try:
                    message.getGroup(i, grp)
                except Exception:
                    continue
                sym = fix.Symbol(); typ = fix.MDEntryType(); px = fix.MDEntryPx()
                try:
                    message.getField(sym)
                except Exception:
                    # Some venues put symbol only per message
                    sym_val = None
                else:
                    sym_val = sym.getValue()
                try: grp.getField(typ); grp.getField(px)
                except Exception: continue
                ts = datetime.now(timezone.utc)
                side = "BID" if typ.getValue() == fix.MDEntryType_BID else "ASK"
                if sym_val is None:
                    # fallback: attempt to read from group
                    s2 = fix.Symbol()
                    if grp.isSetField(s2): grp.getField(s2); sym_val = s2.getValue()
                if sym_val:
                    entries.append({"symbol": sym_val, "side": side, "price": float(px.getValue()), "time": ts})
        except Exception:
            # Try incremental flavor (MsgType=X)
            try:
                group = fix44.MarketDataIncrementalRefresh.NoMDEntries()
                i = 1
                while True:
                    message.getGroup(i, group); i += 1
                    typ = fix.MDEntryType(); px = fix.MDEntryPx(); sym = fix.Symbol()
                    group.getField(typ); group.getField(px); 
                    sym_val = None
                    if group.isSetField(sym): group.getField(sym); sym_val = sym.getValue()
                    ts = datetime.now(timezone.utc)
                    side = "BID" if typ.getValue() == fix.MDEntryType_BID else "ASK"
                    if sym_val:
                        entries.append({"symbol": sym_val, "side": side, "price": float(px.getValue()), "time": ts})
            except Exception:
                pass

        for e in entries:
            self.bus.put(e)

# ---------------- Provider wrapper ----------------
class VantageFIXProvider:
    """
    Spins up a QuickFIX initiator and streams ticks into a queue.
    Drain with .drain_ticks() and persist as needed.
    """
    def __init__(self, cfg_path: str, symbols: List[str]):
        self.bus = TickBus()
        settings = fix.SessionSettings(cfg_path)
        app = MDApp(self.bus, symbols)
        store = fix.FileStoreFactory(settings)
        logf = fix.FileLogFactory(settings)
        self.initiator = fix.SocketInitiator(app, store, settings, logf)
        self.initiator.start()
        time.sleep(1.0)  # allow logon handshake

    def drain_ticks(self, max_items=100_000):
        return self.bus.drain(max_items=max_items)
