# Changelog

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
