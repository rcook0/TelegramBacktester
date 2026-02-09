from __future__ import annotations
import argparse
from datetime import datetime, timezone
from ..storage.sqlite_store_shadow import ShadowStore
from ..replay.idempotency import signal_idem_key
from ..reconcile.schemas import ShadowRecord, ModelTrace, ModelEvent, QuoteSnapshot
from ..reconcile.comparator import reconcile
from ..pricing.pips import PipEngine, Contract

def parse_args():
  p=argparse.ArgumentParser(description='Shadow scaffold')
  p.add_argument('--db', required=True)
  p.add_argument('--channel', required=True)
  p.add_argument('--symbol', default='XAUUSD')
  p.add_argument('--side', default='LONG')
  return p.parse_args()

def main():
  a=parse_args(); store=ShadowStore(a.db)
  sig=dict(channel=a.channel, minute=datetime.now(timezone.utc).isoformat()[:16], side=a.side, symbol=a.symbol, entry=2375.2, sl=2373.8, tps=[2376.0])
  idem=signal_idem_key(sig)
  sid=store.upsert_signal(idem, datetime.now(timezone.utc).isoformat(), a.channel, sig)
  model=ModelTrace(idem_key=idem, symbol=a.symbol, side=a.side, events=[ModelEvent(ts=datetime.now(timezone.utc), kind='ENTRY', px=2375.25, qty=1.0, note='sim')])
  shadow=ShadowRecord(idem_key=idem, channel=a.channel, signal_ts=datetime.now(timezone.utc), symbol=a.symbol, side=a.side, quotes=[QuoteSnapshot(ts=datetime.now(timezone.utc), symbol=a.symbol, bid=2375.2, ask=2375.4, mid=2375.3, spread_pips=2.0)])
  store.add_shadow_snapshot(sid, 'quote', shadow.quotes[0].__dict__)
  pe=PipEngine({}, {a.symbol: Contract(contract_size=100, pip_size=0.1, tick_size=0.01, price_dp=2, min_lot=0.01, lot_step=0.01, value_ccy='USD')})
  diff=reconcile(shadow, model, pe.pip_size(a.symbol))
  store.add_reconcile_diff(sid, diff.__dict__)
  print('diff', diff)

if __name__=='__main__': main()
