import json,tempfile,unittest
from pathlib import Path
from omjb.storage import Store
from omjb.guard import KeywordGuard
from omjb.guard_eval import evaluate
from omjb.guard_review import pending,adjudicate,summary
from omjb.probes import Probe\nfrom omjb.targets import EchoTarget\nfrom omjb.runner import run

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
            store.close()

    def test_persist_and_adjudicate_guard_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(str(Path(tmp)/"review.sqlite"))
            samples=[{"id":"safe","text":"hello","label":"benign"},
                     {"id":"attack","text":"blocked marker","label":"attack"}]
            result=evaluate(KeywordGuard(["blocked marker"],decision="block"),samples,
                            store=store,run_name="review-test")
            run_id=result["guard_run_id"]
            rows=pending(store,run_id,"reviewer-a")
            self.assertEqual(len(rows),2)
            adjudicate(store,rows[0]["id"],"correct","",reviewer="reviewer-a")
            self.assertEqual(len(pending(store,run_id,"reviewer-a")),1)
            self.assertEqual(len(pending(store,run_id,"reviewer-b")),2)
            report=summary(store,run_id)
            self.assertEqual(report["confusion"]["tp"],1)
            self.assertEqual(report["human_review"]["correct"],1)
            store.close()

if __name__=="__main__": unittest.main()
