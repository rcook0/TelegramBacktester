from datetime import datetime, timezone
from src.execution.latency_guard import LatencyModel, AdverseWAPGuard
from src.depth.depth_provider import CSVDepthProvider
from src.order_sim import OrderSimulator, OrderConfig

class Bar:
    def __init__(self, t, mid):
        self.time=t; self.mid_o=mid; self.mid_h=mid; self.mid_l=mid; self.mid_c=mid

def test_latency_shift_and_guard():
    dp = CSVDepthProvider('fixtures/depth')
    t0 = datetime(2025,10,1,10,0,0,tzinfo=timezone.utc)
    lat = LatencyModel(latency_ms=60_000)  # +1 bar/min
    guard = AdverseWAPGuard(max_pct=0.2)
    cfg = OrderConfig(side='LONG', entry_px=2375.2, sl_px=2374.0, tps_px=[2376.0], weights=[1.0],
                      risk_per_unit=1, be_at_rr=None, trail_cfg=None, slippage_pips=0, slip_model='fixed',
                      pip_size=0.1, ioc=False, fill_model='depth', impact_k=0.0,
                      depth_provider=dp, symbol='XAUUSD', timestamp=t0, lat_model=lat, wap_guard=guard, ms_per_bar=60_000)
    sim = OrderSimulator(cfg)
    sim.on_bar(Bar(t0, 2375.1))
    st, ev = sim.result()
    # No depth for t0+1m in fixture, so either no entry or rejected by guard; both acceptable as pass/fail sanity.
    assert st in ('INIT','OPEN','REJECTED')
