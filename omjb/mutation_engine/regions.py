"""Structured values and region-preserving transform dispatch."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Callable
from .core import Kind

class Region(str,Enum):
    PREFIX="prefix"
    BLOB="blob"
    SUFFIX="suffix"
    ALL="all"

@dataclass(frozen=True)
class RegionValue:
    prefix:str
    blob:str
    blob_kind:Kind
    suffix:str=""
    def __post_init__(self):
        if not all(isinstance(x,str) for x in (self.prefix,self.blob,self.suffix)):
            raise TypeError("region values must be strings")
        if not isinstance(self.blob_kind,Kind):
            object.__setattr__(self,"blob_kind",Kind(self.blob_kind))
    def render(self)->str:
        return self.prefix+self.blob+self.suffix

def apply_region(value:RegionValue,*,touches:Region,fn:Callable[[str],str],output_kind:Kind|None=None)->RegionValue:
    if not isinstance(value,RegionValue): raise TypeError("value must be RegionValue")
    if touches is Region.ALL:
        changed=fn(value.render())
        if not isinstance(changed,str): raise TypeError("transform must return str")
        return RegionValue("",changed,output_kind or Kind.TEXT,"")
    if touches is Region.PREFIX:
        changed=fn(value.prefix)
        if not isinstance(changed,str): raise TypeError("transform must return str")
        return RegionValue(changed,value.blob,value.blob_kind,value.suffix)
    if touches is Region.BLOB:
        changed=fn(value.blob)
        if not isinstance(changed,str): raise TypeError("transform must return str")
        return RegionValue(value.prefix,changed,output_kind or value.blob_kind,value.suffix)
    if touches is Region.SUFFIX:
        changed=fn(value.suffix)
        if not isinstance(changed,str): raise TypeError("transform must return str")
        return RegionValue(value.prefix,value.blob,value.blob_kind,changed)
    raise ValueError(f"unsupported region: {touches!r}")

def region_compatible(value:RegionValue,*,touches:Region,input_kind:Kind=Kind.TEXT)->bool:
    if touches in (Region.PREFIX,Region.SUFFIX): return True
    if touches in (Region.BLOB,Region.ALL): return value.blob_kind is input_kind
    return False
