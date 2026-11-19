"""Labeled defensive guard evaluation using the shared corpus reader."""
from __future__ import annotations
from .corpus_io import iter_records
from .provenance import ProvenanceRecord,row_sha256
from .stats import wilson_interval
from .guard import Guard

def load_labeled(path,require_provenance=False,dedupe=False):
    rows=[]; seen=set()
    for i,row in enumerate(iter_records(path)):
        if not isinstance(row,dict): raise ValueError(f"{path}:{i}: record must be an object")
        if "text" not in row or "label" not in row: raise ValueError(f"{path}:{i}: needs 'text' and 'label'")
        if not isinstance(row["text"],str) or not row["text"].strip(): raise ValueError(f"{path}:{i}: text must be non-empty")
        if row["label"] not in ("benign","attack"): raise ValueError(f"{path}:{i}: label must be benign|attack")
        prov=ProvenanceRecord.from_dict(row.get("provenance"))
        if require_provenance: prov.validate(where=f"{path}:{i}")
        digest=row_sha256(row)
        if dedupe and digest in seen: continue
        seen.add(digest); item=dict(row); item["provenance"]=prov.to_dict(); rows.append(item)
    return rows

def evaluate(guard:Guard,samples,store=None,run_name="guard-eval",config=None):
    samples=list(samples); observations=[]
    tp=fp=tn=fn=0; per_category={}
    for row in samples:
        finding=guard.inspect(row["text"],stage="input")
        observations.append(finding)
        predicted=finding.decision in ("block","review"); actual=row["label"]=="attack"
        if actual and predicted: tp+=1
        elif actual: fn+=1
        elif predicted: fp+=1
        else: tn+=1
        bucket=per_category.setdefault(row.get("category","uncategorized"),{"n":0,"correct":0})
        bucket["n"]+=1; bucket["correct"]+=int(actual==predicted)
    n=tp+fp+tn+fn; precision=tp/(tp+fp) if tp+fp else None; recall=tp/(tp+fn) if tp+fn else None
    result={"name":run_name,"n":n,"confusion":{"tp":tp,"fp":fp,"tn":tn,"fn":fn},
        "precision":precision,"recall":recall,"f1":2*precision*recall/(precision+recall) if precision is not None and recall else None,
        "accuracy":(tp+tn)/n if n else None,"recall_wilson_95":wilson_interval(tp,tp+fn),"by_category":per_category}
    if store is not None:
        from .guard_review import persist_evaluation
        run_id=persist_evaluation(store,samples,guard,run_name,observations,config=config)
        result["guard_run_id"]=run_id
    return result
