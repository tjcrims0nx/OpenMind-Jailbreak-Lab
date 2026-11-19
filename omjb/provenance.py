"""Validated source provenance and stable content hashing."""
from __future__ import annotations
import hashlib,json
from dataclasses import asdict,dataclass

@dataclass(frozen=True)
class ProvenanceRecord:
    source:str=""; revision:str=""; upstream_uri:str=""; fetched_at:float=0.0
    license:str=""; author:str=""; date:str=""; notes:str=""
    @classmethod
    def from_dict(cls,data=None):
        data=data or {}
        if not isinstance(data,dict): raise ValueError("provenance must be an object")
        return cls(**{k:data.get(k,getattr(cls(),k)) for k in cls.__dataclass_fields__})
    def validate(self,where=""):
        missing=[k for k in ("source","revision") if not getattr(self,k)]
        if missing: raise ValueError(f"provenance at {where or '<unknown>'}: missing {missing}")
    def to_dict(self): return asdict(self)

def row_sha256(record):
    content={k:v for k,v in record.items() if k not in ("provenance","provenance_record","id")}
    return hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
