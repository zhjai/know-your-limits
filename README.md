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
| **SCOPE_DRIFT** | touched 2+ unplanned modules before any check passes | confirm scope before spreading |
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

Then, for the reliable setup, wire the hook (merge the example into your host's hook config and fix the path):
- Claude Code: [`integrations/claude-code/settings.hooks.json`](integrations/claude-code/settings.hooks.json)
- Codex: [`integrations/codex/hooks.json`](integrations/codex/hooks.json)

You also need the escalation mechanism installed: `npx skills add zhjai/agent-arena`.

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

## Status

`v0.1.0` preview. MIT. Pairs with [`agent-arena`](https://github.com/zhjai/agent-arena) (required: the mechanism), [`agent-completion-gate`](https://github.com/zhjai/agent-completion-gate), and [`agent-lessonbook`](https://github.com/zhjai/agent-lessonbook). Self-tests in [`tests/`](tests/).
