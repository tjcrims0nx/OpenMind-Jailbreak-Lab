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
        return json.dumps(d,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)
    def hash(self):
        return hashlib.sha256(self.canonical().encode()).hexdigest()[:24]

def _arm_compatible(ts,state):
    structured,kind=state
    if ts.touches in ("prefix","suffix"): return structured
    if ts.touches=="blob": return structured and kind is ts.input_kind
    return kind is ts.input_kind

def validate_spec(spec:PipelineSpec,registry=REGISTRY,*,strict=False):
    """Forward dataflow over (structured, blob-kind) states."""
    if not isinstance(spec,PipelineSpec): raise TypeError("spec must be a PipelineSpec")
    if not spec.stages: raise ValueError("pipeline requires at least one stage")
    names=[stage.name for stage in spec.stages]
    if any(not isinstance(name,str) or not name.strip() for name in names):
        raise ValueError("stage names must be non-empty strings")
    if len(set(names))!=len(names): raise ValueError("stage names must be unique")
    states={(False,Kind.TEXT)}
    diagnostics=[]
    contracts={}
    for index,stage in enumerate(spec.stages):
        if not stage.arms: raise ValueError(f"stage {stage.name!r} requires at least one arm")
        compatible=[]
        next_states=set()
        for arm in stage.arms:
            if not isinstance(arm,StageArm): raise TypeError("stage arms must be StageArm instances")
            if not isinstance(arm.params,dict): raise ValueError(f"arm {arm.name!r} params must be an object")
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
    if not isinstance(d,dict) or not isinstance(d.get("stages"),list) or not d["stages"]:
        raise ValueError("spec requires a non-empty stages array")
    budget=d.get("budget",{})
    if not isinstance(budget,dict): raise ValueError("budget must be an object")
    version=d.get("version",1)
    seed=d.get("seed",0)
    if isinstance(version,bool) or not isinstance(version,int) or version<1:
        raise ValueError("spec version must be a positive integer")
    if isinstance(seed,bool) or not isinstance(seed,int):
        raise ValueError("spec seed must be an integer")
    stages=[]
    seen=set()
    for s in d["stages"]:
        if not isinstance(s,dict) or not isinstance(s.get("arms"),list) or not s["arms"]:
            raise ValueError("each stage requires non-empty arms")
        name=s.get("name")
        if not isinstance(name,str) or not name.strip():
            raise ValueError("stage name must be a non-empty string")
        if name in seen: raise ValueError(f"duplicate stage name: {name}")
        seen.add(name)
        if "optional" in s and not isinstance(s["optional"],bool):
            raise ValueError(f"stage {name!r} optional must be boolean")
        arms=[]
        for raw in s["arms"]:
            if isinstance(raw,str):
                if not raw.strip(): raise ValueError("arm name must be non-empty")
                arms.append(StageArm(raw,{}))
            elif isinstance(raw,dict):
                arm_name=raw.get("name")
                params=raw.get("params",{})
                if not isinstance(arm_name,str) or not arm_name.strip():
                    raise ValueError(f"stage {name!r} arm name must be non-empty")
                if not isinstance(params,dict):
                    raise ValueError(f"stage {name!r} arm {arm_name!r} params must be an object")
                arms.append(StageArm(arm_name,dict(params)))
            else:
                raise ValueError(f"stage {name!r} arms must be names or objects")
        stages.append(Stage(name,s.get("optional",False),arms))
    spec=PipelineSpec(version,seed,stages,dict(budget))
    validate_spec(spec,registry,strict=strict_reachability)
    spec.canonical()
    return spec
