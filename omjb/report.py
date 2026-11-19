"""Reports separate heuristic signals from human adjudication."""
from .stats import classification_metrics,wilson_interval,cohen_kappa
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
    comparable=[r for r in scored if r["detector_label"] in ("refusal","compliance")]
    metrics=classification_metrics([{"predicted_label":r["detector_label"],"adjudicated_label":r["adjudicated_label"]} for r in scored])
    kappa=cohen_kappa([r["detector_label"] for r in comparable],[r["adjudicated_label"] for r in comparable])
    provenance={}
    for r in scored:
        try: source=(__import__("json").loads(r.get("provenance") or "{}").get("source") or "unknown")
        except Exception: source="unknown"
        b=provenance.setdefault(source,{"n":0,"human_compliance":0})
        b["n"]+=1; b["human_compliance"]+=int(r["adjudicated_label"]=="compliance")
    for b in provenance.values(): b["human_compliance_rate"]=b["human_compliance"]/b["n"]
    return {"run_id":run_id,"n_adjudicated":len(rows),"n_scored":len(scored),
        "human_bypass_n":n_comp,"human_bypass_rate":n_comp/len(scored) if scored else None,
        "human_bypass_ci_95":lohi,"detector_vs_human":metrics,"detector_vs_human_kappa":kappa,
        "by_category":by,"by_provenance":provenance,
        "note":"Human compliance labels are the measured outcome; detector labels are compared separately."}

def summarize(store:Store,run_id:int):
    run=store.get_run(run_id); rows=store.get_results(run_id)
    labels={}; categories={}; pipeline_stages={}; flags=errors=blocked=0
    for row in rows:
        label=row["detector_label"]; labels[label]=labels.get(label,0)+1
        cat=categories.setdefault(row["probe_category"],{"n":0,"heuristic_flags":0})
        cat["n"]+=1
        if row["bypass"]==1: cat["heuristic_flags"]+=1; flags+=1
        if label=="error": errors+=1
        if label in ("guard_blocked","output_quarantined"): blocked+=1
        if row.get("pipeline_result"):
            try: trace=__import__("json").loads(row["pipeline_result"])
            except (ValueError,TypeError): trace={}
            for stage in trace.get("stages",[]):
                key=f'{stage.get("on","unknown")}:{stage.get("stage","unknown")}'
                bucket=pipeline_stages.setdefault(key,{"n":0,"allow":0,"review":0,"block":0})
                bucket["n"]+=1
                action=stage.get("action")
                if action in bucket: bucket[action]+=1
    return {"run_id":run_id,"name":run.get("name"),"target":run.get("target"),"n":len(rows),
        "labels":labels,"heuristic_flags":flags,"blocked":blocked,"errors":errors,"categories":categories,"pipeline_stages":pipeline_stages,
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
    base_adj={r["probe_id"]:r["adjudicated_label"] for r in store.get_adjudicated_results(baseline_id)}
    cand_adj={r["probe_id"]:r["adjudicated_label"] for r in store.get_adjudicated_results(candidate_id)}
    human_fixed=[]; human_reintroduced=[]; human_changed=[]
    for pid,label in cand_adj.items():
        old=base_adj.get(pid)
        if old=="compliance" and label=="refusal": human_fixed.append(pid)
        elif old=="refusal" and label=="compliance": human_reintroduced.append(pid)
        elif old and old!=label: human_changed.append([pid,old,label])
    return {"fixed":fixed,"reintroduced":reintroduced,"changed":changed,
        "human_adjudicated_fixed":human_fixed,"human_adjudicated_reintroduced":human_reintroduced,
        "human_adjudicated_changed":human_changed,
        "baseline_only":sorted(set(base)-set(cand)),"candidate_only":sorted(set(cand)-set(base)),
        "note":"Heuristic and human-adjudicated regression are reported separately; only human labels count as reviewed outcomes."}
