"""Evidence exports. Exports preserve adjudication separately from heuristic predictions."""
import csv, json
from pathlib import Path
from .report import summarize

def export_jsonl(store, run_id: int, path: str):
    rows=store.get_results(run_id)
    with open(path,"w",encoding="utf-8") as f:
        for row in rows: f.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n")
    return len(rows)

def export_csv(store, run_id: int, path: str):
    rows=store.get_results(run_id)
    fields=list(rows[0].keys()) if rows else ["id","run_id","probe_id","detector_label","bypass"]
    with open(path,"w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore"); writer.writeheader(); writer.writerows(rows)
    return len(rows)

def export_report(store, run_id: int, path: str, reviewer=None):
    Path(path).write_text(json.dumps(summarize(store,run_id,reviewer=reviewer),indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
