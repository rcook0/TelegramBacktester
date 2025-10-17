from datetime import datetime, timezone
import time, threading
from typing import Optional, Dict
import pandas as pd

try:
    from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
    from ctrader_open_api.messages.OpenApiMessages_pb2 import (
        ProtoOAApplicationAuthReq, ProtoOAAccountAuthReq,
        ProtoOASymbolsListReq, ProtoOAGetTrendbarsReq
    )
    from ctrader_open_api.messages.OpenApiModelMessages_pb2 import (
        ProtoOATrendbarPeriod
    )
    _SDK_OK = True
except Exception as e:
    _SDK_OK = False

_PERIOD_MAP = {
    "M1": ProtoOATrendbarPeriod.M1 if _SDK_OK else 0,
    "M5": ProtoOATrendbarPeriod.M5 if _SDK_OK else 0,
    "M15": ProtoOATrendbarPeriod.M15 if _SDK_OK else 0,
    "H1": ProtoOATrendbarPeriod.H1 if _SDK_OK else 0,
}

_SCALE = 100000.0  # per cTrader docs, prices are scaled by 1e5

class _ResponseWaiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._last = None
    def put(self, msg):
        with self._cv:
            self._last = msg
            self._cv.notify_all()
    def wait(self, timeout=10.0):
        with self._cv:
            if self._last is None:
                self._cv.wait(timeout=timeout)
            msg = self._last
            self._last = None
            return msg

class CTraderProvider:
    """
    Minimal market-data adapter using cTrader Open API (Spotware). Auths app + account,
    then fetches trendbars and reconstructs absolute OHLC.
    """
    def __init__(self, client_id: str, client_secret: str, access_token: str,
                 account_id: int, host: str = "LIVE"):
        if not _SDK_OK:
            raise RuntimeError("ctrader-open-api SDK not installed. pip install ctrader-open-api")
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.account_id = int(account_id)
        host = (host or "LIVE").upper()
        self.host = EndPoints.PROTOBUF_LIVE_HOST if host == "LIVE" else EndPoints.PROTOBUF_DEMO_HOST
        self._client = Client(self.host, EndPoints.PROTOBUF_PORT, TcpProtocol)
        self._waiter = _ResponseWaiter()
        self._connected = threading.Event()
        self._reactor_thread = None

        # wire callbacks
        self._client.setConnectedCallback(self._on_connected)
        self._client.setDisconnectedCallback(self._on_disconnected)
        self._client.setMessageReceivedCallback(self._on_message)

        # start service + start reactor in a thread (Twisted runs forever)
        self._client.startService()
        self._start_reactor_thread()

        # do auth handshake
        self._app_auth()
        self._account_auth()

    def _start_reactor_thread(self):
        try:
            from twisted.internet import reactor
        except Exception as e:
            raise RuntimeError("Twisted reactor missing (ctrader-open-api dependency).") from e
        def _run():
            reactor.run(installSignalHandlers=False)
        if not self._reactor_thread or not self._reactor_thread.is_alive():
            self._reactor_thread = threading.Thread(target=_run, name="twisted-reactor", daemon=True)
            self._reactor_thread.start()
        # wait a bit for network socket bind
        time.sleep(0.2)

    # callbacks
    def _on_connected(self, client):  # noqa
        self._connected.set()
    def _on_disconnected(self, client, reason):  # noqa
        self._connected.clear()
    def _on_message(self, client, message):  # noqa
        # naive: forward last message to waiter; in practice, you can route by payloadType
        self._waiter.put(message)

    def _send(self, req, timeout=10.0):
        d = self._client.send(req)
        # block until any message comes back; for brevity. In production, match payloadType.
        msg = self._waiter.wait(timeout=timeout)
        if msg is None:
            raise TimeoutError("Timed out waiting for cTrader response")
        return msg

    def _app_auth(self):
        req = ProtoOAApplicationAuthReq()
        req.clientId = self.client_id
        req.clientSecret = self.client_secret
        self._send(req, timeout=10.0)

    def _account_auth(self):
        req = ProtoOAAccountAuthReq()
        req.ctidTraderAccountId = self.account_id
        req.accessToken = self.access_token
        self._send(req, timeout=10.0)

    def candles(self, symbol: str, start: datetime, end: datetime, timeframe="M1"):
        """Return pandas DataFrame with columns: time, open, high, low, close, volume"""
        period = _PERIOD_MAP.get(timeframe.upper())
        if period is None:
            raise ValueError(f"Unsupported timeframe for cTrader: {timeframe}")
        # cTrader wants ms epoch
        from_ms = int(start.timestamp() * 1000)
        to_ms = int(end.timestamp() * 1000)
        # You must pass broker symbol name, e.g., XAUUSD, EURUSD, etc., as known by the account.
        # First, ensure symbol list is loaded (implicitly via trendbars OK for many servers).
        bars = []
        page = 0
        # Simple single-shot; servers may cap count per request; iterate if needed.
        req = ProtoOAGetTrendbarsReq()
        req.ctidTraderAccountId = self.account_id
        req.symbolName = symbol
        req.period = period
        req.fromTimestamp = from_ms
        req.toTimestamp = to_ms
        res = self._send(req, timeout=15.0)
        # Extract protobuf payload into dict
        try:
            payload = Protobuf.extract(res)
        except Exception:
            # Fallback: return empty
            return pd.DataFrame(columns=["time","open","high","low","close","volume"])
        trendbars = payload.get("trendbar", []) or payload.get("trendbars", [])
        if not trendbars:
            return pd.DataFrame(columns=["time","open","high","low","close","volume"])
        # Reconstruct OHLC from relative encoding (see cTrader docs)
        rows = []
        for tb in trendbars:
            # tb is a dict like {"utcTimestampInMs":..., "low":..., "deltaOpen":..., "deltaHigh":..., "deltaClose":..., "volume":...}
            low_abs = float(tb["low"]) / _SCALE
            o = (tb["deltaOpen"] + tb["low"]) / _SCALE
            h = (tb["deltaHigh"] + tb["low"]) / _SCALE
            c = (tb["deltaClose"] + tb["low"]) / _SCALE
            t = datetime.utcfromtimestamp(tb["utcTimestampInMs"]/1000.0).replace(tzinfo=timezone.utc)
            rows.append({"time": t, "open": o, "high": h, "low": low_abs, "close": c, "volume": float(tb.get("volume",0))})
        df = pd.DataFrame(rows).sort_values("time").reset_index(drop=True)
        return df
