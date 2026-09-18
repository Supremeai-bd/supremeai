#!/usr/bin/env python3
"""SupremeAI Git Pre-Push Hook.
============================
Ensures:
  1. Pull-Before-Push: Verifies that local tracking branch is not behind remote.
     If remote has newer commits, prevents pushing until `git pull --rebase` is performed.
  2. Zero New Regressions: Runs the learned-regression scanner
     (`python scripts/quality/regression_scanner.py --path backend --fail-on critical,high`).
     If any CRITICAL or HIGH findings exist, aborts the push immediately.

Install:
  Included in .git/hooks/pre-push
"""

from __future__ import annotations

import os
import subprocess
import sys

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError) as _exc:
        _ = _exc

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = sys.executable


def get_current_branch() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "main"


def check_remote_up_to_date(branch: str) -> bool:
    """Fetch remote and verify local HEAD is not behind remote tracking branch."""
    print(f"\n[PRE-PUSH 1/2] Checking if local '{branch}' is up-to-date with remote...")
    try:
        remote_check = subprocess.run(
            ["git", "remote"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        if "origin" not in remote_check.stdout:
            print("  [PRE-PUSH] No 'origin' remote configured, skipping remote check.")
            return True

        subprocess.run(
            ["git", "fetch", "origin", branch, "--quiet"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        rev_count = subprocess.run(
            ["git", "rev-list", "--count", f"HEAD..origin/{branch}"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        if rev_count.returncode == 0:
            behind_count = int(rev_count.stdout.strip() or "0")
            if behind_count > 0:
                print(
                    f"\n❌ [PRE-PUSH BLOCKED] Local '{branch}' is behind 'origin/{branch}' by {behind_count} commit(s)!\n"
                    f"👉 MANDATORY PULL-BEFORE-PUSH: Please run:\n"
                    f"    git pull --rebase origin {branch}\n"
                    f"and re-verify tests and regression scanner before pushing.\n",
                    file=sys.stderr,
                )
                return False
        print("  [OK] Local branch is up-to-date with remote.")
        return True
    except (subprocess.SubprocessError, OSError) as e:
        print(f"  [WARN] Remote check skipped ({e}). Proceeding to regression scan.")
        return True


def check_regression_scanner() -> bool:
    """Run regression scanner to ensure zero critical or high findings."""
    print("\n[PRE-PUSH 2/2] Running SupremeAI Regression Scanner on backend...")
    scanner_path = os.path.join(ROOT_DIR, "scripts", "quality", "regression_scanner.py")
    if not os.path.exists(scanner_path):
        print(f"  [WARN] Regression scanner script not found: {scanner_path}")
        return True

    cmd = [
        PYTHON,
        scanner_path,
        "--path",
        "backend",
        "--fail-on",
        "critical,high",
    ]
    res = subprocess.run(cmd, cwd=ROOT_DIR, check=False)
    if res.returncode != 0:
        print(
            "\n❌ [PRE-PUSH BLOCKED] Regression scan failed with critical/high findings!\n"
            "👉 Please resolve the regression scanner findings before pushing to remote.\n",
            file=sys.stderr,
        )
        return False
    print("  [OK] Regression scanner passed (0 critical, 0 high).")
    return True


def main() -> int:
    branch = get_current_branch()
    if not check_remote_up_to_date(branch):
        return 1
    if not check_regression_scanner():
        return 1
    print("\n✅ [PRE-PUSH] All pre-push checks passed! Proceeding with git push.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
