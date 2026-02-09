from datetime import datetime, timezone
from src.depth.depth_provider import CSVDepthProvider
from src.order_sim import OrderSimulator, OrderConfig

class Bar:
    def __init__(self, t, mid):
        self.time=t; self.mid_o=mid; self.mid_h=mid; self.mid_l=mid; self.mid_c=mid

def test_depth_entry_wap():
    dp = CSVDepthProvider('fixtures/depth')
    t = datetime(2025,10,1,10,0,0,tzinfo=timezone.utc)
    cfg = OrderConfig(side='LONG', entry_px=0, sl_px=0, tps_px=[], weights=[], risk_per_unit=1,
                      be_at_rr=None, trail_cfg=None, slippage_pips=0, slip_model='fixed',
                      pip_size=0.1, ioc=False, fill_model='depth', impact_k=0.0, depth_provider=dp,
                      symbol='XAUUSD', timestamp=t)
    sim = OrderSimulator(cfg)
    sim.on_bar(Bar(t, 2375.0))
    st, ev = sim.result()
    assert any(e.kind=='ENTRY' for e in ev)
