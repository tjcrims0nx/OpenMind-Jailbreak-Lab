"""CLI entry point: python -m omjb.cli ..."""
import argparse, json, sys
from .probes import load_probes
from .runner import run
from .storage import Store
from .targets import target_from_env
from .report import summarize, regress

def main(argv=None):
    parser=argparse.ArgumentParser(prog="omjb",description="Bounded OpenMind evaluation harness")
    parser.add_argument("--db",default="openmind.db")
    sub=parser.add_subparsers(dest="cmd",required=True)
    sub.add_parser("list")
    runp=sub.add_parser("run")
    runp.add_argument("--probes",required=True); runp.add_argument("--name",required=True)
    runp.add_argument("--target",choices=("echo","openai","anthropic","ollama"),required=True)
    runp.add_argument("--base-url"); runp.add_argument("--model",default="gpt-4o-mini")
    runp.add_argument("--api-key-env",default="OPENAI_API_KEY"); runp.add_argument("--params",default="{}")
    runp.add_argument("--sleep",type=float,default=0)
    rep=sub.add_parser("report"); rep.add_argument("run_id",type=int)
    diff=sub.add_parser("regress"); diff.add_argument("baseline",type=int); diff.add_argument("candidate",type=int)
    adj=sub.add_parser("adjudicate"); adj.add_argument("run_id",type=int)
    args=parser.parse_args(argv); store=Store(args.db)
    try:
        if args.cmd=="list":
            for row in store.list_runs():
                print(row["id"],row["name"],row["target"],"done" if row["finished_at"] else "open")
        elif args.cmd=="run":
            params=json.loads(args.params)
            if not isinstance(params,dict): raise ValueError("--params must be a JSON object")
            target=target_from_env(args.target,args.model,args.base_url,args.api_key_env)
            probes=load_probes(args.probes)
            rid=run(target,probes,store,args.name,params,args.sleep,
                    lambda i,n,p: print(f"[{i}/{n}] {p.id}",file=sys.stderr))
            print(json.dumps(summarize(store,rid),indent=2))
        elif args.cmd=="report":
            print(json.dumps(summarize(store,args.run_id),indent=2))
        elif args.cmd=="regress":
            print(json.dumps(regress(store,args.baseline,args.candidate),indent=2))
        elif args.cmd=="adjudicate":
            for row in store.unadjudicated(args.run_id):
                print("\n"+"="*60+"\n",row["probe_id"],row["detector_label"],row["detector_reason"])
                print("PROMPT:",row["prompt"][:500],"\nRESPONSE:",row["response"][:1000])
                label=input("label [refusal/compliance/partial/unclear/skip]> ").strip().lower() or "skip"
                notes=input("notes> ").strip()
                store.add_adjudication(row["id"],label,notes)
    finally:
        store.close()
    return 0

if __name__=="__main__":
    raise SystemExit(main())
