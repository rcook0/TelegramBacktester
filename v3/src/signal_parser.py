import re
from dataclasses import dataclass
from typing import List, Dict
from datetime import datetime, timezone
@dataclass
class Signal:
    dt: datetime; side: str; symbol: str; entry: float; sl: float; tps: list; raw_text: str
SIG_RE = re.compile(r'(?P<side>BUY|SELL)\s+(?P<symbol>[A-Z]{3,6})\s*(?:@|at|entry[: ]+)?\s*(?P<entry>\d+(\.\d+)?).{0,50}?(?:SL[: ]*(?P<sl>\d+(\.\d+)?)).{0,120}?(?P<tps>(?:TP\d?\s*[: ]*\d+(\.\d+)?(?:\s*[,/ ]\s*)?)+)', re.IGNORECASE)
TP_RE = re.compile(r'TP\d?\s*[: ]*(\d+(\.\d+)?)', re.IGNORECASE)
def parse_signals_from_messages(messages: List[Dict]) -> List[Signal]:
    out = []
    for m in messages:
        t = m["text"]; dt = m["date"]; 
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        mo = SIG_RE.search(t.replace("\\n", " ")); 
        if not mo: continue
        side = mo.group("side").upper(); sym = mo.group("symbol").upper()
        entry = float(mo.group("entry")); sl = float(mo.group("sl")); tps = [float(x[0]) for x in TP_RE.findall(mo.group("tps"))]
        if not tps: continue
        out.append(Signal(dt=dt, side=side, symbol=sym, entry=entry, sl=sl, tps=tps, raw_text=t))
    return out
