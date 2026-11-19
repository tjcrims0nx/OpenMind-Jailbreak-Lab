# Persistent campaign history

Campaign history is optional and opt-in. Pass `--history` with `--campaign`
to write an append-only JSONL ledger:

```bash
python -m modules.guardrail_lab --provider gemini --campaign \
  --case GL-001 --case GL-002 --budget 12 --variants 3 \
  --history reports/gemini-campaign-history.jsonl \
  --output reports/gemini-campaign.json
```

The ledger stores each result, its complete request/response evidence, provider
and model identity, campaign-plan fingerprint, a stable case/variant/framing
key, and an integrity checksum for each event. Reusing the same history path
skips previously attempted coverage for that provider/model and frozen
framing-set identity. A different provider or model has a separate coverage
namespace. A changed framing-set hash naturally creates new coverage.

## Review before expansion

New results are always recorded as pending. A machine assessment, including
an exact synthetic-canary signal, is not a human review and does not by itself
authorize adaptive follow-ups when history mode is enabled.

List pending result IDs:

```bash
python -m modules.guardrail_lab.campaign_history \
  --history reports/gemini-campaign-history.jsonl pending
```

After inspecting the complete report and transcript, record a human decision:

```bash
python -m modules.guardrail_lab.campaign_history \
  --history reports/gemini-campaign-history.jsonl review \
  --record-id RECORD_ID --reviewer REVIEWER_ID \
  --decision approved \
  --notes "Reviewed the full transcript; exact synthetic canary reproduced."
```

Valid decisions are `approved`, `rejected`, and `inconclusive`. All decisions
are retained as append-only events with reviewer identity and non-empty notes.
Only an `approved` review of a `potential_guardrail_failure` result can seed
the next campaign's additional fixed framings. Those framings are still
bounded by `--variants`, the request/build/time/USD limits, and the existing
harmless-canary design. Rejected, inconclusive, or pending records do not
expand the campaign.

The history ledger prevents repeat requests for already-attempted keys,
including pending results from interrupted campaigns. Reviewed outcomes are
separately tracked and are the only evidence used to authorize expansion.
The event checksum detects accidental modification; it is not a digital
signature or proof of provider origin.

## Operational notes

- Treat the JSONL ledger as sensitive: it contains prompts, provider responses,
  and potentially identifying evaluation metadata. Keep it out of public
  repositories and restrict file permissions.
- Back up the ledger before manual editing. Do not edit event lines directly;
  add review events through the CLI.
- History mode disables same-run machine-triggered expansion. The next run
  can expand only after a reviewer has approved the exact-canary result.
- Keep the same history file for a campaign series. Use a new file when you
  intentionally want a clean coverage ledger.
- The ledger is append-only at the application level. Concurrent writers to
  the same file are not coordinated; run one campaign writer per history file.
