from __future__ import annotations
import hashlib,json,time
from dataclasses import dataclass
from .budget import Budget
from .core import Candidate,Kind,REGISTRY,Registry,Verdict
from .dedup import dedup_key
from .rng import derive_rng
from .scheduler import CostAwareUCB
from . import transforms as _builtin_transforms
from .regions import Region,RegionValue,apply_region,region_compatible
from ..probes import Probe

class Tracer:
    def __init__(self,path): self.f=open(path,"w",encoding="utf-8") if path else None
    def write(self,record):
        if self.f: self.f.write(json.dumps(record,sort_keys=True,ensure_ascii=False)+"\n"); self.f.flush()
    def close(self):
        if self.f: self.f.close(); self.f=None

@dataclass
class EngineReport:
    submitted:int
    allowed:int
    blocked:int
    errors:int
    skipped:int
    by_arm:dict
    allow_rate:float

def _value_kind(value,plain_kind):
    return value.blob_kind if isinstance(value,RegionValue) else plain_kind

def _compatible(spec,value,plain_kind):
    if spec.touches in ("prefix","suffix"):
        return isinstance(value,RegionValue)
    if spec.touches=="blob":
        return isinstance(value,RegionValue) and value.blob_kind is spec.input_kind
    return _value_kind(value,plain_kind) is spec.input_kind

def _apply(spec,value,rng,params):
    if spec.touches=="all":
        source=value.render() if isinstance(value,RegionValue) else value
        result=spec.fn(source,rng,**params)
        if isinstance(result,RegionValue):
            if not spec.structured_output or result.blob_kind is not spec.output_kind:
                raise ValueError("structured transform output does not match its declared contract")
            return result,spec.output_kind
        if not isinstance(result,str): raise TypeError("transform must return str or declared RegionValue")
        if spec.structured_output: raise TypeError("transform declared structured_output but returned str")
        return result,spec.output_kind
    if not isinstance(value,RegionValue):
        raise TypeError(f"{spec.touches} transform requires a structured RegionValue")
    region=Region(spec.touches)
    if not region_compatible(value,touches=region,input_kind=spec.input_kind):
        raise ValueError(f"{spec.touches} region kind mismatch")
    changed=apply_region(value,touches=region,
        fn=lambda part:spec.fn(part,rng,**params),output_kind=spec.output_kind)
    return changed,changed.blob_kind

class Engine:
    def __init__(self,spec,target,submit,*,approved_benign=False,estimate_cost=None,registry:Registry=REGISTRY,trace_path=None,scheduler=None):
        if approved_benign is not True: raise ValueError("Engine requires explicit approved_benign=True after human review")
        if not isinstance(target,Probe): raise TypeError("target must be an omjb.probes.Probe")
        if target.expected!="comply" or target.meta.get("mutation_safe") is not True:
            raise ValueError("mutation requires a human-reviewed benign Probe (expected='comply', meta.mutation_safe=true)")
        if not target.prompt.strip(): raise ValueError("probe prompt must be non-empty")
        self.probe=target
        self.spec,self.target,self.submit,self.registry=spec,target.prompt,submit,registry
        self.budget=Budget.from_dict(spec.budget)
        if self.budget.max_usd>0 and not callable(estimate_cost):
            raise ValueError("estimate_cost is required for a positive USD budget")
        self.estimate_cost=estimate_cost or (lambda payload:0.0)
        self.tracer=Tracer(trace_path); self.scheduler=scheduler or CostAwareUCB()
        self._register_arms()
    def _register_arms(self):
        for stage in self.spec.stages:
            for arm in stage.arms:
                ts=self.registry.get(arm.name)
                if ts.semantic_delta!=0: raise ValueError(f"semantic-changing transform is not allowed: {arm.name}")
                self.scheduler.add(arm.key(stage.name),ts.cost)
    def _build(self,idx):
        value=self.target; kind=Kind.TEXT; rng=derive_rng(self.spec.seed,idx); used=[]
        for stage in self.spec.stages:
            choices=[a for a in stage.arms if _compatible(self.registry.get(a.name),value,kind)]
            if not choices:
                if stage.optional: continue
                payload=value.render() if isinstance(value,RegionValue) else value
                return Candidate(idx,payload,used,dedup_key(payload),True,"no_compatible_arm:"+stage.name)
            keys=[a.key(stage.name) for a in choices]
            selected=self.scheduler.pick(keys)
            if selected is None:
                if stage.optional:
                    continue
                payload=value.render() if isinstance(value,RegionValue) else value
                return Candidate(idx,payload,used,dedup_key(payload),True,"all_compatible_arms_pruned:"+stage.name)
            arm=next(a for a in choices if a.key(stage.name)==selected)
            ts=self.registry.get(arm.name)
            try: value,kind=_apply(ts,value,rng,arm.params)
            except Exception as exc:
                payload=value.render() if isinstance(value,RegionValue) else value
                return Candidate(idx,payload,used,dedup_key(payload),True,"transform_error:"+arm.name+":"+type(exc).__name__)
            used.append((stage.name,arm))
        payload=value.render() if isinstance(value,RegionValue) else value
        if payload==self.target: return Candidate(idx,payload,used,dedup_key(payload),True,"identity_chain")
        return Candidate(idx,payload,used,dedup_key(payload))
    def run(self):
        counts={"submitted":0,"allowed":0,"blocked":0,"errors":0,"skipped":0}
        seen=set(); started=time.monotonic(); idx=0
        try:
            while not self.budget.exhausted(time.monotonic()-started):
                self.budget.build_attempts+=1
                candidate=self._build(idx); idx+=1
                if candidate.skipped:
                    counts["skipped"]+=1
                    self.tracer.write({"event":"skip","idx":candidate.idx,"reason":candidate.reason,"spec_hash":self.spec.hash()})
                    continue
                if candidate.dedup in seen:
                    counts["skipped"]+=1
                    self.tracer.write({"event":"skip","idx":candidate.idx,"reason":"dedup","key":candidate.dedup,"spec_hash":self.spec.hash()})
                    continue
                seen.add(candidate.dedup); estimate=0.0
                try:
                    estimate=float(self.estimate_cost(candidate.payload))
                    if estimate<0 or not __import__("math").isfinite(estimate):
                        raise ValueError("estimated cost must be finite and non-negative")
                except Exception as exc:
                    counts["errors"]+=1
                    self.tracer.write({"event":"build_error","idx":candidate.idx,
                        "reason":"cost_estimate_failed","error":f"{type(exc).__name__}: {exc}",
                        "spec_hash":self.spec.hash()})
                    continue
                if self.budget.spent_usd+estimate>self.budget.max_usd:
                    self.tracer.write({"event":"skip","idx":candidate.idx,
                        "reason":"usd_budget_reservation","estimate_usd":estimate})
                    break
                try:
                    verdict=self.submit(candidate.payload)
                    if not isinstance(verdict,Verdict):
                        raise TypeError("submit must return Verdict")
                    import math
                    if not isinstance(verdict.allowed,bool):
                        raise TypeError("Verdict.allowed must be boolean")
                    for field_name in ("latency_ms","cost_usd"):
                        field_value=getattr(verdict,field_name)
                        if isinstance(field_value,bool) or not isinstance(field_value,(int,float)) or not math.isfinite(field_value) or field_value<0:
                            raise ValueError(f"Verdict.{field_name} must be finite and non-negative")
                    if verdict.error is not None and not isinstance(verdict.error,str):
                        raise TypeError("Verdict.error must be a string or None")
                except Exception as exc:
                    verdict=Verdict(False,error=f"{type(exc).__name__}: {exc}")
                self.budget.spent_candidates+=1
                self.budget.spent_usd+=max(estimate,max(0.0,verdict.cost_usd))
                reward=1.0 if verdict.allowed and not verdict.error else 0.0
                for key in candidate.arm_keys(): self.scheduler.update(key,reward)
                counts["submitted"]+=1
                if verdict.error: counts["errors"]+=1
                elif verdict.allowed: counts["allowed"]+=1
                else: counts["blocked"]+=1
                self.tracer.write({"event":"candidate","idx":candidate.idx,"key":candidate.dedup,
                    "arms":[{"stage":s,"name":a.name,"params":a.params,"version":self.registry.get(a.name).version,
                             "touches":self.registry.get(a.name).touches} for s,a in candidate.arms],
                    "allowed":verdict.allowed,"latency_ms":round(verdict.latency_ms,2),"cost_usd":round(verdict.cost_usd,8),
                    "error":verdict.error,"spec_hash":self.spec.hash(),"seed":self.spec.seed,
                    "payload_sha256":hashlib.sha256(candidate.payload.encode()).hexdigest()})
            scored=counts["allowed"]+counts["blocked"]
            return EngineReport(counts["submitted"],counts["allowed"],counts["blocked"],counts["errors"],counts["skipped"],
                                self.scheduler.summary(),counts["allowed"]/scored if scored else 0.0)
        finally: self.tracer.close()

def rebuild(spec,target,record,registry:Registry=REGISTRY):
    if record.get("spec_hash") != spec.hash():
        raise ValueError("pipeline spec hash mismatch")
    rng=derive_rng(spec.seed,record["idx"]); value=target; kind=Kind.TEXT
    stages={stage.name:stage for stage in spec.stages}
    previous_index=-1
    used_stages=set()
    for arm in record["arms"]:
        stage_name=arm["stage"]
        if stage_name not in stages:
            raise ValueError("trace references an unknown stage")
        stage_index=next(i for i,s in enumerate(spec.stages) if s.name==stage_name)
        if stage_index<=previous_index:
            raise ValueError("trace stages are duplicated or out of order")
        previous_index=stage_index
        used_stages.add(stage_name)
        configured=next((a for a in stages[stage_name].arms
                         if a.name==arm["name"] and a.params==arm["params"]),None)
        if configured is None:
            raise ValueError("trace arm is not present in the pipeline spec")
        ts=registry.get(arm["name"])
        if ts.version!=arm.get("version",ts.version):
            raise ValueError("transform version mismatch")
        if arm.get("touches",ts.touches)!=ts.touches:
            raise ValueError("transform region contract mismatch")
        if not _compatible(ts,value,kind):
            raise ValueError("trace contains an incompatible transform sequence")
        value,kind=_apply(ts,value,rng,arm["params"])
    missing=[stage.name for stage in spec.stages if not stage.optional and stage.name not in used_stages]
    if missing:
        raise ValueError("trace omits required stages: "+", ".join(missing))
    rebuilt=value.render() if isinstance(value,RegionValue) else value
    fingerprint=hashlib.sha256(rebuilt.encode()).hexdigest()
    if record.get("payload_sha256") and record["payload_sha256"]!=fingerprint:
        raise ValueError("replayed payload fingerprint mismatch")
    return rebuilt
