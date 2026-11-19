"""Validated probe records loaded through the shared corpus reader."""
from __future__ import annotations
from dataclasses import dataclass,field
from .corpus_io import iter_records
from .provenance import ProvenanceRecord,row_sha256

@dataclass
class Probe:
    id:str; category:str; prompt:str; expected:str="refuse"; system:str|None=None
    meta:dict=field(default_factory=dict)
    provenance_record:ProvenanceRecord=field(default_factory=ProvenanceRecord)

def load_probes(path,require_provenance=False,dedupe=False):
    probes=[]; seen=set(); hashes=set()
    for i,item in enumerate(iter_records(path)):
        if not isinstance(item,dict): raise ValueError(f"{path}: record {i} must be an object")
        prompt=item.get("prompt",item.get("text",item.get("goal",item.get("instruction"))))
        if not isinstance(prompt,str) or not prompt.strip(): raise ValueError(f"{path}: record {i} missing non-empty prompt")
        pid=item.get("id",f"probe-{i:04d}")
        if not isinstance(pid,str) or not pid.strip() or pid in seen: raise ValueError(f"{path}: record {i} has invalid or duplicate id")
        expected=item.get("expected","refuse")
        if expected not in ("refuse","comply","either"): raise ValueError(f"{path}: probe {pid}: invalid expected value")
        system=item.get("system")
        if system is not None and not isinstance(system,str): raise ValueError(f"{path}: probe {pid}: system must be text")
        meta=item.get("meta",{})
        if not isinstance(meta,dict): raise ValueError(f"{path}: probe {pid}: meta must be an object")
        raw_prov=item.get("provenance") or {}
        if not isinstance(raw_prov,dict): raise ValueError(f"{path}: probe {pid}: provenance must be an object")
        if raw_prov.get("runnable") is False: raise ValueError(f"{path}: probe {pid}: source record is metadata-only")
        prov=ProvenanceRecord.from_dict(raw_prov)
        if require_provenance: prov.validate(where=f"{path}:{i}")
        meta={**meta,"provenance_source":prov.source or "unknown","provenance_revision":prov.revision or ""}
        digest=row_sha256({"prompt":prompt,"category":item.get("category","uncategorized"),"expected":expected,"system":system})
        if dedupe and digest in hashes: continue
        seen.add(pid); hashes.add(digest)
        probes.append(Probe(pid,str(item.get("category","uncategorized")),prompt,expected,system,meta,prov))
    if not probes: raise ValueError(f"{path}: corpus contains no runnable probes")
    return probes
