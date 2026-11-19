"""Validated JSON, JSONL, and optional YAML corpus loader."""
import json
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class Probe:
    id: str
    category: str
    prompt: str
    expected: str = "refuse"
    system: str | None = None
    meta: dict = field(default_factory=dict)

def _records(path):
    suffix=Path(path).suffix.lower()
    with open(path,encoding="utf-8") as stream:
        if suffix == ".jsonl":
            data=[]
            for line_no,line in enumerate(stream,1):
                if not line.strip(): continue
                try: data.append(json.loads(line))
                except json.JSONDecodeError as exc: raise ValueError(f"JSONL line {line_no}: {exc.msg}") from exc
            return data
        if suffix in {".yaml",".yml"}:
            try: import yaml
            except ImportError as exc: raise RuntimeError("YAML support requires optional dependency PyYAML") from exc
            return yaml.safe_load(stream)
        return json.load(stream)

def load_probes(path):
    data=_records(path)
    if not isinstance(data,list) or not data: raise ValueError("corpus must be a non-empty JSON/JSONL/YAML list")
    probes=[]; seen=set()
    for i,item in enumerate(data):
        if not isinstance(item,dict): raise ValueError(f"probe {i} must be an object")
        prompt=item.get("prompt")
        if not isinstance(prompt,str) or not prompt.strip(): raise ValueError(f"probe {i} missing non-empty prompt")
        pid=item.get("id",f"probe-{i:04d}")
        if not isinstance(pid,str) or not pid.strip() or pid in seen: raise ValueError(f"probe {i} has invalid or duplicate id")
        expected=item.get("expected","refuse")
        if expected not in ("refuse","comply","either"): raise ValueError(f"probe {pid}: invalid expected value")
        system=item.get("system")
        if system is not None and not isinstance(system,str): raise ValueError(f"probe {pid}: system must be text")
        meta=item.get("meta",{})
        if not isinstance(meta,dict): raise ValueError(f"probe {pid}: meta must be an object")
        # Provenance is metadata only; raw archive material is never made runnable implicitly.
        provenance=item.get("provenance")
        if provenance is not None:
            if not isinstance(provenance,dict): raise ValueError(f"probe {pid}: provenance must be an object")
            if provenance.get("runnable") is False: raise ValueError(f"probe {pid}: source record is metadata-only")
            meta={**meta,"provenance":provenance}
        seen.add(pid); probes.append(Probe(pid,str(item.get("category","uncategorized")),prompt,expected,system,meta))
    return probes
