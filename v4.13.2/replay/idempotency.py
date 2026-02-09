import hashlib, json

def _norm(x):
  if isinstance(x,float): return round(x,5)
  if isinstance(x,list): return [_norm(v) for v in x]
  if isinstance(x,dict): return {k:_norm(x[k]) for k in sorted(x)}
  return x

def signal_idem_key(payload: dict) -> str:
  raw=json.dumps(_norm(payload), separators=(',',':'), ensure_ascii=False)
  return hashlib.sha256(raw.encode('utf-8')).hexdigest()
