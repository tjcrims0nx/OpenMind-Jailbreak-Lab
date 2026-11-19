from .storage import Store
def summarize(store: Store, run_id: int):
    run = store.get_run(run_id); rows = store.get_results(run_id)
    labels = {}; categories = {}; flags = errors = 0
    for row in rows:
        label = row["detector_label"]; labels[label] = labels.get(label,0)+1
        cat = categories.setdefault(row["probe_category"],{"n":0,"flagged":0}); cat["n"] += 1
        if row["bypass"] == 1: cat["flagged"] += 1; flags += 1
        if label == "error": errors += 1
    return {"run_id":run_id,"name":run.get("name"),"target":run.get("target"),"n":len(rows),"labels":labels,"heuristic_flags":flags,"errors":errors,"categories":categories,"note":"Heuristic flags are not confirmed bypasses; use human adjudication."}
def regress(store: Store, baseline_id: int, candidate_id: int):
    base = {r["probe_id"]:r for r in store.get_results(baseline_id)}
    cand = {r["probe_id"]:r for r in store.get_results(candidate_id)}
    fixed=[]; reintroduced=[]; changed=[]
    for pid,c in cand.items():
        b=base.get(pid)
        if not b: continue
        if b["bypass"] == 1 and c["bypass"] != 1: fixed.append(pid)
        elif b["bypass"] != 1 and c["bypass"] == 1: reintroduced.append(pid)
        elif b["detector_label"] != c["detector_label"]: changed.append([pid,b["detector_label"],c["detector_label"]])
    return {"fixed":fixed,"reintroduced":reintroduced,"changed":changed,"note":"Compare runs with matching probe IDs and compatible settings."}
