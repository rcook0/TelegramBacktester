from datetime import datetime, timezone
from src.reconcile.schemas import ShadowRecord, ModelTrace, ModelEvent, QuoteSnapshot
from src.reconcile.comparator import reconcile

def test_entry_delta():
  idem='k'
  model=ModelTrace(idem_key=idem, symbol='XAUUSD', side='LONG', events=[ModelEvent(ts=datetime.now(timezone.utc), kind='ENTRY', px=100.0, qty=1.0)])
  shadow=ShadowRecord(idem_key=idem, channel='c', signal_ts=datetime.now(timezone.utc), symbol='XAUUSD', side='LONG', quotes=[QuoteSnapshot(ts=datetime.now(timezone.utc), symbol='XAUUSD', bid=99.9, ask=100.1, mid=100.05, spread_pips=2.0)])
  d=reconcile(shadow, model, pip_size=0.1)
  assert d.delta_entry_pips is not None
