from dataclasses import dataclass, field
from typing import Dict, Any, List
from datetime import datetime, timezone
import uuid
from .broker_base import Broker, RiskRails, OrderSpec

@dataclass
class PaperBroker(Broker):
    ledger: List[Dict[str, Any]] = field(default_factory=list)
    open_positions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    day_pnl: float = 0.0
    def __init__(self, risk: RiskRails):
        super().__init__(mode='paper', risk=risk)
        self.ledger = []
        self.open_positions = {}
        self.day_pnl = 0.0
    def _new_id(self) -> str:
        return str(uuid.uuid4())
    def place(self, order: OrderSpec) -> Dict[str, Any]:
        oid = self._new_id()
        now = datetime.now(timezone.utc).isoformat()
        pos = {'id': oid, 'symbol': order.symbol, 'side': order.side, 'lots': order.size_lots,
               'entry': order.entry, 'sl': order.sl, 'tps': order.tps, 'time': now, 'state': 'open'}
        self.open_positions[oid] = pos
        self.ledger.append({'time': now, 'event': 'place', 'id': oid, 'data': pos})
        return {'ok': True, 'id': oid}
    def amend(self, order_id: str, **kwargs) -> Dict[str, Any]:
        pos = self.open_positions.get(order_id)
        if not pos: return {'ok': False, 'error': 'not_found'}
        pos.update(kwargs)
        self.ledger.append({'time': datetime.now(timezone.utc).isoformat(), 'event': 'amend', 'id': order_id, 'data': kwargs})
        return {'ok': True, 'id': order_id}
    def cancel(self, order_id: str) -> Dict[str, Any]:
        if order_id in self.open_positions:
            self.open_positions.pop(order_id)
            self.ledger.append({'time': datetime.now(timezone.utc).isoformat(), 'event': 'cancel', 'id': order_id})
            return {'ok': True}
        return {'ok': False, 'error': 'not_found'}
    def positions(self) -> List[Dict[str, Any]]:
        return list(self.open_positions.values())
