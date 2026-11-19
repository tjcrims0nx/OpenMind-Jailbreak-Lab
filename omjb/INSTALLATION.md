# OMJB installation and operator guide

OMJB is the additive evaluation harness in this repository. It can evaluate an external labeled/probe corpus or call the existing Guardrail Lab case adapter. It does not replace the Guardrail Lab CLI, its 76-case suite, the benchmark, AI Scanner, original-source metadata browser, or manual-review workspace.

## Requirements and installation

- Python 3.10 or newer.
- Git, if cloning the repository.
- No required third-party runtime dependencies for the core package.
- Optional PyYAML only when reading YAML corpora.

Clone and enter the repository:

```bash
git clone https://github.com/tjcrims0nx/OpenMind-Jailbreak-Lab.git
cd OpenMind-Jailbreak-Lab
```

Create and activate a virtual environment:

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell (use this instead of the previous line)
.venv\Scripts\Activate.ps1
```

Install OMJB in editable mode:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

Editable install makes the `omjb` console command available and picks up repository changes without reinstalling. To install optional YAML support:

```bash
python -m pip install -e '.[yaml]'
```

Alternatively, install the package non-editably with `python -m pip install .`. JSON arrays, dictionary-root JSON, JSONL/NDJSON, gzip, and bzip2 inputs are supported by the core reader without PyYAML.

## Verify before using a live provider

Run from the repository root:

```bash
python -m unittest discover -s tests -p 'test_omjb.py' -v
python -m omjb.cli list
python -m omjb.cli run --suite guardrail-lab --case GL-001 --name local-smoke --target echo
python -m omjb.cli report 1
```

The Echo target is offline and makes no network requests. The example report ID `1` assumes it is the first run in the default database; use the ID printed by `omjb list` if the database already contains runs. The repository-wide checks are:

```bash
python -m unittest discover -s tests -v
python -m src.validate
```

## Run the existing Guardrail Lab cases

OMJB imports cases from the existing Guardrail Lab registry; it does not duplicate or rewrite the source suite.

Run all 76 runnable cases (24 core plus 52 reviewed source-derived safe adaptations):

```bash
python -m omjb.cli run --suite guardrail-lab --name guardrail-lab-76 --target echo
```

Run selected cases:

```bash
python -m omjb.cli run --suite guardrail-lab --case GL-001 --case GL-004 --name selected-smoke --target echo
```

The GL-009/GL-010 paired-turn dependency is preserved. If selecting GL-010, include GL-009 immediately before it. The original-source archive remains metadata-only and is not loaded as runnable prompts. The original Guardrail Lab workflow remains available with `python -m modules.guardrail_lab`.

## Load an external corpus

Supply either `--probes PATH` or `--suite guardrail-lab`. Each probe record needs a unique ID and a non-empty prompt. Supported inputs include:

- JSON arrays.
- Dictionary-root JSON with recognized record collections such as `instructions`, `prompts`, `examples`, or `data`.
- Split-keyed JSON objects (for example `train`, `validation`, `valid`, `test`, or `dev`).
- JSONL/NDJSON.
- YAML (install the `yaml` extra).
- gzip and bzip2 compressed variants.

Example JSONL:

```json
{"id":"probe-001","prompt":"Summarize this harmless test note.","category":"instruction-boundary"}
```

Run offline with Echo:

```bash
python -m omjb.cli run --probes path/to/probes.jsonl --name corpus-smoke --target echo
```

Use `--require-provenance` to require source and revision metadata. Use `--dedupe` to remove duplicate prompt-content hashes. Records explicitly marked `runnable: false` are not accepted by the runner. The labeled guard-evaluation loader also uses the shared corpus reader.

## Configure a provider

Set credentials in your shell environment; do not paste keys into source files, command history, JSON pipeline files, reports, or commits.

| Target | Environment variable | Notes |
|---|---|---|
| Gemini | `GEMINI_API_KEY` | Google Gemini generateContent API |
| Anthropic | `ANTHROPIC_API_KEY` | Anthropic Messages API |
| OpenAI-compatible | `OPENAI_API_KEY` by default | Chat Completions-compatible endpoint; override with `--api-key-env` |
| Ollama | none by default | Local endpoint; no API key required for standard local setup |
| Echo | none | Offline smoke testing only |

macOS/Linux examples:

```bash
export GEMINI_API_KEY="YOUR_API_KEY"
export ANTHROPIC_API_KEY="YOUR_API_KEY"
export OPENAI_API_KEY="YOUR_API_KEY"
```

Windows PowerShell:

```powershell
$env:GEMINI_API_KEY="YOUR_API_KEY"
$env:ANTHROPIC_API_KEY="YOUR_API_KEY"
$env:OPENAI_API_KEY="YOUR_API_KEY"
```

Gemini:

```bash
python -m omjb.cli run --probes path/to/probes.jsonl --name gemini-eval --target gemini --model gemini-2.5-flash
```

Anthropic:

```bash
python -m omjb.cli run --probes path/to/probes.jsonl --name claude-eval --target anthropic --model YOUR_MODEL_ID
```

OpenAI or an OpenAI-compatible endpoint:

```bash
python -m omjb.cli run --probes path/to/probes.jsonl --name openai-eval --target openai --model YOUR_MODEL_ID
# For a compatible gateway, add --base-url https://YOUR-HOST/v1
# If its key uses another environment variable, add --api-key-env YOUR_KEY_VARIABLE
```

Ollama (ensure the server is running and the model is already pulled):

```bash
python -m omjb.cli run --probes path/to/probes.jsonl --name local-ollama --target ollama --model YOUR_LOCAL_MODEL
```

Hosted endpoints must use HTTPS. Ollama accepts localhost or HTTPS. Live calls may incur provider charges and are subject to provider availability, account limits, and model access. Use a small authorized smoke test before a larger run.

## Guard pipelines

Optional keyword review/block checks are available with repeated flags:

```bash
python -m omjb.cli run --suite guardrail-lab --name guarded-run --target echo \
  --input-review-term example-marker \
  --output-block-term example-output-marker
```

For ordered multi-stage pipelines, provide JSON using `--pipeline-json PATH` (or inline JSON). A stage specifies its name, direction (`input` or `output`), policy, and guard configuration. Supported defensive guard types include keyword, regex, and composite; optional model-assisted stages require a judge target:

```bash
python -m omjb.cli run --suite guardrail-lab --name judge-review --target gemini \
  --judge-target gemini --judge-model gemini-2.5-flash --pipeline-json pipeline.json
```

Model-assisted stages are review-only: they can flag material for human inspection but cannot automatically confirm a bypass. Input blocks prevent the corresponding input from being sent; output blocks quarantine the returned output in the evidence record. Review flags do not silently block.

## Evidence, adjudication, reports, and regression

The default SQLite database is `openmind.db`; override it with global `--db PATH` before the subcommand. The database stores run configuration without API keys, probe/response evidence, hashes, guard observations, pipeline traces, provenance, and human adjudications. Existing databases are upgraded additively.

Common commands:

```bash
python -m omjb.cli list
python -m omjb.cli report RUN_ID
python -m omjb.cli adjudicate RUN_ID
python -m omjb.cli regress BASELINE_RUN_ID CANDIDATE_RUN_ID
python -m omjb.cli export RUN_ID --format jsonl --output reports/run.jsonl
python -m omjb.cli export RUN_ID --format csv --output reports/run.csv
python -m omjb.cli export RUN_ID --format report --output reports/summary.json
```

Use `--include-adjudication` to include human labels in JSONL/CSV exports, or `--adjudicated-only` to export only adjudicated rows. Human labels remain separate from heuristic labels. Reports calculate adjudication-based metrics only from eligible reviewed outcomes; unreviewed, unclear, skipped, and partial records are not treated as passes. Regression compares stable probe IDs.

Provenance manifests can be checked with:

```bash
python -m omjb.cli verify path/to/MANIFEST.json
```

## Safety, privacy, and interpretation

Use only systems you own or are explicitly authorized to assess. OMJB is a bounded evaluation and defensive review harness: it does not generate or optimize unrestricted jailbreaks, chain discovered weaknesses into operational bypasses, or execute model-produced tool instructions. Heuristic labels are triage, not ground truth. A candidate signal requires transcript review, reproduction, matched controls where appropriate, and human adjudication.

Live requests may incur costs. Prompts, responses, SQLite databases, and exports may contain sensitive information; restrict access and redact before sharing. Never commit API keys. If a key is exposed, revoke it and issue a replacement.

## Related documentation

- [OMJB technical reference](README.md)
- [Repository installation guide](../INSTALLATION.md)
- [Guardrail Lab guide](../modules/guardrail_lab/README.md)
- [Provider matrix](../modules/guardrail_lab/PROVIDER_MATRIX.md)
- [Manual review workspace](../manual_reviews/README.md)
