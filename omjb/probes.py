"""Strict JSON corpus loader; corpus entries are inert test data."""
import json
from dataclasses import dataclass, field
@dataclass
class Probe:
    id: str
    category: str
    prompt: str
    expected: str = "refuse"
    system: str | None = None
    meta: dict = field(default_factory=dict)
def load_probes(path):
    with open(path, encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, list) or not data:
        raise ValueError("corpus must be a non-empty JSON array")
    probes, seen = [], set()
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"probe {i} must be an object")
        prompt = item.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"probe {i} missing non-empty prompt")
        pid = item.get("id", f"probe-{i:04d}")
        if not isinstance(pid, str) or not pid.strip() or pid in seen:
            raise ValueError(f"probe {i} has invalid or duplicate id")
        expected = item.get("expected", "refuse")
        if expected not in ("refuse", "comply", "either"):
            raise ValueError(f"probe {pid}: invalid expected value")
        system = item.get("system")
        if system is not None and not isinstance(system, str):
            raise ValueError(f"probe {pid}: system must be text")
        meta = item.get("meta", {})
        if not isinstance(meta, dict):
            raise ValueError(f"probe {pid}: meta must be an object")
        seen.add(pid)
        probes.append(Probe(pid, str(item.get("category", "uncategorized")), prompt, expected, system, meta))
    return probes
