from src.risk.risk_gate import RiskGate, GateConfig
from src.execution.trade_executor import CTraderExecutor, ExecConfig

def test_gate_blocks_on_spread_and_wap():
    gate = RiskGate(GateConfig(spread_ceil_pips=1.0, max_adverse_wap_pct=0.3), CTraderExecutor(ExecConfig()))
    d = gate.decide(symbol='XAUUSD', side='LONG', lot=0.1, entry_px=100.0, sl_px=99.0,
                    intended_wap=101.0, spread_pips=2.0, pip_value_usd=10.0)
    assert not d.allow
    assert any('spread' in r or 'wap' in r for r in d.reasons)

def test_gate_allows_clean_case():
    gate = RiskGate(GateConfig(spread_ceil_pips=2.0, max_adverse_wap_pct=2.0, whitelist=['XAUUSD']), CTraderExecutor(ExecConfig()))
    d = gate.decide(symbol='XAUUSD', side='LONG', lot=0.1, entry_px=100.0, sl_px=99.5,
                    intended_wap=100.1, spread_pips=0.5, pip_value_usd=10.0)
    assert d.allow
