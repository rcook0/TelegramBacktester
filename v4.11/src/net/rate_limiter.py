import time, random, threading
class TokenBucket:
    def __init__(self, rate_per_sec: float, burst: int):
        self.rate=float(rate_per_sec); self.burst=int(burst); self.tokens=float(burst); self.last=time.monotonic(); self.lock=threading.Lock()
    def take(self, n: float=1.0) -> bool:
        with self.lock:
            now=time.monotonic(); elapsed=now-self.last; self.last=now; self.tokens=min(self.burst, self.tokens+elapsed*self.rate)
            if self.tokens>=n: self.tokens-=n; return True
            return False

def backoff(attempt: int, base_ms: int=200, cap_ms: int=5000) -> float:
    import random
    ms=min(cap_ms, base_ms*(2**attempt)); jitter=random.uniform(0.5,1.25); return (ms*jitter)/1000.0
