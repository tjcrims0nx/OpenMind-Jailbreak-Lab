import json,tempfile,unittest
from pathlib import Path
from omjb.probes import load_probes
from omjb.targets import EchoTarget,Message,OpenAICompatTarget,GeminiTarget
from omjb.detectors import detect
from omjb.storage import Store
from omjb.runner import run
from omjb.report import summarize
from omjb.guard import KeywordGuard
from omjb.stats import wilson_interval,classification_metrics
from omjb.export import export_jsonl,export_csv

class OMJBTests(unittest.TestCase):
    def test_echo_target(self):
        self.assertEqual(EchoTarget().generate([Message("user","hello")]).text,"[echo] hello")
    def test_loader_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"cases.json"; p.write_text(json.dumps([{"id":"x","prompt":"a"},{"id":"x","prompt":"b"}]))
            with self.assertRaisesRegex(ValueError,"duplicate"): load_probes(str(p))
    def test_jsonl_loader_and_invalid_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"cases.jsonl"; p.write_text('{"id":"a","prompt":"hello"}\n')
            self.assertEqual(load_probes(str(p))[0].id,"a")
            p.write_text('not-json\n')
            with self.assertRaisesRegex(ValueError,"line 1"): load_probes(str(p))
    def test_metadata_only_source_is_not_runnable(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"cases.json"; p.write_text(json.dumps([{"id":"src","prompt":"text","provenance":{"runnable":False}}]))
            with self.assertRaisesRegex(ValueError,"metadata-only"): load_probes(str(p))
    def test_detector_unclear_not_bypass(self):
        from omjb.probes import Probe
        self.assertIsNone(detect(Probe("x","test","prompt","refuse"),"").bypass)
    def test_provider_rejects_plain_http_remote(self):
        with self.assertRaisesRegex(ValueError,"HTTPS"): OpenAICompatTarget("test","http://example.com/v1","secret","model")
    def test_gemini_key_not_in_config(self):
        target=GeminiTarget("gemini","not-a-real-key","gemini-test")
        self.assertNotIn("not-a-real-key",json.dumps(target.config()))
    def test_input_guard_blocks_before_provider_and_persists(self):
        class NeverCall:
            name="never"
            def config(self): return {"name":"never"}
            def generate(self,*a,**k): raise AssertionError("provider must not be called")
        from omjb.probes import Probe
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(str(Path(tmp)/"db.sqlite"))
            rid=run(NeverCall(),[Probe("p","test","block-me")],s,"guarded",input_guards=[KeywordGuard(["block-me"],decision="block")])
            row=s.get_results(rid)[0]
            self.assertEqual(row["detector_label"],"guard_blocked")
            self.assertEqual(s.get_guard_observations(row["id"])[0]["decision"],"block")
            s.close()
    def test_output_guard_quarantines_response(self):
        from omjb.probes import Probe
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(str(Path(tmp)/"db.sqlite"))
            rid=run(EchoTarget(),[Probe("p","test","restricted-marker")],s,"guarded",output_guards=[KeywordGuard(["restricted-marker"],decision="block")])
            self.assertEqual(s.get_results(rid)[0]["detector_label"],"output_quarantined")
            s.close()
    def test_adjudicated_metrics_and_wilson(self):
        self.assertEqual(classification_metrics([{"predicted_label":"compliance","adjudicated_label":"compliance"}])["tp"],1)
        self.assertIsNotNone(wilson_interval(1,1))
        self.assertIsNone(wilson_interval(0,0))
    def test_dry_run_hash_report_and_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(str(Path(tmp)/"db.sqlite")); probe=load_probes("corpus/omjb_probes.json")[0]
            rid=run(EchoTarget(),[probe],s,"unit"); row=s.get_results(rid)[0]
            self.assertEqual(len(row["response_sha256"]),64); self.assertEqual(summarize(s,rid)["n"],1)
            self.assertEqual(export_jsonl(s,rid,str(Path(tmp)/"out.jsonl")),1)
            self.assertEqual(export_csv(s,rid,str(Path(tmp)/"out.csv")),1)
            s.close()

if __name__=="__main__": unittest.main()
