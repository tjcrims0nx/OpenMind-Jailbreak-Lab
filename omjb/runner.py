"""Sequential, paced runner with optional defensive input/output guards."""
import time
from .detectors import Detection, detect
from .targets import Message
from .guard import evaluate_guards

def run(target,probes,store,run_name,params=None,sleep=0.0,progress=None,input_guards=(),output_guards=()):
    if sleep < 0 or sleep > 60: raise ValueError("sleep must be between 0 and 60 seconds")
    config={"target":target.config(),"params":params or {},"n_probes":len(probes),
        "input_guards":[type(g).__name__ for g in input_guards],"output_guards":[type(g).__name__ for g in output_guards]}
    rid=store.create_run(run_name,target.name,config)
    try:
        for index,probe in enumerate(probes,1):
            messages=([Message("system",probe.system)] if probe.system else [])+[Message("user",probe.prompt)]
            before=evaluate_guards(probe.prompt,input_guards,stage="input")
            if before.blocked:
                detection=Detection("guard_blocked",1.0,"input blocked by configured defensive guard",None)
                result_id=store.add_result(rid,probe,"",detection)
                store.add_guard_observation(result_id,"input",before.decision,[f.__dict__ for f in before.findings])
            else:
                try:
                    generation=target.generate(messages,**(params or {}))
                    after=evaluate_guards(generation.text,output_guards,stage="output")
                    detection=detect(probe,generation.text)
                    if after.blocked:
                        detection=Detection("output_quarantined",1.0,"output quarantined by configured defensive guard; manual review required",None)
                    result_id=store.add_result(rid,probe,generation.text,detection)
                    if before.findings: store.add_guard_observation(result_id,"input",before.decision,[f.__dict__ for f in before.findings])
                    if after.findings: store.add_guard_observation(result_id,"output",after.decision,[f.__dict__ for f in after.findings])
                except Exception as exc:
                    store.add_result(rid,probe,"",Detection("error",0.0,f"{type(exc).__name__}: {exc}",None))
            if progress: progress(index,len(probes),probe)
            if sleep and index<len(probes): time.sleep(sleep)
    finally: store.finish_run(rid)
    return rid
