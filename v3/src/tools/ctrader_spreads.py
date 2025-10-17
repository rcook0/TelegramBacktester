"""
cTrader live spread recorder using Spotware Open API.
"""
import os, time, threading
from datetime import datetime, timezone
import pandas as pd
from dotenv import load_dotenv

from ctrader_open_api import Client, TcpProtocol, EndPoints, Protobuf
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAApplicationAuthReq, ProtoOAAccountAuthReq, ProtoOASubscribeSpotsReq
)

_SCALE = 100000.0

class CTraderSpreadsRecorder:
    def __init__(self, symbols):
        load_dotenv()
        cid=os.getenv("CTRADER_CLIENT_ID"); sec=os.getenv("CTRADER_CLIENT_SECRET")
        tok=os.getenv("CTRADER_ACCESS_TOKEN"); acc=int(os.getenv("CTRADER_ACCOUNT_ID","0"))
        host=(os.getenv("CTRADER_HOST","LIVE") or "LIVE").upper()
        self.symbols = symbols
        self.account_id = acc
        self.client = Client(EndPoints.PROTOBUF_LIVE_HOST if host=="LIVE" else EndPoints.PROTOBUF_DEMO_HOST,
                             EndPoints.PROTOBUF_PORT, TcpProtocol)
        self.client.setMessageReceivedCallback(self._on_msg)
        self.client.startService()
        self._rows = []  # (sym, time, spread_pips)
        self._lock = threading.Lock()
        self._auth(cid, sec, tok, acc)
        self._subscribe(symbols)

    def _auth(self, client_id, client_secret, access_token, account_id):
        r = ProtoOAApplicationAuthReq(); r.clientId=client_id; r.clientSecret=client_secret; self.client.send(r)
        r2 = ProtoOAAccountAuthReq(); r2.ctidTraderAccountId=account_id; r2.accessToken=access_token; self.client.send(r2)

    def _subscribe(self, symbols):
        req = ProtoOASubscribeSpotsReq()
        req.ctidTraderAccountId = self.account_id
        for s in symbols:
            req.symbolName.append(s)
        self.client.send(req)

    def _on_msg(self, client, message):
        try:
            payload = Protobuf.extract(message)
            if payload.get("payloadType","").endswith("SPOT_EVENT"):
                sym = payload.get("symbolName")
                bid = float(payload.get("bid", 0.0))/_SCALE
                ask = float(payload.get("ask", 0.0))/_SCALE
                if sym and bid>0 and ask>0:
                    # Infer pip size: 0.0001 default, 0.01 for 2dp
                    ps = 0.0001 if max(len(str(bid).split(".")[-1]), len(str(ask).split(".")[-1]))>2 else 0.01
                    spread_pips = (ask - bid)/ps
                    with self._lock:
                        self._rows.append((sym, datetime.now(timezone.utc), spread_pips))
        except Exception:
            pass

    def flush_minute(self, out_dir):
        os.makedirs(out_dir, exist_ok=True)
        with self._lock:
            if not self._rows: return
            df = pd.DataFrame(self._rows, columns=["symbol","time","spread_pips"])
            self._rows = []
        for sym, g in df.groupby("symbol"):
            g["bucket"] = g["time"].dt.floor("1min")
            agg = g.groupby("bucket")["spread_pips"].mean().reset_index()
            path = os.path.join(out_dir, f"{sym}.csv")
            if os.path.exists(path):
                old = pd.read_csv(path, parse_dates=["bucket"])
                agg = pd.concat([old, agg], ignore_index=True).drop_duplicates(subset=["bucket"]).sort_values("bucket")
            agg.to_csv(path, index=False)
