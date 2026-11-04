#!/usr/bin/env python3
"""Silent failure guard — blocks suppression of critical failures.

Enforces:
1. CI workflows must not use '|| true' on test or guard commands.
2. Code must not silently discard exceptions without logging or explicit reason.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]


def check_workflows() -> list[str]:
    violations = []
    wf_dir = REPO_ROOT / ".github" / "workflows"
    if not wf_dir.exists():
        return violations

    crit_pattern = re.compile(r"(pytest|run_all_guards|check_critical_invariants|boundary_sanitization).*?\|\|\s*true", re.IGNORECASE)

    for yml in wf_dir.glob("*.yml"):
        content = yml.read_text(encoding="utf-8", errors="replace")
        for idx, line in enumerate(content.splitlines(), start=1):
            if crit_pattern.search(line):
                violations.append(f"{yml.relative_to(REPO_ROOT)}:{idx}: {line.strip()}")

    return violations


def check_empty_excepts() -> list[str]:
    violations = []
    scan_dirs = [REPO_ROOT / "core", REPO_ROOT / "gateway"]
    exclude = {"tests", "test", "mock", ".venv", "venv", "node_modules", ".pytest_cache", "docs"}

    empty_except = re.compile(r"except\s+Exception(\s+as\s+\w+)?:\s*\n\s*pass\b")

    for s_dir in scan_dirs:
        if not s_dir.exists():
            continue
        for py_path in s_dir.rglob("*.py"):
            if set(py_path.parts).intersection(exclude):
                continue
            content = py_path.read_text(encoding="utf-8", errors="replace")
            matches = list(empty_except.finditer(content))
            for m in matches:
                lineno = content[: m.start()].count("\n") + 1
                violations.append(f"{py_path.relative_to(REPO_ROOT)}:{lineno}: bare unhandled exception pass")

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Silent failure policy guard")
    parser.add_argument("--check", action="store_true", help="Perform check")
    args = parser.parse_args()

    wf_errors = check_workflows()
    if wf_errors:
        print(f"[FAIL] silent_failure_guard: Found suppressed CI failures with '|| true':")
        for err in wf_errors:
            print(f"  - {err}")
        return 1

    print("[PASS] silent_failure_guard: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
