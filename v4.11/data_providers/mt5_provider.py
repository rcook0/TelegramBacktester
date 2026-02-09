from datetime import datetime
import pandas as pd
try:
    import MetaTrader5 as mt5; MT5_AVAILABLE = True
except Exception: MT5_AVAILABLE = False
class MT5Provider:
    def __init__(self):
        if not MT5_AVAILABLE: raise RuntimeError("MetaTrader5 package not available")
        if not mt5.initialize(): raise RuntimeError("Failed to initialize MetaTrader5")
    def __del__(self):
        try: mt5.shutdown()
        except Exception: pass
    def candles(self, symbol: str, start: datetime, end: datetime, timeframe="M1"):
        tf_map = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1}
        tf = tf_map.get(timeframe, mt5.TIMEFRAME_M1); rates = mt5.copy_rates_range(symbol, tf, start, end)
        if rates is None: return pd.DataFrame(columns=["time","open","high","low","close","volume"])
        df = pd.DataFrame(rates); df["time"] = pd.to_datetime(df["time"], unit="s")
        return df[["time","open","high","low","close","tick_volume"]].rename(columns={"tick_volume":"volume"})
