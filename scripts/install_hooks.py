#!/usr/bin/env python3
"""
install_hooks.py — SupremeAI Git Hook Installer
================================================
Installs pre_commit_hook.py as the git pre-commit hook.
Safe to re-run: backs up any existing hook before replacing.

Usage: python scripts/install_hooks.py
"""

import os
import sys
import shutil
import stat
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
GIT_HOOKS_DIR = ROOT_DIR / ".git" / "hooks"
HOOK_SOURCE = ROOT_DIR / "scripts" / "pre_commit_hook.py"
HOOK_DEST = GIT_HOOKS_DIR / "pre-commit"
PYTHON = sys.executable


def main():
    # Validate .git exists
    if not GIT_HOOKS_DIR.exists():
        print("[ERROR] .git/hooks directory not found. Are you in the repo root?")
        sys.exit(1)

    # Validate source script exists
    if not HOOK_SOURCE.exists():
        print(f"[ERROR] Hook source not found: {HOOK_SOURCE}")
        sys.exit(1)

    # Backup existing hook
    if HOOK_DEST.exists():
        backup = HOOK_DEST.with_suffix(".bak")
        shutil.copy2(HOOK_DEST, backup)
        print(f"[INFO] Existing hook backed up -> {backup}")

    # Write the hook wrapper (shell script that calls our Python hook)
    # On Windows, Git Bash uses sh/bash for hooks — write a sh wrapper
    hook_content = f"""#!/bin/sh
# SupremeAI Pre-Commit Hook (auto-installed by install_hooks.py)
# Runs: rotate_lessons.py + checkpoint_update.py
"{PYTHON.replace(chr(92), '/')}" "{HOOK_SOURCE.as_posix()}"
"""

    HOOK_DEST.write_text(hook_content, encoding="utf-8")

    # Make executable (needed on Unix; harmless on Windows)
    current_mode = HOOK_DEST.stat().st_mode
    HOOK_DEST.chmod(current_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    print(f"[OK] Pre-commit hook installed: {HOOK_DEST}")
    print(f"     Python: {PYTHON}")
    print(f"     Hook script: {HOOK_SOURCE}")
    print("\n[INFO] Test it: git commit --allow-empty -m 'test hook'")
    print("[INFO] Remove it: del .git\\hooks\\pre-commit")


if __name__ == "__main__":
    main()
