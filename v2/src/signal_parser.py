import re
from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime, timezone

@dataclass
class Signal:
    dt: datetime
    side: str
    symbol: str
    entry: float
    sl: float
    tps: list
    raw_text: str

SIG_RE = re.compile(
    r'(?P<side>BUY|SELL)\s+'
    r'(?P<symbol>[A-Z]{3,6})\s*'
    r'(?:@|at|entry[: ]+)?\s*(?P<entry>\d+(\.\d+)?).{0,50}?'
    r'(?:SL[: ]*(?P<sl>\d+(\.\d+)?)).{0,120}?'
    r'(?P<tps>(?:TP\d?\s*[: ]*\d+(\.\d+)?(?:\s*[,/ ]\s*)?)+)',
    re.IGNORECASE
)

TP_RE = re.compile(r'TP\d?\s*[: ]*(\d+(\.\d+)?)', re.IGNORECASE)

def parse_signals_from_messages(messages: List[Dict]) -> List[Signal]:
    signals: List[Signal] = []
    for m in messages:
        text = m["text"]
        dt = m["date"]
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        mo = SIG_RE.search(text.replace("\\n", " "))
        if not mo:
            continue
        side = mo.group("side").upper()
        symbol = mo.group("symbol").upper()
        entry = float(mo.group("entry"))
        sl = float(mo.group("sl"))
        tps = [float(x[0]) for x in TP_RE.findall(mo.group("tps"))]
        if len(tps)==0:
            continue
        signals.append(Signal(dt=dt, side=side, symbol=symbol, entry=entry, sl=sl, tps=tps, raw_text=text))
    return signals
