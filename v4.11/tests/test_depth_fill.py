from datetime import datetime, timezone
from src.depth.depth_provider import CSVDepthProvider
from src.order_sim_depth import DepthExecutor, DepthConfig

def ts():
    return datetime(2025,10,1,10,0,0,tzinfo=timezone.utc)

def test_entry_wap_long(tmp_path):
    # copy fixture
    import shutil, os
    fixt = os.path.join(os.path.dirname(__file__), "..", "fixtures", "depth")
    dst = tmp_path / "depth"; shutil.copytree(fixt, dst)
    dp = CSVDepthProvider(str(dst))
    ex = DepthExecutor(dp, impact_k=0.0)
    # consume 0.7 lots from asks at 2375.2 (0.6) and 2375.4 (0.1)
    fill = ex.entry("XAUUSD", ts(), "LONG", 0.7)
    assert fill.qty_lots == 0.7
    assert abs(fill.px - ((2375.2*0.6 + 2375.4*0.1)/0.7)) < 1e-6

def test_partial_and_impact_short(tmp_path):
    import shutil, os
    fixt = os.path.join(os.path.dirname(__file__), "..", "fixtures", "depth")
    dst = tmp_path / "depth"; shutil.copytree(fixt, dst)
    dp = CSVDepthProvider(str(dst))
    ex = DepthExecutor(dp, impact_k=0.2)
    # ask side only 2.0 lots total; request more to trigger impact adj
    fill = ex.entry("EURUSD", ts(), "SHORT", 3.0)
    assert fill.qty_lots == 2.0
    # with impact_k>0, px should be adjusted downward for SHORT if partially filled
    assert fill.px < 1.1002
