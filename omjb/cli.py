"""CLI entry point: python -m omjb.cli ..."""
import argparse,hashlib,json,sys
from pathlib import Path
from .probes import load_probes
from .runner import run
from .storage import Store
from .targets import target_from_env
from .report import summarize,regress
from .guard import KeywordGuard
from .pipeline import pipeline_from_config
from .provenance import verify_manifest
from .export import export_jsonl,export_csv,export_report

def _pipeline_spec(spec,judge=None):
    if not spec: return None
    if spec.lstrip().startswith("{"):
        cfg=json.loads(spec)
    else:
        path=Path(spec)
        if not path.is_file(): raise ValueError(f"pipeline config file not found: {spec}")
        cfg=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cfg,dict) or not isinstance(cfg.get("stages",[]),list): raise ValueError("pipeline JSON must be an object with a stages list")
    return pipeline_from_config(cfg,judge=judge)

def main(argv=None):
    parser=argparse.ArgumentParser(prog="omjb",description="Bounded OpenMind evaluation harness")
    parser.add_argument("--db",default="openmind.db")
    sub=parser.add_subparsers(dest="cmd",required=True)
    sub.add_parser("list")
    rp=sub.add_parser("run"); rp.add_argument("--probes",default=None); rp.add_argument("--suite",choices=("guardrail-lab",),default=None); rp.add_argument("--case",action="append",default=[]); rp.add_argument("--name",required=True)
    rp.add_argument("--target",choices=("echo","openai","anthropic","ollama","gemini"),required=True)
    rp.add_argument("--base-url"); rp.add_argument("--model",default="gemini-2.5-flash")
    rp.add_argument("--api-key-env"); rp.add_argument("--params",default="{}"); rp.add_argument("--sleep",type=float,default=0)
    rp.add_argument("--judge-target",choices=("openai","anthropic","ollama","gemini"),default=None)
    rp.add_argument("--judge-model",default="gemini-2.5-flash"); rp.add_argument("--judge-base-url"); rp.add_argument("--judge-api-key-env")
    rp.add_argument("--require-provenance",action="store_true"); rp.add_argument("--dedupe",action="store_true")
    rp.add_argument("--pipeline-json",default=None,help="pipeline JSON file path or inline JSON object")
    for arg in ("input-review-term","input-block-term","output-review-term","output-block-term"): rp.add_argument("--"+arg,action="append",default=[])
    rep=sub.add_parser("report"); rep.add_argument("run_id",type=int); rep.add_argument("--reviewer",default=None)
    diff=sub.add_parser("regress"); diff.add_argument("baseline",type=int); diff.add_argument("candidate",type=int)
    adj=sub.add_parser("adjudicate"); adj.add_argument("run_id",type=int); adj.add_argument("--reviewer",default=None)
    exp=sub.add_parser("export"); exp.add_argument("run_id",type=int); exp.add_argument("--format",choices=("jsonl","csv","report"),required=True); exp.add_argument("--output",required=True)
    exp.add_argument("--include-adjudication",action="store_true"); exp.add_argument("--adjudicated-only",action="store_true"); exp.add_argument("--reviewer",default=None)
    ge=sub.add_parser("guard-evaluate",help="evaluate a guard against labeled benign/attack samples")
    ge.add_argument("--corpus",required=True); ge.add_argument("--name",default="guard-eval")
    ge.add_argument("--review-term",action="append",default=[]); ge.add_argument("--block-term",action="append",default=[])
    ge.add_argument("--require-provenance",action="store_true"); ge.add_argument("--dedupe",action="store_true")
    ga=sub.add_parser("guard-adjudicate",help="human-review recorded guard decisions")
    ga.add_argument("run_id",type=int); ga.add_argument("--reviewer",default="")
    gr=sub.add_parser("guard-report",help="report standalone guard evaluation and human review")
    gr.add_argument("run_id",type=int); gr.add_argument("--reviewer",default=None)
    ft=sub.add_parser("fetch",help="download a SHA-256-pinned, licensed corpus source")
    ft.add_argument("--source-config",required=True); ft.add_argument("--output",required=True)
    vf=sub.add_parser("verify",help="verify a corpus file against a JSON manifest"); vf.add_argument("manifest")
    args=parser.parse_args(argv)
    if args.cmd=="fetch":
        from .downloaders import fetch_source
        print(json.dumps(fetch_source(args.source_config,args.output),indent=2))
        return 0
    if args.cmd=="verify":
        result=verify_manifest(args.manifest)
        print(json.dumps(result,indent=2))
        return 0 if result["ok"] else 1
    store=Store(args.db)
    try:
        if args.cmd=="list":
            for row in store.list_runs(): print(row["id"],row["name"],row["target"],"done" if row["finished_at"] else "open")
        elif args.cmd=="run":
            params=json.loads(args.params)
            if not isinstance(params,dict): raise ValueError("--params must be a JSON object")
            target=target_from_env(args.target,args.model,args.base_url,args.api_key_env)
            if args.suite:
                from .guardrail_adapter import load_guardrail_lab_cases
                probes=load_guardrail_lab_cases(args.case or None)
            elif args.probes:
                if args.case: raise ValueError("--case is available only with --suite guardrail-lab")
                probes=load_probes(args.probes,require_provenance=args.require_provenance,dedupe=args.dedupe)
            else: raise ValueError("provide --probes PATH or --suite guardrail-lab")
            judge=target_from_env(args.judge_target,args.judge_model,args.judge_base_url,args.judge_api_key_env) if args.judge_target else None
            pipeline=_pipeline_spec(args.pipeline_json,judge=judge)
            input_guards=[KeywordGuard(args.input_review_term,decision="review",name="input-review"),KeywordGuard(args.input_block_term,decision="block",name="input-block")]
            output_guards=[KeywordGuard(args.output_review_term,decision="review",name="output-review"),KeywordGuard(args.output_block_term,decision="block",name="output-block")]
            legacy=any((args.input_review_term,args.input_block_term,args.output_review_term,args.output_block_term))
            rid=run(target,probes,store,args.name,params=params,sleep=args.sleep,
                progress=lambda i,n,p: print(f"[{i}/{n}] {p.id}",file=sys.stderr),
                input_guards=input_guards if legacy and pipeline is None else (),
                output_guards=output_guards if legacy and pipeline is None else (),pipeline=pipeline)
            print(json.dumps(summarize(store,rid),indent=2))
        elif args.cmd=="report": print(json.dumps(summarize(store,args.run_id,reviewer=args.reviewer),indent=2))
        elif args.cmd=="regress": print(json.dumps(regress(store,args.baseline,args.candidate),indent=2))
        elif args.cmd=="export":
            if args.include_adjudication or args.adjudicated_only:
                rows=store.get_results_with_adjudication(args.run_id,reviewer=args.reviewer)
                if args.adjudicated_only: rows=[r for r in rows if r["adj_label"]]
                if args.format=="report": count=export_report(store,args.run_id,args.output,reviewer=args.reviewer)
                elif args.format=="jsonl":
                    with open(args.output,"w",encoding="utf-8") as f:
                        for row in rows: f.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n")
                    count=len(rows)
                else:
                    import csv
                    fields=list(rows[0]) if rows else ["id","probe_id","adj_label"]
                    with open(args.output,"w",newline="",encoding="utf-8") as f:
                        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore"); w.writeheader(); w.writerows(rows)
                    count=len(rows)
            else:
                count=export_report(store,args.run_id,args.output,reviewer=args.reviewer) if args.format=="report" else {"jsonl":export_jsonl,"csv":export_csv}[args.format](store,args.run_id,args.output)
            if count is not None: print(json.dumps({"exported":count,"path":args.output}))
        elif args.cmd=="guard-evaluate":
            from .guard_eval import load_labeled,evaluate
            from .guard import evaluate_guards
            samples=load_labeled(args.corpus,require_provenance=args.require_provenance,dedupe=args.dedupe)
            if not (args.review_term or args.block_term): raise ValueError("provide at least one --review-term or --block-term")
            guards=[]
            if args.review_term: guards.append(KeywordGuard(args.review_term,decision="review",name="review"))
            if args.block_term: guards.append(KeywordGuard(args.block_term,decision="block",name="block"))
            class _Guard:
                name="cli-keyword-guard"
                def inspect(self,text,stage="input"):
                    return evaluate_guards(text,guards,stage=stage)
            print(json.dumps(evaluate(_Guard(),samples,store=store,run_name=args.name,config={"guard":"keyword","review_terms":args.review_term,"block_terms":args.block_term}),indent=2))
        elif args.cmd=="guard-adjudicate":
            from .guard_review import pending,adjudicate
            for row in pending(store,args.run_id,args.reviewer):
                print("\n"+"="*60+"\n",row["sample_id"],row["category"],row["decision"])
                print("EXPECTED:",row["expected_label"],"\nTEXT:",row["text"][:1000])
                label=input("review [correct/incorrect/unclear/skip]> ").strip().lower() or "skip"
                notes=input("notes> ").strip()
                adjudicate(store,row["id"],label,notes,reviewer=args.reviewer)
        elif args.cmd=="guard-report":
            from .guard_review import summary as guard_summary
            print(json.dumps(guard_summary(store,args.run_id,reviewer=args.reviewer),indent=2))
        elif args.cmd=="adjudicate":
            for row in store.unadjudicated(args.run_id,reviewer=args.reviewer):
                print("\n"+"="*60+"\n",row["probe_id"],row["detector_label"],row["detector_reason"])
                print("PROMPT:",row["prompt"][:500],"\nRESPONSE:",row["response"][:1000])
                label=input("label [refusal/compliance/partial/unclear/skip]> ").strip().lower() or "skip"
                notes=input("notes> ").strip(); store.add_adjudication(row["id"],label,notes,reviewer=args.reviewer or "")
    finally: store.close()
    return 0
if __name__=="__main__": raise SystemExit(main())
