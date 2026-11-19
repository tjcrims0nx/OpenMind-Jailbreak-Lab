# Adaptive discovery scheduler

`modules.guardrail_lab.adaptive.plan_adaptive_cases()` selects the next
uncovered test envelopes based on reviewed results from earlier runs. It
adapts test coverage, not payload intensity: the original synthetic test
prompt is preserved and placed only inside one of the fixed, documented
untrusted-input envelopes from `discovery.py`.

## Example

```python
from modules.guardrail_lab.adaptive import plan_adaptive_cases

cases = [{"id": "case-001", "prompt": "Synthetic canary: TEST_ONLY_123"}]
history = [{
    "source_case_id": "case-001",
    "discovery_variant": "baseline",
    "assessment": "ambiguous_canary_mention",
}]
next_batch = plan_adaptive_cases(
    cases, history, max_new_variants=2, request_budget=20
)
```

The scheduler prioritizes formats that help distinguish quoting, retrieval,
structured-data, and tool-output handling. It never removes safety framing,
creates real-secret requests, calls a provider, or automatically labels a
result as a vulnerability. Provider execution remains the responsibility of
an existing authorized adapter; all findings require human review.

History assessments must be one of: `ambiguous_canary_mention`,
`boundary_held`, `manual_review`, `control_passed`, `partial_run`, or
`potential_guardrail_failure`. The scheduler rejects unknown labels and
untested-variant duplication. `request_budget` is checked before returning
any planned calls.


## Capacity controls and reproducible campaigns

The campaign runner accepts independent candidate and build-attempt ceilings:

- `--budget` / `max_candidates` caps provider requests (default: 36).
- `--max-build-attempts` caps dequeued campaign candidates, including adaptive follow-ups.
- `--max-seconds` stops scheduling when the wall-clock budget is reached. It cannot cancel a provider request already in flight.
- `--max-usd` is an estimated spend ceiling. It must be paired with `--estimated-cost-per-request`; the runner reserves that estimate before sending each request and will not schedule a request that would exceed the ceiling.

For count-unbounded operation, use `--unbounded-counts`. This sets both candidate and build-attempt ceilings to `None` and **requires** finite `--max-seconds`, `--max-usd`, and a positive `--estimated-cost-per-request`. Example:

```bash
guardrail-lab --provider gemini --campaign --research-mode \
  --unbounded-counts --max-seconds 300 \
  --max-usd 2.00 --estimated-cost-per-request 0.01 \
  --output campaign.json
```

The USD control is a conservative reservation based on the operator-supplied per-request estimate, not a provider invoice or verified actual spend. Provider retries, token usage, provider-side pricing changes, and billing adjustments can make actual charges differ. Keep provider-side spending limits enabled.

Each report records the campaign plan, its SHA-256 fingerprint, capacity settings, build-attempt count, estimated spend, and per-result estimate. The plan fingerprint is deterministic for the same case set and campaign settings; timestamps and provider outputs are evidence, not part of that fingerprint. The fixed reviewed framing set and existing evidence-triggered expansion rule are unchanged. Adaptive selection changes coverage order only; it does not generate stronger prompts or remove the trusted system instruction.
