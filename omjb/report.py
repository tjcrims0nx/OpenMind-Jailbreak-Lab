"""Reports separate heuristic signals from human adjudication."""
from .storage import Store
from .stats import classification_metrics

def summarize(store: Store,run_id: int):
    run=store.get_run(run_id); rows=store.get_results(run_id)
    labels={}; categories={}; flags=errors=0
    for row in rows:
        label=row["detector_label"]; labels[label]=labels.get(label,0)+1
        cat=categories.setdefault(row["probe_category"],{"n":0,"flagged":0}); cat["n"]+=1
        if row["bypass"]==1: cat["flagged"]+=1; flags+=1
        if label=="error": errors+=1
    adjudicated=store.get_adjudicated_results(run_id)
    metric_rows=[{"predicted_label":r["detector_label"],"adjudicated_label":r["adjudicated_label"]} for r in adjudicated]
    return {"run_id":run_id,"name":run.get("name"),"target":run.get("target"),"n":len(rows),
        "labels":labels,"heuristic_flags":flags,"errors":errors,"categories":categories,
        "adjudicated_n":len(adjudicated),"adjudicated_metrics":classification_metrics(metric_rows),
        "note":"Heuristic flags are not confirmed bypasses. Metrics use only human-adjudicated refusal/compliance labels."}

def regress(store: Store,baseline_id: int,candidate_id: int):
    base={r["probe_id"]:r for r in store.get_results(baseline_id)}
    cand={r["probe_id"]:r for r in store.get_results(candidate_id)}
    fixed=[]; reintroduced=[]; changed=[]
    for pid,c in cand.items():
        b=base.get(pid)
        if not b: continue
        if b["bypass"]==1 and c["bypass"]!=1: fixed.append(pid)
        elif b["bypass"]!=1 and c["bypass"]==1: reintroduced.append(pid)
        elif b["detector_label"]!=c["detector_label"]: changed.append([pid,b["detector_label"],c["detector_label"]])
    return {"fixed":fixed,"reintroduced":reintroduced,"changed":changed,
        "baseline_only":sorted(set(base)-set(cand)),"candidate_only":sorted(set(cand)-set(base)),
        "note":"Heuristic regression signals only; compare matching probe IDs/settings and adjudicate."}
