#!/usr/bin/env python3
"""kyl doctor — health check for know-your-limits setup.

Checks:
- Skill installed
- agent-arena available
- experiment-grill-feishu available (optional)
- Hook wired
- KYL_WORKER_TIER set (for cheap workers)
- Config file exists

Outputs recommendations for missing pieces.
"""
import json, os, pathlib, subprocess, sys

def check_skill(name):
    # Check if skill is in ~/.agent-skills/
    skills_dir = pathlib.Path.home() / ".agent-skills"
    if not skills_dir.exists():
        return None
    skill_path = skills_dir / name
    if skill_path.exists():
        # Try to read version from SKILL.md
        skill_md = skill_path / "SKILL.md"
        if skill_md.exists():
            with open(skill_md) as f:
                for line in f:
                    if line.strip().startswith("version:"):
                        return line.split(":", 1)[1].strip().strip('"')
        return "installed"
    return None

def check_hook_wired():
    # Check Claude Code settings
    claude_settings = pathlib.Path.home() / ".claude" / "settings.json"
    if claude_settings.exists():
        try:
            with open(claude_settings) as f:
                settings = json.load(f)
            hooks = settings.get("hooks", {})
            if "PostToolUse" in hooks or "PreToolUse" in hooks:
                # Check if kyl_hook.py is mentioned
                for event in hooks.values():
                    for matcher in event:
                        for hook in matcher.get("hooks", []):
                            cmd = hook.get("command", "")
                            if "kyl_hook" in cmd:
                                return "claude-code"
        except Exception:
            pass
    
    # Check Codex hooks
    codex_config = pathlib.Path.home() / ".codex" / "config.toml"
    if codex_config.exists():
        try:
            with open(codex_config) as f:
                if "kyl_hook" in f.read():
                    return "codex"
        except Exception:
            pass
    
    return None

def check_env_var(name):
    return os.environ.get(name)

def check_config():
    # Project-level config
    project_cfg = pathlib.Path("state/know-your-limits/config.yaml")
    if project_cfg.exists():
        return "project", project_cfg
    
    # User-level config
    user_cfg = pathlib.Path.home() / ".kyl" / "config.yaml"
    if user_cfg.exists():
        return "user", user_cfg
    
    return None, None

def main():
    print("🔍 know-your-limits health check\n")
    
    issues = []
    warnings = []
    
    # 1. Check know-your-limits skill
    kyl_version = check_skill("know-your-limits")
    if kyl_version:
        print(f"✅ know-your-limits {kyl_version}")
    else:
        print("❌ know-your-limits: not installed")
        issues.append("Install: npx skills add zhjai/know-your-limits -g")
    
    # 2. Check agent-arena (required)
    arena_version = check_skill("agent-arena")
    if arena_version:
        print(f"✅ agent-arena {arena_version}")
    else:
        print("❌ agent-arena: not installed (REQUIRED for escalation)")
        issues.append("Install: npx skills add zhjai/agent-arena -g")
    
    # 3. Check experiment-grill-feishu (optional)
    feishu_version = check_skill("experiment-grill-feishu")
    if feishu_version:
        print(f"✅ experiment-grill-feishu {feishu_version}")
    else:
        print("⚠️  experiment-grill-feishu: not installed (optional, enables async human escalation)")
        warnings.append("Install (optional): npx skills add zhjai/experiment-grill-feishu -g")
    
    # 4. Check hook
    hook_wired = check_hook_wired()
    if hook_wired:
        print(f"✅ Hook wired: {hook_wired}")
    else:
        print("⚠️  Hook: not wired (reactive tripwires won't fire reliably)")
        warnings.append("Wire hook: see integrations/claude-code/settings.hooks.json or integrations/codex/hooks.json")
    
    # 5. Check KYL_WORKER_TIER
    worker_tier = check_env_var("KYL_WORKER_TIER")
    if worker_tier:
        print(f"✅ KYL_WORKER_TIER={worker_tier}")
    else:
        print("⚠️  KYL_WORKER_TIER: not set (cheap workers should set this)")
        warnings.append("Set env var: export KYL_WORKER_TIER=cheap")
    
    # 6. Check config file
    cfg_scope, cfg_path = check_config()
    if cfg_path:
        print(f"✅ Config: {cfg_scope} ({cfg_path})")
    else:
        print("ℹ️  Config: not found (will be created on first escalation)")
    
    # Summary
    print()
    if issues:
        print("❌ Issues (must fix):")
        for i in issues:
            print(f"   - {i}")
        print()
    
    if warnings:
        print("⚠️  Recommendations:")
        for w in warnings:
            print(f"   - {w}")
        print()
    
    if not issues and not warnings:
        print("✅ All checks passed! know-your-limits is ready.")
    elif not issues:
        print("✅ Core setup complete. Optional improvements available above.")
    else:
        print("❌ Fix the issues above before using know-your-limits.")
        sys.exit(1)

if __name__ == "__main__":
    main()
