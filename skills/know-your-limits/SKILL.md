---
name: know-your-limits
description: 'Use when a CHEAP/small model (gpt5.4-mini, Claude Haiku, GLM-4.7-Flash, etc.) is the primary worker on a long or multi-step task and should escalate the hard parts to a STRONG senior model instead of guessing; invoke it as "kyl". Fires on OBJECTIVE tripwires, never on "do you feel unsure" (a weak model won''t notice it is stuck): escalate at the START of a substantial/risky task to review the plan; when the SAME error survives 2 different fix attempts; before any IRREVERSIBLE or wide-blast action (schema/migration/delete/deploy/auth/new-dep); at a phase boundary; and before proposing done on a large/risky diff. Escalation goes through agent-arena (the mechanism); this skill is the POLICY of WHEN. Budget senior calls (they cost money) and send only a minimal evidence packet; the senior replies in a compact schema the worker can act on. If the senior also can''t resolve it, escalate to the HUMAN — do not loop. Not for short tasks where just using the senior outright is cheaper, or trivial reversible steps.'
license: MIT
metadata:
  version: "0.1.1"
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

**Shorthand:** the user may invoke this skill as **`kyl`** — "use kyl", "apply know-your-limits", and
"kyl this task" all mean the same thing.

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

### 0.5. Soft initialization (on first use in a project)
On **first use in a project**, check if `state/know-your-limits/config.yaml` exists. If not, ask the user these questions directly — no script, no form:

1. **Worker tier** *(skip if `KYL_WORKER_TIER` already set in the environment)*
   "Are you running a cheap/small model (Haiku, gpt5.4-mini, GLM-4.7-Flash, deepseek-v4-flash, etc.) as the primary worker on long tasks? You should also export `KYL_WORKER_TIER=cheap` in your shell — that's what the hook uses to send you reminders."

2. **Senior model** *(always ask)*
   "Which model should I escalate hard decisions to? (default: cross-vendor — Codex workers → Claude, Claude workers → Codex)"

3. **Feishu notifications** *(only if `experiment-grill-feishu` skill is detected as installed)*
   "experiment-grill-feishu is installed. Do you want task completion and escalation notifications sent to Feishu?"

Then create `state/know-your-limits/config.yaml` from their answers. If the user skips or is unsure, use auto-detect defaults. The file is **project-level** and version-controlled; the user can edit it at any time.

After writing the config, **auto-check hook wiring**: if the hook is not found in the host's hook config, offer to add it with a brief note — "The hook tracks stall/oscillation/scope counters outside the model; without it, reactive tripwires run in degraded mode." This is a conditional offer, not a question.

Budget limits default to `L1:1 / L2:3 / L3:4` — mention in the post-init summary that these are editable in `config.yaml` once the user has seen a few escalations.

> For a bulk dependency check (agent-arena, hook wired, env vars), the optional utility `scripts/kyl_doctor.py` is available, but it is not part of the initialization flow.

### 1. Classify the task — ONCE per top-level goal (sets the budget + which tripwires are mandatory)
**Classify the top-level goal the user accepted, not each subtask.** One classification, one budget,
one plan review, one final review **per goal**. Subtasks *inherit* the goal's class and share its
ledger — they do **not** create new phases, restart mandatory reviews, or get their own budget.
Reclassify only on a **material change** to the goal or its risk class (e.g. the user widens scope, or
the work newly touches a migration). This single rule is the guard against both failure modes: a
worker that classifies narrowly to dodge escalation, and one that calls every subtask L2 and burns the
budget.

- **L0** — single-step, reversible, one clear validation. No tiering.
- **L1** — ordinary multi-step, bounded, reversible. Tripwires reactive only.
- **L2** — long-running: many steps / multiple subsystems / no single obvious validation. **Plan review
  mandatory at start; final review mandatory before done.**
- **L3** — high-risk / hard-to-reverse: schema/API/config contract, auth/security, billing, concurrency,
  migration, deletion, production ops, a new dependency. **Plan review + final review mandatory; lean
  toward escalating sooner.**

**Phases** are the milestones named in the plan review at the start — *that* is what PHASE-boundary
escalation keys off. Incidental replanning or a new subtask does **not** create a phase.

### 2. Escalate on these tripwires (objective — not "I feel unsure")
**Mandatory (fire regardless of confidence):**
- **PLAN_REVIEW** — at the START of any L2/L3 task, before real work: senior reviews the plan.
- **IRREVERSIBLE_GUARD** — before any irreversible / wide-blast action (schema change, migration,
  delete, deploy, auth change, adding a dependency): senior reviews *before* you do it.
- **PRE_DONE_REVIEW** — before proposing done on any L2/L3 task, regardless of diff size. Also fires
  on L1 when the diff is large/risky or the key validation couldn't be run.

**Reactive (fire on a counted/observed event, not a feeling):**
- **STALL_RESCUE** — the **same error fingerprint** survives **2 materially different** fix attempts,
  or 3 non-improving reruns. (The hook counts this for you; see Reliability.)
- **OSCILLATION** — the same file/function is materially edited 3+ times with no validation improvement.
- **SCOPE_DRIFT** — you've touched ≥3 modules (default threshold) you didn't plan to, before the first acceptance check passes.
- **CHECKPOINT_DEBT** — ≥40 substantive tool actions since phase start or last checkpoint, with no
  plan-defined checkpoint passed yet. Two-stage: 20 actions = local nudge (free), 40 actions = senior
  audit (consumes audit budget). Only fires for L2/L3 tasks with plan-defined checkpoints.
- **GATE_BLOCK** — an [`agent-completion-gate`](https://github.com/zhjai/agent-completion-gate) check
  returns BLOCKED → escalate to fix the real cause, don't loosen the check.

Map each trigger to an agent-arena mode and participant depth (adaptive default — not all escalations need two agents).
When calling a single senior, model choice follows task nature: **GPT/Codex for bug diagnosis** (concrete artifacts, tool execution); **Claude for planning and review** (judgment, long-context reasoning):

| Trigger | Mode | Participants | Default single senior | Why |
|---------|------|--------------|----------------------|-----|
| PLAN_REVIEW | `implementation_plan_review` | heterogeneous | — | Judgment call — framing blind spots matter |
| IRREVERSIBLE_GUARD | `full_arena` | heterogeneous | — | High stakes, irreversible — independent views catch assumptions |
| PRE_DONE_REVIEW | `code_review_arena` | heterogeneous | — | Judgment call on completeness |
| STALL_RESCUE | `solo_red_team` | single senior | **GPT/Codex** (strongest available, not current worker) | Bounded diagnosis with concrete artifacts — GPT stronger at code/tool execution |
| OSCILLATION | `solo_red_team` | single senior | **GPT/Codex** (strongest available, not current worker) | Concrete diagnosis, same reason |
| SCOPE_DRIFT | `quick_panel` | heterogeneous | — | Scope calls are judgment; fast panel works |
| CHECKPOINT_DEBT | `quick_panel` | heterogeneous | — | Progress audit; fast panel works |
| GATE_BLOCK | `solo_red_team` | single senior | **GPT/Codex** (strongest available, not current worker) | Concrete gate failure — diagnose the specific cause, then fix |

Override per-trigger in config under `escalation.mode_preferences`. The default senior model for each trigger can be overridden at init or in config.

### 3. Budget the senior calls (the whole point is saving money)
The budget is **per top-level goal** (shared across all its subtasks), reserved up front; never let
early calls eat the slots you need for planning and final review:
- **L1:** ≤1 escalation.
- **L2:** ≤3, reserve 1 for the final review.
- **L3:** ≤4, reserve 1 for planning and 1 for the final review.
- **Dedupe:** same trigger + same error fingerprint + **no new evidence** → do NOT re-escalate. Get new
  evidence first, or escalate to the human.
- **Budget exhausted but a MANDATORY review is due** (irreversible action / pre-done on a risky diff) →
  do **not** silently skip it and do **not** proceed unreviewed: **escalate to the human** instead.
- **Coalesce** several related irreversible actions into one review rather than one call each.
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
status: proceed | replan | blocked | need_more_evidence | human_required
diagnosis: <one sentence>
next_actions:   # ≤3
  - ...
checks:         # ≤3 deterministic checks to confirm it worked
  - ...
risks:          # ≤2
  - ...
```
`human_required` means the senior cannot resolve it alone — escalate to the human (step 6).
The worker keeps only this structured outcome + cited artifacts, **never the full senior transcript**
(it won't fit the cheap model's context, and following the arena context-budget rule, redirect the raw
output to a file and read back only the digest).

### 6. If the senior can't resolve it → escalate to the HUMAN, don't loop
`status: blocked`, or the same escalation firing twice with no progress, means stop calling the senior
and surface it to the user with the evidence. Looping a senior on an under-specified or judgment-call
problem just burns money.

**For long unattended tasks: use experiment-grill-feishu**

If the senior review says `human_required` and you're running a long task where the user may not be at the keyboard:

1. **Check if `experiment-grill-feishu` skill is available** (installed and configured)
2. **Send Feishu notification** with:
   - The escalation trigger (IRREVERSIBLE_GUARD, senior uncertainty, etc.)
   - Senior's analysis (diagnosis + risks)
   - Concrete question(s) for the user
   - Risk level (high for irreversible actions)
3. **Wait for user reply** (timeout per grill-feishu policy, typically 5-15 min)
4. **Apply decision:**
   - User replied → follow their decision
   - No reply, high-risk → BLOCK (grill-feishu fallback for irreversible actions)
   - No reply, low-risk → provisional execution (logged, reversible)
5. **If grill-feishu unavailable** → traditional: checkpoint and block (synchronous wait)

Example:
```yaml
# Senior review says "HUMAN_REQUIRED"
status: blocked
diagnosis: "Deleting staging DB affects 3 active test runs. Needs user confirmation of scope."
risks:
  - "May break ongoing integration tests"
  - "Recovery requires restore from yesterday's backup (data loss: 8 hours)"

# You call grill-feishu
notification: "⚠️ IRREVERSIBLE_GUARD: About to delete staging DB. Senior says: affects 3 active runs. Confirm scope?"
context: <senior's full analysis>
risk_level: high
timeout_min: 10

# Outcomes:
# - User replies "Confirmed, those 3 runs are obsolete" → proceed
# - No reply after 10 min → grill-feishu fallback: BLOCK (high-risk default)
```

### 7. On task completion — notify the user
When PRE_DONE_REVIEW passed and findings are addressed, proceed in order:
1. completion-gate check
2. If gate clears: **send fire-and-forget Feishu notification** (if `notifications.completion.enabled: true` and `experiment-grill-feishu` available): task summary, duration, key outcomes, any warnings
3. Declare done to the user

Sending notification before declaring done ensures the user is notified even if the model's final message is cut off or not seen.

## Composition (this skill owns *when*, not *how* or *done*)
- **agent-arena** — the escalation *mechanism* (heterogeneous call, independent answers, dissent kept).
  This skill decides *when* to invoke it.
- **experiment-grill-feishu** — async human communication for long unattended tasks. Two uses: (1) when senior says `HUMAN_REQUIRED`, send escalation question via Feishu and wait for reply (risk-based fallback if no reply); (2) when task is done, send a fire-and-forget completion notification. Completes the full loop: cheap → senior → human question → human notified when done.
- **deliberative-analysis** — a *pre-escalation* local thinking aid: if the hard part is a bad framing /
  narrow option space, expand options first; escalate to a senior only if still stuck. It may precede a
  *reactive* escalation, but it **cannot replace or delay a mandatory** escalation (plan / irreversible /
  pre-done). Not the default response to every bug.
- **agent-completion-gate** — still the only thing that can say the work is *actually done*. A
  PRE_DONE_REVIEW here is **advisory**, never acceptance. Ordering at the end: **PRE_DONE_REVIEW →
  address its findings → completion-gate → declare done**. A gate BLOCK is a tripwire. If addressing
  the review's findings produces *new* material change, the pre-done review is stale — re-run it once;
  don't loop indefinitely.
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

## Setup for cheap workers — preventing context loss

**Problem:** If the user says "you are a cheap model" at session start, but context compaction or long
runtime causes the model to forget, it may stop escalating.

**Solution: Set `KYL_WORKER_TIER` environment variable**

```bash
export KYL_WORKER_TIER=cheap
codex exec "Train ResNet on CIFAR-10"
# or
grill-run --tier cheap -- codex exec "..."
```

The hook reads `KYL_WORKER_TIER` and:
1. **Nudges mandatory PLAN_REVIEW** (PreToolUse): if cheap worker on L2/L3 task starts editing without
   plan review, hook issues a strong nudge — no longer relies on model remembering to call the skill.
   (Note: the hook never blocks; it emits context. Full enforcement comes in v0.2.0's guarded launcher.)
2. **Periodic reminder** (every 20 actions): light nudge to use know-your-limits.
3. **PreCompact reminder**: tells the model "you are cheap" before compaction, reducing forgetting.

**Set task class in ledger:**
```bash
# When starting an L2/L3 task, write to ledger
echo '{"task_class": "L2", "plan_reviewed": false, "actions": 0}' > state/know-your-limits/ledger.json
```

The hook will nudge PLAN_REVIEW before the first Edit/Write if `plan_reviewed` is false.

## Do not
- **Do not gate escalation on the worker's self-assessed confidence** — use the objective tripwires.
- **Do not escalate everything** — that defeats the cost saving; respect the budget and dedupe.
- **Do not let the senior's review count as "done"** — only the completion-gate clears completion.
- **Do not loop the senior** — same problem twice with no new evidence → go to the human.
- **Do not feed the senior your favored diagnosis first** — raw evidence first, so its review stays independent.
