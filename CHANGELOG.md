# Changelog

## v0.1.1

- **Hardened over a 3-block heterogeneous Codex arena review of the actual implementation** (the v0.1.0 review had been a self-audit because the endpoint was timing out; re-run here on a working endpoint via stdin to dodge the long-argv stall). Fixes:
  - **Hook — failure/pass detection:** `\bFAILED?\b` matched `FAILE` but not `FAIL`; now `FAIL(?:ED|URE)?` plus `non-zero status` / `command exited with N`. A passing check no longer resets the stuck counters from **mixed output** (an early "12 passed" before a later traceback) — reset requires a test-shaped pass AND no failure in the same call. A successful file edit (exit 0) no longer counts as a validation pass.
  - **Hook — `fired` dedup bug (most important):** a passing check cleared the counters but not the `fired` list, so a file/error that went wrong *again* after a green was suppressed forever. `fired` is now cleared on a genuine pass (fresh epoch).
  - **Hook — reads counted as edits:** oscillation/scope now only count **mutating** tools (Edit/Write/apply_patch/…), not repeated Reads of the same file.
  - **Hook — host safety:** a malformed threshold env (`KYL_STALL_N=abc`) crashed the hook at import (outside the try/except) → now parsed safely. `KYL_LEDGER` with `..` escape rejected (falls back to default); `control/` already rejected.
  - **SKILL.md — scope-boundary (biggest design risk):** classification, budget, plan review, and final review are now explicitly **once per top-level goal**; subtasks inherit and don't re-trigger. Phases defined as plan milestones. Budget-exhausted-but-mandatory-review-due → escalate to the human. Ordering pinned: PRE_DONE_REVIEW → fix → completion-gate → done; deliberative-analysis can't replace a mandatory escalation.
- Tests: 20 (was 11) — added regressions for every fix above.


## v0.1.0

- Initial preview of `know-your-limits`: the **policy of WHEN** a cheap primary worker (gpt-5-mini, Claude Haiku, GLM, DeepSeek, Kimi…) on a long task should escalate the hard parts to a strong senior model, routed through [`agent-arena`](https://github.com/zhjai/agent-arena) (the mechanism).
- **Tripwires, not self-assessment.** Escalation fires on objective events, because an overconfident/cheap model won't notice it's stuck:
  - **Mandatory** (don't depend on the worker noticing): PLAN_REVIEW at the start of L2/L3 work, IRREVERSIBLE_GUARD before schema/migration/delete/deploy/auth/new-dep, PRE_DONE_REVIEW on a large/risky diff.
  - **Reactive** (counted by the hook): STALL_RESCUE (same error survives 2 attempts), OSCILLATION (same file edited 3× with no passing check), SCOPE_DRIFT (2+ unplanned modules), PROGRESS_DEBT, GATE_BLOCK.
- **Thin hook** ([`integrations/hooks/kyl_hook.py`](integrations/hooks/kyl_hook.py)) keeps an on-disk escalation ledger from real lifecycle events and nudges escalation when a tripwire trips — trigger-only, never makes the senior call, never blocks, never marks done, exits 0 on bad input, ledger forced out of any `control/` dir. Cross-host (Claude Code + Codex). Without the hook the skill runs in a degraded mode with the mandatory tripwires as backstop.
- **Budget + minimal packet + compact senior reply schema** so the expensive call stays cheap and its answer fits the cheap worker's context; **human backstop** so a senior is never looped on a judgment call.
- Composes with (does not duplicate): `agent-arena` (mechanism), `deliberative-analysis` (local option expansion), `agent-completion-gate` (sole authority over "done"), `agent-lessonbook` (record policy misses).
- 11 hook self-tests (`tests/test_hook.py`).
- Designed with a heterogeneous agent-arena round (Codex × Claude): mode-first triggers, ledger fields, escalation budget, packet/answer schema, fingerprint dedupe.
