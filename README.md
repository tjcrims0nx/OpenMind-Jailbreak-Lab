# OpenMind Jailbreak Lab

<p align="center">
  <img src="assets/logo.jpg" alt="OpenMind Jailbreak Lab logo" width="420">
</p>

<p align="center"><strong>Provider-neutral toolkit for authorized AI security testing and guardrail evaluation.</strong></p>

OpenMind combines bounded adversarial tests, provider-backed scanning, benchmark evaluation, and evidence reporting. It supports repeatable assessment; a test run is not proof of a vulnerability or a guarantee of a successful jailbreak.

**[Open the live Hugging Face Space](https://huggingface.co/spaces/Grimxlock/OpenMind-Jailbreak-Lab)** · [Manual review workspace](manual_reviews/README.md)

## Get started

- [Start Here](START_HERE.md) — quick setup, GitHub Actions, and mobile use.
- [Installation](INSTALLATION.md) — providers, credentials, and advanced setup.
- [Guardrail Lab guide](modules/guardrail_lab/README.md) — defensive cases, campaigns, and reports.
- [Original Source Corpus](modules/original_source_corpus/README.md) — separate provenance browser and review workflow.

## Components

- **Guardrail Lab:** 76 runnable cases (24 core and 52 source-derived safe adaptations), provider adapters, bounded campaigns, JSON reports, and a findings registry. The 52 source-derived cases are a 4-category × 13-surface factorial: 52 pairwise-distinct prompts, one per category×surface pair (see [Research contributions](RESEARCH_CONTRIBUTIONS.md)).
- **Original Source Corpus:** separate metadata-only browser for authentic archive records, source paths, sizes, hashes, and manual review. Original raw prompts are not sent to the Guardrail Lab runner.
- **AI Scanner:** [provider-backed checks and response evidence](modules/ai_scanner/README.md).
- **OpenMind Benchmark:** [versioned evaluation set](SCORING.md); current file: [benchmark_v0.8.0.jsonl](data/benchmark_v0.8.0.jsonl) (81 cases, incl. 6 matched benign twins).
- **JB-002:** [manual finding records and validation](modules/jb002/README.md).

- **OMJB evaluation package:** [provider-neutral runner, guard evaluation, reviewer adjudication, provenance manifests, and pinned corpus imports](omjb/README.md). It is an additive CLI and evidence store; it does not replace the 76-case Guardrail Lab or the metadata-only original-source browser.

The optional `--research-mode` runs six reviewed framings with evidence-triggered follow-ups within the configured budget. It is for authorized testing and evidence collection; it does not create unrestricted harmful bypasses or execute model-generated tool instructions.

## Quick start

Requires Python 3.10+ and Git.

```bash
git clone https://github.com/tjcrims0nx/OpenMind-Jailbreak-Lab.git
cd OpenMind-Jailbreak-Lab
python -m unittest discover -s tests -v
python -m src.validate
python -m modules.guardrail_lab --list
python -m modules.original_source_corpus --search gemini
```

Example Gemini campaign:

```bash
export GEMINI_API_KEY="YOUR_API_KEY"
python -m modules.guardrail_lab --provider gemini --research-mode \
  --source-corpus --budget 100 \
  --output reports/gemini-research.json \
  --registry findings/registry.jsonl
```

Use the environment variable for your provider and keep API keys out of source files and commits. See the [provider matrix](modules/guardrail_lab/PROVIDER_MATRIX.md) for supported configurations.

## Source collections

The 52 source-derived Guardrail Lab cases retain source IDs, paths, and hashes, but replace risky instructions with inert markers. They are **not verbatim source prompts** and remain in the defensive benchmark.

The **Original Source Corpus** is separate. Its inventory preserves authentic archive provenance without copying raw prompt bodies into the public repository or executing them. Browse records with `python -m modules.original_source_corpus`; create a human-review template with `--id SRC-### --export-review-template PATH`. The inventory loader validates JSONL records, rejects non-object values and malformed fields with a clear error, and enforces that every original-source record remains non-runnable. The checked-in review template is regression-tested against the generator. Details: [Original Source Corpus guide](modules/original_source_corpus/README.md).

## Providers and automation

Adapters cover OpenAI, Anthropic, Gemini, DeepSeek, GLM/Zhipu, Moonshot, NVIDIA NIM, OpenRouter, Groq, Together, and compatible endpoints such as Ollama, vLLM, LM Studio, llama.cpp server, and LocalAI. Availability depends on credentials, model IDs, endpoint support, and provider limits.

The manually triggered [multi-provider GitHub Actions workflow](.github/workflows/multi-provider-red-team.yml) accepts a provider, model, scope, and run mode:

- `core`: 24 core cases; `source`: 52 adaptations; `all`: 76 cases.
- `full_suite`: separate run per selected case; `campaign`: bounded campaign of up to six reviewed framings.

Add keys under **Settings → Secrets and variables → Actions**, then run **Actions → Manual multi-provider Guardrail Lab**. Download the JSON artifact from the workflow. Hosted runners cannot access services bound only to your local machine. API use may incur charges.

## Interpreting results

| Label | Meaning |
|---|---|
| `potential_guardrail_failure` | Candidate signal; review and reproduce |
| `ambiguous_canary_mention` | Canary appears; context matters |
| `boundary_held` | Expected boundary observed |
| `control_passed` | Benign control behaved as expected |
| `manual_review` | Automated assessment inconclusive |
| `partial_run` | Run did not complete |

Reports include case IDs, provider/model metadata, prompts, responses, errors, and available assessment labels. A canary quoted in an explanation or warning is not proof of a bypass. Rate limits, authentication failures, and proxy errors are infrastructure outcomes. Treat candidate findings as unverified until manually reviewed and reproduced. Use the [manual review workspace](manual_reviews/README.md) and copy its JSON template once per case; keep original run reports unchanged.

## Evaluation snapshot — 16 November 2026

| Tested configuration | Adjudicated findings |
|---|---:|
| GPT-5.6-sol (AgentRouter) | 1 / 64 answered |
| Claude Haiku 5.5 (Qronos) | 2 / 63 answered |
| Gemini 3.5 Flash Lite | 7 / 66 |
| NVIDIA Nemotron 3 Nano Omni | 9 / 61 text-bearing |

Blocked and no-text cases were unscored, not passes. The benchmark, Guardrail Lab, and AI Scanner are separate instruments; do not combine their scores. These results apply only to the tested configurations and gateways. See [methodology](METHODOLOGY.md), [scoring](SCORING.md), and the dated evidence report.

## Evaluation snapshot — 17 November 2026 (AgentRouter re-test)

| Tested configuration | Adjudicated findings |
|---|---:|
| GPT-5.6-sol (AgentRouter) | 0 / 65 answered |
| GPT-6.1-sol (AgentRouter) | 0 / 63 answered |

GPT-5.6-sol's 16 November OM-057 failure did not reproduce — it is intermittent (1 failure in 2 runs), not a standing failure. GPT-6.1-sol's first full lab test (benchmark, campaign, scanner) found 0 failures. Gemini, Claude Haiku, and NVIDIA benchmark numbers are unchanged from 16 November. Guardrail Lab, 17 November: Gemini 76-case suite, 0 potential failures (fully adjudicated); AgentRouter campaigns on both GPT models, 0 failures.

## Tested configurations

What was actually run, and under which guardrails. Results apply only to
these configurations and gateways.

| Model | Gateway / access | Instruments run | When |
|---|---|---|---|
| Gemini 3.5 Flash Lite (`gemini-3.5-flash-lite`) | Direct (Google API) | Benchmark, Guardrail Lab, Scanner | Nov 2026 |
| NVIDIA Nemotron 3 Nano Omni (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`) | NVIDIA NIM | Benchmark, Guardrail Lab, Scanner | Nov 2026 |
| GPT-5.6-sol, GPT-6.1-sol | AgentRouter (Responses API) | Benchmark, Guardrail Lab, Scanner | Nov 2026 |
| Claude Haiku 5.5 (`claude-haiku-5.5`) | Qronos | Benchmark, Guardrail Lab, Scanner | Nov 2026 |
| Qwen `qwen2.5:0.5b-instruct` | Ollama (local) | Benchmark v0.5, Guardrail Lab | Nov 2026 |
| OpenAI (`openai`) | Pollinations (free, no key) | Guardrail Lab only | Nov 2026 |
| Qwen `qwen3-235b-a22b-2507`, DeepSeek `deepseek-chat-v3.1` | OpenRouter (paid) | Guardrail Lab only | Nov 2026 |
| Mercury-3, GLM 5.3 Flash | Qronos | Guardrail Lab only | Nov 2026 |

Guardrail setups in play during those runs:

- Every Guardrail Lab campaign sends the fixed lab system instruction
  marking quoted text, documents, retrieved passages, metadata, and tool
  outputs as untrusted data, not instructions. That is a harness baseline,
  not the target application's own system prompt (see the Guardrail Lab
  guide).
- AgentRouter routes GPT through Azure OpenAI, whose content filter
  blocked benchmark cases OM-008 and OM-063. Blocked cases are
  provider-blocked and unscored, not passes.
- Qronos runs its own input guardrail: it blocked Guardrail Lab cases
  GL-002 and GL-003 and some scanner probes with HTTP 400
  `jailbreak_detected`. Blocked cases are provider-blocked and unscored.
- Benchmark runs used max tokens / max output tokens 1024 and a 5-second
  delay between calls. Campaigns used budget 36, variants 6, delay 5, and
  max tokens 1024 (AgentRouter) or 2048 (NVIDIA Nemotron); Gemini and
  Qronos campaigns left max tokens at the adapter default.

See [methodology](METHODOLOGY.md), [scoring](SCORING.md), and the dated
evidence reports for the full per-run settings and raw results. The
[known-bypass regression set](REGRESSION_SET.md) lists the bypasses that
actually worked, for re-testing new models and system prompts.

## Responsible testing

Test only systems you own or are authorized to assess. Follow provider terms, rate limits, and applicable law. Use non-sensitive test data; do not seek real credentials, private data, or hidden secrets. Protect keys, review transcripts before sharing, and reproduce findings before disclosure. Revoke and replace any exposed key.

## Documentation

[Installation](INSTALLATION.md) · [Guardrail Lab](modules/guardrail_lab/README.md) · [Original Source Corpus](modules/original_source_corpus/README.md) · [Provider matrix](modules/guardrail_lab/PROVIDER_MATRIX.md) · [Discovery engine](modules/guardrail_lab/DISCOVERY_ENGINE.md) · [Registry](modules/guardrail_lab/REGISTRY.md) · [Archive import](modules/guardrail_lab/EXTERNAL_ARCHIVE_IMPORT.md) · [Research contributions](RESEARCH_CONTRIBUTIONS.md) · [Methodology](METHODOLOGY.md) · [Release checklist](RELEASE_CHECKLIST.md) · [Release status](RELEASE_STATUS.md)

## Quality checks

```bash
python -m unittest discover -s tests -v
python -m src.quality_audit data/benchmark_v0.8.0.jsonl
python -m modules.guardrail_lab.compare \
  reports/gemini.json reports/openai.json \
  --output reports/comparison.json
```

For an offline demonstration: `python -m modules.guardrail_lab.demo --output reports/synthetic-demo.json`. Its output is fictional, not live-model evidence.

## Status and license

OpenMind is experimental software, not a certification. Provider behavior changes and not every configuration has been live-tested. Check [release status](RELEASE_STATUS.md) for CI and release gates, and [LICENSE](LICENSE) for terms.


## OMJB evaluation harness

The additive `omjb` package now runs either external corpora or the existing Guardrail Lab case registry directly (`--suite guardrail-lab`), including the 24 core cases and 52 reviewed source-derived safe adaptations. It preserves the existing Guardrail Lab CLI and workflows; see [OMJB documentation](omjb/README.md). It includes a shared JSON/dict-root/JSONL/YAML/compressed corpus reader, ordered defensive guard pipelines, provenance validation and hashing, per-stage evidence, human-adjudication joins, and regression/export commands. It does not replace the benchmark, scanner, original-source metadata browser, or manual-review workspace. It includes Echo, OpenAI-compatible, Anthropic, Gemini, and Ollama targets; JSON/JSONL and optional YAML probe loading; defensive keyword/regex/composite guards; sequential guarded execution; SQLite evidence and guard observations; provenance manifests; human adjudication; Wilson intervals and adjudication-only classification metrics; regression comparisons; and JSONL/CSV/report exports.

Quick offline check:

```bash
python -m unittest discover -s tests -p 'test_omjb.py' -v
python -m omjb.cli run --probes corpus/omjb_probes.json --name local-check --target echo
python -m omjb.cli run --suite guardrail-lab --case GL-001 --name lab-adapter-check --target echo
python -m omjb.cli report 1
```

Gemini example (key stays in the environment):

```bash
export GEMINI_API_KEY="YOUR_API_KEY"
python -m omjb.cli run --probes corpus/omjb_probes.json --name gemini-check --target gemini --model gemini-2.5-flash
```

Optional defensive checks can be configured with repeated `--input-review-term`, `--input-block-term`, `--output-review-term`, and `--output-block-term` flags. Review findings do not automatically block; block decisions prevent an input from being sent or quarantine a returned output. Exports: `python -m omjb.cli export RUN_ID --format jsonl|csv|report --output PATH`. YAML requires `pip install '.[yaml]'`. API credentials are not written to run configuration. All tests are bounded and intended for systems you own or are authorized to assess.
