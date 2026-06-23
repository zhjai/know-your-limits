#!/usr/bin/env python3
"""kyl_init_config.py — create default config if missing.

Called by skill on first escalation, or manually by user.
Creates project-level config at state/know-your-limits/config.yaml
"""
import os, pathlib, sys

DEFAULT_CONFIG = """# know-your-limits configuration
# Created automatically on first use

worker:
  # Tier: cheap | expensive | auto-detect
  tier: auto-detect
  
escalation:
  # Senior model to escalate to (or auto-detect for cross-vendor heterogeneity)
  senior_model: auto-detect  # auto | claude-opus | codex-5.5 | glm-4-plus
  
  # Fallback order when escalation fails
  fallback_order:
    - senior        # Try senior model first
    - human_async   # If senior fails, async human via grill-feishu
    - human_sync    # If no grill-feishu, synchronous block
  
  # Arena mode preferences (which arena mode to use per trigger)
  mode_preferences:
    PLAN_REVIEW: implementation_plan_review
    STALL_RESCUE: bug_root_cause_arena
    OSCILLATION: code_review_arena
    SCOPE_DRIFT: quick_panel
    CHECKPOINT_DEBT: quick_panel
    PRE_DONE_REVIEW: code_review_arena

notifications:
  # Task completion notifications (v0.2.0: handled by grilld)
  completion:
    enabled: false
    provider: grilld

limits:
  # Budget per task class
  max_l1_calls: 1   # L1: ordinary multi-step
  max_l2_calls: 3   # L2: long-running (reserve 1 for final review)
  max_l3_calls: 4   # L3: high-risk (reserve 1 for plan + 1 for final)
"""

def create_config(scope="project"):
    if scope == "project":
        cfg_dir = pathlib.Path("state/know-your-limits")
        cfg_path = cfg_dir / "config.yaml"
        desc = "project-level"
    else:  # user
        cfg_dir = pathlib.Path.home() / ".kyl"
        cfg_path = cfg_dir / "config.yaml"
        desc = "user-level"
    
    if cfg_path.exists():
        print(f"Config already exists: {cfg_path}")
        return cfg_path
    
    cfg_dir.mkdir(parents=True, exist_ok=True)
    with open(cfg_path, "w") as f:
        f.write(DEFAULT_CONFIG)
    
    print(f"✅ Created {desc} config: {cfg_path}")
    print("   Edit this file to customize escalation behavior.")
    return cfg_path

def main():
    scope = sys.argv[1] if len(sys.argv) > 1 else "project"
    if scope not in ("project", "user"):
        print(f"Usage: {sys.argv[0]} [project|user]")
        sys.exit(1)
    
    create_config(scope)

if __name__ == "__main__":
    main()
