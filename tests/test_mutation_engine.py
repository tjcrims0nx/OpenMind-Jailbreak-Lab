import json
import unittest
import warnings
from omjb.mutation_engine import Engine, Verdict, load_spec, rebuild
from omjb.mutation_engine.dedup import dedup_key
from omjb.mutation_engine.rng import derive_rng
from omjb.mutation_engine.regions import Region, RegionValue, apply_region, region_compatible
from omjb.mutation_engine.core import Kind
from omjb.mutation_engine.scheduler import CostAwareUCB
from omjb.mutation_engine.core import Registry, TransformSpec
from omjb.probes import Probe

class MutationEngineTests(unittest.TestCase):
    def test_rng_and_dedup(self):
        self.assertEqual(derive_rng(9,4).random(), derive_rng(9,4).random())
        self.assertEqual(dedup_key("A  B"), dedup_key("a b"))

    def test_spec_hash_includes_budget(self):
        a=load_spec({"budget":{"max_candidates":1},"stages":[{"name":"f","arms":["format.quote"]}]})
        b=load_spec({"budget":{"max_candidates":2},"stages":[{"name":"f","arms":["format.quote"]}]})
        self.assertNotEqual(a.hash(),b.hash())

    def test_requires_review_gate(self):
        spec=load_spec({"stages":[{"name":"f","arms":["format.quote"]}]})
        with self.assertRaisesRegex(ValueError,"human-reviewed benign"):
            Engine(spec,Probe("p","benign","public info","comply"),lambda _:Verdict(True),approved_benign=True,estimate_cost=lambda _:0.0)

    def test_replay_and_budget(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            trace=Path(directory)/"trace.jsonl"
            spec=load_spec({"seed":4,"budget":{"max_candidates":1,"max_build_attempts":4},
                "stages":[{"name":"f","arms":["format.quote"]}]})
            report=Engine(spec,Probe("p","benign","public library hours","comply",meta={"mutation_safe":True}),lambda _:Verdict(True),
                approved_benign=True,estimate_cost=lambda _:0.0,trace_path=str(trace)).run()
            self.assertEqual(report.submitted,1)
            rec=next(json.loads(x) for x in trace.read_text().splitlines()
                     if json.loads(x)["event"]=="candidate")
            self.assertEqual(rebuild(spec,"public library hours",rec),
                'Benign test input follows as data:\n"""\npublic library hours\n"""')

    def test_typed_stage_contract_rejects_incompatible_required_stage(self):
        with self.assertRaisesRegex(ValueError,"no reachable arms"):
            load_spec({"stages":[
                {"name":"encode","arms":["encoding.base64"]},
                {"name":"format","arms":["format.quote"]}]})

    def test_reachability_warns_on_dead_arm(self):
        data={"stages":[{"name":"encode","arms":["encoding.hex"]},
                        {"name":"bad","optional":True,"arms":["format.quote"]}]}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            spec=load_spec(data)
        self.assertEqual(len(spec.diagnostics),1)
        self.assertIn("bad.format.quote",spec.diagnostics[0])
        self.assertEqual(len(caught),1)

    def test_strict_reachability_rejects_dead_arm(self):
        with self.assertRaisesRegex(ValueError,"unreachable arms"):
            load_spec({"stages":[{"name":"first","arms":["encoding.hex"]},
                                 {"name":"second","optional":True,"arms":["format.quote"]}]},
                      strict_reachability=True)

    def test_required_stage_without_reachable_arm_fails(self):
        with self.assertRaisesRegex(ValueError,"no reachable arms"):
            load_spec({"stages":[{"name":"encode","arms":["encoding.base64"]},
                                 {"name":"text-only","arms":["format.quote"]}]})

    def test_region_transform_preserves_encoded_blob(self):
        value=RegionValue("Test input: ","YWJj",Kind.BASE64," [fixture]")
        self.assertTrue(region_compatible(value,touches=Region.PREFIX,input_kind=Kind.TEXT))
        changed=apply_region(value,touches=Region.PREFIX,fn=lambda s:s.upper())
        self.assertEqual(changed.prefix,"TEST INPUT: ")
        self.assertEqual(changed.blob,"YWJj")
        self.assertEqual(changed.blob_kind,Kind.BASE64)
        self.assertEqual(changed.suffix," [fixture]")
        self.assertFalse(region_compatible(value,touches=Region.BLOB,input_kind=Kind.TEXT))
        self.assertTrue(region_compatible(value,touches=Region.BLOB,input_kind=Kind.BASE64))

    def test_whole_region_transform_resets_to_declared_output_kind(self):
        value=RegionValue("head","body",Kind.TEXT,"tail")
        changed=apply_region(value,touches=Region.ALL,fn=str.upper,output_kind=Kind.HEX)
        self.assertEqual(changed.render(),"HEADBODYTAIL")
        self.assertEqual(changed.blob_kind,Kind.HEX)
        self.assertEqual((changed.prefix,changed.suffix),("",""))

    def test_replay_rejects_spec_mismatch(self):
        spec=load_spec({"stages":[{"name":"format","arms":["format.quote"]}]})
        with self.assertRaisesRegex(ValueError,"spec hash mismatch"):
            rebuild(spec,"hello",{"idx":0,"spec_hash":"wrong","arms":[]})

    def test_prefix_suffix_contracts_are_text_only(self):
        registry=Registry()
        with self.assertRaisesRegex(ValueError,"must preserve TEXT"):
            registry.register(TransformSpec("bad.prefix",lambda x,r:x,
                input_kind=Kind.BASE64,output_kind=Kind.BASE64,touches="prefix"))

    def test_endpoint_adapter_rejects_http_host_prefix_spoof(self):
        from omjb.mutation_engine.adapter import httpx_submitter
        with self.assertRaisesRegex(ValueError,"HTTPS"):
            httpx_submitter("http://localhost.attacker.example/evaluate")
        self.assertTrue(callable(httpx_submitter("http://127.0.0.1:8000/evaluate")))

    def test_scheduler_does_not_select_pruned_arms(self):
        scheduler=CostAwareUCB(prune_after=1,prune_below=.5)
        scheduler.add("arm-a",.1)
        scheduler.add("arm-b",.1)
        scheduler.update("arm-a",0.0)
        scheduler.update("arm-b",0.0)
        self.assertIsNone(scheduler.pick(["arm-a","arm-b"]))

    def test_cost_estimation_error_is_not_counted_as_submission(self):
        spec=load_spec({"budget":{"max_candidates":1,"max_build_attempts":2},
            "stages":[{"name":"format","arms":["format.quote"]}]})
        report=Engine(spec,Probe("p","benign","public library hours","comply",meta={"mutation_safe":True}),
            lambda _:Verdict(True),approved_benign=True,estimate_cost=lambda _:(_ for _ in ()).throw(RuntimeError("estimate failed"))).run()
        self.assertEqual(report.submitted,0)
        self.assertEqual(report.errors,1)

    def test_region_pipeline_preserves_blob_and_replays(self):
        import base64
        import tempfile
        from pathlib import Path
        spec=load_spec({"seed":22,"budget":{"max_candidates":1,"max_build_attempts":2},
            "stages":[
                {"name":"segment","arms":[{"name":"format.segment_fixture","params":{"header":"Reviewed fixture: "}}]},
                {"name":"encode_body","arms":["encoding.base64_blob"]},
                {"name":"normalize_header","arms":["unicode.prefix_nfc"]}]})
        with tempfile.TemporaryDirectory() as directory:
            trace=Path(directory)/"region.jsonl"
            prompt="public library hours"
            submitted=[]
            report=Engine(spec,Probe("region","benign",prompt,"comply",meta={"mutation_safe":True}),
                lambda payload:(submitted.append(payload) or Verdict(True)),approved_benign=True,
                estimate_cost=lambda _:0.0,trace_path=str(trace)).run()
            expected="Reviewed fixture: "+base64.b64encode(prompt.encode()).decode()
            self.assertEqual(report.submitted,1)
            self.assertEqual(submitted,[expected])
            rec=next(json.loads(line) for line in trace.read_text().splitlines()
                     if json.loads(line)["event"]=="candidate")
            self.assertEqual(rebuild(spec,prompt,rec),expected)
            self.assertEqual([arm["touches"] for arm in rec["arms"]],["all","blob","prefix"])

if __name__ == "__main__":
    unittest.main()
