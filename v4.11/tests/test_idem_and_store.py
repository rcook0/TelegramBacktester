from src.replay.idempotency import signal_idem_key
from src.storage.sqlite_store import Store

def test_idem_stability_and_perturb():
    p=dict(channel='c', minute='2025-10-01T10:00', side='LONG', symbol='XAUUSD', entry=2375.20001, sl=2373.8, tps=[2376.0,2376.5000])
    a=signal_idem_key(p); b=signal_idem_key(dict(p)); assert a==b
    c=signal_idem_key({**p,'entry':2375.21}); assert a!=c

def test_store_basics(tmp_path):
    s=Store(str(tmp_path/'t.db')); rid=s.new_run({'x':1}); sid=s.upsert_signal('k','2025-10-01T10:00:00Z','chan',{'p':1})
    dec=s.add_decision(sid, True, []); oid=s.add_order(sid, 'ORD-1','LONG','XAUUSD',0.1,2373.8,[2376.0]); s.add_fill(oid,2375.25,0.05,'tp1'); s.add_pnl(sid,12.3,0.5,11.8,'USD')
