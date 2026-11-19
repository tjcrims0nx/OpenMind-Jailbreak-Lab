from dataclasses import dataclass
import math

@dataclass
class Budget:
    max_candidates:int=100
    max_usd:float=1.0
    max_seconds:float=60.0
    max_build_attempts:int=1000
    spent_candidates:int=0
    spent_usd:float=0.0
    build_attempts:int=0

    @classmethod
    def from_dict(cls,d):
        if not isinstance(d,dict): raise ValueError("budget must be an object")
        int_values={}
        for name,default in (("max_candidates",100),("max_build_attempts",1000)):
            value=d.get(name,default)
            if isinstance(value,bool) or not isinstance(value,int):
                raise ValueError(f"{name} must be an integer")
            int_values[name]=value
        float_values={}
        for name,default in (("max_usd",1.0),("max_seconds",60.0)):
            value=d.get(name,default)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite and numeric")
            float_values[name]=float(value)
        return cls(int_values["max_candidates"],float_values["max_usd"],
                   float_values["max_seconds"],int_values["max_build_attempts"])

    def __post_init__(self):
        for name,value,minimum in (
            ("max_candidates",self.max_candidates,0),
            ("max_build_attempts",self.max_build_attempts,1),
            ("spent_candidates",self.spent_candidates,0),
            ("build_attempts",self.build_attempts,0),
        ):
            if isinstance(value,bool) or not isinstance(value,int) or value<minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}")
        for name,value in (("max_usd",self.max_usd),("max_seconds",self.max_seconds),
                           ("spent_usd",self.spent_usd)):
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
                raise ValueError(f"{name} must be finite and non-negative")

    def exhausted(self,elapsed):
        return (self.spent_candidates>=self.max_candidates or
                self.spent_usd>=self.max_usd or
                elapsed>=self.max_seconds or
                self.build_attempts>=self.max_build_attempts)
