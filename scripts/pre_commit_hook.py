#!/usr/bin/env python3
"""
SupremeAI Git Pre-Commit Hook
==============================
Runs automatically on every `git commit`:
  1. rotate_lessons.py  — Enforces 12KB cap on LESSONS_LEARNED.md (archives if over limit)
  2. checkpoint_update.py — Updates CHECKPOINT.md with current session state

Install:
  python scripts/install_hooks.py
  (or manually: copy this file to .git/hooks/pre-commit)
"""

import subprocess
import sys
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")
PYTHON = sys.executable


def run_script(script_name: str, args: list[str] = []) -> bool:
    """Run a script and return True if successful."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.exists(script_path):
        print(f"[WARN] Script not found, skipping: {script_path}")
        return True  # Non-blocking — don't fail commit if script missing

    try:
        result = subprocess.run(
            [PYTHON, script_path] + args,
            cwd=ROOT_DIR,
            capture_output=False,  # Show output live
            text=True,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[WARN] Failed to run {script_name}: {e}")
        return True  # Non-blocking


def main():
    print("\n[PRE-COMMIT] SupremeAI hook running...")
    print("-" * 50)

    # Step 1: Rotate LESSONS_LEARNED.md if over 12KB cap
    print("[1/2] Checking LESSONS_LEARNED.md size...")
    run_script("rotate_lessons.py")

    # Step 2: Update CHECKPOINT.md
    print("\n[2/2] Updating CHECKPOINT.md...")
    run_script("checkpoint_update.py", ["--message", "Auto-updated via pre-commit hook"])

    # Stage any changes made by the scripts above
    try:
        files_to_stage = ["CHECKPOINT.md", "LESSONS_LEARNED.md", "docs/archive/"]
        for f in files_to_stage:
            full_path = os.path.join(ROOT_DIR, f)
            if os.path.exists(full_path):
                subprocess.run(
                    ["git", "add", f],
                    cwd=ROOT_DIR,
                    capture_output=True
                )
    except Exception:
        pass

    print("-" * 50)
    print("[PRE-COMMIT] Done. Proceeding with commit.\n")
    sys.exit(0)  # Always allow commit — hook is advisory, not blocking


if __name__ == "__main__":
    main()
