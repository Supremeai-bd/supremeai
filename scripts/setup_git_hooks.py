#!/usr/bin/env python3
"""Enable shared SupremeAI git hooks for this clone.

Run once per clone/agent worktree:
    python scripts/setup_git_hooks.py
"""
import shutil, subprocess, sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
src = root / "scripts" / "pre_push_shared.sh"
dst_dir = root / ".git" / "hooks"
if not src.is_file():
    print("ERROR: scripts/pre_push_shared.sh not found")
    sys.exit(1)
dst_dir.mkdir(parents=True, exist_ok=True)
dst = dst_dir / "pre-push"
shutil.copy2(src, dst)
try:
    dst.chmod(0o755)
except Exception:
    pass
subprocess.run(["git", "config", "core.hooksPath", str(dst_dir)], check=True, cwd=root)
print("Git hooks installed:", dst)
print("Hooks active: pre-push (behind-main check + zero-regression gate)")
