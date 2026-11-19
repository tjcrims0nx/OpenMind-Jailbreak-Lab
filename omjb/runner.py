"""Sequential runner with bounded pacing and per-case error capture."""
import time
from .detectors import Detection, detect
from .targets import Message
def run(target, probes, store, run_name, params=None, sleep=0.0, progress=None):
    if sleep < 0 or sleep > 60:
        raise ValueError("sleep must be between 0 and 60 seconds")
    config = {"target":target.config(), "params":params or {}, "n_probes":len(probes)}
    rid = store.create_run(run_name, target.name, config)
    try:
        for index, probe in enumerate(probes, 1):
            messages = ([Message("system",probe.system)] if probe.system else []) + [Message("user",probe.prompt)]
            try:
                generation = target.generate(messages, **(params or {}))
                detection = detect(probe, generation.text)
                store.add_result(rid, probe, generation.text, detection)
            except Exception as exc:
                store.add_result(rid, probe, "", Detection("error",0.0,f"{type(exc).__name__}: {exc}",None))
            if progress:
                progress(index,len(probes),probe)
            if sleep and index < len(probes):
                time.sleep(sleep)
    finally:
        store.finish_run(rid)
    return rid
