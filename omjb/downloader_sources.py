"""Configuration validation for explicitly pinned, licensed corpus sources."""
from __future__ import annotations
import json
from pathlib import Path

REQUIRED=("name","url","sha256","revision","license","format","prompt_field")
def load_source_config(path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data,dict): raise ValueError("source config must be a JSON object")
    missing=[key for key in REQUIRED if not isinstance(data.get(key),str) or not data[key].strip()]
    if missing: raise ValueError("source config missing non-empty fields: "+", ".join(missing))
    if data.get("reviewed") is not True: raise ValueError("set reviewed: true only after manually confirming this is a safe, authorized test corpus")\n    if not data["url"].startswith("https://"): raise ValueError("source URL must use HTTPS")
    if len(data["sha256"])!=64 or any(c not in "0123456789abcdefABCDEF" for c in data["sha256"]):
        raise ValueError("sha256 must be 64 hexadecimal characters")
    if data["format"] not in ("json","jsonl","ndjson","yaml","yml"):
        raise ValueError("format must be json, jsonl, ndjson, yaml, or yml")
    if data.get("expected_field","expected") not in ("expected","label","target"):
        raise ValueError("expected_field must be expected, label, or target")
    return data
