from dataclasses import dataclass
from typing import Dict, Any
from .broker_base import Broker, OrderSpec

@dataclass
class LiveRouter:
    broker: Broker
    auto_confirm: bool = False
    def route_signal(self, sig: Dict[str, Any]) -> Dict[str, Any]:
        spec = OrderSpec(symbol=sig['symbol'], side=sig['side'], size_lots=sig['lots'],
                         entry=sig['entry'], sl=sig['sl'], tps=sig['tps'], comment=sig.get('comment',''))
        if not self.auto_confirm:
            return {'ok': False, 'pending': True, 'spec': spec.__dict__}
        return self.broker.place(spec)
