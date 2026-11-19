from dataclasses import dataclass
import math
@dataclass
class Budget:
 max_candidates:int=100; max_usd:float=1.0; max_seconds:float=60.0; max_build_attempts:int=1000
 spent_candidates:int=0; spent_usd:float=0.0; build_attempts:int=0
 @classmethod
 def from_dict(cls,d):
  return cls(int(d.get("max_candidates",100)),float(d.get("max_usd",1)),float(d.get("max_seconds",60)),int(d.get("max_build_attempts",1000)))
 def __post_init__(self):
  if self.max_candidates<0 or self.max_usd<0 or self.max_seconds<0 or self.max_build_attempts<1: raise ValueError("invalid budget")
  if not math.isfinite(self.max_usd) or not math.isfinite(self.max_seconds): raise ValueError("budgets must be finite")
 def exhausted(self,elapsed):
  return self.spent_candidates>=self.max_candidates or self.spent_usd>=self.max_usd or elapsed>=self.max_seconds or self.build_attempts>=self.max_build_attempts