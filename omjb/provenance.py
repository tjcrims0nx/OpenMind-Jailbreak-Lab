"""Source provenance helpers for imported evaluation records."""
from __future__ import annotations
import hashlib, json
from dataclasses import asdict, dataclass
from pathlib import Path

@dataclass(frozen=True)
class Provenance:
    source: str
    source_id: str = ""
    source_path: str = ""
    source_sha256: str = ""
    license: str = ""
    imported_at: str = ""
    runnable: bool = True

def sha256_file(path: str | Path) -> str:
    digest=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): digest.update(chunk)
    return digest.hexdigest()

def manifest_for(path: str | Path, *, source: str, license: str = "", source_id: str = "") -> dict:
    p=Path(path)
    return asdict(Provenance(source=source,source_id=source_id,source_path=str(p),
        source_sha256=sha256_file(p),license=license))

def write_manifest(path: str | Path, manifest: dict) -> None:
    required={"source","source_id","source_path","source_sha256","license","imported_at","runnable"}
    if set(manifest) != required: raise ValueError("provenance manifest fields do not match schema")
    if len(manifest["source_sha256"]) != 64: raise ValueError("invalid source SHA-256")
    Path(path).write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
