from __future__ import annotations
from typing import Optional
from .schemas import ShadowRecord, ModelTrace, ReconcileDiff

def _first_model_entry(trace: ModelTrace) -> Optional[float]:
  for e in trace.events:
    if e.kind.upper()=='ENTRY': return e.px
  return None

def _first_broker_px(shadow: ShadowRecord) -> Optional[float]:
  if shadow.fills: return shadow.fills[0].get('px')
  if shadow.quotes: return shadow.quotes[0].mid
  return None

def reconcile(shadow: ShadowRecord, model: ModelTrace, pip_size: float) -> ReconcileDiff:
  d=ReconcileDiff(idem_key=shadow.idem_key, symbol=shadow.symbol, side=shadow.side)
  me=_first_model_entry(model); be=_first_broker_px(shadow)
  d.entry_px_model=me; d.entry_px_broker=be
  if me is not None and be is not None and pip_size>0:
    d.delta_entry_pips = (be-me)/pip_size if shadow.side=='LONG' else (me-be)/pip_size
  d.notes.append('WAP/spread/latency reconciliation pending capture + trace enrichment.')
  return d
