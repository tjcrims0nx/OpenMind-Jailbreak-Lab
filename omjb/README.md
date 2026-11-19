# OMJB: OpenMind evaluation harness

OMJB is an additive, provider-neutral evaluation package. It does not replace the repository's Guardrail Lab, 76-case suite, benchmark, scanner, original-source metadata browser, or manual-review workspace.

## Install and run

Python 3.10+; standard library only for the core package.

```bash
python -m unittest discover -s tests -p 'test_omjb.py' -v
python -m unittest discover -s tests -p 'test_guard_review.py' -v
python -m unittest discover -s tests -p 'test_downloaders.py' -v
python -m omjb.cli run --suite guardrail-lab --case GL-001 --name existing-lab-smoke --target echo
python -m omjb.cli run --probes corpus/omjb_probes.json --name offline-check --target echo
python -m omjb.cli list
python -m omjb.cli report 1
python -m omjb.cli adjudicate 1 --reviewer reviewer-1
python -m omjb.cli report 1 --reviewer reviewer-1
python -m omjb.cli regress 1 2
python -m omjb.cli guard-evaluate --corpus guard_samples.jsonl --name local-keyword-check --block-term "test marker"
python -m omjb.cli guard-adjudicate 1 --reviewer reviewer-1
python -m omjb.cli guard-report 1 --reviewer reviewer-1
python -m omjb.cli fetch --source-config source.json --output corpus/fetched.jsonl
python -m omjb.cli verify corpus/fetched.jsonl.manifest.json
python -m omjb.cli export 1 --format jsonl --output reports/run.jsonl
```

Install with `pip install .`; this adds the `omjb` console command. Optional YAML support: `pip install '.[yaml]'`. JSON and JSONL work without dependencies.

## Providers

Supported targets: Echo, OpenAI-compatible Chat Completions, Anthropic Messages, Google Gemini generateContent, and Ollama. Put credentials in environment variables, never source files:

- OpenAI-compatible: `OPENAI_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY`
- Gemini: `GEMINI_API_KEY`

Example Gemini run:

```bash
export GEMINI_API_KEY="YOUR_API_KEY"
python -m omjb.cli run --probes corpus/omjb_probes.json --name gemini-baseline --target gemini --model gemini-2.5-flash
```

Hosted endpoints require HTTPS. Ollama is restricted to localhost or HTTPS. Generation parameters are allowlisted; model, message and routing fields cannot be overridden through generation parameters. Live requests may incur provider charges.

## Data and guards

Probe files may be JSON arrays, common dictionary-root datasets (including `instructions`, `prompts`, `examples`, or `data`), JSONL/NDJSON, YAML, and gzip/bzip2-compressed variants. Each record requires a non-empty prompt and unique ID. Optional provenance is validated and stored; `--require-provenance` requires source and revision, and `--dedupe` removes duplicate content hashes. A record explicitly marked `runnable: false` is rejected by the runner loader.

The `omjb.guardrail_adapter` imports the repository's existing Guardrail Lab cases directly, including the 24 core cases and 52 reviewed source-derived safe adaptations. It preserves case IDs, expected signals, canaries, source metadata, native Guardrail Lab assessment labels, and the GL-009/GL-010 paired-turn context. Selecting GL-010 requires GL-009 immediately before it. It does not copy or execute the original-source archive. Run the existing suite through OMJB with `python -m omjb.cli run --suite guardrail-lab --name guardrail-omjb --target echo` (replace Echo with an authorized live provider when ready). The original `python -m modules.guardrail_lab` workflow remains unchanged.

Composable keyword, regex, composite, and optional model-assisted review guards are available; ordered stages are configured with `--pipeline-json PATH` or inline JSON. Model stages require `--judge-target gemini|openai|anthropic|ollama` and optional `--judge-model`; they can only flag for human review, never auto-confirm a finding. The legacy keyword review/block flags remain supported.

Example pipeline:

```json
{
  "name": "input-and-output-review",
  "stages": [
    {"name": "input-keywords", "on": "input", "policy": "block", "guard": {"kind": "keyword", "block_terms": ["example-marker"]}},
    {"name": "output-patterns", "on": "output", "policy": "flag", "guard": {"kind": "regex", "patterns": ["\\\\bexample\\\\b"]}}
  ]
}
```

Run it with `python -m omjb.cli run --suite guardrail-lab --name pipeline-check --target echo --pipeline-json pipeline.json`. A blocked input is not sent to the provider. A blocked output is quarantined in the evidence record and marked for review. A review decision is recorded but does not silently block. These are defensive controls, not jailbreak generation or bypass optimization.

## Standalone guard review and pinned downloads

Standalone guard evaluation accepts labeled JSON/JSONL/YAML corpora with `text` and `label` fields (`benign` or `attack`). Use `guard-evaluate` to persist each sample, expected label, guard decision, findings, and provenance in separate guard-evaluation tables. Use `guard-adjudicate` to review whether a recorded guard decision was correct, incorrect, unclear, or skipped. Reviewer identity scopes the pending queue. `guard-report` reports guard precision/recall against corpus labels and reviewer agreement separately. These records are intentionally not mixed with model-response adjudications (`refusal/compliance/partial/unclear/skip`), because a guard decision and a model response are different measurements.

The `fetch` command downloads only a caller-configured HTTPS source with an explicit immutable revision, license declaration, expected SHA-256, and `reviewed: true` after a human has confirmed the source is authorized and safe as a runnable test corpus. Its JSON config requires `name`, `url`, `sha256`, `revision`, `license`, `format`, and `prompt_field`; optional field mappings include `id_field`, `category_field`, `expected_field`, `system_field`, `author`, `date`, and `notes`. The downloader rejects hash mismatches and unsupported expected labels, writes probe-schema JSONL, and uses the existing provenance manifest writer. It does not invent source licenses or ship third-party corpora; the license field is a caller-supplied declaration, not an independent legal determination. Original archive prompts should remain metadata-only unless separately reviewed and transformed into safe adaptations. Example: `python -m omjb.cli fetch --source-config source.json --output corpus/fetched.jsonl`, followed by `python -m omjb.cli verify corpus/fetched.jsonl.manifest.json`.

## Evidence, adjudication and metrics

SQLite stores run configuration without API keys, prompts, responses, response SHA-256 digests, heuristic triage, guard observations and human adjudications. Existing databases are upgraded additively; tables are not dropped. Model reviewers can work independently using `adjudicate RUN_ID --reviewer NAME`; `report RUN_ID --reviewer NAME` and adjudication exports can be scoped to that reviewer. Existing calls without a reviewer retain the original shared-queue behavior.

Standalone guard evaluation persists separate `guard_eval_runs`, `guard_eval_results`, and `guard_adjudications` records. Guard labels are deliberately distinct: corpus truth is `benign/attack`, predictions are `allow/review/block`, and human assessments are `correct/incorrect/unclear/skip`. Use `guard-evaluate` with one or more `--review-term` or `--block-term` values, then `guard-adjudicate` and `guard-report`. Add `--reviewer NAME` to review and report a particular reviewer. The report separates corpus-based confusion metrics from human assessments; it does not combine guard results with model-response adjudications.

Reports show heuristic signals separately from adjudication-based precision, recall, F1 and Wilson confidence intervals. Only adjudicated refusal/compliance pairs are scored; partial, unclear, skip and unreviewed records are excluded. Regression compares stable probe IDs and reports added/removed cases.

Exports:

```bash
python -m omjb.cli export RUN_ID --format jsonl --output reports/run.jsonl
python -m omjb.cli export RUN_ID --format csv --output reports/run.csv
python -m omjb.cli export RUN_ID --format report --output reports/summary.json
```

`omjb.provenance` provides validated source/revision records and stable row hashes. Result rows persist provenance and per-stage pipeline traces; reports stratify adjudicated outcomes by category and source. `omjb.guard_eval.load_labeled` shares the same corpus reader for benign/attack guard datasets. Keep original archive records metadata-only and import only reviewed, inert test adaptations into runnable corpora. `omjb verify MANIFEST.json` checks a materialized corpus against its file-level SHA-256 manifest.

## Safety and interpretation

Use only systems you own or are authorized to assess. The harness does not generate, optimize, chain, or execute unrestricted jailbreaks, and it does not execute model-produced tool actions. Heuristic detections are triage, not ground truth. A flag is not a confirmed vulnerability; manually adjudicate and reproduce findings. Protect SQLite databases and exported transcripts because they may contain sensitive prompts and responses.
