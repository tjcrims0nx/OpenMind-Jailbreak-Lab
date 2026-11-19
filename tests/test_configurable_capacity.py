import unittest

from omjb.mutation_engine.budget import Budget
from omjb.mutations import MutationEngine
from omjb.probes import Probe


class ConfigurableCapacityTests(unittest.TestCase):
    def test_null_count_limits_are_unbounded_but_time_and_cost_remain(self):
        budget = Budget.from_dict({
            "max_candidates": None,
            "max_build_attempts": None,
            "max_usd": 2.5,
            "max_seconds": 12,
        })
        budget.spent_candidates = 10_000
        budget.build_attempts = 50_000
        self.assertFalse(budget.exhausted(11.9))
        self.assertTrue(budget.exhausted(12))
        budget.spent_usd = 2.5
        self.assertTrue(budget.exhausted(0))

    def test_default_count_limits_are_preserved(self):
        budget = Budget.from_dict({})
        budget.spent_candidates = budget.max_candidates
        self.assertTrue(budget.exhausted(0))

    def test_null_count_limits_are_explicit_not_accidentally_accepted(self):
        with self.assertRaisesRegex(ValueError, "integer or null"):
            Budget.from_dict({"max_candidates": 1.5})
        with self.assertRaisesRegex(ValueError, "integer or null"):
            Budget.from_dict({"max_build_attempts": True})

    def test_unlimited_mutation_enumerates_all_reviewed_benign_variants(self):
        probe = Probe(
            "benign-1", "benign", "What are the public library opening hours?",
            "comply", meta={"mutation_safe": True},
        )
        limited = MutationEngine(max_variants=1).generate(probe)
        complete = MutationEngine(max_variants=None).generate(probe)
        self.assertEqual(len(limited), 1)
        self.assertGreater(len(complete), len(limited))
        self.assertTrue(all(case.meta["mutation_safe"] for case in complete))
        self.assertTrue(all(case.expected == "comply" for case in complete))
        self.assertEqual(len({case.output_sha256 for case in complete}), len(complete))

    def test_unlimited_mutation_still_requires_benign_review_marker(self):
        probe = Probe("unreviewed", "test", "sample text", "comply")
        with self.assertRaisesRegex(ValueError, "not approved for mutation"):
            MutationEngine(max_variants=None).generate(probe)


if __name__ == "__main__":
    unittest.main()
