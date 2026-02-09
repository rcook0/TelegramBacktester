from datetime import datetime, timezone
from src.depth.depth_provider import CSVDepthProvider
from src.order_sim import OrderSimulator, OrderConfig
from src.execution.latency_guard import LatencyModel, AdverseWAPGuard
from src.execution.live_control import LiveControl

class Bar:
    def __init__(self, t, o,h,l,c):
        self.time=t; self.mid_o=o; self.mid_h=h; self.mid_l=l; self.mid_c=c

def test_adaptive_mult_and_manual_sl():
    dp = CSVDepthProvider('fixtures/depth')
    t = datetime(2025,10,1,10,0,0,tzinfo=timezone.utc)
    lc = LiveControl()
    cfg = OrderConfig(side='LONG', entry_px=0, sl_px=2374.0, tps_px=[2375.6], weights=[1.0],
                      risk_per_unit=1, be_at_rr=None,
                      trail_cfg={'type':'atr-adaptive','win':5,'base_mult':2.0,'mult_at_r':{'0.5':2.0,'1.0':1.5,'2.0':1.0}},
                      slippage_pips=0, slip_model='fixed', pip_size=0.1, ioc=False, fill_model='depth',
                      impact_k=0.0, depth_provider=dp, symbol='XAUUSD', timestamp=t, ms_per_bar=60_000,
                      lat_model=LatencyModel(0), wap_guard=AdverseWAPGuard(1.0), live_control=lc)
    sim = OrderSimulator(cfg)
    sim.on_bar(Bar(t, 2375.2, 2375.7, 2375.1, 2375.5))
    lc.set_sl(2375.3)
    sim.on_bar(Bar(t, 2375.5, 2376.0, 2375.4, 2375.8))
    st, ev = sim.result()
    assert any(e.kind=='ENTRY' for e in ev)
    assert any(e.kind=='TRAIL' and 'manual SL' in e.note for e in ev)
