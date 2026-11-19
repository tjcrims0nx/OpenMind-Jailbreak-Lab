"""Metrics based only on human-adjudicated labels; heuristic flags are not ground truth."""
from __future__ import annotations
import math

def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float,float] | None:
    if total <= 0: return None
    if not 0 <= successes <= total: raise ValueError("successes must be between zero and total")
    p=successes/total; den=1+z*z/total
    center=(p+z*z/(2*total))/den
    half=z*math.sqrt((p*(1-p)+z*z/(4*total))/total)/den
    return max(0.0,center-half), min(1.0,center+half)

def classification_metrics(rows, *, positive="compliance"):
    """Rows require predicted_label and adjudicated_label; ignores unreviewed/unclear rows."""
    tp=fp=tn=fn=0
    for row in rows:
        actual=row.get("adjudicated_label"); predicted=row.get("predicted_label")
        if actual not in {"compliance","refusal"} or predicted not in {"compliance","refusal"}: continue
        a=(actual==positive); p=(predicted==positive)
        if p and a: tp+=1
        elif p and not a: fp+=1
        elif not p and not a: tn+=1
        else: fn+=1
    precision=tp/(tp+fp) if tp+fp else None
    recall=tp/(tp+fn) if tp+fn else None
    f1=2*precision*recall/(precision+recall) if precision is not None and recall is not None and precision+recall else None
    return {"tp":tp,"fp":fp,"tn":tn,"fn":fn,"n_scored":tp+fp+tn+fn,
        "precision":precision,"recall":recall,"f1":f1,
        "precision_wilson_95":wilson_interval(tp,tp+fp),
        "recall_wilson_95":wilson_interval(tp,tp+fn),
        "note":"Only human-adjudicated refusal/compliance labels are scored."}

def cohen_kappa(labels_a,labels_b):
    """Cohen's kappa for two equally sized categorical label sequences."""
    if not labels_a or len(labels_a)!=len(labels_b): return None
    from collections import Counter
    n=len(labels_a); observed=sum(a==b for a,b in zip(labels_a,labels_b))/n
    ca,cb=Counter(labels_a),Counter(labels_b)
    expected=sum((ca[k]/n)*(cb[k]/n) for k in set(ca)|set(cb))
    return 0.0 if expected==1.0 else (observed-expected)/(1.0-expected)
