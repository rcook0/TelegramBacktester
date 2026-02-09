from datetime import datetime, timezone
from src.depth.ctrader_depth_provider import CTraderDepthProvider
from src.order_sim_depth import DepthExecutor

def test_ctrader_adapter_partial_fill():
    dp = CTraderDepthProvider()
    t = datetime(2025,10,1,10,0,0,tzinfo=timezone.utc)
    # Build ask book for LONG entries: 0.4 + 0.3 + 0.2 lots
    dp.on_depth('XAUUSD', t, 'ask', 2375.2, 0.4, 'set')
    dp.on_depth('XAUUSD', t, 'ask', 2375.3, 0.3, 'set')
    dp.on_depth('XAUUSD', t, 'ask', 2375.5, 0.2, 'set')
    ex = DepthExecutor(dp, impact_k=0.0)
    fill = ex.entry('XAUUSD', t, 'LONG', 0.7)
    assert abs(fill.qty_lots - 0.7) < 1e-9
    assert fill.px > 2375.2 and fill.px < 2375.4  # WAP between levels
