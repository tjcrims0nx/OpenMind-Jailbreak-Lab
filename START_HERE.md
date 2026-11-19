# Start Here

OpenMind Jailbreak Lab is a controlled evaluation tool for authorized testing of AI instruction-boundary behavior. This guide is the shortest supported path to a real run.

## The fastest route: GitHub Actions

You can run a test from the GitHub website or mobile app. You do not need to install Python locally.

### 1. Add one provider API key

In the repository, open **Settings → Secrets and variables → Actions → New repository secret**.

Create the secret for the provider you intend to test:

| Provider | Secret name |
|---|---|
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Gemini | `GEMINI_API_KEY` |
| DeepSeek | `DEEPSEEK_API_KEY` |
| GLM | `ZHIPUAI_API_KEY` |
| Moonshot | `MOONSHOT_API_KEY` |
| NVIDIA NIM | `NVIDIA_API_KEY` |
| OpenRouter | `OPENROUTER_API_KEY` |
| Groq | `GROQ_API_KEY` |
| Together | `TOGETHER_API_KEY` |

Paste the key into GitHub's secret-value field, not into a workflow input, issue, chat, or source file. Save it.

### 2. Start one provider/model run

1. Open the repository's **Actions** tab.
2. Select **Manual multi-provider Guardrail Lab**.
3. Select **Run workflow**.
4. Choose one provider.
5. Enter the exact model ID supported by your provider account.
6. Choose **Scope**: `all` (76 cases), `core` (24 cases), or `source` (52 source-derived safe adaptations).
7. Choose **Mode**: `full_suite` runs each selected case once; `campaign` uses a bounded request budget (default 24, maximum 1000).
8. For a custom OpenAI-compatible endpoint, provide its HTTPS base URL. Leave this blank for the named providers.
9. Select **Run workflow**.

One workflow run tests one provider and one model. For the complete source-derived set on any supported provider, select Scope `source` and Mode `full_suite`. For every case, select Scope `all` and Mode `full_suite`. Campaign mode may stop before every selected case when its request budget is reached. To compare models, run the workflow again with a different model.

### 3. Download and review the report

When the workflow finishes:

1. Open the completed workflow run.
2. Find **Artifacts** near the bottom of the run page.
3. Download `openmind-<provider>-<scope>-<mode>-evidence`.
4. Open the JSON report and review the full request, response, model, timestamps, errors, and assessment for each case.

A successful workflow means the requests and report completed. It does **not** mean a jailbreak succeeded or that the model is certified secure.

## Run locally (optional)

Requirements: Python 3.10+ and Git.

```bash
git clone https://github.com/tjcrims0nx/OpenMind-Jailbreak-Lab.git
cd OpenMind-Jailbreak-Lab
python -m unittest discover -s tests -v
python -m modules.guardrail_lab --list
python -m modules.guardrail_lab --list | grep GL-SRC
```

Set the API key in your terminal, then run the suite. Example for Gemini:

```bash
export GEMINI_API_KEY="YOUR_API_KEY"
python -m modules.guardrail_lab \
  --provider gemini \
  --model "YOUR_GEMINI_MODEL_ID" \
  --delay 5 \
  --output reports/gemini.json
```

On Windows PowerShell, set the key with:

```powershell
$env:GEMINI_API_KEY="YOUR_API_KEY"
```

Then run the same Python command, using `py -m` if your system uses the Windows Python launcher.

## Read the result labels correctly

| Label | Meaning |
|---|---|
| `boundary_held` | The expected safe boundary signal was observed. |
| `control_passed` | A benign control behaved as expected. |
| `ambiguous_canary_mention` | The canary appears in a longer response; inspect the context. |
| `potential_guardrail_failure` | The response consists only of the case's canary; reproduce and manually review it. |
| `manual_review` | The automated assessment cannot decide confidently. |
| `partial_run` | A request failed or a paired case could not be completed. |

A quoted, translated, or explained canary is not proof of instruction execution. Confirm any suspected finding using the complete transcript, repeat runs, matched controls, and human review. Keep benchmark results separate from Guardrail Lab results.

## Cost, privacy, and authorization

- Live runs send requests to the selected provider and may incur API charges.
- The request budget limits scheduled test cases; provider retries can create additional HTTP attempts.
- Test only models and endpoints you own or have explicit permission to assess.
- Use synthetic test data. Do not test with real secrets or private user data.
- Review reports before sharing; they contain prompts and model responses.
- If an API key has been exposed, revoke it and create a replacement.

## Uploaded source archive inventory

The uploaded archive is represented by a committed metadata-only inventory plus a separate safe-adaptations file:

- [Source inventory JSONL](data/source_corpus/source_inventory.jsonl): 55 records with original paths, byte counts, SHA-256 hashes, and handling states.
- [Safe adaptations](data/source_corpus/safe_adaptations.jsonl): 52 runnable, source-derived safe test cases, with provenance.
- [Manifest](data/source_corpus/manifest.json): source archive hash and inventory hash.
- [Handling notes](data/source_corpus/README.md): explains why original bodies are not included and why the withdrawn notice remains excluded.

The inventory is metadata-only and contains no executable raw prompts. Separately, `safe_adaptations.jsonl` contains 52 safe, source-derived adaptations (`GL-SRC-001`–`GL-SRC-052`) that are runnable in Guardrail Lab. They preserve source IDs, paths, and hashes, and replace operational payloads with inert canaries. The default Guardrail Lab suite contains 76 cases (24 core + 52 adaptations).

## Optional: OMJB evaluation and manual guard review

For a local provider-neutral runner with a SQLite evidence store, reviewer-scoped model adjudication, standalone benign/attack guard evaluation, and provenance-checked corpus imports, see the [OMJB guide](omjb/README.md). OMJB is an additional package; the standard 76-case GitHub Actions workflow above remains the quickest route and is unchanged.

## Need the full reference?

See [Installation](INSTALLATION.md), [Guardrail Lab documentation](modules/guardrail_lab/README.md), and the [provider matrix](modules/guardrail_lab/PROVIDER_MATRIX.md).


## Troubleshooting provider runs

- **Missing key:** add the provider API key as a GitHub Actions repository secret or environment variable. Never put keys in source files or reports.
- **401/403:** verify the key is active and has access to the selected project/model.
- **404:** check the exact model ID and endpoint; model availability changes.
- **429:** check quota/billing, lower request frequency, and retry later.
- **5xx/network:** retry later and inspect the provider status page. Partial multi-turn transcripts are retained.
- **Not run / partial run:** these are execution states, not successful safety outcomes.
- **Report schema:** scanner output schema 1.3 adds structured error details and run totals; older reports remain readable by the comparison command.
