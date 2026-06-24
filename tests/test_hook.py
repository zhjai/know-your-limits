#!/usr/bin/env python3
"""Self-tests for kyl_hook.py — the know-your-limits escalation ledger/tripwire hook.

Run: python3 tests/test_hook.py    (exit 0 = all pass)
"""
import json, os, subprocess, sys, tempfile, pathlib, unittest

HOOK = str(pathlib.Path(__file__).resolve().parents[1] / "integrations" / "hooks" / "kyl_hook.py")


def run(event, ledger, env_extra=None):
    env = dict(os.environ, KYL_LEDGER=ledger)
    if env_extra:
        env.update(env_extra)
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(event),
                       capture_output=True, text=True, env=env)
    ctx = ""
    if p.stdout.strip():
        try:
            ctx = json.loads(p.stdout).get("hookSpecificOutput", {}).get("additionalContext", "")
        except Exception:
            ctx = ""
    return p.returncode, ctx


class KylHook(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.ledger = os.path.join(self.dir, "ledger.json")

    def test_bad_input_exits_zero(self):
        p = subprocess.run([sys.executable, HOOK], input="not json{",
                           capture_output=True, text=True, env=dict(os.environ, KYL_LEDGER=self.ledger))
        self.assertEqual(p.returncode, 0)

    def test_empty_input_exits_zero(self):
        p = subprocess.run([sys.executable, HOOK], input="",
                           capture_output=True, text=True, env=dict(os.environ, KYL_LEDGER=self.ledger))
        self.assertEqual(p.returncode, 0)

    def test_stall_fires_on_second_identical_error(self):
        fail = {"hook_event_name": "PostToolUse", "tool_exit_code": 1,
                "tool_response": "Traceback: ValueError at line 42 in train.py"}
        _, c1 = run(fail, self.ledger)
        self.assertNotIn("STALL_RESCUE", c1)        # first failure: no escalation
        _, c2 = run(fail, self.ledger)
        self.assertIn("STALL_RESCUE", c2)           # second identical: escalate

    def test_stall_dedupes(self):
        fail = {"hook_event_name": "PostToolUse", "tool_exit_code": 1, "tool_response": "Error: boom"}
        run(fail, self.ledger); run(fail, self.ledger)
        _, c3 = run(fail, self.ledger)
        self.assertNotIn("STALL_RESCUE", c3)        # already fired once; don't spam

    def test_passing_check_resets_stall(self):
        fail = {"hook_event_name": "PostToolUse", "tool_exit_code": 1, "tool_response": "Error: boom"}
        run(fail, self.ledger)
        run({"hook_event_name": "PostToolUse", "tool_exit_code": 0, "tool_response": "5 passed"}, self.ledger)
        _, c = run(fail, self.ledger)               # only 1 failure since the pass
        self.assertNotIn("STALL_RESCUE", c)

    def test_oscillation_fires_on_third_edit(self):
        ed = {"hook_event_name": "PostToolUse", "tool_exit_code": 0,
              "tool_input": {"file_path": "src/model.py"}, "tool_response": "edited"}
        _, c1 = run(ed, self.ledger); _, c2 = run(ed, self.ledger); _, c3 = run(ed, self.ledger)
        self.assertNotIn("OSCILLATION", c1)
        self.assertNotIn("OSCILLATION", c2)
        self.assertIn("OSCILLATION", c3)

    def test_scope_drift_fires_past_threshold(self):
        for i, m in enumerate(["a", "b", "c"]):  # 3 modules > default K=2
            ed = {"hook_event_name": "PostToolUse", "tool_exit_code": 0,
                  "tool_input": {"file_path": f"{m}/f{i}.py"}, "tool_response": "edited"}
            _, c = run(ed, self.ledger)
        self.assertIn("SCOPE_DRIFT", c)

    def test_checkpoint_debt(self):
        ed = {"hook_event_name": "PostToolUse", "tool_exit_code": 0, "tool_response": "working"}
        c = ""
        for _ in range(40):
            _, c = run(ed, self.ledger, {"KYL_ACTIONS_A": "40"})
        self.assertIn("CHECKPOINT_DEBT", c)

    def test_precompact_reminds_about_ledger(self):
        _, c = run({"hook_event_name": "PreCompact"}, self.ledger)
        self.assertIn("ledger", c.lower())

    def test_ledger_never_under_control_dir(self):
        # even if asked to write under control/, it must redirect away from authority
        env = {"KYL_LEDGER": os.path.join(self.dir, "control", "ledger.json")}
        p = subprocess.run([sys.executable, HOOK],
                           input=json.dumps({"hook_event_name": "PostToolUse", "tool_response": "x"}),
                           capture_output=True, text=True, env=dict(os.environ, **env))
        self.assertEqual(p.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "control", "ledger.json")))

    def test_success_output_does_not_trip_stall(self):
        ok = {"hook_event_name": "PostToolUse", "tool_exit_code": 0,
              "tool_response": "0 errors, all tests pass"}
        _, c1 = run(ok, self.ledger); _, c2 = run(ok, self.ledger)
        self.assertNotIn("STALL_RESCUE", c2)

    def test_segfault_and_killed_count_as_failures(self):
        # crashes with no numeric exit code must still trip STALL (regression: these were missed)
        for resp in ["Segmentation fault (core dumped)", "Killed"]:
            ledger = os.path.join(tempfile.mkdtemp(), "l.json")
            ev = {"hook_event_name": "PostToolUse", "tool_response": resp}
            run(ev, ledger)
            _, c2 = run(ev, ledger)
            self.assertIn("STALL_RESCUE", c2, f"{resp!r} should count as a failure")

    def test_greenfield_does_not_falsely_reset(self):
        # 'greenfield'/'looks ok' must NOT count as a passing check (regression: substring 'green'/'ok')
        fail = {"hook_event_name": "PostToolUse", "tool_exit_code": 1, "tool_response": "Error: boom"}
        run(fail, self.ledger)
        # benign output mentioning 'greenfield' — must not reset the stall counter
        run({"hook_event_name": "PostToolUse", "tool_exit_code": 0,
             "tool_response": "refactoring the greenfield module, looks ok so far"}, self.ledger)
        _, c = run(fail, self.ledger)   # 2nd real failure -> should now fire
        self.assertIn("STALL_RESCUE", c)

    def test_mixed_output_does_not_falsely_reset(self):
        # an early pass-phrase + a later failure in the SAME call must NOT reset the stall counter
        fail = {"hook_event_name": "PostToolUse", "tool_exit_code": 1, "tool_response": "Error: boom"}
        run(fail, self.ledger)
        # mixed: contains '12 passed' but also fails (exit 1)
        run({"hook_event_name": "PostToolUse", "tool_exit_code": 1,
             "tool_response": "12 passed\n...\nTraceback: boom"}, self.ledger)
        _, c = run(fail, self.ledger)
        self.assertIn("STALL_RESCUE", c)   # never reset -> 3 fails -> fired

    def test_fail_word_forms(self):
        # FAIL / FAILURE / non-zero status text must count as failures (regression: \bFAILED?\b)
        for resp in ["FAIL: test_x", "build FAILURE", "returned non-zero status"]:
            ledger = os.path.join(tempfile.mkdtemp(), "l.json")
            ev = {"hook_event_name": "PostToolUse", "tool_response": resp}  # no exit code -> text path
            run(ev, ledger)
            _, c2 = run(ev, ledger)
            self.assertIn("STALL_RESCUE", c2, f"{resp!r} should count as a failure")

    def test_clean_pass_still_resets(self):
        fail = {"hook_event_name": "PostToolUse", "tool_exit_code": 1, "tool_response": "Error: boom"}
        run(fail, self.ledger)
        run({"hook_event_name": "PostToolUse", "tool_exit_code": 0, "tool_response": "5 passed"}, self.ledger)
        _, c = run(fail, self.ledger)   # reset happened -> only 1 fail since -> no fire
        self.assertNotIn("STALL_RESCUE", c)
        # many distinct errors must not corrupt the ledger (regression: JSON string truncation)
        for i in range(300):
            run({"hook_event_name": "PostToolUse", "tool_exit_code": 1,
                 "tool_response": f"Error: unique failure number {i} xyz"}, self.ledger)
        # ledger must still parse
        with open(self.ledger) as fh:
            json.load(fh)   # raises if corrupt

    def test_fired_clears_on_pass_so_later_trigger_can_refire(self):
        # after a green, the same file going wrong again must be able to re-trigger oscillation
        ed = {"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_exit_code": 0,
              "tool_input": {"file_path": "src/m.py"}, "tool_response": "edited"}
        run(ed, self.ledger); run(ed, self.ledger)
        _, c = run(ed, self.ledger)
        self.assertIn("OSCILLATION", c)                       # fired once
        run({"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_exit_code": 0,
             "tool_response": "5 passed"}, self.ledger)        # green -> new epoch, fired cleared
        run(ed, self.ledger); run(ed, self.ledger)
        _, c2 = run(ed, self.ledger)
        self.assertIn("OSCILLATION", c2)                      # can fire again, not suppressed forever

    def test_reads_do_not_count_as_oscillation(self):
        # reading the same file repeatedly is not thrashing
        rd = {"hook_event_name": "PostToolUse", "tool_name": "Read", "tool_exit_code": 0,
              "tool_input": {"file_path": "src/m.py"}, "tool_response": "contents"}
        c = ""
        for _ in range(5):
            _, c = run(rd, self.ledger)
        self.assertNotIn("OSCILLATION", c)

    def test_bad_env_does_not_crash(self):
        # a malformed threshold env must not break the host (regression: int() at import)
        env = dict(os.environ, KYL_LEDGER=self.ledger, KYL_STALL_N="not-a-number")
        p = subprocess.run([sys.executable, HOOK],
                           input=json.dumps({"hook_event_name": "PostToolUse", "tool_response": "x"}),
                           capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0)

    def test_ledger_dotdot_path_rejected(self):
        # a '..' escape in KYL_LEDGER must fall back to default, not write outside the tree
        env = dict(os.environ, KYL_LEDGER="../../escape/ledger.json")
        p = subprocess.run([sys.executable, HOOK], cwd=self.dir,
                           input=json.dumps({"hook_event_name": "PostToolUse", "tool_response": "x"}),
                           capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "..", "..", "escape", "ledger.json")))

    def test_cheap_worker_periodic_reminder(self):
        # Every 20 actions, cheap workers get a light reminder
        ledger = os.path.join(tempfile.mkdtemp(), "l.json")
        env = {"KYL_LEDGER": ledger, "KYL_WORKER_TIER": "cheap"}
        ok = {"hook_event_name": "PostToolUse", "tool_exit_code": 0, "tool_response": "working"}

        # 19 actions: no reminder yet
        for _ in range(19):
            run(ok, ledger, env)

        # Read ledger to check action count
        with open(ledger) as f:
            L = json.load(f)
        self.assertEqual(L["actions"], 19)

        # 20th action: reminder fires
        _, c20 = run(ok, ledger, env)
        self.assertIn("know-your-limits reminder", c20)

        # 21-39: no reminder
        for _ in range(19):
            _, c = run(ok, ledger, env)
            if _ < 18:  # actions 21-38
                self.assertNotIn("know-your-limits reminder", c)

        # 40th: reminder again
        _, c40 = run(ok, ledger, env)
        self.assertIn("know-your-limits reminder", c40)

    def test_mandatory_plan_review_for_cheap_l2(self):
        # PreToolUse: cheap worker on L2 task editing without plan review → forced nudge
        ledger = os.path.join(tempfile.mkdtemp(), "l.json")
        # Seed ledger with L2 task, no plan review
        with open(ledger, "w") as f:
            json.dump({"task_class": "L2", "plan_reviewed": False, "actions": 0}, f)

        env = {"KYL_LEDGER": ledger, "KYL_WORKER_TIER": "cheap"}
        pre_edit = {"hook_event_name": "PreToolUse", "tool_name": "Edit"}

        _, ctx = run(pre_edit, ledger, env)
        self.assertIn("MANDATORY PLAN_REVIEW", ctx)
        self.assertIn("cheap worker on an L2/L3 task", ctx)

    def test_mandatory_plan_review_not_for_expensive(self):
        # Expensive worker or no tier → no forced plan review
        ledger = os.path.join(tempfile.mkdtemp(), "l.json")
        with open(ledger, "w") as f:
            json.dump({"task_class": "L2", "plan_reviewed": False, "actions": 0}, f)

        env = {"KYL_LEDGER": ledger}  # no WORKER_TIER
        pre_edit = {"hook_event_name": "PreToolUse", "tool_name": "Edit"}

        _, ctx = run(pre_edit, ledger, env)
        self.assertNotIn("MANDATORY PLAN_REVIEW", ctx)

    def test_precompact_reminds_cheap_worker(self):
        # PreCompact should remind cheap worker about tier
        ledger = os.path.join(tempfile.mkdtemp(), "l.json")
        env = {"KYL_LEDGER": ledger, "KYL_WORKER_TIER": "cheap"}

        _, ctx = run({"hook_event_name": "PreCompact"}, ledger, env)
        self.assertIn("You are a cheap worker", ctx)
        self.assertIn("KYL_WORKER_TIER=cheap", ctx)

    def test_codex_apply_patch_path_extraction(self):
        # Codex apply_patch puts path in command field
        ledger = os.path.join(tempfile.mkdtemp(), "l.json")
        patch1 = {"hook_event_name": "PostToolUse", "tool_name": "apply_patch",
                  "tool_input": {"command": "apply_patch src/model.py <<EOF\n..."}, "tool_exit_code": 0,
                  "tool_response": "edited"}

        # First edit
        _, c1 = run(patch1, ledger)
        self.assertNotIn("OSCILLATION", c1)

        # Second edit
        _, c2 = run(patch1, ledger)
        self.assertNotIn("OSCILLATION", c2)

        # Third edit - should trigger oscillation
        _, c3 = run(patch1, ledger)
        self.assertIn("OSCILLATION", c3)
        self.assertIn("src/model.py", c3)

    def test_plan_review_fires_for_unclassified_cheap_worker(self):
        # Regression: a weak model that never classified the task left task_class="" so the
        # L2/L3 nudge could never fire. An unclassified cheap worker about to edit must still be
        # nudged to classify + plan-review (once, deduped).
        ledger = os.path.join(tempfile.mkdtemp(), "l.json")
        env = {"KYL_WORKER_TIER": "cheap"}
        pre_edit = {"hook_event_name": "PreToolUse", "tool_name": "Edit"}

        _, c1 = run(pre_edit, ledger, env)
        self.assertIn("PLAN_REVIEW CHECK", c1)            # nudged despite no task_class
        _, c2 = run(pre_edit, ledger, env)
        self.assertNotIn("PLAN_REVIEW CHECK", c2)         # deduped — fires once, no spam

    def test_task_class_env_declares_l2_without_model(self):
        # KYL_TASK_CLASS=L2 must make the strong PLAN_REVIEW fire even with no ledger task_class
        ledger = os.path.join(tempfile.mkdtemp(), "l.json")
        env = {"KYL_WORKER_TIER": "cheap", "KYL_TASK_CLASS": "L2"}
        _, c = run({"hook_event_name": "PreToolUse", "tool_name": "Edit"}, ledger, env)
        self.assertIn("MANDATORY PLAN_REVIEW", c)

    def test_task_class_env_l1_no_plan_review(self):
        # An explicitly-small task (L1) declared via env must NOT trigger plan review
        ledger = os.path.join(tempfile.mkdtemp(), "l.json")
        env = {"KYL_WORKER_TIER": "cheap", "KYL_TASK_CLASS": "L1"}
        _, c = run({"hook_event_name": "PreToolUse", "tool_name": "Edit"}, ledger, env)
        self.assertNotIn("PLAN_REVIEW", c)

    def test_irreversible_guard_fires_on_dangerous_command(self):
        # The guard must fire on the COMMAND (memory-independent), before it runs
        ledger = os.path.join(tempfile.mkdtemp(), "l.json")
        env = {"KYL_WORKER_TIER": "cheap"}
        for cmd in ["rm -rf build/", "git push origin main --force", "alembic upgrade head",
                    "kubectl apply -f deploy.yaml", "pip install somenewdep", "DROP TABLE users"]:
            led = os.path.join(tempfile.mkdtemp(), "l.json")
            ev = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": cmd}}
            _, c = run(ev, led, env)
            self.assertIn("IRREVERSIBLE_GUARD", c, f"{cmd!r} should trip the guard")

    def test_irreversible_guard_dedupes(self):
        ledger = os.path.join(tempfile.mkdtemp(), "l.json")
        env = {"KYL_WORKER_TIER": "cheap"}
        ev = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git push --force"}}
        _, c1 = run(ev, ledger, env)
        self.assertIn("IRREVERSIBLE_GUARD", c1)
        _, c2 = run(ev, ledger, env)
        self.assertNotIn("IRREVERSIBLE_GUARD", c2)            # same command → don't spam

    def test_safe_command_no_guard(self):
        ledger = os.path.join(tempfile.mkdtemp(), "l.json")
        env = {"KYL_WORKER_TIER": "cheap"}
        for cmd in ["ls -la", "python -m pytest", "git status", "cat README.md"]:
            led = os.path.join(tempfile.mkdtemp(), "l.json")
            ev = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": cmd}}
            _, c = run(ev, led, env)
            self.assertNotIn("IRREVERSIBLE_GUARD", c, f"{cmd!r} is safe, should NOT trip")


if __name__ == "__main__":
    unittest.main(verbosity=2)
