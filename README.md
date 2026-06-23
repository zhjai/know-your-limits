# know-your-limits

> **A cheap model running a long task should know when it's out of its depth — and phone a senior, instead of confidently guessing.**

You run a small/cheap model (gpt-5-mini, Claude Haiku, GLM, DeepSeek, Kimi…) as the primary worker on a long task to save tokens. It does the grunt work fine — until it hits a hard moment (a bug it can't crack, a plan that needs judgment, an irreversible change) and **confidently guesses wrong**, burning hours on a bad path.

`know-your-limits` is the **policy of WHEN** that worker should escalate the hard parts to a strong senior model. The escalation **mechanism** is [`agent-arena`](https://github.com/zhjai/agent-arena) (it makes the heterogeneous cross-model call); this skill decides *when* to pull that lever, so you pay for the expensive model only at the moments that need it.

## The core idea: tripwires, not "do you feel unsure?"

The trap: **an overconfident/cheap model is exactly the one that won't notice it's stuck.** Asking it "are you unsure?" is self-referential — it'll say no and keep guessing.

So escalation fires on **objective, observable events** instead:

| Trigger | Fires when… | → escalate for |
|---|---|---|
| **PLAN_REVIEW** (mandatory) | a substantial/risky task starts | review the plan before doing it |
| **IRREVERSIBLE_GUARD** (mandatory) | about to do a schema change / migration / delete / deploy / auth change / add a dependency | review *before* the irreversible action |
| **PRE_DONE_REVIEW** (mandatory) | about to call it done on a large/risky diff | a real review before "done" |
| **STALL_RESCUE** | the same error survives 2 different fix attempts | stop guessing, get a root-cause |
| **OSCILLATION** | same file edited 3× with no passing check | the approach is wrong, not the code |
| **SCOPE_DRIFT** | touched ≥3 unplanned modules (default) before any check passes | confirm scope before spreading |
| **CHECKPOINT_DEBT** | ≥40 actions since phase start / last checkpoint, no checkpoint passed | senior audit to confirm still on track |
| **GATE_BLOCK** | an [`agent-completion-gate`](https://github.com/zhjai/agent-completion-gate) check returns BLOCKED | fix the real cause |

The **mandatory** ones don't depend on the worker noticing anything — they fire on the task class and the action type. The **reactive** ones are *counted by a hook*, not by the model (a cheap model mis-counts its own attempts).

## Why a hook, not just a skill

A cheap worker can't reliably track "have I failed the same way twice?" across a long session — it mis-counts, rationalizes ("this attempt was different"), and loses the count when context compacts. So the reliable setup is **the skill + a thin hook**:

- The **hook** ([`integrations/hooks/kyl_hook.py`](integrations/hooks/kyl_hook.py)) keeps a small on-disk **escalation ledger** (attempts per error, files touched, modules, actions, budget) from real lifecycle events, and **nudges escalation when a tripwire trips**. It never makes the senior call, never blocks, never marks anything done.
- The **skill** owns the mandatory escalations (start / irreversible / pre-done) — the backstop that works even with no hook.

Without the hook it still runs in a **degraded mode** (the worker self-reports a one-line status each step), but the mandatory tripwires remain the safety net.

## Get started

```bash
npx skills add zhjai/know-your-limits -g -a claude-code   # or -a codex, … any host
```

**Health check (optional):** verify your setup

```bash
cd <know-your-limits-repo>
python3 scripts/kyl_doctor.py
```

This checks:
- ✅ Skills installed (know-your-limits, agent-arena required; grill-feishu optional)
- ✅ Hook wired (for reliable reactive tripwires)
- ✅ `KYL_WORKER_TIER` set (for cheap workers)
- ℹ️ Config exists (auto-created on first escalation)

**Config:** On first escalation, `state/know-your-limits/config.yaml` is auto-created with defaults (worker tier, senior model, budget limits). Edit to customize. Run `python3 scripts/kyl_init_config.py project` to create it manually.

Then, for the reliable setup, wire the hook (merge the example into your host's hook config and fix the path):
- Claude Code: [`integrations/claude-code/settings.hooks.json`](integrations/claude-code/settings.hooks.json)
- Codex: [`integrations/codex/hooks.json`](integrations/codex/hooks.json)

You also need the escalation mechanism installed: `npx skills add zhjai/agent-arena`.

**For cheap workers: set the environment variable to prevent context-loss forgetting**

```bash
# Tell the hook this is a cheap worker
export KYL_WORKER_TIER=cheap

# Then run your agent
codex exec "Train ResNet on CIFAR-10"

# Or use a wrapper (if you have one)
grill-run --tier cheap -- codex exec "..."
```

This enables:
- **Mandatory PLAN_REVIEW nudging** (hook issues strong nudge at PreToolUse if cheap worker on L2/L3 starts editing without review; full enforcement in v0.2.0)
- **Periodic reminders** (every 20 actions: light nudge to use know-your-limits)
- **PreCompact reminder** (before context compaction, reminds "you are cheap")

Without `KYL_WORKER_TIER`, the hook still counts tripwires (STALL/OSCILLATION/etc.), but won't nudge mandatory reviews or remind the model.

## Budget — escalation is a scarce tool, not the default

The whole point is saving money, so senior calls are capped and reserved up front:

- **L1** (ordinary): ≤1 escalation
- **L2** (long-running): ≤3, reserve 1 for the final review
- **L3** (high-risk / irreversible): ≤4, reserve 1 for planning + 1 for final review
- **Dedupe:** same trigger + same error + no new evidence → don't re-escalate
- **Human backstop:** if the senior also can't resolve it (or the same escalation fires twice with no progress), stop and surface it to *you* — don't loop a senior on a judgment call.

The packet sent to the senior is minimal (trigger, goal, acceptance criteria, raw evidence, ≤3 questions), and the senior replies in a compact schema (`status / diagnosis / next_actions / checks / risks`) the cheap worker can actually act on — never a transcript that blows its context.

## When NOT to use it

- **Short tasks** — if it's small *and* hard, just use the senior model directly. Tiering only saves money when there's lots of cheap grunt work around a few hard moments.
- **When the host can't call the senior** — agent-arena needs shell + the senior's CLI + credentials. Without that, this degrades to "flag the moment and ask the human."

## Where it fits

```
know-your-limits      — WHEN a cheap worker escalates the hard parts
agent-arena           — HOW the heterogeneous senior call happens
deliberative-analysis — expand options locally before escalating (if the problem is bad framing)
agent-completion-gate — the only thing that says the work is actually DONE (a senior review is advisory)
agent-lessonbook      — record policy misses (escalated too late/early; a threshold to tune)
```

This skill owns **when**. It never replaces the gate's authority over "done", and it routes *through* agent-arena rather than reimplementing cross-model calls.

## How this compares to existing solutions

We surveyed model routing / fallback / escalation systems to understand what exists and what's missing. **TL;DR: know-your-limits is the only system that detects "I'm stuck" at runtime using objective tripwires, rather than relying on the model's self-assessment or reacting passively to timeouts.**

| Feature | LiteLLM | AutoGen | Swarm | FrugalGPT | know-your-limits |
|---------|---------|---------|-------|-----------|------------------|
| **Runtime stuck detection** | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Objective tripwires** (not model self-eval) | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Fine-grained failure modes** (stall/oscillation/scope) | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Hook maintains ledger** (model-external counting) | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Mandatory tripwires** (plan/irreversible/pre-done) | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Per-goal budget** | ✅ (partial) | ❌ | ❌ | ❌ | ✅ |
| **Long-task specialized** | ❌ | ❌ | ❌ | ✅ (partial) | ✅ |

### What exists

- **LiteLLM:** Passive fallback (timeout / 429 / 5xx → retry → switch model). Production-grade cost tracking, but no "I'm about to get stuck" detection.
- **AutoGen / Swarm:** Explicit orchestration (a coordinator routes tasks to specialist agents). No runtime self-awareness or automatic escalation.
- **FrugalGPT (Stanford):** Static routing (offline-trained classifier: question features → model choice). 98% cost reduction, but not dynamic escalation (doesn't detect getting stuck mid-run).
- **LLM confidence calibration research:** Self-assessed confidence has ~50% calibration error, especially for overconfident cheap models. This validates our "objective tripwires" design — asking "do you feel unsure?" is unreliable.

### What's unique here

**Objective tripwires instead of self-assessment.** The core insight: an overconfident or cheap model won't notice it's stuck (asking it "are you unsure?" is self-referential). So escalation fires on **counted, observable events**:
- **STALL:** same error fingerprint survives 2 fix attempts (the hook counts this, not the model)
- **OSCILLATION:** same file edited 3× with no passing check
- **SCOPE_DRIFT:** touched ≥3 unplanned modules (default) before any check passes
- **CHECKPOINT_DEBT:** ≥40 actions with no checkpoint passed (two-stage: 20 = nudge, 40 = audit)
- **Mandatory:** plan review at start / irreversible-action guard / pre-done review (fire regardless of model confidence)

The **hook keeps the ledger** outside the model's context (a cheap model forgets/mis-counts its own attempts across compaction). The **skill is the policy** (when to escalate), **agent-arena is the mechanism** (how to call the senior).

### Lessons we borrowed

- **LiteLLM's cost tracking:** per-user/project/goal token accounting. We added per-goal budget with reserved slots for mandatory reviews.
- **FrugalGPT's tiering insight:** Not every task needs the strongest model. We apply this to *long* tasks (short hard tasks should just use the senior directly).
- **Confidence research:** Validates that self-assessment is unreliable, so we never gate escalation on "I feel unsure."

## Roadmap: what we're adding based on this research

### v0.2.0 (short-term) — Hardened enforcement

**Core fix: move from advisory to enforced budgeting.** Codex arena review found that the current design has no enforcement point — the hook observes calls after they happen, and worker self-report is untrustworthy.

1. **Guarded launcher** (`kyl-escalate`): introduces a control point (like LiteLLM's request gateway) that wraps agent-arena calls. The launcher:
   - Accepts `goal_id`, `request_id`, trigger, mode, and packet
   - Atomically reserves a budget slot before calling the senior
   - Records state: `pending → started → completed/failed/unknown`
   - Uses `request_id` as the idempotency key
   - Returns `HUMAN_REQUIRED` when a mandatory review cannot be funded (no silent skip)
   - Enforcement mode: `guarded` (can reject calls) or `advisory` (can only log)

2. **Evidence-aware deduplication**: hash includes `goal_id + trigger + mode + sorted evidence digests + normalized questions`. Skip only when an equivalent request is pending or already answered AND no evidence revision occurred. Time windows don't define equivalence — evidence changes do.

3. **~~Verbalized confidence~~** — **removed from v0.2.0**. Arena review found this is a Trojan horse: "I think / probably" measures writing style and model family, not calibrated uncertainty (cautious models false-positive, overconfident models false-negative). It contradicts the core "objective tripwires" principle. Demoted to optional telemetry (not policy) for future calibration experiments.

4. **Explicit `goal_id` tracking**: ledger and launcher use a stable goal identifier so budgets don't leak across goals and dedup works correctly.

5. **Formalize CHECKPOINT_DEBT tripwire** (already exists in code, now documented): two-stage escalation at 20 actions (local nudge, free) and 40 actions (senior audit, consumes audit budget). Only fires for L2/L3 tasks with plan-defined checkpoints. More accurate name than PROGRESS_DEBT.

6. **Split budget pools**: separate mandatory / rescue / audit pools instead of a single shared cap:
   - **Mandatory pool**: plan review + irreversible guards + pre-done review (always funded)
   - **Rescue pool**: stall / oscillation / scope drift (opt-in, default budget)
   - **Audit pool**: checkpoint debt + optional phase reviews (opt-in, 0 by default, max 1 call per goal, only for tasks >60min estimated duration)
   
   Prevents early reactive calls from blocking mandatory reviews, and makes audit budget an explicit opt-in rather than stealing from rescue capacity.

7. **Integrate experiment-grill-feishu for async human escalation**: when senior review returns `HUMAN_REQUIRED` (e.g., IRREVERSIBLE_GUARD needs judgment, or senior is uncertain), and the user is not at the keyboard:
   - If `experiment-grill-feishu` skill is available, send Feishu notification with senior's analysis + context
   - Wait for user reply (timeout per grill-feishu policy, typically 5-15 min)
   - If user replies: apply their decision
   - If no reply: apply grill-feishu's risk-based fallback (BLOCK for high-risk irreversible actions, provisional for low-risk)
   - If grill-feishu unavailable: checkpoint and block (traditional synchronous wait)
   
   Closes the gap: currently "escalate to HUMAN" has no async mechanism for long unattended tasks. This makes know-your-limits + grill-feishu a complete escalation chain: cheap → senior → human (with async notification).

### v0.3.0 (mid-term) — Cross-goal learning

**Prerequisite: a separate cross-goal history layer.** The current per-goal ledger is a single mutable JSON — it cannot support "10+ similar goals." Introduce two layers:
- **Per-goal ledger**: real-time enforcement (current)
- **Append-only event stream** (`state/know-your-limits/history.jsonl`): cross-goal, sanitized, durable

Minimum events: `goal_started(task_class, risk_class)`, `phase_started`, `tripwire_fired`, `escalation_completed(cost, diagnosis_code, outcome)`, `goal_completed`.

1. **Descriptive priors, not learned routing**: Start with aggregate stats ("6/12 repo migrations triggered STALL during validation") rather than training on 10 samples (insufficient for credible prediction). Offline learning becomes viable only after held-out evaluation is possible.

2. **Structured diagnosis for lesson recurrence**: Extend senior reply schema with `diagnosis: {code, taxonomy_version, component, summary}`. Hook matches by code (not free-text). Create a lesson candidate only after the same versioned code appears across ≥3 distinct goals, was followed by successful resolution, and repeated calls in one stuck loop count once. Requires cross-goal history + human review before promotion to `control/lessons/`.

3. **Procedure tiers** (renamed from "tiered quality"): Budget pressure may remove optional deliberation or audits, but never acceptance checks, mandatory reviews, irreversible-action guards, or the human backstop. Modes:
   - `THOROUGH`: local deliberation + optional senior audit
   - `BALANCED`: direct implementation + targeted checks
   - `DIRECT`: direct implementation + mandatory validation only
   - `HUMAN_REQUIRED`: continuation unsafe or unfunded
   
   Measure with ablation: does DIRECT actually save money, or do increased retries trigger more senior calls?

**Boundary preserved:** trigger hook = deterministic counters (fail-open); guarded launcher = authorization + accounting (fail-closed for mandatory); models = proposals; human = final authority.

These stay true to the core principle: **objective, model-external tripwires**. We're adding enforcement infrastructure and cross-goal observability, not replacing tripwires with self-assessment.

## Status

`v0.1.0` preview. MIT. Pairs with [`agent-arena`](https://github.com/zhjai/agent-arena) (required: the mechanism), [`agent-completion-gate`](https://github.com/zhjai/agent-completion-gate), and [`agent-lessonbook`](https://github.com/zhjai/agent-lessonbook). Self-tests in [`tests/`](tests/).
