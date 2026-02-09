from dataclasses import dataclass
from typing import Literal, List, Dict, Any

Side = Literal['buy','sell']
Mode = Literal['none','paper','live']

@dataclass
class RiskRails:
    daily_loss_cap_pct: float = 5.0
    max_risk_pct: float = 2.0
    kill_switch: bool = True

@dataclass
class OrderSpec:
    symbol: str
    side: Side
    size_lots: float
    entry: float
    sl: float
    tps: List[float]
    comment: str = ''

class Broker:
    def __init__(self, mode: Mode, risk: RiskRails):
        self.mode = mode
        self.risk = risk
    def can_trade(self) -> bool:
        return self.mode in ('paper','live')
    def place(self, order: OrderSpec) -> Dict[str, Any]:
        raise NotImplementedError
    def amend(self, order_id: str, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError
    def cancel(self, order_id: str) -> Dict[str, Any]:
        raise NotImplementedError
    def positions(self) -> List[Dict[str, Any]]:
        raise NotImplementedError
