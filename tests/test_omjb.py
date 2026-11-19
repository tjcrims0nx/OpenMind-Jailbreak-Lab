import json, tempfile, unittest
from pathlib import Path
from omjb.probes import load_probes
from omjb.targets import EchoTarget, Message, OpenAICompatTarget
from omjb.detectors import detect
from omjb.storage import Store
from omjb.runner import run
from omjb.report import summarize

class OMJBTests(unittest.TestCase):
    def test_echo_target(self):
        result=EchoTarget().generate([Message("user","hello")])
        self.assertEqual(result.text,"[echo] hello")
    def test_loader_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"cases.json"
            path.write_text(json.dumps([{"id":"x","prompt":"a"},{"id":"x","prompt":"b"}]))
            with self.assertRaisesRegex(ValueError,"duplicate"):
                load_probes(str(path))
    def test_detector_does_not_call_unclear_a_bypass(self):
        from omjb.probes import Probe
        result=detect(Probe("x","test","prompt","refuse"),"")
        self.assertIsNone(result.bypass)
    def test_provider_rejects_plain_http_remote(self):
        with self.assertRaisesRegex(ValueError,"HTTPS"):
            OpenAICompatTarget("test","http://example.com/v1","secret","model")
    def test_dry_run_persists_hash_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"test.db"
            store=Store(str(db))
            probes=[load_probes("corpus/omjb_probes.json")[0]]
            rid=run(EchoTarget(),probes,store,"unit")
            row=store.get_results(rid)[0]
            self.assertEqual(len(row["response_sha256"]),64)
            self.assertEqual(summarize(store,rid)["n"],1)
            store.close()

if __name__=="__main__":
    unittest.main()
