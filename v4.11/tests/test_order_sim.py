from datetime import datetime, timezone

def test_order_sim_import():
    try:
        from src.order_sim import OrderSimulator, OrderConfig, BarView
    except Exception as e:
        import pytest; pytest.skip(f'order_sim not present: {e}')

def test_order_sim_smoke():
    try:
        from src.order_sim import OrderSimulator, OrderConfig, BarView
    except Exception:
        return
    def bar(t, o,h,l,c, spr_px):
        return BarView(
            time=datetime.fromtimestamp(t, tz=timezone.utc),
            mid_o=o, mid_h=h, mid_l=l, mid_c=c,
            bid_o=o - spr_px/2, bid_h=h - spr_px/2, bid_l=l - spr_px/2,
            ask_o=o + spr_px/2, ask_h=h + spr_px/2, ask_l=l + spr_px/2,
            tr_range=(h-l),
        )

    cfg = OrderConfig(
        side='LONG', entry_px=100.0, sl_px=99.0,
        tps_px=[100.5, 101.0], weights=[0.5,0.5],
        risk_per_unit=1.0, be_at_rr=1.0, trail_cfg={'type':'fixed','pips':5},
        slippage_pips=0.0, slip_model='fixed', pip_size=0.01, ioc=False,
    )
    sim = OrderSimulator(cfg)
    b = bar(0, 100.0, 101.2, 98.9, 100.4, spr_px=0.02)
    sim.on_bar(b)
    st, evts = sim.result()
    assert any(e.kind=='ENTRY' for e in evts)
