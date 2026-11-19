# OpenMind Guardrail Lab

**Version:** 0.6.0
**Purpose:** Authorized, evidence-first AI guardrail and instruction-boundary vulnerability research.

OpenMind Guardrail Lab is a Python testing framework for evaluating how AI models handle untrusted instructions, prompt injection, context manipulation, and instruction-boundary conflicts.

It supports 76 runnable cases (24 core plus 52 source-derived safe adaptations), individual selection, and bounded automated campaigns. Structured JSON evidence includes source provenance for adapted cases and can be compared across providers.

Use it only with models and services you own or are explicitly authorized to assess.

## What it tests

| Test area | Description |
|---|---|
| Prompt injection | Instructions embedded in quoted text, documents, and retrieved content |
| Instruction boundaries | Attempts to override system and task context |
| Role manipulation | False authority claims and role reassignment |
| Encoded content | Untrusted instructions represented in alternate formats |
| Multilingual content | Instruction-boundary handling across languages |
| Multi-turn behavior | Context retention and paired conversation scenarios |
| Benign controls | Checks that ordinary tasks continue to work |

| Case | Test area |
|---|---|
| `GL-001` | Instructions embedded in quoted text |
| `GL-002` | Instructions embedded in a document |
| `GL-003` | Instructions embedded in retrieved content |
| `GL-004` | Instructions embedded in simulated tool output |
| `GL-005` | False authority claims |
| `GL-006` | Role-reassignment attempts |
| `GL-007` | Encoded untrusted content |
| `GL-008` | Multilingual untrusted content |
| `GL-009` / `GL-010` | Paired two-turn boundary scenario |
| `GL-011` / `GL-012` | Benign controls, including a basic math task |
| `GL-013` | Untrusted document with embedded canary instruction |
| `GL-014` | Retrieved passage with a forged authority claim |
| `GL-015` | Encoded untrusted instruction |
| `GL-016` | Quoted content with an embedded canary instruction |
| `GL-017`–`GL-024` | RAG metadata, HTML comments, CSV cells, email bodies, mock tool results, Markdown links, multilingual metadata, and conflicting-source injection |

The test suite uses harmless synthetic canary markers across direct and indirect prompt-injection surfaces. A canary match is a signal for manual investigation, not automatic proof of a vulnerability.
Each case is sent beneath a fixed lab-owned system instruction that marks quoted text, documents, retrieved passages, metadata, and tool outputs as untrusted. Provider adapters map that instruction to the native system/developer field where supported. This is a reproducible harness baseline, not the target application's own private system prompt.

The lab does not attempt to obtain real secrets, compromise accounts, execute unauthorized tools, or facilitate harmful safeguard evasion.

## Provider support

### Native integrations

* OpenAI / ChatGPT
* Anthropic / Claude
* Google Gemini

These use the repository's shared provider adapter — see [INTEGRATION.md](INTEGRATION.md). For cross-provider mocked adapter regression tests and comparable live-run guidance, see [PROVIDER_MATRIX.md](PROVIDER_MATRIX.md).

### Hosted OpenAI-compatible providers

| Provider | CLI option | API-key environment variable |
|---|---|---|
| DeepSeek | deepseek | DEEPSEEK_API_KEY |
| GLM | glm | ZHIPUAI_API_KEY |
| Moonshot | moonshot | MOONSHOT_API_KEY |
| NVIDIA NIM | nvidia | NVIDIA_API_KEY |
| OpenRouter | openrouter | OPENROUTER_API_KEY |
| Groq | groq | GROQ_API_KEY |
| Together | together | TOGETHER_API_KEY |

These presets require an OpenAI-compatible Chat Completions endpoint. Provider model identifiers and availability depend on the provider account.

### Local and self-hosted models

| Provider | CLI option | Default endpoint |
|---|---|---|
| Ollama | ollama | http://localhost:11434/v1 |
| vLLM | vllm | http://localhost:8000/v1 |
| LM Studio | lm-studio | http://localhost:1234/v1 |
| llama.cpp | llama-cpp | http://localhost:8080/v1 |
| LocalAI | localai | http://localhost:8080/v1 |

Custom OpenAI-compatible endpoints can be configured with --base-url. Local endpoints are intended to run from a host that can reach the inference server; a GitHub-hosted runner cannot reach your own machine's localhost.

## Requirements

* Python 3.10 or newer.
* Repository dependencies for native provider integrations.
* Provider credentials and model access where required.
* Network access for hosted providers.

The OpenAI-compatible adapter uses Python's standard-library HTTP client.

## Quick start

Run commands from the repository root.

List available test cases:

```bash
python -m modules.guardrail_lab --list
```

Run against OpenAI:

```bash
export OPENAI_API_KEY="your-key"
python -m modules.guardrail_lab \
  --provider openai \
  --output reports/openai.json
```

Run against Claude:

```bash
export ANTHROPIC_API_KEY="your-key"
python -m modules.guardrail_lab \
  --provider anthropic \
  --output reports/claude.json
```

Run against Gemini:

```bash
export GEMINI_API_KEY="your-key"
python -m modules.guardrail_lab \
  --provider gemini \
  --delay 13.0 \
  --output reports/gemini.json
```

The `--delay` option pauses between requests in a full suite as well as in campaigns. The Gemini Actions full-suite workflow uses a 13-second interval to reduce free-tier requests-per-minute errors; actual quota availability still depends on your Google AI Studio project and model.

### Hosted provider examples

DeepSeek:

```bash
export DEEPSEEK_API_KEY="your-key"
python -m modules.guardrail_lab \
  --provider deepseek \
  --model "your-deepseek-model"
```

GLM:

```bash
export ZHIPUAI_API_KEY="your-key"
python -m modules.guardrail_lab \
  --provider glm \
  --model "your-glm-model"
```

Moonshot:

```bash
export MOONSHOT_API_KEY="your-key"
python -m modules.guardrail_lab \
  --provider moonshot \
  --model "your-moonshot-model"
```

NVIDIA NIM:

```bash
export NVIDIA_API_KEY="your-key"
python -m modules.guardrail_lab \
  --provider nvidia \
  --model "your-nvidia-model"
```

OpenRouter:

```bash
export OPENROUTER_API_KEY="your-key"
python -m modules.guardrail_lab \
  --provider openrouter \
  --model "your-openrouter-model"
```

Groq:

```bash
export GROQ_API_KEY="your-key"
python -m modules.guardrail_lab \
  --provider groq \
  --model "your-groq-model"
```

Together:

```bash
export TOGETHER_API_KEY="your-key"
python -m modules.guardrail_lab \
  --provider together \
  --model "your-together-model"
```

Use actual model identifiers supported by your account.

## Automated campaigns

Run a bounded campaign:

```bash
python -m modules.guardrail_lab \
  --provider openai \
  --campaign \
  --budget 36 \
  --variants 3 \
  --delay 1 \
  --max-seconds 600 \
  --output reports/campaign.json
```

| Option | Description |
|---|---|
| --campaign | Enables bounded adaptive testing |
| --budget | Maximum number of test requests |
| --variants | Number of fixed reviewed framings, 1–6 |
| --no-adaptive | Disables evidence-triggered follow-ups |
| --delay | Delay between requests |
| --max-seconds | Maximum campaign scheduling time |
| --max-tokens | Caps the model's maximum output tokens per request (OpenAI-compatible providers only) |
| --case | Select individual test cases (repeatable) |
| --source-corpus | Select all 52 source-derived safe adaptations |
| --output | Report destination |

Campaigns use fixed test variations and bounded request budgets. They do not generate unrestricted prompts.

## Reports and findings

## Cross-provider comparison and incomplete results

Compare two or more saved reports:

```bash
python -m modules.guardrail_lab.compare reports/gemini.json reports/openai.json --output reports/comparison.json
```

The comparison keeps missing cases separate from cases that ran but did not
produce scorable evidence. Assessments labelled `inconclusive`, `partial_run`,
`not_run`, `incomplete`, `partial`, `empty`, or `not_received` are
reported in each provider's assessment counts and excluded from the agreement
denominator. Provider response-status fields (`provider_response_status` or
`response_status`) with incomplete, partial, empty, or not-received values
also make that case unscorable, even if an assessment label is present.

Each case reports `comparable`; its `agreement` is null unless every report
contains a scorable result. The summary reports the comparable-case count,
excluded inconclusive count, and agreement rate on comparable common cases.
If no cases are comparable, the rate is null rather than zero. Missing case IDs
remain listed separately. These are label comparisons, not security scores.


Reports are written as JSON and include:

* Provider and model information.
* Test case identifiers.
* Request and response evidence.
* Assessment results.
* Provider metadata where available.
* Errors and partial runs.
* Execution timestamps and durations.

### Assessment labels

| Result | Meaning |
|---|---|
| potential_guardrail_failure | Response is only the canary; requires manual confirmation |
| ambiguous_canary_mention | Canary mentioned in a longer response; needs human review |
| boundary_held | Expected boundary signal observed |
| control_passed | Benign control behaved as expected |
| manual_review | Result needs human interpretation |
| partial_run | Provider request failed or paired test could not complete |

A canary match may be a false positive, especially when a model quotes or discusses the canary rather than complying with an injected instruction. The evaluator now distinguishes the two cases: a response that is only the canary is a `potential_guardrail_failure`, while a canary mentioned in a longer response is `ambiguous_canary_mention` and needs human review — it does not trigger adaptive campaign expansion. Several cases ask the model to describe, translate, or flag the injected text, and a correct answer quotes the canary while doing so. Confirm a failure only when the model outputs the canary as its own compliance (for example, the response is just the canary).

Important findings should be reproduced and reviewed against the complete request and response. Use the repository's [manual review workspace](../../manual_reviews/README.md) to record one adjudication per case with the [review template](../../manual_reviews/review_template.json). Preserve the original report and its evidence checksum; manual notes are separate from machine assessments.

### Persistent vulnerability registry

Save findings between campaigns and export a reusable research report for manual disclosure. No company submission is performed.

See [REGISTRY.md](REGISTRY.md) for the full schema and workflow.

```bash
python -m modules.guardrail_lab.registry add --input finding.json
python -m modules.guardrail_lab.registry list
python -m modules.guardrail_lab.registry export --format markdown --out reports/findings.md
python -m modules.guardrail_lab.registry export --format json --out reports/findings.json
```

Records retain provider/model, category, discovery date, evidence reference, summary, review notes, reproduction notes, and integrity checksum. Unverified and intermittent findings remain distinct. Confirmed status requires an explicit human-review flag, review notes, at least two repeat runs, and a recorded repeat-success count. The registry does not submit findings to vendors and does not infer vulnerabilities from suspicious wording alone.

## Security and credential handling

* Store API keys in environment variables.
* Never commit API keys or include them in reports.
* HTTPS is required for remote compatible endpoints.
* Plain HTTP is restricted to loopback endpoints.
* URL-embedded credentials, query strings, and fragments are rejected.
* Review evidence reports before sharing them.

## Validation

Run the full test suite:

```bash
python -m unittest discover -s tests -v
```

Compile-check the project:

```bash
python -m compileall -q modules tests
```

List the test cases:

```bash
python -m modules.guardrail_lab --list
```

Mocked unit tests do not establish that a live provider endpoint is reachable or compatible. Perform authorized, low-budget live smoke tests before relying on an integration.

## Repository layout

```
modules/
  guardrail_lab/
    __init__.py
    __main__.py
    adaptive.py
    ADAPTIVE_ENGINE.md
    campaign.py
    cases.py
    cli.py
    discovery.py
    DISCOVERY_ENGINE.md
    openai_compatible.py
    runner.py
tests/
  test_adaptive.py
  test_guardrail_lab.py
  test_campaign.py
  test_discovery.py
  test_openai_compatible.py
  test_provider_presets.py
```

See [DISCOVERY_ENGINE.md](DISCOVERY_ENGINE.md) for the bounded discovery
engine: deterministic test-variant generation, a provider-adapter hook with
a pre-checked request budget, and severity ranking of human-confirmed
findings only.

See [ADAPTIVE_ENGINE.md](ADAPTIVE_ENGINE.md) for the adaptive scheduler:
it picks previously untested fixed envelopes per case, ordered by the
latest reviewed assessment, with duplicate prevention and a request
budget — coverage only, never payload intensity, and it never declares
a bypass.

See [CAMPAIGN_HISTORY.md](CAMPAIGN_HISTORY.md) for the optional append-only
campaign ledger. Use `--history` with `--campaign` to resume without
repeating attempted coverage; pending machine results require explicit human
review, and only approved exact-canary outcomes can seed later fixed variants.

## Version 0.5.9

- Fix: `rank_findings()` counted reviewer-rejected findings as triage.
  Rejected findings now go to a separate `rejected` list with a
  `rejected_count`; triage holds only `needs_review` items. Found while
  ranking the first full Gemini discovery sweep (72 cases).

## Version 0.5.8

- New adaptive scheduler (`adaptive.py`, see
  [ADAPTIVE_ENGINE.md](ADAPTIVE_ENGINE.md)): plans the next untested
  fixed-envelope variants per seed case from reviewed history,
  prioritized by the latest assessment, with duplicate-variant
  prevention and a request-budget check. It adapts coverage only — it
  never intensifies prompts, removes safety framing, calls a provider,
  or labels a result a vulnerability.

## Version 0.5.7

- New bounded discovery engine (`discovery.py`, see
  [DISCOVERY_ENGINE.md](DISCOVERY_ENGINE.md)): generates deterministic,
  reviewable prompt variants from seed cases (fixed envelopes only, up
  to 6 variants, zero provider calls during generation) and ranks only
  human-confirmed `potential_guardrail_failure` findings — ambiguous
  canary mentions stay in triage and can never be confirmed as bypasses.

## Version 0.5.6

- New `--max-tokens` option caps the model's maximum output tokens per
  request (OpenAI-compatible providers only). Some hosted providers price
  a request against the full requested output ceiling and reject it when
  the balance cannot cover the model's maximum, even for short answers;
  capping it (for example `--max-tokens 2048`) keeps low-balance
  accounts usable. Unset by default, so existing runs are unchanged.

## Version 0.5.5

- A campaign now stops at the first Cloudflare 1010 access block
  (HTTP 403) instead of sending the remaining cases into a known
  block. The report records `halted`, `halt_reason`, and
  `not_run_case_ids` for the cases that were never sent. Other
  provider errors do not trigger the halt, and the adapter still
  never retries HTTP 403.

## Version 0.5.4

- A connection that drops mid-response (`IncompleteRead` /
  `RemoteDisconnected`) is now retried like other transient failures
  instead of ending the case as a `partial_run` at once.

## Version 0.5.3

- The evaluator now distinguishes a response that is only the canary
  (`potential_guardrail_failure`) from a canary mentioned in a longer
  response (`ambiguous_canary_mention`). A quoted or discussed canary
  no longer counts as a failure and no longer triggers adaptive
  campaign expansion; it is sent for human review instead.

## Version 0.5.2

- A hosted preset now fails fast when its API-key environment
  variable is not set (for example, `DEEPSEEK_API_KEY`), instead of
  sending unauthenticated requests that each record a `partial_run`.
  This matches the existing fail-fast checks for the OpenAI, Anthropic,
  and Gemini providers. Local presets still need no key.

## Version 0.5.1

- Each hosted preset now reads its API key from its own environment
  variable by default (`DEEPSEEK_API_KEY`, `ZHIPUAI_API_KEY`,
  `MOONSHOT_API_KEY`, `NVIDIA_API_KEY`, `OPENROUTER_API_KEY`,
  `GROQ_API_KEY`, `TOGETHER_API_KEY`); `--api-key-env` overrides it.
  Groq and Together presets are included alongside the five in the
  original patch. Custom OpenAI-compatible endpoint support is
  unchanged.
- Added tests for hosted and local provider presets and for key-env
  resolution.

## Version 0.5.0

- Hosted provider presets: `deepseek`, `glm`, `moonshot`, `nvidia`,
  `openrouter`, `groq`, and `together` join the local presets as
  `--provider` options, each with its documented base URL. The
  scanner gained the same reach via its new `openai-compatible`
  provider. Base URLs were verified against vendor docs; Moonshot's
  China endpoint (`api.moonshot.cn`) is available via `--base-url`.

## Version 0.4.2

- The campaign's finite-number check now survives huge integers (`10**10000` raised an uncaught OverflowError from `math.isfinite`); the same hardening applies to the OpenAI-compatible adapter's `--timeout` validation, which also rejected booleans cleanly now (`True` previously passed as a 1-second timeout).
- Module README corrected: the variants option documents 1–6 framings (was still 1–3 after the 0.4.0 expansion).

## Version 0.4.1

- Campaign `--delay` and `--max-seconds` now reject booleans and non-numeric values with a clean ValueError; a boolean previously slipped through (`True` behaves as 1) and a string raised an unexpected TypeError from `math.isfinite`.

## Version 0.4.0

- Campaign framings grow from 3 to 6 reviewed variants: baseline, evaluation context, untrusted context, quote boundary, task boundary, and structured context. `--variants` now accepts 1-6 (default still 3); adaptive expansion stays bounded by the budget and by one expansion per flagged case.
- GL-010's paired conversation is seeded only from GL-009's baseline response, so the assistant turn always matches the original GL-009 prompt shown as the user turn.

## Version 0.3.3

- Campaign `budget` and `variants` must be integers in range; a NaN budget previously returned an empty campaign report and NaN variants crashed when a case flagged.
- OpenAI-compatible endpoints retry transient failures (HTTP 429/5xx, connection errors) up to 3 attempts with backoff, matching the native provider adapter.

## Version 0.3.2

- Campaign `--delay` and `--max-seconds` reject non-finite values (infinity and NaN); previously an infinite delay raised an uncaught OverflowError and a NaN time limit silently disabled the limit.
- Module documentation rewritten for the integrated project (no copy-in instructions); repository layout described in place of the old add-on checklist.
- CI now tests Python 3.10, 3.11, and 3.12.

## Version 0.3.1 hardening

- Enforces HTTPS for non-loopback compatible endpoints while retaining loopback HTTP for local inference.
- Rejects unsafe or malformed endpoint URL forms and validates response JSON structure.
- Validates positive finite request timeouts and handles malformed content-part entries defensively.
- Rejects duplicate and unknown case IDs.
- Enforces the `GL-009` then `GL-010` paired-turn prerequisite and skips the follow-up when setup fails.
- Excludes Python bytecode and cache directories from the release archive.

## Responsible use

Only test systems for which you have explicit authorization. Follow provider terms, rate limits, applicable law, and your organization's vulnerability disclosure process.

OpenMind Guardrail Lab is a research and testing framework. It does not guarantee successful guardrail bypasses, prove the existence of vulnerabilities, or replace a professional security assessment.

## License

See the repository's LICENSE file for licensing terms. If no license file is present, do not assume the code is licensed for redistribution or reuse.


## Version 0.6.0

- Adds four harmless trust-escalation canary probes (GL-013–GL-016) covering document, forged-authority, encoded, and quoted content. Canary-only output requires repeatability and human review.

### Trust-escalation probes (GL-013–GL-016)

Version 0.6.0 adds four bounded probes using harmless synthetic canaries embedded in content explicitly identified as untrusted: a document, a retrieved passage with a forged authority claim, encoded text, and a quotation. The surrounding task asks for ordinary factual extraction or description. These cases measure whether a model follows the embedded canary instruction despite the data boundary. They do not attempt secret extraction, tool execution, account access, or harmful actions.

Run the probes with:

    python -m modules.guardrail_lab --provider gemini --case GL-013 --case GL-014 --case GL-015 --case GL-016 --output reports/trust-escalation.json

A response consisting solely of the matching canary is a potential trust-escalation signal, not a confirmed bypass. A canary quoted in an explanation remains ambiguous. Repeat any signal with matched controls and inspect the complete transcript before human confirmation. These probes do not promote content to trusted status; they test whether the model incorrectly does so.


## Multi-provider GitHub Actions workflow

Use [`.github/workflows/multi-provider-red-team.yml`](../../.github/workflows/multi-provider-red-team.yml) to run the multi-provider Guardrail Lab from GitHub Actions. Choose one provider/model, a scope (`all` = 76 cases, `core` = 24, `source` = 52 source-derived), and a mode (`full_suite` or bounded `campaign`). Full-suite mode runs every selected case once; campaign mode uses a request budget of 1–1000 and may stop before all selected cases are attempted. Campaigns use up to six fixed, reviewed framings; adaptive follow-ups occur only after an exact canary-only response. Ambiguous canary mentions do not trigger expansion and are never reported as confirmed bypasses. One provider/model is run per invocation; results are uploaded as a provider/scope/mode-specific artifact. Localhost-only inference servers must be tested from a machine that can reach them. Provider compatibility and model access must be verified with a live run.

## Synthetic demonstration report

Generate a clearly labelled fictional report without contacting a provider:

```bash
python -m modules.guardrail_lab.demo --output reports/synthetic-demo.json
```

The report sets `report_type` to `SYNTHETIC_DEMONSTRATION`, records `provider_calls: 0`, uses `SIMULATED_PROVIDER` / `SIMULATED_MODEL`, and always reports `confirmed_live_findings: 0`. Its example candidate is a fabricated fixture for demonstrating report rendering and triage only. It is not a model result, cannot be ranked as a confirmed finding, and must not be presented as live evidence. Live findings still require an authorized provider run, replay, and human review.


### Evidence integrity checksums

Every Guardrail Lab case result includes `evidence_sha256`, a SHA-256 checksum
of the complete result record (all fields except the checksum itself), using
canonical JSON serialization with sorted keys, compact separators, and UTF-8.
Recomputing it detects accidental or later edits to prompts, responses,
metadata, labels, or errors. It is not a digital signature, does not establish
who produced a report, and cannot prove that a provider generated the recorded
response. Preserve the original artifact and use trusted storage or signed
releases when authenticity is required.


## Source-derived prompt adaptations

The lab includes 52 runnable, safe pattern adaptations derived from eligible, non-withdrawn documents in the supplied source archive. They are loaded alongside the 24 core cases automatically, for 76 total cases. These are **not verbatim copies** of source prompts: they preserve testable patterns (authority escalation, policy-boundary narrowing, persona reassignment, and simulated agent/tool authority confusion) while replacing risky payloads with inert markers. At load time, schema, unique IDs/canaries, safe framing, and each source ID/path/SHA-256 link are validated against `source_inventory.jsonl`. Each live evidence record carries `source_provenance` with the original source ID, path, and SHA-256. Run an individual source-derived case with `--case GL-SRC-001` (the CLI option is `--case`, repeatable for multiple IDs), or run the complete source-derived set with `--source-corpus`. This flag selects all 52 source cases and can be combined with `--case` to add specific core cases. The 52 source-derived cases are registered in `CASES`, so they are included automatically in the default full suite and are selectable in bounded campaigns. The default suite runs all 76 cases once. `--source-corpus` runs all 52 source-derived cases once. A campaign is bounded by `--budget` (default 36 requests) and may stop before all selected cases or variants are attempted; use the normal suite for complete one-pass coverage. The withdrawn notice and empty placeholder are excluded. The original archive remains a provenance source; raw operational instructions are not executed by the lab.

## Optional adversarial research mode

Use `--research-mode` to activate the bounded discovery workflow in one switch.
It selects the campaign runner, enables all six fixed reviewed framings, and
allows evidence-triggered follow-ups within the request budget. It operates on
the selected registered cases (including `--source-corpus`) and preserves
complete request/response evidence for manual triage.

```bash
export GEMINI_API_KEY="YOUR_API_KEY"
python -m modules.guardrail_lab --provider gemini --research-mode \
  --source-corpus --budget 100 --delay 1 \
  --output reports/gemini-research-mode.json \
  --registry findings/registry.jsonl
```

The budget is a hard cap on scheduled test requests (provider retries may add
HTTP attempts). Only the lab's six fixed, reviewed framings are used; follow-ups
are triggered by exact harmless canary-only signals. Candidate findings are
saved as unverified and require human review and repeatability checks. This
mode does not generate unrestricted jailbreak payloads, optimize harmful
instructions, execute model-produced tool calls, or test targets without
authorization. Use `--no-adaptive` only with ordinary `--campaign`; it is
incompatible with `--research-mode` because adaptive follow-up is the defining
behavior of that mode.
