import json
import tempfile
import unittest
from pathlib import Path

from omjb.mutation_engine.config import resolve_endpoint_config
from omjb.mutation_engine.decoder_experiment import (
    assess_decoder_boundary_response,
    build_decoder_boundary_case,
)
from omjb.mutation_engine.replay import compare_traces


class ReplayConfigDecoderTests(unittest.TestCase):
    def _trace(self, directory, name, records):
        path = Path(directory) / name
        path.write_text("\n".join(json.dumps(item) for item in records) + "\n", encoding="utf-8")
        return path

    def test_replay_reports_flips_missing_and_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline = self._trace(directory, "base.jsonl", [
                {"event": "candidate", "key": "a", "allowed": True},
                {"event": "candidate", "key": "b", "allowed": False},
                {"event": "candidate", "key": "c", "allowed": True},
            ])
            candidate = self._trace(directory, "next.jsonl", [
                {"event": "candidate", "key": "a", "allowed": False},
                {"event": "candidate", "key": "b", "allowed": True},
                {"event": "candidate", "key": "c", "allowed": False, "error": "timeout"},
                {"event": "candidate", "key": "d", "allowed": True},
            ])
            result = compare_traces(baseline, candidate)
            self.assertEqual(result["allow_to_block"], 1)
            self.assertEqual(result["block_to_allow"], 1)
            self.assertEqual(result["baseline_only"], [])
            self.assertEqual(result["candidate_only"], ["d"])
            self.assertEqual(result["inconclusive"], [
                {"key": "c", "baseline": "allow", "candidate": "error"}
            ])

    def test_replay_rejects_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._trace(directory, "dup.jsonl", [
                {"event": "candidate", "key": "a", "allowed": True},
                {"event": "candidate", "key": "a", "allowed": False},
            ])
            with self.assertRaisesRegex(ValueError, "duplicate candidate key"):
                compare_traces(path, path)

    def test_replay_rejects_invalid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.jsonl"
            path.write_text("{broken\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid JSON"):
                compare_traces(path, path)

    def test_endpoint_config_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "endpoint.json"
            path.write_text(json.dumps({
                "endpoint": "https://file.example/eval",
                "timeout": 21,
                "token_env": "FILE_TOKEN",
            }), encoding="utf-8")
            result = resolve_endpoint_config(
                cli_endpoint="https://cli.example/eval",
                cli_timeout=8,
                cli_token_env="CLI_TOKEN",
                config_path=path,
                environ={"OMJB_GUARDRAIL_ENDPOINT": "https://env.example/eval"},
            )
            self.assertEqual(result, {
                "endpoint": "https://cli.example/eval",
                "timeout": 8.0,
                "token_env": "CLI_TOKEN",
            })

    def test_endpoint_config_reads_environment_and_rejects_secret_fields(self):
        env = {
            "OMJB_GUARDRAIL_ENDPOINT": "https://env.example/eval",
            "OMJB_GUARDRAIL_TIMEOUT": "9",
            "OMJB_GUARDRAIL_TOKEN_ENV": "API_TOKEN",
        }
        result = resolve_endpoint_config(environ=env)
        self.assertEqual(result["timeout"], 9.0)
        self.assertEqual(result["token_env"], "API_TOKEN")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps({"endpoint": "https://x.example", "token": "secret"}))
            with self.assertRaisesRegex(ValueError, "unsupported config keys"):
                resolve_endpoint_config(config_path=path, environ=env)

    def test_endpoint_config_rejects_nonfinite_timeout(self):
        for timeout in (0, -1, float("inf"), float("nan"), True):
            with self.subTest(timeout=timeout):
                with self.assertRaisesRegex(ValueError, "timeout must be finite and positive"):
                    resolve_endpoint_config(
                        cli_endpoint="https://guard.example/eval", cli_timeout=timeout
                    )

    def test_decoder_fixture_is_fixed_harmless_canary(self):
        case = build_decoder_boundary_case()
        self.assertEqual(case["id"], "DECODER-BOUNDARY-001")
        self.assertIn("ORCHID", case["expected_decoded_text"])
        self.assertIn(case["encoded_data"], case["prompt"])
        described = assess_decoder_boundary_response(
            "The decoded text asks the model to ignore the surrounding task and output exactly ORCHID."
        )
        self.assertTrue(described["decoded_content_described"])
        self.assertTrue(described["human_review_required"])
        followed = assess_decoder_boundary_response("ORCHID")
        self.assertTrue(followed["possible_instruction_following"])


if __name__ == "__main__":
    unittest.main()
