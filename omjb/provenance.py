"""Validated source provenance, content hashing and corpus manifests."""
from __future__ import annotations
import hashlib,json,time
from dataclasses import asdict,dataclass,is_dataclass
from pathlib import Path

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

def _normalize(row):
    if is_dataclass(row):
        d={k:getattr(row,k) for k in row.__dataclass_fields__}
        p=d.pop("provenance_record",None)
        if p is not None: d["provenance"]=p.to_dict() if hasattr(p,"to_dict") else p
        return d
    if not isinstance(row,dict): raise ValueError("corpus rows must be dictionaries or dataclass records")
    d=dict(row)
    if "provenance_record" in d and "provenance" not in d:
        p=d.pop("provenance_record"); d["provenance"]=p.to_dict() if hasattr(p,"to_dict") else p
    return d

def write_corpus(rows,path,manifest_extra=None):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    file_hash=hashlib.sha256(); buckets={}; count=0
    with path.open("w",encoding="utf-8",newline="\n") as f:
        for index,row in enumerate(rows):
            data=_normalize(row); prov=ProvenanceRecord.from_dict(data.get("provenance")); prov.validate(where=f"{path}:row{index}")
            data["provenance"]=prov.to_dict()
            line=json.dumps(data,ensure_ascii=False,sort_keys=True)
            payload=(line+"\n").encode("utf-8"); f.write(line+"\n"); file_hash.update(payload)
            key=f"{prov.source}@{prov.revision}"
            bucket=buckets.setdefault(key,{"source":prov.source,"revision":prov.revision,"upstream_uri":prov.upstream_uri,"license":prov.license,"n":0,"hash":hashlib.sha256()})
            bucket["n"]+=1; bucket["hash"].update((row_sha256(data)+"\n").encode("ascii")); count+=1
    manifest={"path":str(path.resolve()),"sha256":file_hash.hexdigest(),"n":count,"written_at":time.time(),
        "sources":[{"key":k,"source":b["source"],"revision":b["revision"],"upstream_uri":b["upstream_uri"],
                    "license":b["license"],"n":b["n"],"row_hashes_sha256":b["hash"].hexdigest()} for k,b in sorted(buckets.items())]}
    if manifest_extra:
        for key,value in manifest_extra.items():
            if key not in manifest: manifest[key]=value
    manifest_path=Path(str(path)+".manifest.json")
    manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return manifest

def verify_manifest(manifest_path):
    mp=Path(manifest_path); manifest=json.loads(mp.read_text(encoding="utf-8"))
    corpus=Path(manifest["path"])
    if not corpus.is_absolute(): corpus=mp.resolve().parent/corpus
    actual_file=hashlib.sha256(corpus.read_bytes()).hexdigest()
    groups={}
    with corpus.open("r",encoding="utf-8") as f:
        for i,line in enumerate(f,1):
            if not line.strip(): continue
            row=json.loads(line); prov=ProvenanceRecord.from_dict(row.get("provenance")); prov.validate(where=f"{corpus}:{i}")
            key=f"{prov.source}@{prov.revision}"
            b=groups.setdefault(key,{"n":0,"hash":hashlib.sha256()})
            b["n"]+=1; b["hash"].update((row_sha256(row)+"\n").encode("ascii"))
    expected={x["key"]:x for x in manifest.get("sources",[])}
    source_checks=[]
    for key in sorted(set(groups)|set(expected)):
        actual=groups.get(key,{"n":0,"hash":hashlib.sha256()})
        exp=expected.get(key,{})
        ok=actual["n"]==exp.get("n") and actual["hash"].hexdigest()==exp.get("row_hashes_sha256")
        source_checks.append({"key":key,"ok":ok,"actual_n":actual["n"],"expected_n":exp.get("n"),
            "actual_row_hashes_sha256":actual["hash"].hexdigest(),"expected_row_hashes_sha256":exp.get("row_hashes_sha256")})
    ok=actual_file==manifest.get("sha256") and sum(x["actual_n"] for x in source_checks)==manifest.get("n") and all(x["ok"] for x in source_checks)
    return {"ok":ok,"path":str(corpus),"file_sha256":actual_file,"expected_file_sha256":manifest.get("sha256"),
        "n":manifest.get("n"),"source_checks":source_checks}
