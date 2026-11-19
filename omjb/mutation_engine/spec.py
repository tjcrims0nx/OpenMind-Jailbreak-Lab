import hashlib,json,warnings
from dataclasses import dataclass,field
from .core import Kind,REGISTRY,StageArm

@dataclass
class Stage:
    name:str
    optional:bool
    arms:list[StageArm]

@dataclass
class PipelineSpec:
    version:int
    seed:int
    stages:list[Stage]
    budget:dict
    diagnostics:list[str]=field(default_factory=list)
    transform_contracts:dict=field(default_factory=dict)
    def canonical(self):
        d={"version":self.version,"seed":self.seed,"budget":self.budget,
           "transform_contracts":self.transform_contracts,
           "stages":[{"name":s.name,"optional":s.optional,"arms":[{"name":a.name,"params":a.params} for a in s.arms]} for s in self.stages]}
        return json.dumps(d,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    def hash(self):
        return hashlib.sha256(self.canonical().encode()).hexdigest()[:24]

def _arm_compatible(ts,state):
    structured,kind=state
    if ts.touches in ("prefix","suffix"): return structured
    if ts.touches=="blob": return structured and kind is ts.input_kind
    return kind is ts.input_kind

def validate_spec(spec:PipelineSpec,registry=REGISTRY,*,strict=False):
    """Forward dataflow over (structured, blob-kind) states."""
    states={(False,Kind.TEXT)}
    diagnostics=[]
    contracts={}
    for index,stage in enumerate(spec.stages):
        compatible=[]
        next_states=set()
        for arm in stage.arms:
            ts=registry.get(arm.name)
            contracts[arm.name]={"input_kind":ts.input_kind.value,"output_kind":ts.output_kind.value,
                "touches":ts.touches,"version":ts.version,"structured_output":ts.structured_output,
                "semantic_delta":ts.semantic_delta}
            matching=[state for state in states if _arm_compatible(ts,state)]
            if matching:
                compatible.append(arm)
                for structured,kind in matching:
                    if ts.touches in ("prefix","suffix"):
                        next_states.add((True,kind))
                    elif ts.touches=="blob":
                        next_states.add((True,ts.output_kind))
                    else:
                        next_states.add((ts.structured_output,ts.output_kind))
            else:
                diagnostics.append(f"unreachable arm {stage.name}.{arm.name}: touches={ts.touches}, input_kind={ts.input_kind.value}, reachable={[(s,k.value) for s,k in sorted(states,key=lambda x:(x[0],x[1].value))]}")
        if not compatible and not stage.optional:
            stage_errors=[d for d in diagnostics if d.startswith(f"unreachable arm {stage.name}.")]
            raise ValueError(f"stage {stage.name!r} has no reachable arms at index {index}; "+"; ".join(stage_errors))
        if stage.optional: next_states.update(states)
        if compatible: states=next_states
    spec.diagnostics=diagnostics
    spec.transform_contracts=contracts
    if strict and diagnostics: raise ValueError("pipeline contains unreachable arms: "+"; ".join(diagnostics))
    for message in diagnostics: warnings.warn(message,UserWarning,stacklevel=2)
    return diagnostics

def load_spec(d,*,registry=REGISTRY,strict_reachability=False):
    if not isinstance(d,dict) or not isinstance(d.get("stages"),list):
        raise ValueError("spec requires a stages array")
    stages=[]
    for s in d["stages"]:
        if not isinstance(s,dict) or not isinstance(s.get("arms"),list) or not s["arms"]:
            raise ValueError("each stage requires non-empty arms")
        arms=[StageArm(a,{}) if isinstance(a,str) else StageArm(a["name"],dict(a.get("params",{}))) for a in s["arms"]]
        stages.append(Stage(str(s["name"]),bool(s.get("optional",False)),arms))
    spec=PipelineSpec(int(d.get("version",1)),int(d.get("seed",0)),stages,dict(d.get("budget",{})))
    validate_spec(spec,registry,strict=strict_reachability)
    return spec
