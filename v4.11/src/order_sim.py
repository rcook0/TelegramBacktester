from __future__ import annotations
from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple
from datetime import datetime, timedelta, timezone
try:
    from .depth.depth_provider import DepthProvider, DepthSnapshot
except Exception:
    DepthProvider = None  # type: ignore
from .execution.latency_guard import LatencyModel, AdverseWAPGuard
from .execution.live_control import LiveControl
from .indicators.atr import init_atr, update_atr

Side = Literal['LONG','SHORT']

@dataclass
class OrderConfig:
    side: Side
    entry_px: float
    sl_px: float
    tps_px: List[float]
    weights: List[float]
    risk_per_unit: float
    be_at_rr: Optional[float]
    trail_cfg: Optional[dict]
    slippage_pips: float
    slip_model: str
    pip_size: float
    ioc: bool
    fill_model: Literal['bar','depth'] = 'bar'
    impact_k: float = 0.0
    depth_provider: Optional[DepthProvider] = None
    symbol: Optional[str] = None
    timestamp: Optional[datetime] = None
    lat_model: Optional[LatencyModel] = None
    wap_guard: Optional[AdverseWAPGuard] = None
    ms_per_bar: float = 60_000.0
    be_mode: Literal['level','realized_r','time_and_r'] = 'level'
    be_min_minutes: int = 0
    live_control: Optional[LiveControl] = None

@dataclass
class Event:
    kind: Literal['ENTRY','TP','SL','EXIT','BE','TRAIL','SKIP']
    time: datetime
    px: float
    qty: float
    note: str = ''

class OrderSimulator:
    def __init__(self, cfg: OrderConfig):
        self.cfg = cfg
        self._events: List[Event] = []
        self._open_qty = 0.0
        self._state = 'INIT'
        self._entry_px: Optional[float] = None
        self._active_sl = cfg.sl_px
        self._tp_cursor = 0
        if self.cfg.weights and abs(sum(self.cfg.weights) - 1.0) > 1e-9:
            s = sum(self.cfg.weights)
            self.cfg.weights = [w/s for w in self.cfg.weights]
        self._last_bar_time: Optional[datetime] = None
        self._current_mid: Optional[float] = None
        self._entered_at: Optional[datetime] = None
        self._realized_pl_units: float = 0.0
        self._atr_state = None
        if self.cfg.trail_cfg and self.cfg.trail_cfg.get('type') in ('atr','atr-adaptive'):
            win = int(self.cfg.trail_cfg.get('win', 14))
            self._atr_state = init_atr(win)

    def on_bar(self, bar):
        self._last_bar_time = bar.time
        self._current_mid = bar.mid_c
        if self._atr_state is not None:
            update_atr(self._atr_state, bar.mid_h, bar.mid_l, bar.mid_c)
        if self.cfg.fill_model == 'depth' and self.cfg.depth_provider and self.cfg.symbol and self.cfg.timestamp:
            self._depth_step(bar)
        else:
            self._bar_step(bar)

    def result(self):
        return (self._state, list(self._events))

    def _bar_step(self, bar):
        if self._state == 'INIT':
            self._events.append(Event('ENTRY', bar.time, bar.mid_o, 1.0, 'bar entry'))
            self._open_qty = 1.0
            self._entry_px = bar.mid_o
            self._entered_at = bar.time
            self._state = 'OPEN'

    def _delay_minutes(self) -> int:
        if not self.cfg.lat_model: return 0
        return self.cfg.lat_model.delay_bars(self.cfg.ms_per_bar)

    def _snap_at(self, ts: datetime) -> Optional[DepthSnapshot]:
        delay_bars = self._delay_minutes()
        t_eff = (ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc))
        t_eff = t_eff + timedelta(minutes=delay_bars)
        return self.cfg.depth_provider.snapshot(self.cfg.symbol, t_eff)  # type: ignore

    def _consume(self, levels: List[Tuple[float,float]], need: float):
        remain, notional, filled = need, 0.0, 0.0
        for px, qty in levels:
            if remain <= 0: break
            if qty <= 0: continue
            take = min(qty, remain)
            notional += px * take; filled += take; remain -= take
        if filled <= 0: return (float('nan'), 0.0, remain)
        return (notional/filled, filled, remain)

    def _guard_ok(self, intended_px: float, wap: float) -> bool:
        if not self.cfg.wap_guard: return True
        return self.cfg.wap_guard.allowed(intended_px, wap)

    def _apply_live_overrides(self):
        lc = self.cfg.live_control
        if not lc: return
        for kind, val in lc.pull():
            if kind == "SET_SL":
                self._active_sl = float(val)
                self._events.append(Event('TRAIL', self._last_bar_time or self.cfg.timestamp, self._active_sl, 0.0, 'manual SL'))
            elif kind == "KILL" and self._open_qty > 0:
                px = self._current_mid or self._entry_px or 0.0
                self._events.append(Event('EXIT', self._last_bar_time or self.cfg.timestamp, px, self._open_qty, 'manual exit'))
                self._open_qty = 0.0
                self._state = 'CLOSED'

    def _live_R(self) -> float:
        if self._entry_px is None: return 0.0
        risk = abs(self._entry_px - self.cfg.sl_px)
        if risk <= 0: return 0.0
        mid = self._current_mid or self._entry_px
        if self.cfg.side == 'LONG':
            return max(0.0, (mid - self._entry_px) / risk)
        else:
            return max(0.0, (self._entry_px - mid) / risk)

    def _adaptive_mult(self, R: float) -> float:
        cfg = self.cfg.trail_cfg or {}
        base = float(cfg.get('base_mult', 2.0))
        clamp_min = float(cfg.get('clamp_mult_min', 0.8))
        clamp_max = float(cfg.get('clamp_mult_max', 3.0))
        mode = cfg.get('mode', 'piecewise')
        if mode == 'smooth':
            k = float(cfg.get('smooth_k', 1.5))
            mult = clamp_min + (base - clamp_min) / (1.0 + (R ** k))
        else:
            anchors = cfg.get('mult_at_r', {})
            pts = sorted((float(r), float(m)) for r, m in anchors.items())
            if not pts:
                mult = base
            elif R <= pts[0][0]:
                mult = pts[0][1]
            elif R >= pts[-1][0]:
                mult = pts[-1][1]
            else:
                mult = base
                for i in range(1, len(pts)):
                    r0, m0 = pts[i-1]; r1, m1 = pts[i]
                    if r0 <= R <= r1:
                        t = (R - r0) / max(1e-9, (r1 - r0))
                        mult = m0 + t * (m1 - m0)
                        break
        return max(clamp_min, min(clamp_max, mult))

    def _apply_trailing(self):
        if not self.cfg.trail_cfg or self._current_mid is None: return
        t = self.cfg.trail_cfg.get('type','fixed')
        if t == 'fixed':
            pips = float(self.cfg.trail_cfg.get('pips', 0.0))
            if pips <= 0: return
            pip = self.cfg.pip_size
            if self.cfg.side == 'LONG':
                trail_sl = self._current_mid - pips * pip
                if trail_sl > self._active_sl:
                    self._active_sl = trail_sl
                    self._events.append(Event('TRAIL', self._last_bar_time, self._active_sl, 0.0, 'trail fixed'))
            else:
                trail_sl = self._current_mid + pips * pip
                if trail_sl < self._active_sl:
                    self._active_sl = trail_sl
                    self._events.append(Event('TRAIL', self._last_bar_time, self._active_sl, 0.0, 'trail fixed'))
        elif t == 'atr':
            if self._atr_state is None or self._atr_state.atr is None: return
            atr = self._atr_state.atr
            if self.cfg.side == 'LONG':
                trail_sl = self._current_mid - float(self.cfg.trail_cfg.get('mult', 2.0)) * atr
                if trail_sl > self._active_sl:
                    self._active_sl = trail_sl
                    self._events.append(Event('TRAIL', self._last_bar_time, self._active_sl, 0.0, 'trail atr'))
            else:
                trail_sl = self._current_mid + float(self.cfg.trail_cfg.get('mult', 2.0)) * atr
                if trail_sl < self._active_sl:
                    self._active_sl = trail_sl
                    self._events.append(Event('TRAIL', self._last_bar_time, self._active_sl, 0.0, 'trail atr'))
        elif t == 'atr-adaptive':
            if self._atr_state is None or self._atr_state.atr is None: return
            atr = self._atr_state.atr
            R = self._live_R()
            mult = self._adaptive_mult(R)
            if self.cfg.side == 'LONG':
                trail_sl = self._current_mid - mult * atr
                if trail_sl > self._active_sl:
                    self._active_sl = trail_sl
                    self._events.append(Event('TRAIL', self._last_bar_time, self._active_sl, 0.0, f'trail atr-adaptive R={R:.2f} mult={mult:.2f}'))
            else:
                trail_sl = self._current_mid + mult * atr
                if trail_sl < self._active_sl:
                    self._active_sl = trail_sl
                    self._events.append(Event('TRAIL', self._last_bar_time, self._active_sl, 0.0, f'trail atr-adaptive R={R:.2f} mult={mult:.2f}'))

    def _depth_step(self, bar):
        if self._state == 'INIT':
            snap = self._snap_at(self.cfg.timestamp)
            if not snap: return
            levels = snap.asks if self.cfg.side=='LONG' else snap.bids
            wap, filled, remain = self._consume(levels, 1.0)
            if filled < 1.0 and self.cfg.impact_k>0 and remain>0:
                adj = self.cfg.impact_k * remain
                wap = wap + (adj if self.cfg.side=='LONG' else -adj)
                filled = 1.0
            intended = self.cfg.entry_px if self.cfg.entry_px>0 else bar.mid_o
            if not self._guard_ok(intended, wap):
                self._events.append(Event('EXIT', bar.time, float('nan'), 0.0, 'entry rejected by guard'))
                self._state = 'REJECTED'; return
            self._events.append(Event('ENTRY', bar.time, wap, 1.0, f'depth entry (lat={self._delay_minutes()} bars)'))
            self._open_qty = 1.0
            self._entry_px = wap
            self._entered_at = bar.time
            self._state = 'OPEN'
            return

        if self._state == 'OPEN' and self._open_qty > 0:
            self._apply_live_overrides()
            if self._state != 'OPEN': return
            snap = self._snap_at(bar.time)
            if not snap: return
            self._apply_trailing()
            sl_levels = ([(px,q) for px,q in snap.bids if px <= self._active_sl] if self.cfg.side=='LONG'
                         else [(px,q) for px,q in snap.asks if px >= self._active_sl])
            if sl_levels:
                wap, filled, _ = self._consume(sl_levels, self._open_qty)
                if filled > 0 and self._guard_ok(self._active_sl, wap):
                    self._events.append(Event('SL', bar.time, wap, filled, 'depth SL'))
                    self._open_qty -= filled
                    if self._open_qty <= 0: self._state = 'CLOSED'; return
            if self.cfg.tps_px and self.cfg.weights:
                for i in range(self._tp_cursor, len(self.cfg.tps_px)):
                    tp = self.cfg.tps_px[i]; w = self.cfg.weights[i]
                    if w <= 0: self._tp_cursor = i+1; continue
                    need = min(self._open_qty, w)
                    if need <= 0: self._tp_cursor = i+1; continue
                    levels = ([(px,q) for px,q in snap.bids if px >= tp] if self.cfg.side=='LONG'
                              else [(px,q) for px,q in snap.asks if px <= tp])
                    if not levels: continue
                    wap, filled, rem = self._consume(levels, need)
                    if filled > 0 and self._guard_ok(tp, wap):
                        self._events.append(Event('TP', bar.time, wap, filled, f'tp{i+1}'))
                        self._open_qty -= filled
                        self._realized_pl_units += filled
                        if filled >= need - 1e-9: self._tp_cursor = i+1
                    if self._open_qty <= 0: self._state = 'CLOSED'; return
