import json
import tempfile
import unittest
from pathlib import Path

from modules.guardrail_lab.campaign import run_campaign
from modules.guardrail_lab.campaign_history import (
    CampaignHistoryError, CampaignHistoryStore,
)


class CampaignHistoryTests(unittest.TestCase):
    def test_pending_results_are_not_used_for_adaptive_expansion(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "history.jsonl")
            response = lambda messages: "CANARY-GL001"
            first = run_campaign(
                response, provider="mock", budget=1, variants=3,
                adaptive=True, case_ids=["GL-001"], history_path=path,
            )
            self.assertEqual(first["campaign"]["attempts"], 1)
            self.assertEqual(len(CampaignHistoryStore(path).list_pending()), 1)

            resumed = run_campaign(
                response, provider="mock", budget=3, variants=3,
                adaptive=True, case_ids=["GL-001"], history_path=path,
            )
            self.assertEqual(resumed["campaign"]["attempts"], 0)
            self.assertEqual(resumed["campaign"]["queue_remaining"], 0)

    def test_only_approved_reviewed_canary_expands_on_later_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "history.jsonl")
            report = run_campaign(
                lambda messages: "CANARY-GL001", provider="mock",
                budget=1, variants=3, adaptive=True,
                case_ids=["GL-001"], history_path=path,
            )
            store = CampaignHistoryStore(path)
            pending = store.list_pending()
            self.assertEqual(len(pending), 1)
            store.record_review(
                record_id=pending[0]["record_id"], reviewer="test-reviewer",
                decision="approved", notes="Exact synthetic canary reproduced.",
            )
            resumed = run_campaign(
                lambda messages: "The source is untrusted.",
                provider="mock", budget=2, variants=3, adaptive=True,
                case_ids=["GL-001"], history_path=path,
            )
            self.assertEqual(
                [item["variant"] for item in resumed["results"]],
                ["evaluation_context", "untrusted_context"],
            )

    def test_review_rejection_does_not_expand(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "history.jsonl")
            run_campaign(
                lambda messages: "CANARY-GL001", provider="mock",
                budget=1, variants=3, case_ids=["GL-001"],
                history_path=path,
            )
            store = CampaignHistoryStore(path)
            pending = store.list_pending()[0]
            store.record_review(
                record_id=pending["record_id"], reviewer="reviewer",
                decision="rejected", notes="Not a valid finding.",
            )
            resumed = run_campaign(
                lambda messages: "safe", provider="mock", budget=3,
                variants=3, case_ids=["GL-001"], history_path=path,
            )
            self.assertEqual(resumed["campaign"]["attempts"], 0)

    def test_history_is_provider_and_model_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "history.jsonl")
            run_campaign(
                lambda messages: "safe", provider="mock", model="model-a",
                budget=1, case_ids=["GL-001"], history_path=path,
            )
            other = run_campaign(
                lambda messages: "safe", provider="mock", model="model-b",
                budget=1, case_ids=["GL-001"], history_path=path,
            )
            self.assertEqual(other["campaign"]["attempts"], 1)

    def test_history_checksum_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            run_campaign(
                lambda messages: "safe", provider="mock", budget=1,
                case_ids=["GL-001"], history_path=str(path),
            )
            event = json.loads(path.read_text(encoding="utf-8"))
            event["result"]["assessment"] = "potential_guardrail_failure"
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(CampaignHistoryError, "checksum mismatch"):
                CampaignHistoryStore(str(path)).snapshot()


if __name__ == "__main__":
    unittest.main()
