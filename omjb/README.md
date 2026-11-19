# OMJB: OpenMind evaluation harness

OMJB is an additive, provider-neutral evaluation package. It does not replace the repository's Guardrail Lab, 76-case suite, benchmark, scanner, original-source metadata browser, or manual-review workspace.

## Install and run

Python 3.10+; standard library only for the core package.

```bash
python -m unittest discover -s tests -p 'test_omjb.py' -v
python -m omjb.cli run --probes corpus/omjb_probes.json --name offline-check --target echo
python -m omjb.cli list
python -m omjb.cli report 1
python -m omjb.cli adjudicate 1
python -m omjb.cli regress 1 2
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

Probe files may be JSON arrays, JSONL records, or YAML lists (YAML requires PyYAML). Each record requires a non-empty prompt and unique ID. Optional provenance is carried as metadata; a record explicitly marked `runnable: false` is rejected by the runner loader.

Composable keyword, regex and composite guards are available in `omjb.guard`. The CLI exposes keyword review/block controls at input and output stages. A blocked input is not sent to the provider. A blocked output is quarantined in the evidence record and marked for review. A review decision is recorded but does not silently block. These are defensive controls, not jailbreak generation or bypass optimization.

## Evidence, adjudication and metrics

SQLite stores run configuration without API keys, prompts, responses, response SHA-256 digests, heuristic triage, guard observations and human adjudications. Existing databases are upgraded additively; tables are not dropped. Manual labels are stored separately from model/heuristic labels.

Reports show heuristic signals separately from adjudication-based precision, recall, F1 and Wilson confidence intervals. Only adjudicated refusal/compliance pairs are scored; partial, unclear, skip and unreviewed records are excluded. Regression compares stable probe IDs and reports added/removed cases.

Exports:

```bash
python -m omjb.cli export RUN_ID --format jsonl --output reports/run.jsonl
python -m omjb.cli export RUN_ID --format csv --output reports/run.csv
python -m omjb.cli export RUN_ID --format report --output reports/summary.json
```

`omjb.provenance` provides source SHA-256 manifests. Keep original archive records metadata-only and import only reviewed, inert test adaptations into runnable corpora.

## Safety and interpretation

Use only systems you own or are authorized to assess. The harness does not generate, optimize, chain, or execute unrestricted jailbreaks, and it does not execute model-produced tool actions. Heuristic detections are triage, not ground truth. A flag is not a confirmed vulnerability; manually adjudicate and reproduce findings. Protect SQLite databases and exported transcripts because they may contain sensitive prompts and responses.
