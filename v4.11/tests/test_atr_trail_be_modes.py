from datetime import datetime, timezone
from src.depth.depth_provider import CSVDepthProvider
from src.order_sim import OrderSimulator, OrderConfig
from src.execution.latency_guard import LatencyModel, AdverseWAPGuard

class Bar:
    def __init__(self, t, o,h,l,c):
        self.time=t; self.mid_o=o; self.mid_h=h; self.mid_l=l; self.mid_c=c

def test_depth_entry_and_be_realized():
    dp = CSVDepthProvider('fixtures/depth')
    t = datetime(2025,10,1,10,0,0,tzinfo=timezone.utc)
    cfg = OrderConfig(side='LONG', entry_px=0, sl_px=2374.0, tps_px=[2375.4, 2375.6], weights=[0.5,0.5],
                      risk_per_unit=1, be_at_rr=0.5, be_mode='realized_r', trail_cfg={'type':'atr','win':5,'mult':1.0},
                      slippage_pips=0, slip_model='fixed', pip_size=0.1, ioc=False, fill_model='depth',
                      impact_k=0.0, depth_provider=dp, symbol='XAUUSD', timestamp=t, ms_per_bar=60_000,
                      lat_model=LatencyModel(0), wap_guard=AdverseWAPGuard(0.5))
    sim = OrderSimulator(cfg)
    sim.on_bar(Bar(t, 2375.2, 2375.7, 2375.1, 2375.5))
    st, ev = sim.result()
    assert any(e.kind=='ENTRY' for e in ev)
