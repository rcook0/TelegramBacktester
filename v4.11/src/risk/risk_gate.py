from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from datetime import datetime, time, timezone

@dataclass
class GateConfig:
    spread_ceil_pips: float = 0.0
    max_adverse_wap_pct: float = 0.0
    max_sym_risk: float = 0.03
    max_total_risk: float = 0.06
    whitelist: Optional[List[str]] = None
    sessions: Optional[List[str]] = None
    tz: str = 'UTC'

@dataclass
class Decision:
    allow: bool
    reasons: List[str]

class RiskGate:
    def __init__(self, cfg: GateConfig, exec_iface):
        self.cfg = cfg
        self.exec = exec_iface
    @staticmethod
    def _in_session(now: datetime, sessions: Optional[List[str]]) -> bool:
        if not sessions: return True
        windows = {'AS': (time(0,0), time(8,0)), 'LON': (time(7,0), time(16,0)), 'NY': (time(12,0), time(21,0))}
        for s in sessions:
            if s not in windows: continue
            lo, hi = windows[s]
            if lo <= now.time() <= hi: return True
        return False
    def decide(self, *, symbol: str, side: str, lot: float, entry_px: float,
               sl_px: float, intended_wap: float, spread_pips: float,
               pip_value_usd: float) -> Decision:
        eq = float(self.exec.account_info().get('equity', 0.0))
        fm = float(self.exec.account_info().get('free_margin', 0.0))
        reasons: List[str] = []
        if self.cfg.whitelist and symbol not in self.cfg.whitelist:
            reasons.append(f"symbol {symbol} not whitelisted")
        now = datetime.now(timezone.utc)
        if not self._in_session(now, self.cfg.sessions):
            reasons.append("outside allowed session")
        if self.cfg.spread_ceil_pips > 0 and spread_pips > self.cfg.spread_ceil_pips:
            reasons.append(f"spread {spread_pips:.2f} > ceil {self.cfg.spread_ceil_pips:.2f}")
        if self.cfg.max_adverse_wap_pct > 0 and entry_px > 0:
            dev = abs(intended_wap - entry_px) / entry_px * 100.0
            if dev > self.cfg.max_adverse_wap_pct:
                reasons.append(f"adverse wap {dev:.2f}% > {self.cfg.max_adverse_wap_pct:.2f}%")
        risk_per_lot_usd = abs(entry_px - sl_px) * pip_value_usd
        sym_risk = lot * risk_per_lot_usd
        if eq > 0 and sym_risk / eq > self.cfg.max_sym_risk:
            reasons.append(f"symbol risk {sym_risk/eq:.3%} > {self.cfg.max_sym_risk:.1%}")
        if fm <= 0 or fm < sym_risk * 2:
            reasons.append("insufficient free margin for safety")
        allow = len(reasons) == 0
        return Decision(allow=allow, reasons=reasons)
