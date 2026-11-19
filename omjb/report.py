"""Reports separate heuristic signals from human adjudication."""
from .stats import classification_metrics,wilson_interval
from .storage import Store

def adjudicated_summary(store,run_id):
    rows=store.get_adjudicated_results(run_id)
    if not rows: return {"run_id":run_id,"n_adjudicated":0,"note":"No human adjudications yet; run omjb adjudicate RUN_ID."}
    scored=[r for r in rows if r["adjudicated_label"] in ("refusal","compliance")]
    n_comp=sum(r["adjudicated_label"]=="compliance" for r in scored)
    lohi=wilson_interval(n_comp,len(scored))
    by={}
    for r in scored:
        cat=r["probe_category"] or "unknown"; b=by.setdefault(cat,{"n":0,"human_compliance":0})
        b["n"]+=1; b["human_compliance"]+=int(r["adjudicated_label"]=="compliance")
    for b in by.values(): b["human_compliance_rate"]=b["human_compliance"]/b["n"]
    metrics=classification_metrics([{"predicted_label":r["detector_label"],"adjudicated_label":r["adjudicated_label"]} for r in scored])
    provenance={}
    for r in scored:
        try: source=(__import__("json").loads(r.get("provenance") or "{}").get("source") or "unknown")
        except Exception: source="unknown"
        b=provenance.setdefault(source,{"n":0,"human_compliance":0})
        b["n"]+=1; b["human_compliance"]+=int(r["adjudicated_label"]=="compliance")
    for b in provenance.values(): b["human_compliance_rate"]=b["human_compliance"]/b["n"]
    return {"run_id":run_id,"n_adjudicated":len(rows),"n_scored":len(scored),
        "human_bypass_n":n_comp,"human_bypass_rate":n_comp/len(scored) if scored else None,
        "human_bypass_ci_95":lohi,"detector_vs_human":metrics,
        "by_category":by,"by_provenance":provenance,
        "note":"Human compliance labels are the measured outcome; detector labels are compared separately."}

def summarize(store:Store,run_id:int):
    run=store.get_run(run_id); rows=store.get_results(run_id)
    labels={}; categories={}; flags=errors=blocked=0
    for row in rows:
        label=row["detector_label"]; labels[label]=labels.get(label,0)+1
        cat=categories.setdefault(row["probe_category"],{"n":0,"heuristic_flags":0})
        cat["n"]+=1
        if row["bypass"]==1: cat["heuristic_flags"]+=1; flags+=1
        if label=="error": errors+=1
        if label in ("guard_blocked","output_quarantined"): blocked+=1
    return {"run_id":run_id,"name":run.get("name"),"target":run.get("target"),"n":len(rows),
        "labels":labels,"heuristic_flags":flags,"blocked":blocked,"errors":errors,"categories":categories,
        "adjudication":adjudicated_summary(store,run_id),
        "note":"Heuristic flags are not confirmed bypasses. Human adjudications are reported separately."}

def regress(store,baseline_id,candidate_id):
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
        "note":"Heuristic regression signals only; adjudicated labels are reported in run summaries."}
