"""Adapters that connect OMJB runs to existing Guardrail Lab evidence without replacing it."""
from __future__ import annotations
from dataclasses import dataclass
from .guard import evaluate_guards
from .targets import Message

@dataclass
class GuardedResult:
    response: str
    input_decision: object
    output_decision: object
    error: str = ""

def guarded_generate(target, messages, *, input_guards=(), output_guards=(), params=None):
    """Apply local defensive checks around one provider call.

    A blocked input is not sent. A blocked output is returned for evidence but must
    be treated as quarantined by callers. This wrapper does not rewrite prompts.
    """
    user_text="\n".join(m.content for m in messages if m.role=="user")
    before=evaluate_guards(user_text,input_guards,stage="input")
    if before.blocked:
        return GuardedResult("",before,evaluate_guards("",output_guards,stage="output"),"blocked by input guard")
    generated=target.generate(messages,**(params or {}))
    after=evaluate_guards(generated.text,output_guards,stage="output")
    return GuardedResult(generated.text,before,after,"")
