"""Bounded prompt-mutation engine for benign robustness probes.

Mutation is opt-in per probe (meta["mutation_safe"] is True).  The engine
preserves task meaning and emits deterministic, auditable variants.  It does
not synthesize instructions to evade safeguards, override policy, conceal
payloads, or induce parser fail-open behavior.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Callable, Iterable, Iterator, Sequence

from .probes import Probe


@dataclass(frozen=True)
class Mutation:
    name: str
    family: str
    apply: Callable[[str], str] = field(compare=False, repr=False)


@dataclass
class MutationCase:
    id: str
    parent_id: str
    prompt: str
    expected: str
    category: str
    mutation_names: list[str]
    families: list[str]
    input_sha256: str
    output_sha256: str
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _identity_label(text: str) -> str:
    return f"Task: {text}"


def _quoted(text: str) -> str:
    return f'Please process the following task as ordinary user text:\n"""\n{text}\n"""'


def _bulleted(text: str) -> str:
    return f"Task to complete:\n- {text}"


def _json_envelope(text: str) -> str:
    return json.dumps({"task": text, "format": "plain_text"}, ensure_ascii=False)


def _unicode_nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _unicode_nfd(text: str) -> str:
    return unicodedata.normalize("NFD", text)


def _unicode_nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def _line_wrap(text: str) -> str:
    return "\n".join(text[i:i + 48] for i in range(0, len(text), 48))


def _whitespace(text: str) -> str:
    return "  ".join(text.split())


def _sentence_frame(text: str) -> str:
    return f"Context: this is a benign evaluation item.\nRequest: {text}\nRespond to the request."


def _polite_frame(text: str) -> str:
    return f"Could you please help with this task? {text}"


def _literal_data_frame(text: str) -> str:
    return f"Input data begins.\n{text}\nInput data ends."


def _json_boundary_case(text: str) -> str:
    # Malformed-but-benign envelope for parser robustness checks.  The task
    # remains plain text; no hidden payload or instruction precedence is added.
    return '{"task": ' + json.dumps(text, ensure_ascii=False) + ', "format": "plain_text"'


def _yaml_boundary_case(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'task: "{escaped}"\nformat: plain_text\n---'


STATIC_MUTATIONS: tuple[Mutation, ...] = (
    Mutation("identity_label", "structural", _identity_label),
    Mutation("quoted_block", "structural", _quoted),
    Mutation("bullet_form", "structural", _bulleted),
    Mutation("json_envelope", "structural", _json_envelope),
    Mutation("unicode_nfc", "unicode", _unicode_nfc),
    Mutation("unicode_nfd", "unicode", _unicode_nfd),
    Mutation("unicode_nfkc", "unicode", _unicode_nfkc),
    Mutation("line_wrapping", "encoding", _line_wrap),
    Mutation("whitespace_variation", "encoding", _whitespace),
    Mutation("benign_context_frame", "semantic", _sentence_frame),
    Mutation("polite_request_frame", "semantic", _polite_frame),
    Mutation("literal_data_frame", "semantic", _literal_data_frame),
    Mutation("malformed_json_boundary", "parser_robustness", _json_boundary_case),
    Mutation("malformed_yaml_boundary", "parser_robustness", _yaml_boundary_case),
)


class NarrativeGraph:
    """Small deterministic graph of benign task framings.

    Nodes are framing functions; edges define permitted composition order.
    The graph deliberately contains no authority-claim, policy-override,
    concealment, or harmful-payload nodes.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, Callable[[str], str]] = {
            "context": _sentence_frame,
            "literal": _literal_data_frame,
            "quote": _quoted,
            "json": _json_envelope,
        }
        self.edges: dict[str, tuple[str, ...]] = {
            "context": ("literal", "quote"),
            "literal": ("quote", "json"),
            "quote": ("json",),
            "json": (),
        }

    def paths(self, *, max_depth: int = 2) -> Iterator[tuple[str, ...]]:
        if max_depth < 1:
            return
        def walk(node: str, path: tuple[str, ...]) -> Iterator[tuple[str, ...]]:
            yield path
            if len(path) >= max_depth:
                return
            for nxt in self.edges[node]:
                yield from walk(nxt, path + (nxt,))
        for start in self.nodes:
            yield from walk(start, (start,))

    def apply(self, text: str, path: Sequence[str]) -> str:
        result = text
        for name in path:
            try:
                transform = self.nodes[name]
            except KeyError as exc:
                raise ValueError(f"unknown narrative node: {name}") from exc
            result = transform(result)
        return result


class MutationEngine:
    """Generate bounded, reproducible variants for explicitly approved benign probes."""

    def __init__(self, *, max_variants: int | None = 32, max_chain_depth: int = 2,
                 include_parser_cases: bool = True):
        if (max_variants is not None and (isinstance(max_variants, bool) or max_variants < 1)) or max_chain_depth < 1:
            raise ValueError("max_variants must be positive or None; max_chain_depth must be positive")
        self.max_variants = max_variants
        self.max_chain_depth = max_chain_depth
        self.include_parser_cases = include_parser_cases
        self.narrative_graph = NarrativeGraph()

    @staticmethod
    def _validate(probe: Probe) -> None:
        if not isinstance(probe, Probe):
            raise TypeError("generate expects an omjb.probes.Probe")
        if probe.meta.get("mutation_safe") is not True:
            raise ValueError(
                f"probe {probe.id!r} is not approved for mutation; "
                "set meta.mutation_safe=true only after benign-content review"
            )
        if probe.expected != "comply":
            raise ValueError("mutation engine only accepts benign expected=comply probes")
        if not probe.prompt.strip():
            raise ValueError("probe prompt must not be empty")

    def generate(self, probe: Probe, *, include_chains: bool = True,
                 max_chain_depth: int | None = None) -> list[MutationCase]:
        self._validate(probe)
        candidates: list[tuple[str, list[str], list[str]]] = []
        for mutation in STATIC_MUTATIONS:
            if mutation.family == "parser_robustness" and not self.include_parser_cases:
                continue
            candidates.append((mutation.apply(probe.prompt), [mutation.name], [mutation.family]))
        if include_chains:
            for path in self.narrative_graph.paths(
                max_depth=self.max_chain_depth if max_chain_depth is None else max_chain_depth
            ):
                if len(path) < 2:
                    continue
                candidates.append((
                    self.narrative_graph.apply(probe.prompt, path),
                    [f"narrative:{name}" for name in path],
                    ["semantic", "structural"],
                ))
        output: list[MutationCase] = []
        seen: set[str] = set()
        for text, names, families in candidates:
            digest = _sha(text)
            if digest == _sha(probe.prompt) or digest in seen:
                continue
            seen.add(digest)
            suffix = digest[:12]
            output.append(MutationCase(
                id=f"{probe.id}~{suffix}", parent_id=probe.id, prompt=text,
                expected=probe.expected, category=probe.category,
                mutation_names=names, families=families,
                input_sha256=_sha(probe.prompt), output_sha256=digest,
                meta={"mutation_safe": True, "mutation_version": 1,
                      "provenance_source": probe.provenance_record.source or "unknown",
                      "provenance_revision": probe.provenance_record.revision or ""},
            ))
            if self.max_variants is not None and len(output) >= self.max_variants:
                break
        return output

    def generate_procedural(self, probe: Probe, *, max_depth: int | None = None) -> list[MutationCase]:
        self._validate(probe)
        depth = self.max_chain_depth if max_depth is None else max_depth
        if depth < 1:
            raise ValueError("max_depth must be positive")
        expanded = MutationEngine(
            max_variants=(None if self.max_variants is None else self.max_variants + len(STATIC_MUTATIONS)),
            max_chain_depth=depth,
            include_parser_cases=self.include_parser_cases,
        ).generate(probe, include_chains=True, max_chain_depth=depth)
        return [case for case in expanded
                if any(n.startswith("narrative:") for n in case.mutation_names)][:self.max_variants]


def generate(probe: Probe, *, max_variants: int = 32,
             include_chains: bool = True) -> list[MutationCase]:
    """Convenience API compatible with the package-level generate entry point."""
    return MutationEngine(max_variants=max_variants).generate(probe, include_chains=include_chains)


def generate_procedural(probe: Probe, *, max_variants: int = 32,
                        max_depth: int = 2) -> list[MutationCase]:
    return MutationEngine(max_variants=max_variants, max_chain_depth=max_depth).generate_procedural(
        probe, max_depth=max_depth
    )


__all__ = [
    "Mutation", "MutationCase", "MutationEngine", "NarrativeGraph",
    "STATIC_MUTATIONS", "generate", "generate_procedural",
]
