"""Persistent, human-reviewable evidence for standalone guard evaluations.

Guard corpus truth (benign/attack), guard predictions (allow/review/block), and
reviewer assessments are stored separately from model-response adjudications.
"""
from __future__ import annotations
import json
import time
from dataclasses import asdict, is_dataclass
from .stats import wilson_interval

SCHEMA = """
CREATE TABLE IF NOT EXISTS guard_eval_runs (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, guard_name TEXT NOT NULL,
 config TEXT NOT NULL, started_at REAL NOT NULL, finished_at REAL
);
CREATE TABLE IF NOT EXISTS guard_eval_results (
 id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES guard_eval_runs(id),
 sample_id TEXT, category TEXT, text TEXT NOT NULL, expected_label TEXT NOT NULL,
 decision TEXT NOT NULL, findings TEXT NOT NULL, provenance TEXT,
 created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS guard_adjudications (
 id INTEGER PRIMARY KEY, result_id INTEGER NOT NULL REFERENCES guard_eval_results(id),
 reviewer TEXT NOT NULL DEFAULT '', label TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
 adjudicated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_guard_eval_results_run ON guard_eval_results(run_id);
CREATE INDEX IF NOT EXISTS idx_guard_adjudications_result ON guard_adjudications(result_id);
"""

def ensure_schema(store):
    store.conn.executescript(SCHEMA)
    store.conn.commit()

def persist_evaluation(store, samples, guard, run_name, observations, config=None):
    ensure_schema(store)
    if len(samples)!=len(observations):
        raise ValueError("sample and observation counts do not match")
    started=time.time()
    cur=store.conn.execute(
        "INSERT INTO guard_eval_runs(name,guard_name,config,started_at,finished_at) VALUES(?,?,?,?,NULL)",
        (run_name, getattr(guard,"name",guard.__class__.__name__),
         json.dumps(config or {},sort_keys=True),started))
    run_id=cur.lastrowid
    try:
        for index,(sample,observation) in enumerate(zip(samples,observations)):
            findings=getattr(observation,"findings",None)
            if findings is None:
                findings=[observation]
            serialized=[]
            for finding in findings:
                if is_dataclass(finding):
                    serialized.append(asdict(finding))
                elif hasattr(finding,"__dict__"):
                    serialized.append(dict(finding.__dict__))
                else:
                    serialized.append(finding)
            store.conn.execute(
                """INSERT INTO guard_eval_results
                (run_id,sample_id,category,text,expected_label,decision,findings,provenance,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (run_id,str(sample.get("id",f"sample-{index+1:04d}")),
                 sample.get("category","uncategorized"),sample["text"],sample["label"],
                 observation.decision,json.dumps(serialized,sort_keys=True),
                 json.dumps(sample.get("provenance",{}),sort_keys=True),time.time()))
        store.conn.execute("UPDATE guard_eval_runs SET finished_at=? WHERE id=?",(time.time(),run_id))
        store.conn.commit()
    except Exception:
        store.conn.rollback()
        raise
    return run_id

def pending(store, run_id, reviewer=""):
    ensure_schema(store)
    return [dict(r) for r in store.conn.execute(
        """SELECT r.* FROM guard_eval_results r
        WHERE r.run_id=? AND NOT EXISTS (
          SELECT 1 FROM guard_adjudications a WHERE a.result_id=r.id AND a.reviewer=?
        ) ORDER BY r.id""",(run_id,reviewer))]

def adjudicate(store, result_id, label, notes="", reviewer=""):
    if label not in ("correct","incorrect","unclear","skip"):
        raise ValueError("guard review label must be correct|incorrect|unclear|skip")
    ensure_schema(store)
    store.conn.execute(
        """INSERT INTO guard_adjudications(result_id,reviewer,label,notes,adjudicated_at)
        VALUES(?,?,?,?,?)""",(result_id,reviewer,label,notes,time.time()))
    store.conn.commit()

def summary(store, run_id, reviewer=None):
    ensure_schema(store)
    run=store.conn.execute("SELECT * FROM guard_eval_runs WHERE id=?",(run_id,)).fetchone()
    if not run: raise ValueError(f"unknown guard evaluation run: {run_id}")
    rows=[dict(r) for r in store.conn.execute(
        "SELECT * FROM guard_eval_results WHERE run_id=? ORDER BY id",(run_id,))]
    tp=fp=tn=fn=0
    for row in rows:
        predicted=row["decision"] in ("block","review")
        actual=row["expected_label"]=="attack"
        if actual and predicted: tp+=1
        elif actual: fn+=1
        elif predicted: fp+=1
        else: tn+=1
    review_sql="""SELECT a.* FROM guard_adjudications a JOIN guard_eval_results r
        ON r.id=a.result_id WHERE r.run_id=?"""
    review_params=[run_id]
    if reviewer is not None:
        review_sql+=" AND a.reviewer=?"
        review_params.append(reviewer)
    all_reviews=[dict(r) for r in store.conn.execute(review_sql,review_params)]
    reviews=[r for r in all_reviews if r["label"] in ("correct","incorrect")]
    correct=sum(r["label"]=="correct" for r in reviews)
    n=len(reviews)
    return {"run_id":run_id,"name":run["name"],"guard":run["guard_name"],"n":len(rows),
      "confusion":{"tp":tp,"fp":fp,"tn":tn,"fn":fn},
      "precision":tp/(tp+fp) if tp+fp else None,
      "recall":tp/(tp+fn) if tp+fn else None,
      "accuracy":(tp+tn)/len(rows) if rows else None,
      "recall_wilson_95":wilson_interval(tp,tp+fn),
      "human_review":{"n":n,"correct":correct,"incorrect":sum(r["label"]=="incorrect" for r in reviews),
                      "unclear":sum(r["label"]=="unclear" for r in all_reviews),
                      "skip":sum(r["label"]=="skip" for r in all_reviews),
                      "reviewer":reviewer,
                      "agreement_rate":correct/n if n else None},
      "note":"Human review assesses whether each recorded guard decision is correct; it is not model-response adjudication."}
