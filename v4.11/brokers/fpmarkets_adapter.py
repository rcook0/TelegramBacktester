from datetime import datetime
import pandas as pd
class FPMarketsProvider:
    def __init__(self, api_key: str = "", secret: str = ""): self.api_key=api_key; self.secret=secret
    def candles(self, symbol: str, start: datetime, end: datetime, timeframe="M1"):
        return pd.DataFrame(columns=["time","bid_open","bid_high","bid_low","bid_close","ask_open","ask_high","ask_low","ask_close","volume"])
