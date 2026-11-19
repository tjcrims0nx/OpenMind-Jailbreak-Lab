# OMJB: OpenMind evaluation harness

This dependency-free subsystem adds repeatable provider-backed evaluation, SQLite evidence capture, heuristic triage, regression comparisons, and human adjudication.

## Run

From the repository root (Python 3.10+):

    python -m omjb.cli run --probes corpus/omjb_probes.json --name dry-run --target echo
    python -m omjb.cli list
    python -m omjb.cli report 1
    python -m omjb.cli adjudicate 1
    python -m omjb.cli regress 1 2

For a live OpenAI-compatible run, set a provider key in the environment; never put credentials in arguments or committed files:

    export OPENAI_API_KEY="..."
    python -m omjb.cli run --probes corpus/omjb_probes.json --name baseline --target openai --model gpt-4o-mini

Targets: openai (OpenAI-compatible Chat Completions), anthropic, ollama, and echo. Hosted endpoints require HTTPS; local Ollama is restricted to localhost unless using HTTPS. Generation parameters are allowlisted so callers cannot override model, messages, or endpoint routing.

## Evidence and interpretation

Each result stores the exact probe, response, SHA-256 response digest, model configuration (never the API key), heuristic label, timestamp, and optional human adjudication. The detector is deliberately conservative and is not ground truth. A heuristic flag is not a confirmed bypass; quoted discussion, partial answers, and benign-control false positives require human review. Automated labels remain separate from adjudicated labels.

## Safety and limits

Use only systems you own or are explicitly authorized to evaluate. The corpus is for benign controls and safe boundary calibration. The harness does not generate, optimize, chain, or execute jailbreaks; it does not execute model-produced tool calls or actions. Keep tests synthetic and bounded. Live provider requests can incur charges and reports may contain sensitive prompts and responses, so protect the SQLite database.

## Layout

- targets.py: Echo, OpenAI-compatible, Anthropic, and Ollama adapters.
- probes.py: strict JSON corpus loader.
- detectors.py: heuristic triage.
- storage.py: SQLite evidence and adjudication.
- runner.py: sequential, paced orchestration with per-case error capture.
- report.py: summaries and regression diffs.
- cli.py: command-line interface.
