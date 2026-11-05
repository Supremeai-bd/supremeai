#!/usr/bin/env python3
"""Enable shared SupremeAI git hooks for this clone.

Run once per clone/agent worktree:
    python scripts/setup_git_hooks.py
"""
import subprocess, sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
hooks = root / ".githooks"
if not hooks.is_dir():
    print("ERROR: .githooks/ not found")
    sys.exit(1)

subprocess.run(["git", "config", "core.hooksPath", str(hooks)], check=True, cwd=root)
print("Git hooks path set to", hooks)
print("Hooks active: pre-push (behind-main check + zero-regression gate)")
