"""Composable defensive input/output checks. Findings are triage, never bypass labels."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Iterable

@dataclass(frozen=True)
class GuardFinding:
    guard: str
    decision: str
    reason: str
    matches: tuple[str, ...] = ()

@dataclass(frozen=True)
class GuardDecision:
    decision: str
    findings: tuple[GuardFinding, ...] = ()
    @property
    def blocked(self) -> bool:
        return self.decision == "block"

class Guard:
    name = "guard"
    def inspect(self, text: str, *, stage: str) -> GuardFinding:
        raise NotImplementedError

class KeywordGuard(Guard):
    def __init__(self, terms: Iterable[str], *, decision="review", name="keyword"):
        if decision not in {"allow", "review", "block"}: raise ValueError("invalid decision")
        self.terms = tuple(t.casefold() for t in terms if isinstance(t,str) and t.strip())
        self.decision, self.name = decision, name
    def inspect(self, text, *, stage):
        found = tuple(t for t in self.terms if t in (text or "").casefold())
        return GuardFinding(self.name, self.decision if found else "allow",
            f"{len(found)} configured term(s) matched" if found else "no configured terms matched", found)

class RegexGuard(Guard):
    def __init__(self, patterns: Iterable[str], *, decision="review", name="regex"):
        if decision not in {"allow", "review", "block"}: raise ValueError("invalid decision")
        self.patterns = tuple(re.compile(p, re.I) for p in patterns)
        self.decision, self.name = decision, name
    def inspect(self, text, *, stage):
        hits = tuple(p.pattern for p in self.patterns if p.search(text or ""))
        return GuardFinding(self.name, self.decision if hits else "allow",
            f"{len(hits)} configured pattern(s) matched" if hits else "no configured patterns matched", hits)

class CompositeGuard(Guard):
    def __init__(self, guards: Iterable[Guard], *, mode="any", name="composite"):
        if mode not in {"any","all"}: raise ValueError("mode must be any or all")
        self.guards, self.mode, self.name = tuple(guards), mode, name
    def inspect(self, text, *, stage):
        findings = tuple(g.inspect(text, stage=stage) for g in self.guards)
        selected = [f for f in findings if f.decision != "allow"]
        if not selected: decision = "allow"
        elif any(f.decision == "block" for f in selected): decision = "block"
        elif self.mode == "any" or all(f.decision != "allow" for f in findings): decision = "review"
        else: decision = "allow"
        return GuardFinding(self.name, decision, f"{len(selected)} child guard(s) raised findings",
                            tuple(f.guard for f in selected))

def evaluate_guards(text: str, guards: Iterable[Guard], *, stage: str) -> GuardDecision:
    findings = tuple(g.inspect(text, stage=stage) for g in guards)
    if any(f.decision == "block" for f in findings): overall = "block"
    elif any(f.decision == "review" for f in findings): overall = "review"
    else: overall = "allow"
    return GuardDecision(overall, findings)
