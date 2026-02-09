class LiveControl:
    def __init__(self):
        self._inbox = []
    def set_sl(self, px: float):
        self._inbox.append(("SET_SL", float(px)))
    def kill_trade(self):
        self._inbox.append(("KILL", None))
    def pull(self):
        msgs, self._inbox = self._inbox, []
        return msgs
