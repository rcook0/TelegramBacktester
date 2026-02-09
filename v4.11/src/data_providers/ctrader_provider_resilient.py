class ResilientCTraderProvider:
    def __init__(self, inner, heartbeat_sec=15.0, max_backoff=20.0, verbose=True):
        self.inner=inner
