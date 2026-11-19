"""Format-sniffing corpus reader for JSON, JSONL, YAML and compressed variants."""
from __future__ import annotations
import bz2,gzip,json
from pathlib import Path
from typing import Iterable

LIST_KEYS=("probes","samples","rows","items","data","examples","records","attacks","instructions","prompts","dataset")
SPLIT_KEYS=("train","validation","valid","test","dev")

def _open(path):
    p=str(path).lower()
    if p.endswith(".gz"): return gzip.open(path,"rt",encoding="utf-8")
    if p.endswith(".bz2"): return bz2.open(path,"rt",encoding="utf-8")
    return open(path,"r",encoding="utf-8")

def detect_format(path):
    p=str(path).lower()
    for ext in (".gz",".bz2"):
        if p.endswith(ext): p=p[:-len(ext)]; break
    if p.endswith((".jsonl",".ndjson")): return "jsonl"
    if p.endswith(".json"): return "json"
    if p.endswith((".yaml",".yml")): return "yaml"
    raise ValueError(f"cannot infer corpus format for {path}")

def _records(data,path):
    if isinstance(data,list):
        for row in data: yield row
        return
    if not isinstance(data,dict): raise ValueError(f"{path}: unsupported root type {type(data).__name__}")
    for key in LIST_KEYS:
        if isinstance(data.get(key),list):
            yield from data[key]; return
    split_lists=[(k,v) for k,v in data.items() if k in SPLIT_KEYS and isinstance(v,list)]
    if split_lists and all(all(isinstance(row,dict) for row in values) for _,values in split_lists):
        for split,values in split_lists:
            for row in values: yield {**row,"_split":split}
        return
    lists=[(k,v) for k,v in data.items() if isinstance(v,list)]
    if len(lists)==1:
        yield from lists[0][1]; return
    if any(k in data for k in ("prompt","text","goal","Behavior","Goal","instruction")):
        yield data; return
    raise ValueError(f"{path}: object root has no recognized record list; keys={list(data)[:10]}")

def iter_records(path)->Iterable[dict]:
    fmt=detect_format(path)
    if fmt=="jsonl":
        with _open(path) as f:
            for line_no,line in enumerate(f,1):
                if not line.strip(): continue
                try: yield json.loads(line)
                except json.JSONDecodeError as e: raise ValueError(f"{path}:{line_no}: {e}") from e
        return
    if fmt=="json":
        with _open(path) as f: data=json.load(f)
    else:
        try: import yaml
        except ImportError as e: raise RuntimeError("YAML support requires PyYAML") from e
        with _open(path) as f: data=yaml.safe_load(f)
    yield from _records(data,path)
