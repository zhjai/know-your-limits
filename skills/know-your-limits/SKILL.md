---
name: know-your-limits
description: 'Use when a CHEAP/small model (gpt-5-mini, Claude Haiku, GLM, DeepSeek, Kimi, etc.) is the primary worker on a long or multi-step task and should escalate the hard parts to a STRONG senior model instead of guessing. Fires on OBJECTIVE tripwires, never on "do you feel unsure" (a weak model won''t notice it is stuck): escalate at the START of a substantial/risky task to review the plan; when the SAME error survives 2 different fix attempts; before any IRREVERSIBLE or wide-blast action (schema/migration/delete/deploy/auth/new-dep); at a phase boundary; and before proposing done on a large/risky diff. Escalation goes through agent-arena (the mechanism); this skill is the POLICY of WHEN. Budget senior calls (they cost money) and send only a minimal evidence packet; the senior replies in a compact schema the worker can act on. If the senior also can''t resolve it, escalate to the HUMAN — do not loop. Not for short tasks where just using the senior outright is cheaper, or trivial reversible steps.'
license: MIT
metadata:
  version: "0.1.0"
  author: zhjai
  tags: "escalation, cost-tiering, cheap-model, senior-model, long-task, agent-arena, know-your-limits"
  related_skills: "agent-arena, deliberative-analysis, agent-completion-gate, agent-lessonbook"
---

# Know Your Limits

A cheap model running a long task should know when it's out of its depth and **phone a senior**,
instead of confidently guessing and burning hours of work on a wrong path. This skill is the
**policy of WHEN** to escalate; [`agent-arena`](https://github.com/zhjai/agent-arena) is the
**mechanism of HOW** (it makes the actual heterogeneous call to the strong model).

**The one rule that must not break:** escalation fires on **objective, observable tripwires** — not
on the worker asking itself "do I feel unsure?". An overconfident or cheap model is exactly the one
that *won't* notice it's stuck (the self-detection is self-referential). So the triggers below are
all things you can *count or observe*, and the most important ones are **mandatory regardless of how
confident the worker feels**.

## When to use
- A **cheap/small model is the primary worker** on a long, multi-step, or long-running task, run that
  way to save tokens/money, and you want the hard parts handled by a strong model — without paying
  for the strong model on every trivial step.
- **Not** when the task is short — if it's small *and* hard, just use the senior model directly; tiering
  only saves money when there's a lot of cheap grunt work around a few hard moments (see step 0).

## Procedure

### 0. Right-size first — is tiering even worth it?
Before adopting this policy, check it actually saves money:
- **Lots of cheap work + a few hard moments** → tier (use this skill).
- **Short task, or mostly-hard task** → skip tiering; run the senior model directly. Planning +
  periodic audits + final review all on a frontier model can cost *more* than just doing the whole
  thing on the frontier model once.
- **Feasibility precondition:** the worker's host must actually be able to call the senior (agent-arena
  needs shell + the senior's CLI + credentials). If it can't, this skill degrades to "flag the moment
  and ask the human" — say so, don't pretend an escalation happened.

### 1. Classify the task (sets the budget + which tripwires are mandatory)
- **L0** — single-step, reversible, one clear validation. No tiering.
- **L1** — ordinary multi-step, bounded, reversible. Tripwires reactive only.
- **L2** — long-running: many steps / multiple subsystems / no single obvious validation. **Plan review
  mandatory at start; final review mandatory before done.**
- **L3** — high-risk / hard-to-reverse: schema/API/config contract, auth/security, billing, concurrency,
  migration, deletion, production ops, a new dependency. **Plan review + final review mandatory; lean
  toward escalating sooner.**

### 2. Escalate on these tripwires (objective — not "I feel unsure")
**Mandatory (fire regardless of confidence):**
- **PLAN_REVIEW** — at the START of any L2/L3 task, before real work: senior reviews the plan.
- **IRREVERSIBLE_GUARD** — before any irreversible / wide-blast action (schema change, migration,
  delete, deploy, auth change, adding a dependency): senior reviews *before* you do it.
- **PRE_DONE_REVIEW** — before proposing done when the diff is large/risky or the key validation
  couldn't be run.

**Reactive (fire on a counted/observed event, not a feeling):**
- **STALL_RESCUE** — the **same error fingerprint** survives **2 materially different** fix attempts,
  or 3 non-improving reruns. (The hook counts this for you; see Reliability.)
- **OSCILLATION** — the same file/function is materially edited 3+ times with no validation improvement.
- **SCOPE_DRIFT** — you've touched 2+ modules you didn't plan to, before the first acceptance check passes.
- **GATE_BLOCK** — an [`agent-completion-gate`](https://github.com/zhjai/agent-completion-gate) check
  returns BLOCKED → escalate to fix the real cause, don't loosen the check.

Map each trigger to an agent-arena mode: plan → `implementation_plan_review`; stall → `bug_root_cause_arena`;
audit/scope → `quick_panel`; pre-done → `code_review_arena`.

### 3. Budget the senior calls (the whole point is saving money)
Reserve up front; never let early calls eat the slots you need for planning and final review:
- **L1:** ≤1 escalation.
- **L2:** ≤3, reserve 1 for the final review.
- **L3:** ≤4, reserve 1 for planning and 1 for the final review.
- **Dedupe:** same trigger + same error fingerprint + **no new evidence** → do NOT re-escalate. Get new
  evidence first, or escalate to the human.
- (Tune the numbers to your task — these are defaults, not measured constants.)

### 4. Send a minimal packet (keep the expensive call cheap)
The worker sends ONLY:
- the trigger code, the goal + constraints + acceptance criteria,
- the current step and what was already tried,
- **raw evidence only** (stack trace, diff hunks, file excerpts, failing checks) — not your own
  pet theory first (that anchors the senior; principle #1 of agent-arena),
- at most **3 concrete questions**.

Keep it ~800–2000 tokens. If more is needed, send a file/artifact index and let agent-arena request more.

### 5. Senior replies in a compact, actionable schema
```yaml
status: proceed | replan | blocked | need_more_evidence
diagnosis: <one sentence>
next_actions:   # ≤3
  - ...
checks:         # ≤3 deterministic checks to confirm it worked
  - ...
risks:          # ≤2
  - ...
```
The worker keeps only this structured outcome + cited artifacts, **never the full senior transcript**
(it won't fit the cheap model's context, and following the arena context-budget rule, redirect the raw
output to a file and read back only the digest).

### 6. If the senior can't resolve it → escalate to the HUMAN, don't loop
`status: blocked`, or the same escalation firing twice with no progress, means stop calling the senior
and surface it to the user with the evidence. Looping a senior on an under-specified or judgment-call
problem just burns money.

## Composition (this skill owns *when*, not *how* or *done*)
- **agent-arena** — the escalation *mechanism* (heterogeneous call, independent answers, dissent kept).
  This skill decides *when* to invoke it.
- **deliberative-analysis** — a *pre-escalation* local thinking aid: if the hard part is a bad framing /
  narrow option space, expand options first; escalate to a senior only if still stuck. Not the default
  response to every bug.
- **agent-completion-gate** — still the only thing that can say the work is *actually done*. A
  PRE_DONE_REVIEW here is **advisory**, never acceptance. A gate BLOCK is a tripwire.
- **agent-lessonbook** — record policy misses (escalated too late/early, a threshold that needs tuning,
  a recurring error fingerprint) so the human can adjust.

## Reliability — why a hook, not just this skill
A cheap worker **cannot reliably maintain the counters** the reactive tripwires need (it mis-counts
attempts, rationalizes "this attempt was different", loses track across compaction). So the reliable
setup is **this skill + the thin hook** in [`integrations/`](integrations/): the hook keeps a small
**escalation ledger** (elapsed, action count, error fingerprints, files touched, diff size, budget
left) from real lifecycle events and **nudges escalation when a tripwire trips** — it never makes the
senior call itself. Without the hook, the skill still works in a **degraded mode** (the worker
self-reports a one-line status after each attempt), but the mandatory START / IRREVERSIBLE / PRE_DONE
escalations are the backstop that does **not** depend on the worker noticing anything.

## Do not
- **Do not gate escalation on the worker's self-assessed confidence** — use the objective tripwires.
- **Do not escalate everything** — that defeats the cost saving; respect the budget and dedupe.
- **Do not let the senior's review count as "done"** — only the completion-gate clears completion.
- **Do not loop the senior** — same problem twice with no new evidence → go to the human.
- **Do not feed the senior your favored diagnosis first** — raw evidence first, so its review stays independent.
