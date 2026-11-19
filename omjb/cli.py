"""CLI entry point: python -m omjb.cli ..."""
import argparse,json,sys
from .probes import load_probes
from .runner import run
from .storage import Store
from .targets import target_from_env
from .report import summarize,regress
from .guard import KeywordGuard
from .export import export_jsonl,export_csv,export_report

def main(argv=None):
    parser=argparse.ArgumentParser(prog="omjb",description="Bounded OpenMind evaluation harness")
    parser.add_argument("--db",default="openmind.db")
    sub=parser.add_subparsers(dest="cmd",required=True)
    sub.add_parser("list")
    rp=sub.add_parser("run"); rp.add_argument("--probes",required=True); rp.add_argument("--name",required=True)
    rp.add_argument("--target",choices=("echo","openai","anthropic","ollama","gemini"),required=True)
    rp.add_argument("--base-url"); rp.add_argument("--model",default="gemini-2.5-flash")
    rp.add_argument("--api-key-env"); rp.add_argument("--params",default="{}"); rp.add_argument("--sleep",type=float,default=0)
    for arg in ("input-review-term","input-block-term","output-review-term","output-block-term"): rp.add_argument("--"+arg,action="append",default=[])
    rep=sub.add_parser("report"); rep.add_argument("run_id",type=int)
    diff=sub.add_parser("regress"); diff.add_argument("baseline",type=int); diff.add_argument("candidate",type=int)
    adj=sub.add_parser("adjudicate"); adj.add_argument("run_id",type=int)
    exp=sub.add_parser("export"); exp.add_argument("run_id",type=int); exp.add_argument("--format",choices=("jsonl","csv","report"),required=True); exp.add_argument("--output",required=True)
    args=parser.parse_args(argv); store=Store(args.db)
    try:
        if args.cmd=="list":
            for row in store.list_runs(): print(row["id"],row["name"],row["target"],"done" if row["finished_at"] else "open")
        elif args.cmd=="run":
            params=json.loads(args.params)
            if not isinstance(params,dict): raise ValueError("--params must be a JSON object")
            target=target_from_env(args.target,args.model,args.base_url,args.api_key_env); probes=load_probes(args.probes)
            input_guards=[KeywordGuard(args.input_review_term,decision="review",name="input-review"),KeywordGuard(args.input_block_term,decision="block",name="input-block")]
            output_guards=[KeywordGuard(args.output_review_term,decision="review",name="output-review"),KeywordGuard(args.output_block_term,decision="block",name="output-block")]
            rid=run(target,probes,store,args.name,params,args.sleep,lambda i,n,p: print(f"[{i}/{n}] {p.id}",file=sys.stderr),input_guards,output_guards)
            print(json.dumps(summarize(store,rid),indent=2))
        elif args.cmd=="report": print(json.dumps(summarize(store,args.run_id),indent=2))
        elif args.cmd=="regress": print(json.dumps(regress(store,args.baseline,args.candidate),indent=2))
        elif args.cmd=="export":
            count={"jsonl":export_jsonl,"csv":export_csv,"report":export_report}[args.format](store,args.run_id,args.output)
            if count is not None: print(json.dumps({"exported":count,"path":args.output}))
        elif args.cmd=="adjudicate":
            for row in store.unadjudicated(args.run_id):
                print("\n"+"="*60+"\n",row["probe_id"],row["detector_label"],row["detector_reason"])
                print("PROMPT:",row["prompt"][:500],"\nRESPONSE:",row["response"][:1000])
                label=input("label [refusal/compliance/partial/unclear/skip]> ").strip().lower() or "skip"
                notes=input("notes> ").strip(); store.add_adjudication(row["id"],label,notes)
    finally: store.close()
    return 0
if __name__=="__main__": raise SystemExit(main())
