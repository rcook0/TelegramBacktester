def exp_backoff(attempt, base=0.5, factor=2.0, cap=30.0, jitter=0.4):
    attempt = max(0, int(attempt))
    raw = min(cap, base * (factor ** attempt))
    lo = raw * (1.0 - jitter)
    import random
    return lo + random.random() * (raw * jitter)
