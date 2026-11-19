"""Adapter that exposes the existing Guardrail Lab cases to OMJB without replacing them."""
from __future__ import annotations
from .probes import Probe
from .provenance import ProvenanceRecord

def load_guardrail_lab_cases(case_ids=None):
    from modules.guardrail_lab.cases import CASES
    from modules.guardrail_lab import __version__ as suite_version
    selected=list(CASES)
    if case_ids:
        if "GL-010" in case_ids:
            index=case_ids.index("GL-010")
            if index==0 or case_ids[index-1]!="GL-009": raise ValueError("GL-010 requires GL-009 immediately before it")
        wanted=set(case_ids); known={c.case_id for c in selected}
        unknown=sorted(wanted-known)
        if unknown: raise ValueError("unknown Guardrail Lab case IDs: "+", ".join(unknown))
        selected=[c for c in selected if c.case_id in wanted]
    probes=[]
    for case in selected:
        source=case.source_id or "guardrail-lab"
        revision=case.source_sha256 or suite_version
        prov=ProvenanceRecord(source=source,revision=revision,
            upstream_uri=case.source_path or "repository:modules/guardrail_lab/cases.py",
            license="")
        meta={"suite":"Guardrail Lab","suite_version":suite_version,
            "expected_signal":case.expected_signal,"canary":case.canary,
            "control":case.control,"source_id":case.source_id,
            "source_path":case.source_path,"source_sha256":case.source_sha256,
            "variant":case.variant}
        probes.append(Probe(case.case_id,case.category,case.prompt,"either",None,meta,prov))
    return probes
