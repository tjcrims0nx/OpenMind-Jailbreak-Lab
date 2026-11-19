# Mutation robustness evaluation

The mutation engine is an opt-in extension for benign robustness probes. It
covers encoding/whitespace, Unicode normalization, structural envelopes,
meaning-preserving semantic framings, malformed-but-benign JSON/YAML boundary
inputs, bounded chaining, and a deterministic `NarrativeGraph`.

## Approval gate

A probe is eligible only when both conditions hold:

- `expected == "comply"`
- `meta.mutation_safe == true`, set after review confirms the prompt is benign.

Refusal/attack probes are rejected by the engine. The engine does not generate
policy overrides, false authority claims, hidden harmful payloads, or
safeguard-evasion instructions. Parser cases are malformed data envelopes for
testing parser error handling; they do not ask a model to fail open.

## Python API

```python
from omjb.mutations import MutationEngine, generate, generate_procedural

engine = MutationEngine(max_variants=16, max_chain_depth=2)
cases = engine.generate(reviewed_benign_probe)
procedural = engine.generate_procedural(reviewed_benign_probe)

# Convenience APIs:
cases = generate(reviewed_benign_probe)
procedural = generate_procedural(reviewed_benign_probe)
```

Each `MutationCase` includes its parent probe ID, deterministic ID, transform
names/families, and SHA-256 hashes of input and output. Duplicate outputs are
removed. `max_variants` defaults to 32 and must be a positive integer or `None`.
Passing `None` removes the per-probe count cap and returns all distinct variants
available from the registered static transforms and the configured
`max_chain_depth`. The search space is finite for a fixed chain depth; this is
not an unbounded or continuously running generator.

### Enumerate all available variants

```python
from omjb.mutations import MutationEngine

engine = MutationEngine(max_variants=None, max_chain_depth=2)
cases = engine.generate(reviewed_benign_probe)
```

This still enforces the approval gate above, removes duplicate outputs, and
uses the configured chain depth. Increasing chain depth can expand the
combinatorial search space; review the resulting corpus size before sending it
to a remote endpoint.

## Pipeline integration

The existing pipeline remains unchanged by default. Enable benign robustness
cases explicitly:

```python
result = await pipeline.run(
    probes,
    endpoint="https://your-guard.example/evaluate",
    mutation_profile="robustness",
    max_mutations_per_probe=None,
)
```

`max_mutations_per_probe` defaults to 16. Set it to `None` to remove the
per-probe cap and enumerate the mutation engine's available variants at its
default chain depth. This setting does not bypass the endpoint: provider calls
remain limited to probes allowed by the guard endpoint and explicitly marked
as reviewed benign. The async evaluator does not impose the mutation engine's
separate USD/time budget; apply provider quotas, rate limits, and billing
controls when running remote evaluations. The report includes generated cases
under `mutation_cases` and both original and generated probe IDs.
