"""CLI for running the professional engine on a reviewed OMJB probe."""
import argparse,json,os,sys
from pathlib import Path
from ..probes import load_probes
from .adapter import httpx_submitter
from .engine import Engine
from .spec import load_spec

def main(argv=None):
    parser=argparse.ArgumentParser(prog="omjb-mutate")
    parser.add_argument("--spec",required=True)
    parser.add_argument("--corpus",required=True)
    parser.add_argument("--probe-id",required=True)
    parser.add_argument("--endpoint",required=True)
    parser.add_argument("--token-env",default="OMJB_GUARDRAIL_TOKEN")
    parser.add_argument("--trace",default="mutation-trace.jsonl")
    parser.add_argument("--estimated-request-cost",type=float,default=0.0)
    args=parser.parse_args(argv)
    probes=load_probes(args.corpus)
    matches=[p for p in probes if p.id==args.probe_id]
    if len(matches)!=1:
        parser.error(f"expected exactly one probe with id {args.probe_id!r}; found {len(matches)}")
    probe=matches[0]
    if probe.expected!="comply" or probe.meta.get("mutation_safe") is not True:
        parser.error("selected probe must be human-reviewed benign: expected=comply and meta.mutation_safe=true")
    token=os.environ.get(args.token_env)
    headers={"Authorization":f"Bearer {token}"} if token else {}
    spec=load_spec(json.loads(Path(args.spec).read_text(encoding="utf-8")))
    submit=httpx_submitter(args.endpoint,headers=headers)
    engine=Engine(spec,probe,submit,approved_benign=True,
                  estimate_cost=lambda _payload:args.estimated_request_cost,
                  trace_path=args.trace)
    report=engine.run()
    print(json.dumps({
        "spec_hash":spec.hash(),"probe_id":probe.id,"submitted":report.submitted,
        "allowed":report.allowed,"blocked":report.blocked,"errors":report.errors,
        "skipped":report.skipped,"allow_rate":report.allow_rate,"by_arm":report.by_arm
    },indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    sys.exit(main())
