from __future__ import annotations

DEFAULT_PACKS = {
  "shadow_gate_v1": {
    "version": "1.0",
    "description": "Baseline shadow parity thresholds for slippage, latency, and P&L sanity.",
    "rules": [
      {"id":"slip_total_warn", "metric":"recon.total_slip_pips", "op":"<=", "value": 2.0, "severity":"WARN", "weight": 0.25},
      {"id":"slip_total_error","metric":"recon.total_slip_pips", "op":"<=", "value": 5.0, "severity":"ERROR","weight": 0.45},

      {"id":"lat_entry_warn", "metric":"recon.latency_entry_sec", "op":"<=", "value": 2.0, "severity":"WARN", "weight": 0.10},
      {"id":"lat_entry_error","metric":"recon.latency_entry_sec", "op":"<=", "value": 8.0, "severity":"ERROR","weight": 0.20},

      {"id":"pnl_required", "metric":"pnl.pnl_ccy", "op":"exists", "value": True, "severity":"ERROR", "weight": 0.35},
      {"id":"pnl_floor_warn", "metric":"pnl.pnl_ccy", "op":">=", "value": -500.0, "severity":"WARN", "weight": 0.15, "when":"pnl.pnl_ccy exists"},
    ],
    "scoring": {
      "method": "weighted_penalty",
      "warn_penalty": 0.25,
      "error_penalty": 1.0,
      "pass_score": 0.75,
    }
  }
}
