from __future__ import annotations
import hashlib,json,math
from dataclasses import dataclass,field
from enum import Enum
from typing import Callable,Iterable

class Kind(str,Enum):
    TEXT="text"
    BASE64="base64"
    HEX="hex"
    ROT13="rot13"

@dataclass(frozen=True)
class TransformSpec:
    name:str
    fn:Callable
    input_kind:Kind=Kind.TEXT
    output_kind:Kind=Kind.TEXT
    cost:float=1.0
    semantic_delta:float=0.0
    tags:tuple[str,...]=()
    version:int=1
    description:str=""
    touches:str="all"
    structured_output:bool=False

class Registry:
    def __init__(self): self._specs={}
    def register(self,spec):
        if not isinstance(spec,TransformSpec): raise TypeError("registry accepts TransformSpec instances")
        if not isinstance(spec.name,str) or not spec.name.strip(): raise ValueError("transform name must be non-empty")
        if not callable(spec.fn): raise ValueError("transform function must be callable")
        if spec.name in self._specs: raise ValueError(f"duplicate transform: {spec.name}")
        if not isinstance(spec.input_kind,Kind) or not isinstance(spec.output_kind,Kind):
            raise ValueError("transform input_kind and output_kind must be Kind values")
        if isinstance(spec.cost,bool) or not isinstance(spec.cost,(int,float)) or not math.isfinite(spec.cost) or spec.cost<0:
            raise ValueError("transform cost must be finite and non-negative")
        if isinstance(spec.semantic_delta,bool) or not isinstance(spec.semantic_delta,(int,float)) or not math.isfinite(spec.semantic_delta) or not 0<=spec.semantic_delta<=1:
            raise ValueError("semantic_delta must be finite and between 0 and 1")
        if isinstance(spec.version,bool) or not isinstance(spec.version,int) or spec.version<1:
            raise ValueError("transform version must be a positive integer")
        if spec.touches not in ("all","prefix","blob","suffix"): raise ValueError("touches must be all, prefix, blob, or suffix")
        if spec.touches!="all" and spec.structured_output: raise ValueError("only whole-value transforms may create structured values")
        if spec.touches in ("prefix","suffix") and (spec.input_kind is not Kind.TEXT or spec.output_kind is not Kind.TEXT):
            raise ValueError("prefix and suffix transforms must preserve TEXT kind")
        self._specs[spec.name]=spec
        return spec
    def get(self,name):
        if name not in self._specs: raise KeyError(f"unknown transform {name!r}; registered: {sorted(self._specs)}")
        return self._specs[name]
    def names(self): return sorted(self._specs)
    def __iter__(self): return iter(self._specs.values())

REGISTRY=Registry()
def transform(name,*,input_kind=Kind.TEXT,output_kind=Kind.TEXT,cost=1.0,semantic_delta=0.0,
              tags:Iterable[str]=(),version=1,description="",touches="all",structured_output=False):
    def deco(fn):
        REGISTRY.register(TransformSpec(name,fn,input_kind,output_kind,cost,semantic_delta,
                         tuple(tags),version,description,touches,structured_output))
        return fn
    return deco

@dataclass
class StageArm:
    name:str
    params:dict=field(default_factory=dict)
    def key(self,stage):
        if not isinstance(self.name,str) or not self.name.strip():
            raise ValueError("arm name must be non-empty")
        if not isinstance(self.params,dict):
            raise ValueError("arm params must be an object")
        raw=json.dumps(self.params,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)
        return f"{stage}:{self.name}:{hashlib.sha256(raw.encode()).hexdigest()[:8]}"

@dataclass
class Verdict:
    allowed:bool
    latency_ms:float=0.0
    cost_usd:float=0.0
    raw:dict|None=None
    error:str|None=None

@dataclass
class Candidate:
    idx:int
    payload:str
    arms:list
    dedup:str
    skipped:bool=False
    reason:str=""
    def arm_keys(self): return [a.key(s) for s,a in self.arms]

def load_extensions(group: str = "openmind_omjb.mutation_transforms") -> list[str]:
    """Load installed third-party transform modules from Python entry points."""
    from importlib.metadata import entry_points
    points=entry_points()
    selected=points.select(group=group) if hasattr(points,"select") else points.get(group,[])
    loaded=[]
    for point in sorted(selected,key=lambda item:item.name):
        point.load()
        loaded.append(point.name)
    return loaded
