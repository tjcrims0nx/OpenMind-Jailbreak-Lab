import json,tempfile,unittest,io
from contextlib import redirect_stdout
from unittest.mock import patch
from pathlib import Path
from omjb.storage import Store
from omjb.guard import KeywordGuard
from omjb.guard_eval import evaluate
from omjb.guard_review import pending,adjudicate,summary
from omjb.probes import Probe
from omjb.targets import EchoTarget
from omjb.runner import run
from omjb.report import summarize
from omjb.cli import main

class GuardReviewTests(unittest.TestCase):
    def test_reviewer_scoped_model_adjudication_is_backward_compatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(str(Path(tmp)/"model.sqlite"))
            run_id=run(EchoTarget(),[Probe("p","test","hello")],store,"model-review")
            result=store.get_results(run_id)[0]
            store.add_adjudication(result["id"],"refusal","reviewed",reviewer="alice")
            self.assertEqual(len(store.unadjudicated(run_id,reviewer="bob")),1)
            self.assertEqual(len(store.unadjudicated(run_id,reviewer="alice")),0)
            self.assertEqual(store.get_results_with_adjudication(run_id,reviewer="alice")[0]["adj_label"],"refusal")
            self.assertEqual(store.get_results_with_adjudication(run_id)[0]["adj_label"],"refusal")
            self.assertEqual(summarize(store,run_id,reviewer="alice")["adjudication"]["n_adjudicated"],1)
            self.assertEqual(summarize(store,run_id,reviewer="bob")["adjudication"]["n_adjudicated"],0)
            store.close()

    def test_persist_and_adjudicate_guard_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(str(Path(tmp)/"review.sqlite"))
            samples=[{"id":"safe","text":"hello","label":"benign"},
                     {"id":"attack","text":"blocked marker","label":"attack"}]
            result=evaluate(KeywordGuard(["blocked marker"],decision="block"),samples,
                            store=store,run_name="review-test",config={"keyword_terms":["blocked marker"]})
            run_id=result["guard_run_id"]
            rows=pending(store,run_id,"reviewer-a")
            self.assertEqual(len(rows),2)
            adjudicate(store,rows[0]["id"],"correct","",reviewer="reviewer-a")
            self.assertEqual(len(pending(store,run_id,"reviewer-a")),1)
            self.assertEqual(len(pending(store,run_id,"reviewer-b")),2)
            report=summary(store,run_id)
            self.assertEqual(report["confusion"]["tp"],1)
            run_record=store.conn.execute("SELECT config,started_at,finished_at FROM guard_eval_runs WHERE id=?",(run_id,)).fetchone()
            self.assertEqual(json.loads(run_record["config"]),{"keyword_terms":["blocked marker"]})
            self.assertGreaterEqual(run_record["finished_at"],run_record["started_at"])
            self.assertEqual(report["human_review"]["correct"],1)
            self.assertTrue(json.loads(rows[1]["findings"]))
            adjudicate(store,rows[0]["id"],"incorrect","second opinion",reviewer="reviewer-b")
            self.assertEqual(summary(store,run_id,reviewer="reviewer-a")["human_review"]["correct"],1)
            self.assertEqual(summary(store,run_id,reviewer="reviewer-a")["human_review"]["incorrect"],0)
            self.assertEqual(summary(store,run_id,reviewer="reviewer-b")["human_review"]["incorrect"],1)
            store.close()

    def test_cli_guard_evaluate_adjudicate_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"cli.sqlite"
            corpus=Path(tmp)/"samples.jsonl"
            corpus.write_text(json.dumps({"id":"a","text":"marker attack sample","label":"attack"})+"\n")
            output=io.StringIO()
            with redirect_stdout(output):
                main(["--db",str(db),"guard-evaluate","--corpus",str(corpus),
                      "--name","cli-test","--block-term","marker"])
            run_id=json.loads(output.getvalue())["guard_run_id"]
            with patch("builtins.input",side_effect=["correct","looks right"]),redirect_stdout(io.StringIO()):
                main(["--db",str(db),"guard-adjudicate",str(run_id),"--reviewer","cli-reviewer"])
            output=io.StringIO()
            with redirect_stdout(output):
                main(["--db",str(db),"guard-report",str(run_id),"--reviewer","cli-reviewer"])
            report=json.loads(output.getvalue())
            self.assertEqual(report["human_review"]["correct"],1)
            self.assertEqual(report["human_review"]["reviewer"],"cli-reviewer")

    def test_cli_default_model_adjudication_preserves_legacy_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"legacy-cli.sqlite"
            store=Store(str(db))
            run_id=run(EchoTarget(),[Probe("p","test","hello")],store,"model-review")
            result=store.get_results(run_id)[0]
            store.add_adjudication(result["id"],"refusal","already reviewed",reviewer="alice")
            store.close()
            with patch("builtins.input") as prompt,redirect_stdout(io.StringIO()):
                main(["--db",str(db),"adjudicate",str(run_id)])
            prompt.assert_not_called()

if __name__=="__main__": unittest.main()
