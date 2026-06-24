#!/usr/bin/env python3
"""kyl-run — minimal GUARDED LAUNCHER for know-your-limits.

Why this exists (the result of an agent-arena debate): the hook can only *nudge*
(emit context); it cannot block a tool call, force the senior call, or stop a weak
model from editing. So a MANDATORY tripwire like PLAN_REVIEW cannot be reliably
enforced from inside the worker — a model weak enough to need tiering is exactly the
one that will ignore the nudge.

kyl-run moves the gate OUT of the worker. It:
  1. classifies the task (deterministic; UNKNOWN defaults to L2),
  2. for L2/L3 runs a senior PLAN_REVIEW as a *precondition*,
  3. launches the write-capable worker execution phase ONLY if the senior approves.

Enforcement = phase ordering owned by the launcher (gate before execute), not mid-run
filesystem interception. Authority (the approval record) is written under control/ —
the worker never produces it. The invariant this guarantees, and tests:

    worker_exec is NEVER called for an L2/L3 task that the senior did not approve.

The senior reviewer and the worker executor are injected as callables so the gate
logic is unit-testable without real CLIs; `main()` wires them to real commands.
"""
import json, os, re, sys, pathlib, hashlib


def _fingerprint(text):
    return hashlib.sha1(str(text).encode("utf-8", "replace")).hexdigest()[:12]

# --- 1. Deterministic classification (UNKNOWN -> L2) -----------------------------
# Rationale (from the arena): a false positive costs one senior planning call; a false
# negative defeats the whole policy. So default unknown to L2, and only DOWNGRADE to L1
# on clearly-bounded signals. L3 on anything irreversible / wide-blast.
_L3 = re.compile(r"\b(migrat\w*|schema|drop\s+table|delete|deploy\w*|production|prod\b|auth\w*|security|billing|credential|secret|lockfile|dependenc\w*|infra\w*|ci/cd|rollback|irreversible)\b|迁移|删除|部署|不可逆|鉴权|密钥", re.I)
_L2 = re.compile(r"\b(pipeline|train\w*|sft|grpo|rl\b|eval\w*|refactor\w*|integrat\w*|architecture|multi[- ]?(step|subsystem)|unattended|long[- ]?running|end[- ]?to[- ]?end)\b|全链路|多子系统|多步骤|长时间|流水线|训练|评测", re.I)
_L1 = re.compile(r"\b(rename|fix\s+typo|typo|comment|reformat|lint|one[- ]?line|single (file|function|line)|bump\s+version)\b|改个|拼写|注释|单行|单个文件", re.I)


def classify(task: str) -> str:
    t = task or ""
    if _L3.search(t):
        return "L3"
    if _L2.search(t):
        return "L2"
    if _L1.search(t):
        return "L1"
    return "L2"  # UNKNOWN -> L2 (fail safe toward review)


# --- 2. Authority (written by the launcher, under control/) ----------------------
def _write_authority(control_dir, goal_id, record):
    try:
        p = pathlib.Path(control_dir) / f"{goal_id}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    except Exception:
        pass  # never let bookkeeping crash the run


def _obtain_plan(task, plan_path):
    if plan_path and pathlib.Path(plan_path).is_file():
        return pathlib.Path(plan_path).read_text()
    return task  # minimal: review the task statement itself if no plan.md given


# --- 3. The gate ------------------------------------------------------------------
def run(task, *, senior_review, worker_exec, task_class=None, plan_path=None,
        control_dir="control/kyl", goal_id="goal"):
    """Classify → (L2/L3) senior-gate → execute only on approval.

    senior_review(plan_text) -> {"status": "approve"|"revise"|"blocked", ...}
    worker_exec(task, plan)   -> result   (the WRITE-CAPABLE phase)

    Returns a result dict. GUARANTEE: worker_exec is not called for an L2/L3 task
    unless senior_review returned status == "approve".
    """
    cls = (task_class or os.environ.get("KYL_TASK_CLASS") or classify(task)).upper()
    record = {"goal_id": goal_id, "task_class": cls, "plan_reviewed": False, "approved": False}

    if cls in ("L0", "L1"):
        record["approved"] = True  # no plan gate for small/reversible work
        _write_authority(control_dir, goal_id, record)
        return {"status": "executed", "class": cls, "gated": False,
                "result": worker_exec(task, None)}

    # L2/L3 — PLAN_REVIEW is a precondition to any write-capable execution
    plan = _obtain_plan(task, plan_path)
    verdict = senior_review(plan) or {"status": "blocked", "diagnosis": "no senior verdict"}
    record["plan_reviewed"] = True
    record["verdict"] = verdict

    if str(verdict.get("status", "")).lower() == "approve":
        record["approved"] = True
        _write_authority(control_dir, goal_id, record)
        return {"status": "executed", "class": cls, "gated": True, "verdict": verdict,
                "result": worker_exec(task, plan)}

    # not approved → DO NOT launch the worker. Surface to the human.
    _write_authority(control_dir, goal_id, record)
    return {"status": str(verdict.get("status", "blocked")).lower(), "class": cls,
            "gated": True, "executed": False, "verdict": verdict}


# --- 3b. Completion gate — PRE_DONE_REVIEW as a gated action ----------------------
# "Done" must be a request the senior approves, not free prose the worker asserts. The token is bound
# to the diff_hash so it can't be reused after the worker keeps editing.
def gate_completion(req, *, senior_review, control_dir="control/kyl", goal_id="goal"):
    """req = {task_class, diff_hash, tests_run, ...}. Returns {status: done|blocked, token?, ...}.
    GUARANTEE: an L2/L3 completion is never 'done' unless senior_review approved THIS diff_hash."""
    cls = str(req.get("task_class", "")).upper()
    diff = str(req.get("diff_hash", ""))
    rec = {"goal_id": goal_id, "type": "COMPLETION_REQUEST", "task_class": cls,
           "diff_hash": diff, "tests_run": req.get("tests_run", [])}
    if cls in ("L0", "L1"):
        rec["status"] = "done"
        _write_authority(control_dir, goal_id + ".done", rec)
        return {"status": "done", "gated": False}
    verdict = senior_review(req) or {"status": "blocked", "diagnosis": "no senior verdict"}
    rec["verdict"] = verdict
    if str(verdict.get("status", "")).lower() == "approve" and diff:
        token = "complete-" + _fingerprint(goal_id + diff)
        rec.update(status="done", token=token, valid_for_diff_hash=diff)
        _write_authority(control_dir, goal_id + ".done", rec)
        return {"status": "done", "gated": True, "token": token, "valid_for_diff_hash": diff}
    rec["status"] = "blocked"
    _write_authority(control_dir, goal_id + ".done", rec)
    return {"status": "blocked", "gated": True, "verdict": verdict}


def verify_done(diff_hash, *, control_dir="control/kyl", goal_id="goal"):
    """True only if a valid completion exists for THIS diff_hash: L0/L1 (no gate) or an approved token
    bound to diff_hash. A stale diff (worker edited after approval) or a missing token → False."""
    import pathlib
    try:
        rec = json.loads((pathlib.Path(control_dir) / f"{goal_id}.done.json").read_text())
    except Exception:
        return False
    if rec.get("status") != "done":
        return False
    if str(rec.get("task_class", "")).upper() in ("L0", "L1"):
        return True
    return bool(rec.get("token")) and rec.get("valid_for_diff_hash") == str(diff_hash)


# --- 4. CLI wiring (real senior + worker commands) -------------------------------
def _real_senior_review(plan_text):
    """Send the plan to a senior via `claude -p` (implementation_plan_review).
    Replace/extend to route through agent-arena for heterogeneity."""
    import subprocess
    prompt = ("You are a senior reviewer. Review this implementation plan (agent-arena "
              "implementation_plan_review). Reply with a single line `STATUS: approve|revise|blocked` "
              "followed by <=3 concrete next_actions and <=2 risks.\n\nPLAN:\n" + plan_text)
    try:
        out = subprocess.run(["claude", "-p", prompt, "--allowedTools", "", "--max-turns", "2"],
                             capture_output=True, text=True, timeout=600).stdout
    except Exception as e:
        return {"status": "blocked", "diagnosis": f"senior call failed: {e}"}
    m = re.search(r"STATUS:\s*(approve|revise|blocked)", out, re.I)
    return {"status": (m.group(1).lower() if m else "revise"), "raw": out[-2000:]}


# Empirically, weak workers obey a rule stated as a top-level/system constraint but ignore the same
# rule buried in context. So the execution phase leads with an unmissable rule block, not a buried note.
_WORKER_RULE = (
    "[SYSTEM RULE — non-negotiable] You are a cheap worker. A senior has APPROVED the plan below; "
    "execute it. Before any IRREVERSIBLE action (schema/migration/delete/deploy/auth/new-dep) STOP and "
    "request a senior review. Do NOT declare the task done without a PRE_DONE_REVIEW. Stay within the "
    "approved plan; if you must deviate materially, STOP and re-escalate.\n")


def _real_worker_exec(task, plan):
    """Hand the approved task+plan to the cheap worker command from KYL_WORKER_CMD.

    Leads with _WORKER_RULE so the constraint arrives as a top-level instruction (which weak models
    obey) rather than a buried note (which they ignore). If KYL_WORKER_SYSTEM_CMD-style routing is
    available in your wrapper, route _WORKER_RULE into the actual system message for best effect."""
    import subprocess
    cmd = os.environ.get("KYL_WORKER_CMD")
    if not cmd:
        return {"note": "set KYL_WORKER_CMD to the cheap-worker command to actually execute",
                "approved_task": task}
    prompt = _WORKER_RULE + "\n# Task:\n" + task + (f"\n\n# Approved plan (senior-reviewed):\n{plan}" if plan else "")
    return subprocess.run(cmd, shell=True, input=prompt, text=True).returncode


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print('usage:\n  kyl_run.py "<task>" [--class L2] [--plan plan.md] [--goal <id>]   # plan gate + execute\n'
              '  kyl_run.py complete --class L2 --diff-hash <h> [--tests "..."] [--goal <id>]  # done gate',
              file=sys.stderr)
        return 2

    # `complete` subcommand: PRE_DONE_REVIEW gate — "done" must be senior-approved for L2/L3
    if argv[0] == "complete":
        opts = {argv[i]: argv[i + 1] for i in range(1, len(argv) - 1, 2)}
        req = {"task_class": opts.get("--class", os.environ.get("KYL_TASK_CLASS", "L2")),
               "diff_hash": opts.get("--diff-hash", ""),
               "tests_run": [t for t in opts.get("--tests", "").split(",") if t]}
        res = gate_completion(req, senior_review=_real_senior_review, goal_id=opts.get("--goal", "goal"))
        print(json.dumps(res, ensure_ascii=False, indent=2))
        if res.get("status") != "done":
            print("\n⛔ NOT done — PRE_DONE_REVIEW did not pass. Do not declare the task complete.", file=sys.stderr)
            return 1
        return 0

    task = argv[0]
    opts = {argv[i]: argv[i + 1] for i in range(1, len(argv) - 1, 2)}
    res = run(task, senior_review=_real_senior_review, worker_exec=_real_worker_exec,
              task_class=opts.get("--class"), plan_path=opts.get("--plan"),
              goal_id=opts.get("--goal", "goal"))
    print(json.dumps({k: v for k, v in res.items() if k != "result"}, ensure_ascii=False, indent=2))
    if res.get("status") not in ("executed",):
        print(f"\n⛔ NOT executed (class {res['class']}, senior status "
              f"{res.get('verdict', {}).get('status')}). Plan review did not pass — surface to the human.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
