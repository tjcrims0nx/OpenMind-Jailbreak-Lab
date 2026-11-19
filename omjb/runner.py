"""Sequential, paced runner with ordered input/output guard pipelines."""
import time
from .detectors import Detection,detect
from .targets import Message
from .guard import evaluate_guards
from .pipeline import GuardPipeline,Stage,PipelineResult

def _legacy_pipeline(input_guards,output_guards):
    stages=[]
    for i,g in enumerate(input_guards): stages.append(Stage(f"input-{i+1}",g,"input","block"))
    for i,g in enumerate(output_guards): stages.append(Stage(f"output-{i+1}",g,"output","block"))
    return GuardPipeline(stages,"legacy-guard-list") if stages else None

def _execute(target,probe,pipeline,params):
    traces=[]
    if pipeline:
        before,verdict=pipeline.check_input(probe.prompt); traces.extend(before.stages)
        if verdict=="block": return "",Detection("guard_blocked",1.0,before.reason,None),PipelineResult("block",before.score,before.reason,traces,before.blocked_at)
    messages=([Message("system",probe.system)] if probe.system else [])+[Message("user",probe.prompt)]
    try: generation=target.generate(messages,**params)
    except Exception as exc: return "",Detection("error",0.0,f"{type(exc).__name__}: {exc}",None),PipelineResult("review",0.0,"provider error",traces) if traces else None
    if pipeline and pipeline.has_output_stages():
        after,verdict=pipeline.check_output(generation.text,probe.prompt); traces.extend(after.stages)
        if verdict=="block":
            return generation.text,Detection("output_quarantined",1.0,after.reason,None),PipelineResult("block",after.score,after.reason,traces,after.blocked_at)
    action="review" if any(x.action=="review" for x in traces) else "allow"
    pr=PipelineResult(action,0.5 if action=="review" else 0.0,"guard pipeline completed",traces) if pipeline else None
    return generation.text,detect(probe,generation.text),pr

def run(target,probes,store,run_name,params=None,sleep=0.0,progress=None,input_guards=(),output_guards=(),pipeline=None,concurrency=1):
    if sleep<0 or sleep>60: raise ValueError("sleep must be between 0 and 60 seconds")
    if concurrency!=1: raise ValueError("this runner currently supports concurrency=1 to preserve deterministic evidence ordering")
    if pipeline is not None and (input_guards or output_guards): raise ValueError("use either pipeline or legacy guard lists, not both")
    pipeline=pipeline or _legacy_pipeline(input_guards,output_guards)
    params=params or {}
    config={"target":target.config(),"params":params,"n_probes":len(probes),"pipeline":pipeline.config() if pipeline else None}
    rid=store.create_run(run_name,target.name,config)
    try:
        for index,probe in enumerate(probes,1):
            response,detection,pr=_execute(target,probe,pipeline,params)
            result_id=store.add_result(rid,probe,response,detection,pipeline_result=pr)
            if pr:
                for stage in pr.stages:
                    decision="block" if stage.action=="block" else "review" if stage.action=="review" else "allow"
                    store.add_guard_observation(result_id,stage.on,decision,[stage.__dict__])
            if progress: progress(index,len(probes),probe)
            if sleep and index<len(probes): time.sleep(sleep)
    finally: store.finish_run(rid)
    return rid
