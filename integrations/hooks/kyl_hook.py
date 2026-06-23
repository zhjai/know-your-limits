#!/usr/bin/env python3
"""kyl_hook.py — a THIN, trigger-only hook for the know-your-limits escalation policy.

A cheap worker can't reliably count its own attempts/stalls (it mis-counts, rationalizes "this try
was different", loses the count across compaction). This hook keeps that bookkeeping OUTSIDE the
model: it reads one lifecycle event on stdin (Claude Code OR Codex), updates a small JSON
**escalation ledger**, and — when an OBJECTIVE tripwire trips — emits a context nudge telling the
worker to escalate via agent-arena. It NEVER makes the senior call, never blocks, never decides the
task is done, and exits 0 on bad input.

Tripwires it can observe deterministically (no model self-report needed):
  - STALL_RESCUE     : same error fingerprint survives N (default 2) failing tool results
  - OSCILLATION      : same file materially edited M (default 3) times with no passing check between
  - SCOPE_DRIFT      : >K (default 2) distinct modules touched before any passing check
  - CHECKPOINT_DEBT  : >A (default 40) tool actions with no passing check observed
The MANDATORY tripwires (PLAN_REVIEW at start, IRREVERSIBLE_GUARD, PRE_DONE_REVIEW) are the skill's
job — they don't depend on counting and shouldn't be faked by a hook.

Output (valid on Claude Code AND Codex): a single line of JSON
  {"hookSpecificOutput": {"hookEventName": "<Event>", "additionalContext": "<nudge>"}}

Env:
  KYL_LEDGER       path to the ledger JSON (default state/know-your-limits/ledger.json)
  KYL_STALL_N      stall threshold (default 2)
  KYL_OSC_M        oscillation threshold (default 3)
  KYL_SCOPE_K      scope-drift module threshold (default 2)
  KYL_ACTIONS_A    checkpoint-debt action threshold (default 40)
The ledger path is forced out of any control/ dir so it can never be mistaken for authority.
"""
import json, os, pathlib, re, sys, hashlib

def _envint(name, default):
    # never let a malformed env value crash the hook at import time (would break the host)
    try:
        return max(1, int(os.environ.get(name, str(default))))
    except (TypeError, ValueError):
        return default

STALL_N    = _envint("KYL_STALL_N", 2)
OSC_M      = _envint("KYL_OSC_M", 3)
SCOPE_K    = _envint("KYL_SCOPE_K", 2)
ACTIONS_A  = _envint("KYL_ACTIONS_A", 40)

# Tools that actually MUTATE a file — only these count toward oscillation/scope. A Read/Grep of the
# same file 3x must not look like thrashing.
_MUTATING_TOOLS = {"edit", "write", "notebookedit", "multiedit", "create", "update", "apply_patch", "str_replace"}

_FAIL = re.compile(r"\btraceback\b|\berror:|\bfatal\b|command failed|command exited with [1-9]|exit (?:code |status )?[1-9]|non-zero (?:exit|status)|returned non-zero|assertion(?:error)?|\bFAIL(?:ED|URE)?\b|segmentation fault|\bsegfault\b|core dumped|\bKilled\b|\bpanic\b|\bOOM\b|out of memory", re.I)
_OK   = re.compile(r"\b0 errors?\b|\bno errors?\b|\ball (?:tests? )?pass|\bsuccess\b|\bPASSED\b|\bok\b\s*$", re.I)
# a "passing check" signal in tool output — resets stall/oscillation/scope counters.
# Keep markers UNAMBIGUOUS: "green"/"ok" as bare substrings false-reset on "greenfield"/"looks ok",
# so require word boundaries and test-shaped phrases only.
_PASS_CHECK = re.compile(r"\b\d+ passed\b|\ball tests? pass(?:ed)?\b|\btests? passed\b|\b\d+ passing\b|exit (?:code |status )?0\b|\ball green\b|✓", re.I)


def _read_event():
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def _ledger_path():
    # The ledger is just a counter file (the user sets KYL_LEDGER). Constrain it so a stray value
    # can't corrupt authority or climb out of its tree: reject a control/ (authority) segment and
    # any parent-escape ('..'). Absolute paths are allowed (that's how you point it at your state
    # dir). Fall back to the default on anything suspicious.
    default = pathlib.Path("state/know-your-limits/ledger.json")
    raw = os.environ.get("KYL_LEDGER", "")
    if not raw:
        return default
    p = pathlib.Path(raw)
    if ".." in p.parts or "control" in {x.lower() for x in p.parts}:
        return default
    return p


def _load(p):
    try:
        return json.loads(p.read_text())
    except Exception:
        return {"actions": 0, "errs": {}, "files": {}, "modules": [], "since_pass": 0, "fired": []}


def _save(p, d):
    try:
        # Bound the growing collections so the ledger stays small — do NOT truncate the serialized
        # JSON string (that would produce invalid JSON and silently reset all counters on next load).
        if len(d.get("fired", [])) > 200:
            d["fired"] = d["fired"][-200:]
        if len(d.get("errs", {})) > 200:
            d["errs"] = dict(list(d["errs"].items())[-200:])
        if len(d.get("files", {})) > 500:
            d["files"] = dict(list(d["files"].items())[-500:])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d))
    except Exception:
        pass


def _fingerprint(text):
    # normalize volatile bits (paths, line numbers, hex addrs, digits) so "the same error" matches
    t = re.sub(r"0x[0-9a-f]+|\b\d+\b|/[^\s:]+", "", str(text).lower())
    t = re.sub(r"\s+", " ", t).strip()
    return hashlib.sha1(t.encode("utf-8", "replace")).hexdigest()[:12] if t else ""


def _tool_failed(d):
    code = d.get("tool_exit_code")
    if isinstance(code, int):
        return code != 0  # Claude Code: reliable
    resp = str(d.get("tool_response", "") or d.get("tool_output", ""))  # Codex: best-effort
    return bool(_FAIL.search(resp)) and not _OK.search(resp)


def _passed(d):
    # A genuine *validation* pass (a test/check going green) — this is what resets the "stuck"
    # counters. NOT just any command exiting 0: a successful file edit (exit 0) must not clear an
    # oscillation/scope count. So we require a test-shaped pass phrase. The caller also requires
    # not _tool_failed(d), so a mixed "12 passed ... <traceback>" output won't reset anything.
    resp = str(d.get("tool_response", "") or d.get("tool_output", ""))
    return bool(_PASS_CHECK.search(resp))


def _tool_text(d):
    return str(d.get("tool_response", "") or d.get("tool_output", "") or "")


def _touched_path(d):
    # only count MUTATING tools — a Read/Grep of the same file 3x is not thrashing
    name = str(d.get("tool_name") or d.get("name") or "").lower().strip()
    if name and not any(m in name for m in _MUTATING_TOOLS):
        return ""
    ti = d.get("tool_input") or {}
    for k in ("file_path", "path", "notebook_path"):
        v = ti.get(k)
        if isinstance(v, str) and v:
            return v
    return ""


def _module_of(path):
    parts = pathlib.PurePosixPath(path).parts
    return parts[0] if parts else ""


def _emit(event, text):
    if text:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}))


def main():
    d = _read_event()
    event = d.get("hook_event_name") or d.get("hookEventName") or d.get("event") or ""
    p = _ledger_path()
    L = _load(p)
    nudges = []

    if event == "PostToolUse":
        L["actions"] = L.get("actions", 0) + 1
        out = _tool_text(d)

        # a passing check resets the "stuck" counters — but only on a GENUINE validation pass
        # (a test/check going green, not just any exit 0). Never reset when the same call also shows
        # a failure (mixed "12 passed ... <traceback>" must NOT clear the counters). Clearing `fired`
        # too starts a fresh epoch, so a file/error that goes wrong AGAIN after a green can re-trigger.
        if _passed(d) and not _tool_failed(d):
            L["errs"], L["files"], L["modules"], L["since_pass"], L["fired"] = {}, {}, [], 0, []
        else:
            L["since_pass"] = L.get("since_pass", 0) + 1

        # STALL: same error fingerprint repeats
        if _tool_failed(d):
            fp = _fingerprint(out)
            if fp:
                L["errs"][fp] = L["errs"].get(fp, 0) + 1
                if L["errs"][fp] >= STALL_N and f"stall:{fp}" not in L.get("fired", []):
                    L.setdefault("fired", []).append(f"stall:{fp}")
                    nudges.append(
                        f"STALL_RESCUE: the same failure has survived {L['errs'][fp]} attempts. "
                        "Stop retrying blindly — escalate to a senior model via agent-arena "
                        "(bug_root_cause_arena) with the stack trace + what you tried, max 3 questions.")

        # OSCILLATION + SCOPE_DRIFT: by touched file/module
        path = _touched_path(d)
        if path:
            L["files"][path] = L["files"].get(path, 0) + 1
            if L["files"][path] >= OSC_M and f"osc:{path}" not in L.get("fired", []):
                L.setdefault("fired", []).append(f"osc:{path}")
                nudges.append(
                    f"OSCILLATION: {path} has been edited {L['files'][path]}x with no passing check. "
                    "You may be guessing — escalate the approach to a senior (code_review_arena) instead of re-editing.")
            mod = _module_of(path)
            if mod and mod not in L["modules"]:
                L["modules"].append(mod)
            if len(L["modules"]) > SCOPE_K and "scope" not in L.get("fired", []):
                L.setdefault("fired", []).append("scope")
                nudges.append(
                    f"SCOPE_DRIFT: you've touched {len(L['modules'])} modules ({', '.join(L['modules'][:5])}) "
                    "before any passing check. Confirm scope with a senior (quick_panel) before spreading further.")

        # CHECKPOINT_DEBT: many actions, no pass
        if L.get("since_pass", 0) >= ACTIONS_A and "debt" not in L.get("fired", []):
            L.setdefault("fired", []).append("debt")
            nudges.append(
                f"CHECKPOINT_DEBT: {L['since_pass']} actions with no passing check. "
                "Do a senior audit (quick_panel): are you still on the right track, or drifting?")

    elif event == "PreCompact":
        # counters survive in the on-disk ledger; remind the worker not to lose escalation state
        nudges.append(
            "Context is about to compact. The know-your-limits ledger is on disk (state/know-your-limits/"
            "ledger.json) — after compaction, re-read it rather than resetting your stall/scope counters to zero.")

    _save(p, L)
    _emit(event, "  ".join(nudges))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)  # a hook must never break the host
