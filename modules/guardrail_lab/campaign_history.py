"""Append-only, integrity-checked campaign history for resumable evaluations.

Only explicitly reviewed outcomes may seed future adaptive expansion. Machine
assessments are retained as pending evidence and never treated as human review.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional


def _canonical(value: Dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def campaign_test_key(case_id: str, variant: str, frame_set_hash: str,
                      frame_variant: Optional[str] = None,
                      shape_variant: Optional[str] = None,
                      provider: Optional[str] = None,
                      model: Optional[str] = None) -> str:
    """Stable identity for one case/variant under a frozen framing set."""
    payload = {"case_id": case_id, "variant": variant,
               "frame_set_hash": frame_set_hash,
               "frame_variant": frame_variant, "shape_variant": shape_variant,
               "provider": provider, "model": model}
    return hashlib.sha256(_canonical(payload)).hexdigest()


class CampaignHistoryError(ValueError):
    """Raised when a history file contains malformed or altered evidence."""


class CampaignHistoryStore:
    """Append-only JSONL history with explicit human-review events."""

    def __init__(self, path: str):
        if not isinstance(path, str) or not path.strip():
            raise ValueError("history path must be non-empty text")
        self.path = Path(path)

    def _events(self) -> List[Dict]:
        if not self.path.exists():
            return []
        events = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise CampaignHistoryError(
                        f"invalid JSON on history line {line_number}"
                    ) from exc
                if not isinstance(event, dict):
                    raise CampaignHistoryError(f"history line {line_number} must be an object")
                checksum = event.get("event_sha256")
                payload = {k: v for k, v in event.items() if k != "event_sha256"}
                if not isinstance(checksum, str) or hashlib.sha256(_canonical(payload)).hexdigest() != checksum:
                    raise CampaignHistoryError(f"history checksum mismatch on line {line_number}")
                if event.get("event_type") not in {"result", "review"}:
                    raise CampaignHistoryError(f"unknown history event on line {line_number}")
                events.append(event)
        return events

    def _append(self, payload: Dict) -> Dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        event = dict(payload)
        event["event_sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
            handle.flush()
        return event

    def record_result(self, *, test_key: str, campaign_plan_sha256: str,
                      result: Dict) -> Dict:
        if not isinstance(test_key, str) or not test_key:
            raise ValueError("test_key must be non-empty text")
        if not isinstance(result, dict):
            raise ValueError("result must be an object")
        events = self._events()
        if any(e.get("event_type") == "result" and e.get("test_key") == test_key for e in events):
            raise CampaignHistoryError(f"test already exists in history: {test_key}")
        record_id = hashlib.sha256(_canonical({
            "test_key": test_key, "campaign_plan_sha256": campaign_plan_sha256,
            "evidence_sha256": result.get("evidence_sha256"),
        })).hexdigest()
        return self._append({
            "event_type": "result", "record_id": record_id,
            "test_key": test_key, "campaign_plan_sha256": campaign_plan_sha256,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "review_status": "pending", "result": result,
        })

    def record_review(self, *, record_id: str, reviewer: str,
                      decision: str, notes: str) -> Dict:
        if decision not in {"approved", "rejected", "inconclusive"}:
            raise ValueError("decision must be approved, rejected, or inconclusive")
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise ValueError("reviewer must be non-empty text")
        if not isinstance(notes, str) or not notes.strip():
            raise ValueError("review notes must be non-empty text")
        events = self._events()
        results = {e["record_id"]: e for e in events if e.get("event_type") == "result"}
        if record_id not in results:
            raise ValueError(f"unknown result record_id: {record_id}")
        return self._append({
            "event_type": "review", "record_id": record_id,
            "test_key": results[record_id]["test_key"],
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "reviewer": reviewer.strip(), "decision": decision, "notes": notes.strip(),
        })

    def snapshot(self) -> Dict:
        """Return attempted keys and latest reviewed outcomes by test key."""
        events = self._events()
        results = {e["record_id"]: e for e in events if e.get("event_type") == "result"}
        reviews = {}
        for event in events:
            if event.get("event_type") == "review":
                reviews[event["record_id"]] = event
        reviewed = {}
        for record_id, review in reviews.items():
            result_event = results.get(record_id)
            if result_event is None:
                raise CampaignHistoryError(f"review references missing result: {record_id}")
            reviewed[result_event["test_key"]] = {
                "record_id": record_id, "decision": review["decision"],
                "reviewer": review["reviewer"], "notes": review["notes"],
                "result": result_event["result"],
            }
        return {
            "attempted_test_keys": {e["test_key"] for e in results.values()},
            "results_by_test_key": {e["test_key"]: e["result"] for e in results.values()},
            "reviewed_by_test_key": reviewed,
            "result_count": len(results),
            "review_count": len(reviews),
        }

    def list_pending(self) -> List[Dict]:
        events = self._events()
        reviewed_ids = {e["record_id"] for e in events if e.get("event_type") == "review"}
        return [e for e in events if e.get("event_type") == "result"
                and e["record_id"] not in reviewed_ids]


def main(argv=None) -> int:
    """Small review CLI; review decisions are explicit and append-only."""
    import argparse
    parser = argparse.ArgumentParser(description="Inspect and review campaign history")
    parser.add_argument("--history", required=True, help="JSONL history path")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("pending", help="List pending result record IDs")
    review = sub.add_parser("review", help="Record a human review")
    review.add_argument("--record-id", required=True)
    review.add_argument("--reviewer", required=True)
    review.add_argument("--decision", required=True,
                        choices=("approved", "rejected", "inconclusive"))
    review.add_argument("--notes", required=True)
    args = parser.parse_args(argv)
    store = CampaignHistoryStore(args.history)
    if args.command == "pending":
        for item in store.list_pending():
            print(json.dumps({
                "record_id": item["record_id"],
                "test_key": item["test_key"],
                "case_id": item["result"].get("case_id"),
                "variant": item["result"].get("variant"),
                "assessment": item["result"].get("assessment"),
            }, ensure_ascii=False))
    else:
        event = store.record_review(
            record_id=args.record_id, reviewer=args.reviewer,
            decision=args.decision, notes=args.notes,
        )
        print(json.dumps({"record_id": event["record_id"],
                          "decision": event["decision"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
