from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class ExecConfig:
    exec_mode: str = "dry"
    account_id: Optional[int] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    access_token: Optional[str] = None
    host: str = "LIVE"

class ITradeExecutor:
    def submit_market(self, symbol: str, side: str, qty: float, sl: Optional[float]=None, tps: Optional[List[float]]=None) -> str: ...
    def modify_sl_tp(self, order_id: str, sl: Optional[float]=None, tps: Optional[List[float]]=None) -> bool: ...
    def close(self, order_id: str, qty: Optional[float]=None) -> bool: ...
    def fetch_fills(self, order_id: str) -> List[Dict[str, Any]]: ...
    def account_info(self) -> Dict[str, Any]: ...
    def positions(self) -> List[Dict[str, Any]]: ...

class CTraderExecutor(ITradeExecutor):
    def __init__(self, cfg: ExecConfig):
        self.cfg = cfg
        self._id_seq = 0
        self._orders = {}
        self._fills = {}
    def _next_id(self) -> str:
        self._id_seq += 1
        return f"ORD-{self._id_seq:06d}"
    def submit_market(self, symbol: str, side: str, qty: float, sl: Optional[float]=None, tps: Optional[List[float]]=None) -> str:
        oid = self._next_id()
        self._orders[oid] = dict(symbol=symbol, side=side, qty=qty, sl=sl, tps=tps or [])
        return oid
    def modify_sl_tp(self, order_id: str, sl: Optional[float]=None, tps: Optional[List[float]]=None) -> bool:
        if order_id not in self._orders: return False
        if sl is not None: self._orders[order_id]['sl'] = sl
        if tps is not None: self._orders[order_id]['tps'] = tps
        return True
    def close(self, order_id: str, qty: Optional[float]=None) -> bool:
        return order_id in self._orders
    def fetch_fills(self, order_id: str):
        return self._fills.get(order_id, [])
    def account_info(self) -> Dict[str, Any]:
        return dict(equity=10000.0, free_margin=8000.0, currency="USD", leverage=500)
    def positions(self) -> List[Dict[str, Any]]:
        return []
