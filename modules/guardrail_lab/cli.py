"""CLI. Uses the repository's existing provider adapter when installed in-repo."""
import argparse, json, os, sys
from pathlib import Path
from .cases import CASES
from .source_cases import SOURCE_CASES
from .runner import run_suite, write_report
from .measurement import (
    RunConfig, case_set_hashes, fingerprint_endpoint, not_measured_entry,
)
from .campaign import run_campaign
from .registry import save_candidate_records
from .preflight import preflight
from .openai_compatible import (
    PRESET_BASE_URLS,
    PRESET_API_KEY_ENVS,
    call_openai_compatible,
)

def _adapter(provider, model, base_url=None, api_key_env=None, max_tokens=None):
    if provider == "openai-compatible" or provider in PRESET_BASE_URLS:
        resolved_url = (
            base_url
            or PRESET_BASE_URLS.get(provider)
            or os.getenv("OPENAI_COMPAT_BASE_URL")
        )
        resolved_key_env = (
            api_key_env
            or PRESET_API_KEY_ENVS.get(provider)
            or "OPENAI_COMPAT_API_KEY"
        )
        def compatible_call(messages):
            return call_openai_compatible(
                messages,
                model=model,
                base_url=resolved_url,
                api_key_env=resolved_key_env,
                max_tokens=max_tokens,
            )
        return compatible_call
    try:
        from modules.ai_scanner.providers import call_provider_messages
    except ImportError as exc:
        raise RuntimeError("Could not import modules.ai_scanner.providers. Run this from the repository root or install the project.") from exc
    def call(messages):
        return call_provider_messages(provider, messages, model=model)
    return call

def main(argv=None):
    parser = argparse.ArgumentParser(prog="guardrail-lab", description="Authorized AI guardrail robustness tests")
    parser.add_argument("--provider", choices=["openai", "anthropic", "gemini", "openai-compatible", *PRESET_BASE_URLS.keys()])
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None, help="OpenAI-compatible API base URL (for local servers or hosted providers)")
    parser.add_argument("--api-key-env", default=None, help="Override the environment variable used for the provider API key")
    parser.add_argument("--output", default="guardrail-report.json")
    parser.add_argument("--registry", default=None,
                        help="Optional JSONL findings registry; exact-canary signals are saved as unverified")
    parser.add_argument("--case", action="append", dest="case_ids", help="Case ID; repeat to select multiple. Default: all cases.")
    parser.add_argument("--source-corpus", action="store_true", help="Run all 52 source-derived safe adaptations (combine with --case to add individual cases).")
    parser.add_argument("--list", action="store_true", help="List cases without making API calls")
    parser.add_argument("--campaign", action="store_true", help="Run an automated, bounded adaptive campaign")
    parser.add_argument("--history", default=None,
                        help="Optional append-only JSONL campaign history; skips prior coverage and enables review-gated follow-ups")
    parser.add_argument("--research-mode", action="store_true", help="Enable the bounded adversarial research workflow: six reviewed framings, evidence-triggered follow-ups, and manual-review evidence. Does not generate unrestricted bypass payloads.")
    parser.add_argument("--budget", type=int, default=36, help="Maximum test requests (1-1000; default: 36); provider retries may add HTTP attempts")
    parser.add_argument("--unbounded-counts", action="store_true",
                        help="Remove candidate/build-attempt count ceilings; requires --max-seconds, --max-usd, and --estimated-cost-per-request")
    parser.add_argument("--max-build-attempts", type=int, default=None,
                        help="Optional ceiling on dequeued campaign candidates")
    parser.add_argument("--max-usd", type=float, default=None,
                        help="Estimated campaign spend ceiling in USD (requires --estimated-cost-per-request)")
    parser.add_argument("--estimated-cost-per-request", type=float, default=None,
                        help="Conservative fixed USD estimate reserved before each request")
    parser.add_argument("--variants", type=int, choices=[1, 2, 3, 4, 5, 6], default=3, help="Maximum reviewed prompt framings per flagged case")
    parser.add_argument("--no-adaptive", action="store_true", help="Disable evidence-triggered follow-up variations")
    parser.add_argument("--delay", type=float, default=0.0, help="Seconds between API calls")
    parser.add_argument("--max-seconds", type=float, default=None, help="Stop scheduling new requests after this many seconds; cannot interrupt an in-flight API request")
    parser.add_argument("--max-tokens", type=int, default=None, help="Cap the model's maximum output tokens per request (OpenAI-compatible providers only; omit to leave unset)")
    parser.add_argument("--judge-id", default=None, help="Identity of the review judge attached to this run (recorded in reproduction attributes)")
    parser.add_argument("--judge-hash", default=None, help="SHA-256 of the review judge command/config (recorded in reproduction attributes)")
    parser.add_argument("--require-ready", action="store_true",
                        help="Fail closed unless a benign real-forward smoke confirms readiness")
    parser.add_argument("--preflight-only", action="store_true",
                        help="Run the typed preflight and write its receipt without running cases")
    parser.add_argument("--preflight-output", default=None,
                        help="Optional JSON path for the preflight receipt (evidence)")
    args = parser.parse_args(argv)
    if args.list:
        for case in CASES:
            print(f"{case.case_id}\t{case.category}")
        return 0
    if not args.provider:
        parser.error("--provider is required unless --list is used")
    if args.provider in ("openai-compatible", *PRESET_BASE_URLS.keys()) and not (args.base_url or PRESET_BASE_URLS.get(args.provider) or os.getenv("OPENAI_COMPAT_BASE_URL")):
        parser.error("Set --base-url or OPENAI_COMPAT_BASE_URL for this provider")
    if args.provider in ("openai-compatible", *PRESET_BASE_URLS.keys()) and not (args.model or os.getenv("OPENAI_COMPAT_MODEL")):
        parser.error("Set --model or OPENAI_COMPAT_MODEL for this provider")
    if args.provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY is not set")
    if args.provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        parser.error("ANTHROPIC_API_KEY is not set")
    if args.provider == "gemini" and not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        parser.error("GEMINI_API_KEY or GOOGLE_API_KEY is not set")
    if args.provider in PRESET_API_KEY_ENVS:
        key_env = args.api_key_env or PRESET_API_KEY_ENVS[args.provider]
        if not os.getenv(key_env):
            parser.error(f"{key_env} is not set")
    if args.max_tokens is not None and args.max_tokens <= 0:
        parser.error("--max-tokens must be a positive integer")
    selected_case_ids = list(args.case_ids or [])
    if args.source_corpus:
        selected_case_ids.extend(case.case_id for case in SOURCE_CASES)
    if selected_case_ids:
        selected_case_ids = list(dict.fromkeys(selected_case_ids))
    else:
        selected_case_ids = None
    if args.research_mode and args.no_adaptive:
        parser.error("--research-mode cannot be combined with --no-adaptive")
    if args.research_mode:
        args.campaign = True
        args.variants = 6
    try:
        measured = {
            "provider": args.provider,
            "model": args.model,
            "case_set_hashes": case_set_hashes(),
        }
        if args.max_tokens is not None and args.provider in ("openai-compatible", *PRESET_BASE_URLS.keys()):
            measured["max_tokens"] = args.max_tokens
        if args.judge_id:
            measured["judge_id"] = args.judge_id
        if args.judge_hash:
            measured["judge_hash"] = args.judge_hash
        not_measured = []
        if args.max_tokens is not None and "max_tokens" not in measured:
            not_measured.append(not_measured_entry(
                "max_tokens", "hosted provider adapter does not transmit max_tokens"
            ))
        run_config = RunConfig(**measured, not_measured=not_measured)
        adapter = _adapter(args.provider, args.model, args.base_url, args.api_key_env, max_tokens=args.max_tokens)
        if args.require_ready or args.preflight_only:
            receipt = preflight(
                adapter, provider=args.provider, model=args.model,
                base_url=args.base_url,
                config={"provider": args.provider, "model": args.model,
                        "base_url_fingerprint": fingerprint_endpoint(args.base_url),
                        "max_tokens": args.max_tokens},
            )
            if args.preflight_output:
                dest = Path(args.preflight_output)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8")
            print(json.dumps(receipt, indent=2, ensure_ascii=False))
            if args.preflight_only:
                return 0 if receipt["state"] == "ready" else 2
            if receipt["state"] != "ready":
                print(f"preflight blocked the run: state={receipt['state']}", file=sys.stderr)
                return 2
        if args.campaign:
            report = run_campaign(
                adapter, provider=args.provider, model=args.model,
                budget=None if args.unbounded_counts else args.budget,
                variants=args.variants,
                max_build_attempts=None if args.unbounded_counts else args.max_build_attempts,
                max_usd=args.max_usd,
                estimated_cost_per_request=args.estimated_cost_per_request,
                adaptive=not args.no_adaptive, delay_seconds=args.delay,
                max_seconds=args.max_seconds, case_ids=selected_case_ids,
                history_path=args.history,
            )
            report.setdefault("provenance", {}).update(run_config.evidence_block())
        else:
            report = run_suite(
                adapter, provider=args.provider, model=args.model,
                case_ids=selected_case_ids, delay_seconds=args.delay,
                run_config=run_config, base_url=args.base_url,
            )
        write_report(report, args.output)
        if args.registry:
            saved = save_candidate_records(report, args.output, Path(args.registry))
            print(f"unverified_candidates_saved={len(saved)} registry={args.registry}")
    except (RuntimeError, KeyError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report["summary"], indent=2))
    print(f"Evidence report written to {args.output}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
