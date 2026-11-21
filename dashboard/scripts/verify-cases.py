#!/usr/bin/env python3
"""Verify dashboard/public/cases.json matches a fresh CASES export.

Exports CASES from a pristine `git archive` of the repo at HEAD (never the
working tree), the same approach as the HF Space build script's
verify_cases_json, and compares it field-for-field with public/cases.json.
Exit 0 on an exact match, 1 otherwise.

Usage:
    python3 scripts/verify-cases.py [--repo PATH] [--cases PATH]
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

FIELDS = (
    "case_id",
    "category",
    "prompt",
    "expected_signal",
    "canary",
    "control",
    "source_id",
    "source_path",
    "source_sha256",
)


def fresh_export(repo: Path) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp:
        archive = subprocess.run(
            ["git", "-C", str(repo), "archive", "--format=zip", "HEAD"],
            capture_output=True,
            check=True,
        ).stdout
        zf = zipfile.ZipFile(io.BytesIO(archive))
        zf.extractall(tmp)
        code = (
            "import json, sys; sys.path.insert(0, sys.argv[1]);"
            "from modules.guardrail_lab.cases import CASES;"
            "print(json.dumps([{"
            + ",".join(f"'{f}': c.{f}" for f in FIELDS)
            + "} for c in CASES], ensure_ascii=False))"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code, tmp],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(proc.stdout)


def main() -> int:
    here = Path(__file__).resolve()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=None)
    ap.add_argument("--cases", default=None)
    args = ap.parse_args()

    if args.repo:
        repo = Path(args.repo)
    else:
        repo = here.parents[2]
    cases_path = Path(args.cases) if args.cases else here.parents[1] / "public" / "cases.json"

    if not cases_path.is_file():
        print(f"error: {cases_path} does not exist", file=sys.stderr)
        return 1
    shipped = json.loads(cases_path.read_text(encoding="utf-8"))
    fresh = fresh_export(repo)
    if shipped != fresh:
        print(f"error: {cases_path} does not match a fresh CASES export "
              f"({len(shipped)} vs {len(fresh)} rows)", file=sys.stderr)
        for a, b in zip(shipped, fresh):
            if a != b:
                print(f"first mismatch at {a.get('case_id')}:", file=sys.stderr)
                for f in FIELDS:
                    if a.get(f) != b.get(f):
                        print(f"  {f}: shipped={a.get(f)!r} fresh={b.get(f)!r}", file=sys.stderr)
                break
        return 1
    print(f"cases.json verified: {len(shipped)} rows match CASES at HEAD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
