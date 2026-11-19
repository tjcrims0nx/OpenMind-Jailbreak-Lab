import hashlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from omjb.downloaders import fetch_source
from omjb.probes import load_probes
from omjb.provenance import verify_manifest

class FakeResponse(io.BytesIO):
    def __init__(self,payload,url):
        super().__init__(payload); self.url=url
    def __enter__(self): return self
    def __exit__(self,*args): self.close()
    def geturl(self): return self.url

class DownloaderTests(unittest.TestCase):
    def test_pinned_download_emits_loadable_provenance_corpus(self):
        payload=json.dumps([{"id":"fixture-1","prompt":"safe evaluation prompt","expected":"either","category":"fixture"}]).encode()
        digest=hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp)/"source.json"
            config.write_text(json.dumps({"name":"fixture","url":"https://example.test/data.json",
                "sha256":digest,"revision":"v1.2.3","license":"CC0-1.0","format":"json",
                "prompt_field":"prompt","reviewed":True}))
            output=Path(tmp)/"probes.jsonl"
            with patch("omjb.downloaders.urllib.request.urlopen",
                       return_value=FakeResponse(payload,"https://example.test/data.json")):
                result=fetch_source(config,output)
            self.assertEqual(result["n"],1)
            probes=load_probes(str(output),require_provenance=True)
            self.assertEqual(probes[0].id,"fixture-1")
            self.assertEqual(probes[0].expected,"either")
            self.assertEqual(probes[0].provenance_record.revision,"v1.2.3")
            self.assertTrue(verify_manifest(str(output)+".manifest.json")["ok"])

    def test_hash_mismatch_rejected_before_output(self):
        payload=b'[{"prompt":"safe"}]'
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp)/"source.json"
            config.write_text(json.dumps({"name":"fixture","url":"https://example.test/data.json",
                "sha256":"0"*64,"revision":"v1","license":"CC0-1.0","format":"json",
                "prompt_field":"prompt","reviewed":True}))
            output=Path(tmp)/"probes.jsonl"
            with patch("omjb.downloaders.urllib.request.urlopen",
                       return_value=FakeResponse(payload,"https://example.test/data.json")):
                with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
                    fetch_source(config,output)
            self.assertFalse(output.exists())

    def test_requires_human_reviewed_source_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp)/"source.json"
            config.write_text(json.dumps({"name":"fixture","url":"https://example.test/data.json",
                "sha256":"0"*64,"revision":"v1","license":"CC0-1.0","format":"json",
                "prompt_field":"prompt","reviewed":False}))
            with self.assertRaisesRegex(ValueError,"reviewed: true"):
                fetch_source(config,Path(tmp)/"out.jsonl")

    def test_rejects_non_text_system_prompt(self):
        payload=json.dumps([{"prompt":"safe","system":123}]).encode()
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp)/"source.json"
            config.write_text(json.dumps({"name":"fixture","url":"https://example.test/data.json",
                "sha256":hashlib.sha256(payload).hexdigest(),"revision":"v1","license":"CC0-1.0",
                "format":"json","prompt_field":"prompt","reviewed":True}))
            with patch("omjb.downloaders.urllib.request.urlopen",
                       return_value=FakeResponse(payload,"https://example.test/data.json")):
                with self.assertRaisesRegex(ValueError,"system value must be text"):
                    fetch_source(config,Path(tmp)/"out.jsonl")

if __name__=="__main__": unittest.main()
