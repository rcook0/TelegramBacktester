from dataclasses import dataclass
from typing import Dict
@dataclass
class Contract:
  contract_size: float
  pip_size: float
  tick_size: float
  price_dp: int
  min_lot: float
  lot_step: float
  value_ccy: str
class PipEngine:
  def __init__(self, aliases: Dict[str,str], contracts: Dict[str,Contract]):
    self.aliases=aliases or {}; self.contracts=contracts or {}
  def canonical(self,s): return self.aliases.get(s,s)
  def pip_size(self,s): return self.contracts[self.canonical(s)].pip_size
