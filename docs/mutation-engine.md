# Reproducible mutation robustness engine

This implementation adapts the typed pipeline design for reviewed benign
robustness probes. It includes transform I/O kinds, deterministic per-candidate
RNG, canonical spec hashing, trace-based replay, deduplication, candidate/USD/time
budgets plus a build-attempt ceiling, cost-aware UCB sampling, JSONL tracing,
transform version records, and a decorator-based extension registry.

## Spec reachability

Spec loading performs forward dataflow from the initial TEXT kind. Each stage is
checked against kinds reachable from preceding stages. Unreachable arms emit a
UserWarning and are retained in spec.diagnostics. A required stage with no
reachable arm fails immediately. Optional stages retain their bypass path, so
downstream reachability accounts for both taking and skipping that stage.

Use load_spec(data, strict_reachability=True) in CI or production configuration
validation to turn any unreachable-arm warning into a ValueError. Diagnostics
are derived from the spec and registry and are excluded from the canonical hash.

## Structured regions

The engine now carries RegionValue(prefix, blob, blob_kind, suffix) through
pipelines. Transform metadata declares touches="all", "prefix", "blob", or
"suffix". Prefix and suffix transforms preserve the blob byte-for-byte and keep
its Kind; blob transforms require an exact blob-kind match; whole-value
transforms remain kind-gated. Structured-value creation is explicit through a
transform declaring structured_output=true.

The benign built-ins include format.segment_fixture, encoding.base64_blob, and
unicode.prefix_nfc. The example configs/mutation-regions.example.json composes
them as a reviewed fixture header, Base64 body, and prefix-only normalization.
No instruction-wrapper obfuscation or concealment transform is registered.
Trace entries record each selected transform's touches scope, and replay uses
the same typed dispatch.

## Safety gate

Construct Engine with approved_benign=True only after human review confirms the
target is benign. Built-ins have semantic_delta=0 and are limited to formatting,
Unicode normalization, and representation encoding. The engine does not ship
authority overrides, safeguard evasion, concealed instructions, filter attacks,
instruction splitting, or decode-and-execute operators. Adaptive reward measures
handling of reviewed benign robustness cases, not harmful bypass yield.

## Spec and API

Load a JSON-compatible dict with load_spec. Each stage declares arms and may be
optional. A transform can consume only its declared input kind; incompatible
required stages fail validation, while unreachable optional arms are reported.
Budget defaults are bounded; max_build_attempts prevents endless loops.

Use Engine(spec, reviewed_probe, submit, approved_benign=True,
trace_path="trace.jsonl"). The submit callback returns Verdict. The target must
be an OMJB Probe with expected="comply" and meta.mutation_safe=true.

Every candidate trace records the spec hash, seed, candidate index, selected
arms and transform versions, plus a SHA-256 output fingerprint. rebuild() uses
the recorded arm sequence and deterministic RNG to reproduce the payload.

Extensions register through @transform(...) or a dedicated Registry instance.
Third-party transforms declare input/output kinds, cost, semantic delta, tags,
and version. The engine rejects transforms with nonzero semantic_delta.

For a positive USD budget, Engine requires an estimate_cost callback returning
a conservative upper-bound estimate. Candidates whose reservation exceeds the
remaining budget are not sent.

## CLI

Install the optional HTTP client and run against a guardrail endpoint you operate:

    pip install -e ".[api]"
    export OMJB_GUARDRAIL_TOKEN="..."
    omjb-mutate --spec configs/mutation-robustness.example.json \
      --corpus reviewed-benign-probes.jsonl --probe-id benign-001 \
      --endpoint https://guardrail.example/evaluate \
      --estimated-request-cost 0.001 --trace mutation-trace.jsonl

The corpus record must have expected=comply and meta.mutation_safe=true.
The CLI selects exactly one probe by ID and reads its bearer token from the
named environment variable; credentials are never written to the trace.
