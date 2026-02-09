from __future__ import annotations
from dataclasses import dataclass

@dataclass
class ATRState:
    win: int
    alpha: float
    prev_close: float | None = None
    atr: float | None = None

def true_range(h: float, l: float, pc: float | None):
    if pc is None:
        return float(h - l)
    return max(h - l, abs(h - pc), abs(l - pc))

def init_atr(win: int) -> ATRState:
    alpha = 2.0 / (win + 1.0)
    return ATRState(win=win, alpha=alpha)

def update_atr(state: ATRState, h: float, l: float, c: float) -> float:
    tr = true_range(h, l, state.prev_close)
    if state.atr is None:
        state.atr = tr
    else:
        state.atr = state.atr + state.alpha * (tr - state.atr)
    state.prev_close = c
    return state.atr
