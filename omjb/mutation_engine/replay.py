"""Compare two JSONL mutation-engine traces without re-running a target."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_trace(path: str | Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number}: trace record must be an object")
            if record.get("event") != "candidate":
                continue
            key = record.get("key") or record.get("payload_sha256")
            if not isinstance(key, str) or not key:
                raise ValueError(f"{path}:{line_number}: candidate requires key or payload_sha256")
            if key in records:
                raise ValueError(f"{path}:{line_number}: duplicate candidate key {key!r}")
            # Failed submissions are not equivalent to a guardrail block.
            if record.get("error"):
                records[key] = {"key": key, "outcome": "error"}
                continue
            if not isinstance(record.get("allowed"), bool):
                raise ValueError(f"{path}:{line_number}: candidate allowed must be boolean")
            records[key] = {"key": key, "outcome": "allow" if record["allowed"] else "block"}
    return records


def compare_traces(baseline_path: str | Path, candidate_path: str | Path) -> dict[str, Any]:
    """Match candidates by stable key and report decision flips and inconclusive rows."""
    baseline = _load_trace(baseline_path)
    candidate = _load_trace(candidate_path)
    common = sorted(baseline.keys() & candidate.keys())
    flips = []
    inconclusive = []
    for key in common:
        before = baseline[key]["outcome"]
        after = candidate[key]["outcome"]
        if "error" in (before, after):
            inconclusive.append({"key": key, "baseline": before, "candidate": after})
        elif before != after:
            flips.append({
                "key": key,
                "baseline": before,
                "candidate": after,
                "change": "block_to_allow" if after == "allow" else "allow_to_block",
            })
    return {
        "baseline_count": len(baseline),
        "candidate_count": len(candidate),
        "matched_count": len(common),
        "baseline_only": sorted(baseline.keys() - candidate.keys()),
        "candidate_only": sorted(candidate.keys() - baseline.keys()),
        "inconclusive": inconclusive,
        "flips": flips,
        "allow_to_block": sum(item["change"] == "allow_to_block" for item in flips),
        "block_to_allow": sum(item["change"] == "block_to_allow" for item in flips),
    }
