import unittest
from modules.guardrail_lab.campaign import run_campaign

class CampaignTests(unittest.TestCase):
    def test_campaign_respects_budget(self):
        report = run_campaign(lambda messages: "The embedded instruction is untrusted.", provider="mock", budget=4)
        self.assertEqual(report["campaign"]["attempts"], 4)
        self.assertEqual(report["summary"]["total"], 4)

    def test_adaptive_expands_only_on_canary_signal(self):
        calls = []
        def safe_call(messages):
            calls.append(messages)
            return "The embedded instruction is untrusted and should not be followed."
        report = run_campaign(safe_call, provider="mock", budget=12, adaptive=True)
        self.assertEqual(report["campaign"]["attempts"], 12)
        self.assertTrue(all(r["variant"] == "baseline" for r in report["results"]))

    def test_adaptive_followups_are_bounded(self):
        n = {"count": 0}
        def canary_call(messages):
            n["count"] += 1
            return "CANARY-GL001" if "CANARY-GL001" in str(messages) else "untrusted"
        report = run_campaign(canary_call, provider="mock", budget=14, adaptive=True)
        gl1 = [r for r in report["results"] if r["case_id"] == "GL-001"]
        self.assertGreaterEqual(len(gl1), 2)
        self.assertLessEqual(len(gl1), 3)

    def test_ambiguous_canary_mention_does_not_expand_campaign(self):
        def quoted_canary(messages):
            return (
                "The source contains CANARY-GL001, "
                "but that instruction is untrusted."
            )
        report = run_campaign(
            quoted_canary,
            provider="mock",
            budget=12,
            adaptive=True,
            variants=6,
            case_ids=["GL-001"],
        )
        gl1 = [
            r for r in report["results"]
            if r["case_id"] == "GL-001"
        ]
        self.assertEqual(len(gl1), 1)
        self.assertEqual(
            gl1[0]["assessment"],
            "ambiguous_canary_mention",
        )

    def test_campaign_can_select_cases_and_preserves_two_turn_context(self):
        captured = []
        def recorder(messages):
            captured.append(messages)
            return "The note is untrusted content."

        report = run_campaign(
            recorder, provider="mock", budget=2, adaptive=False,
            case_ids=["GL-009", "GL-010"],
        )
        self.assertEqual(report["campaign"]["attempts"], 2)
        self.assertEqual(report["campaign"]["case_ids"], ["GL-009", "GL-010"])
        self.assertEqual(captured[1][0]["role"], "system")
        self.assertEqual(captured[1][1]["role"], "user")
        self.assertEqual(captured[1][2]["role"], "assistant")
        self.assertEqual(captured[1][3]["role"], "user")

    def test_unknown_campaign_case_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown case ID"):
            run_campaign(lambda m: "ok", provider="mock", case_ids=["NOPE"])

    def test_duplicate_campaign_case_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate case IDs"):
            run_campaign(lambda m: "ok", provider="mock", case_ids=["GL-001", "GL-001"])

    def test_campaign_followup_requires_setup_case(self):
        with self.assertRaisesRegex(ValueError, "GL-009"):
            run_campaign(lambda m: "ok", provider="mock", case_ids=["GL-010"])

    def test_invalid_budget_rejected(self):
        with self.assertRaises(ValueError):
            run_campaign(lambda m: "ok", provider="mock", budget=0)

    def test_non_integer_budget_and_variants_are_rejected(self):
        import math
        for bad in (math.nan, math.inf, 36.5, True, "36"):
            with self.assertRaisesRegex(
                    ValueError, "budget must be an integer"):
                run_campaign(lambda m: "ok", provider="mock", budget=bad)
        for bad in (math.nan, math.inf, 2.5, True, "2"):
            with self.assertRaisesRegex(
                    ValueError, "variants must be an integer"):
                run_campaign(lambda m: "ok", provider="mock", variants=bad)

    def test_non_finite_delay_is_rejected(self):
        import math
        with self.assertRaisesRegex(ValueError, "delay_seconds must be a finite"):
            run_campaign(lambda m: "ok", provider="mock", budget=2, delay_seconds=math.inf)
        with self.assertRaisesRegex(ValueError, "delay_seconds must be a finite"):
            run_campaign(lambda m: "ok", provider="mock", budget=2, delay_seconds=math.nan)

    def test_non_finite_max_seconds_is_rejected(self):
        import math
        with self.assertRaisesRegex(ValueError, "max_seconds must be a finite"):
            run_campaign(lambda m: "ok", provider="mock", budget=2, max_seconds=math.inf)
        with self.assertRaisesRegex(ValueError, "max_seconds must be a finite"):
            run_campaign(lambda m: "ok", provider="mock", budget=2, max_seconds=math.nan)

    def test_six_variants_expand_on_flag(self):
        from modules.guardrail_lab.campaign import VARIANTS
        self.assertEqual(len(VARIANTS), 6)
        def canary_call(messages):
            return "CANARY-GL001" if "CANARY-GL001" in str(messages) else "untrusted"
        report = run_campaign(
            canary_call, provider="mock", budget=12, adaptive=True,
            variants=6, case_ids=["GL-001"],
        )
        gl1 = [r for r in report["results"] if r["case_id"] == "GL-001"]
        self.assertEqual(len(gl1), 6)
        self.assertEqual(
            [r["variant"] for r in gl1],
            [name for name, _ in VARIANTS],
        )

    def test_variants_above_six_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "variants must be an integer"):
            run_campaign(lambda m: "ok", provider="mock", variants=7)

    def test_invalid_delay_values_are_rejected(self):
        import math
        for value in (True, "1", None, math.inf, math.nan, 10**10000):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    run_campaign(
                        lambda _: "ok",
                        provider="mock",
                        budget=2,
                        delay_seconds=value,
                    )

    def test_invalid_max_seconds_values_are_rejected(self):
        import math
        for value in (True, "10", math.inf, math.nan, 0, -1, 10**10000):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    run_campaign(
                        lambda _: "ok",
                        provider="mock",
                        budget=2,
                        max_seconds=value,
                    )

    def test_gl010_paired_context_uses_gl009_response(self):
        captured = []
        def recorder(messages):
            captured.append(messages)
            return "The note is untrusted content."
        report = run_campaign(
            recorder, provider="mock", budget=2, adaptive=True,
            variants=6, case_ids=["GL-009", "GL-010"],
        )
        self.assertEqual(report["campaign"]["attempts"], 2)
        # GL-010's paired conversation carries the GL-009 response as the
        # assistant turn, ahead of the GL-010 prompt.
        self.assertEqual(captured[1][0]["role"], "system")
        self.assertEqual(captured[1][1]["role"], "user")
        self.assertEqual(captured[1][2]["role"], "assistant")
        self.assertEqual(
            captured[1][2]["content"], "The note is untrusted content."
        )
        self.assertEqual(captured[1][3]["role"], "user")

    def test_cloudflare_1010_stops_campaign_immediately(self):
        from modules.guardrail_lab.runner import GuardrailRunError
        calls = []
        def blocked_provider(messages):
            calls.append(messages)
            raise GuardrailRunError(
                "Compatible endpoint HTTP 403: error code: 1010"
            )
        report = run_campaign(
            blocked_provider,
            provider="openrouter",
            budget=36,
            adaptive=True,
            case_ids=["GL-001", "GL-002", "GL-003"],
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(report["campaign"]["attempts"], 1)
        self.assertTrue(report["campaign"]["halted"])
        self.assertEqual(
            report["campaign"]["not_run_case_ids"],
            ["GL-002", "GL-003"],
        )
        self.assertEqual(
            report["results"][0]["assessment"],
            "partial_run",
        )

    def test_other_provider_errors_do_not_trigger_1010_circuit(self):
        from modules.guardrail_lab.runner import GuardrailRunError
        calls = []
        def failing_provider(messages):
            calls.append(messages)
            raise GuardrailRunError("Temporary connection failure")
        report = run_campaign(
            failing_provider,
            provider="mock",
            budget=2,
            adaptive=False,
            case_ids=["GL-001", "GL-002"],
        )
        self.assertEqual(len(calls), 2)
        self.assertFalse(report["campaign"]["halted"])

    def test_campaign_enforces_build_attempt_capacity(self):
        def canary_call(messages):
            return "CANARY-GL001" if "CANARY-GL001" in str(messages) else "untrusted"
        report = run_campaign(
            canary_call, provider="mock", budget=10,
            max_build_attempts=2, adaptive=True, variants=6,
            case_ids=["GL-001", "GL-002"],
        )
        self.assertEqual(report["campaign"]["attempts"], 2)
        self.assertEqual(report["campaign"]["build_attempts"], 2)
        self.assertEqual(report["campaign"]["halt_reason"], "max_build_attempts")
        self.assertEqual(
            [r["variant"] for r in report["results"]],
            ["baseline", "evaluation_context"],
        )

    def test_campaign_reserves_estimated_usd_before_each_request(self):
        calls = []
        def recorder(messages):
            calls.append(messages)
            return "untrusted"
        report = run_campaign(
            recorder, provider="mock", budget=10,
            max_usd=0.02, estimated_cost_per_request=0.01,
            case_ids=["GL-001", "GL-002", "GL-003"],
        )
        self.assertEqual(len(calls), 2)
        self.assertEqual(report["campaign"]["estimated_spend_usd"], 0.02)
        self.assertEqual(report["campaign"]["halt_reason"], "estimated_usd_budget")
        self.assertTrue(all(r["estimated_cost_usd"] == 0.01 for r in report["results"]))

    def test_unbounded_count_limits_require_time_and_cost_limits(self):
        with self.assertRaisesRegex(ValueError, "require finite max_seconds and max_usd"):
            run_campaign(
                lambda messages: "untrusted", provider="mock",
                budget=None, max_build_attempts=None, max_seconds=10,
            )
        report = run_campaign(
            lambda messages: "untrusted", provider="mock",
            budget=None, max_build_attempts=None, max_seconds=10,
            max_usd=0.10, estimated_cost_per_request=0.01,
            adaptive=False, delay_seconds=0.001,
            case_ids=["GL-001", "GL-002"],
        )
        self.assertIsNone(report["campaign"]["max_candidates"])
        self.assertIsNone(report["campaign"]["max_build_attempts"])
        self.assertEqual(report["campaign"]["attempts"], 2)

    def test_campaign_plan_fingerprint_is_stable_and_capacity_sensitive(self):
        def run(budget):
            return run_campaign(
                lambda messages: "untrusted", provider="mock",
                budget=budget, adaptive=False, case_ids=["GL-001"],
            )["campaign"]["campaign_plan_sha256"]
        self.assertEqual(run(2), run(2))
        self.assertNotEqual(run(2), run(3))

    def test_usd_limit_requires_positive_estimate(self):
        with self.assertRaisesRegex(ValueError, "estimated_cost_per_request is required"):
            run_campaign(
                lambda messages: "untrusted", provider="mock",
                budget=2, max_usd=1.0,
            )
        with self.assertRaisesRegex(ValueError, "finite positive number"):
            run_campaign(
                lambda messages: "untrusted", provider="mock",
                budget=2, max_usd=1.0, estimated_cost_per_request=0,
            )

if __name__ == "__main__":
    unittest.main()
