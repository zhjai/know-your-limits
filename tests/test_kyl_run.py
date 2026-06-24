#!/usr/bin/env python3
"""Tests for kyl_run.py — the guarded launcher.

The central guarantee: worker_exec is NEVER called for an L2/L3 task the senior
did not approve. This is the enforcement a non-blocking hook cannot provide.

Run: python3 tests/test_kyl_run.py   (exit 0 = all pass)
"""
import os, sys, json, tempfile, pathlib, unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import kyl_run  # noqa: E402


def senior(status):
    return lambda plan: {"status": status}


class Spy:
    """A worker that records whether it was allowed to run (i.e. could have written)."""
    def __init__(self):
        self.ran = False
    def __call__(self, task, plan):
        self.ran = True
        return "did work"


class Classify(unittest.TestCase):
    def test_irreversible_is_l3(self):
        for t in ["run the db migration", "deploy to production", "rotate auth secret", "迁移数据库"]:
            self.assertEqual(kyl_run.classify(t), "L3", t)

    def test_multistep_is_l2(self):
        for t in ["build the SFT+GRPO+eval pipeline", "refactor the training loop", "全链路评测"]:
            self.assertEqual(kyl_run.classify(t), "L2", t)

    def test_bounded_is_l1(self):
        for t in ["fix typo in README", "rename a single function", "改个注释"]:
            self.assertEqual(kyl_run.classify(t), "L1", t)

    def test_unknown_defaults_to_l2(self):
        # fail safe toward review — an ambiguous task is treated as needing a plan gate
        self.assertEqual(kyl_run.classify("do the thing with the stuff"), "L2")


class Gate(unittest.TestCase):
    def setUp(self):
        self.ctl = tempfile.mkdtemp()

    def _run(self, task, sr, **kw):
        spy = Spy()
        res = kyl_run.run(task, senior_review=sr, worker_exec=spy,
                          control_dir=self.ctl, goal_id="g", **kw)
        return res, spy

    def test_blocked_plan_never_executes(self):
        # THE core guarantee: senior blocks -> the write-capable worker never runs
        res, spy = self._run("build the SFT+GRPO pipeline", senior("blocked"))
        self.assertFalse(spy.ran)
        self.assertFalse(res["executed"])
        self.assertEqual(res["status"], "blocked")

    def test_revise_plan_never_executes(self):
        res, spy = self._run("refactor the training loop", senior("revise"))
        self.assertFalse(spy.ran)
        self.assertEqual(res["status"], "revise")

    def test_approved_plan_executes(self):
        res, spy = self._run("build the SFT+GRPO pipeline", senior("approve"))
        self.assertTrue(spy.ran)
        self.assertEqual(res["status"], "executed")
        self.assertTrue(res["gated"])

    def test_l1_executes_without_senior_call(self):
        called = {"n": 0}
        def sr(plan):
            called["n"] += 1
            return {"status": "approve"}
        res, spy = self._run("fix typo in README", sr)
        self.assertTrue(spy.ran)
        self.assertFalse(res["gated"])
        self.assertEqual(called["n"], 0)   # no senior call for L1

    def test_no_senior_verdict_blocks(self):
        # a senior call that returns nothing must fail CLOSED (not execute)
        res, spy = self._run("build the pipeline", lambda plan: None)
        self.assertFalse(spy.ran)
        self.assertFalse(res["executed"])

    def test_env_task_class_overrides_classifier(self):
        # operator declares L2 on a task the classifier would call L1
        os.environ["KYL_TASK_CLASS"] = "L2"
        try:
            res, spy = self._run("fix typo", senior("blocked"))
            self.assertFalse(spy.ran)           # gated as L2, blocked -> no run
            self.assertEqual(res["class"], "L2")
        finally:
            del os.environ["KYL_TASK_CLASS"]

    def test_authority_record_written_under_control(self):
        self._run("build the pipeline", senior("approve"))
        rec = json.loads((pathlib.Path(self.ctl) / "g.json").read_text())
        self.assertTrue(rec["approved"])
        self.assertTrue(rec["plan_reviewed"])
        self.assertEqual(rec["task_class"], "L2")


class CompletionGate(unittest.TestCase):
    def setUp(self):
        self.ctl = tempfile.mkdtemp()

    def _req(self, cls="L2", diff="abc"):
        return {"task_class": cls, "diff_hash": diff, "tests_run": ["pytest"]}

    def test_l2_done_requires_senior_approval(self):
        # senior blocks → not done, no token, verify_done False
        r = kyl_run.gate_completion(self._req(), senior_review=senior("blocked"),
                                    control_dir=self.ctl, goal_id="g")
        self.assertEqual(r["status"], "blocked")
        self.assertNotIn("token", r)
        self.assertFalse(kyl_run.verify_done("abc", control_dir=self.ctl, goal_id="g"))

    def test_l2_done_issues_token_bound_to_diff(self):
        r = kyl_run.gate_completion(self._req(diff="abc"), senior_review=senior("approve"),
                                    control_dir=self.ctl, goal_id="g")
        self.assertEqual(r["status"], "done")
        self.assertTrue(r["token"])
        self.assertTrue(kyl_run.verify_done("abc", control_dir=self.ctl, goal_id="g"))
        # stale diff (worker edited after approval) → token no longer valid
        self.assertFalse(kyl_run.verify_done("DIFFERENT", control_dir=self.ctl, goal_id="g"))

    def test_l1_done_needs_no_senior(self):
        called = {"n": 0}
        def sr(req):
            called["n"] += 1; return {"status": "approve"}
        r = kyl_run.gate_completion(self._req(cls="L1"), senior_review=sr,
                                    control_dir=self.ctl, goal_id="g")
        self.assertEqual(r["status"], "done")
        self.assertFalse(r["gated"])
        self.assertEqual(called["n"], 0)
        self.assertTrue(kyl_run.verify_done("anything", control_dir=self.ctl, goal_id="g"))

    def test_verify_done_false_when_no_record(self):
        self.assertFalse(kyl_run.verify_done("abc", control_dir=self.ctl, goal_id="missing"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
