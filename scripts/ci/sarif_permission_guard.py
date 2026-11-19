#!/usr/bin/env python3
"""sarif_permission_guard.py — a SARIF upload without `security-events: write`
always fails, and it fails only on `main`.

Defect this guard exists for (observed 2026-11-19, twice: PR #685 and PR #686):
`.github/workflows/gateway-image.yml` ran `github/codeql-action/upload-sarif`
while the workflow's `permissions:` granted only `contents: read` and
`packages: write`. The build, the Trivy scan and the summary all succeeded; the
upload step died with a permission error. Because the step only runs on `main`
(PR runs never push/serve SARIF), every PR was green and every merge to `main`
turned red — the failure was invisible to the gate that was supposed to catch it.

Rule enforced: if a workflow file references `upload-sarif` (or `codeql-action`
with `sarif_file`), then the *enclosing job* or the workflow-level `permissions:`
block must grant `security-events: write`.

Deliberately stdlib-only and line-based (no PyYAML): this guard has to run on
runners that install nothing, and the failure class is structural — indentation
plus a literal key — not something that needs a full YAML model.

Usage:
    python scripts/ci/sarif_permission_guard.py --check
    python scripts/ci/sarif_permission_guard.py --self-test
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW_DIRS = (".github/workflows", ".github/actions")
UPLOAD_MARKERS = ("upload-sarif", "sarif_file")
REQUIRED = "security-events: write"
JOB_KEY = re.compile(r"^  ([A-Za-z0-9_.-]+):\s*(?:#.*)?$")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _workflow_level_grants(lines: list[str]) -> bool:
    """True when a column-0 `permissions:` block grants security-events: write."""
    for index, line in enumerate(lines):
        if line.rstrip() == "permissions:":
            for follow in lines[index + 1:]:
                if not follow.strip():
                    continue
                if _indent(follow) == 0:
                    break
                if follow.strip().replace(" ", "") == REQUIRED.replace(" ", ""):
                    return True
    return False


def _enclosing_job_grants(lines: list[str], line_index: int) -> bool:
    """True when the job owning `line_index` grants security-events: write."""
    start = None
    for index in range(line_index, -1, -1):
        if _indent(lines[index]) == 2 and JOB_KEY.match(lines[index]):
            start = index
            break
    if start is None:
        return False
    for follow in lines[start + 1:]:
        stripped = follow.strip()
        if stripped and _indent(follow) <= 2 and not stripped.startswith("#"):
            break  # next job (or an unrelated column-0 block) — stop scanning
        if stripped.replace(" ", "") == REQUIRED.replace(" ", ""):
            return True
    return False


def audit_text(text: str, name: str = "<text>") -> list[str]:
    """Return one message per SARIF upload that cannot succeed."""
    lines = text.splitlines()
    problems: list[str] = []
    markers = ("upload-sarif",) if "upload-sarif" in text else UPLOAD_MARKERS
    uploads = [
        (index, line.strip())
        for index, line in enumerate(lines)
        if any(marker in line for marker in markers) and not line.strip().startswith("#")
    ]
    if not uploads:
        return []
    if _workflow_level_grants(lines):
        return []
    for index, _line in uploads:
        if not _enclosing_job_grants(lines, index):
            problems.append(
                f"{name}:{index + 1}: SARIF upload without `{REQUIRED}` — the step "
                "cannot succeed on main (add it to the job's or the workflow's "
                "`permissions:`)"
            )
    return problems


def audit_surface(root: pathlib.Path = REPO_ROOT) -> list[str]:
    problems: list[str] = []
    scanned = 0
    for rel in WORKFLOW_DIRS:
        directory = root / rel
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.yml")) + sorted(directory.rglob("*.yaml")):
            scanned += 1
            problems.extend(audit_text(path.read_text(encoding="utf-8"),
                                       str(path.relative_to(root))))
    if scanned == 0:
        problems.append("SURFACE_EMPTY: no workflow files found — nothing verified")
    return problems


def _self_test() -> int:
    cases: list[tuple[str, str, bool]] = [
        (
            "missing permission",
            """name: x
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: github/codeql-action/upload-sarif@v4
        with:
          sarif_file: out.sarif
""",
            False,
        ),
        (
            "job-level permission",
            """name: x
permissions:
  contents: read
jobs:
  build:
    permissions:
      contents: read
      security-events: write
    runs-on: ubuntu-latest
    steps:
      - uses: github/codeql-action/upload-sarif@v4
        with:
          sarif_file: out.sarif
""",
            True,
        ),
        (
            "workflow-level permission",
            """name: x
permissions:
  contents: read
  security-events: write
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: github/codeql-action/upload-sarif@v4
""",
            True,
        ),
        (
            "other job's permission does not count",
            """name: x
permissions:
  contents: read
jobs:
  scan:
    permissions:
      security-events: write
    runs-on: ubuntu-latest
    steps:
      - run: echo nothing
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: github/codeql-action/upload-sarif@v4
""",
            False,
        ),
        ("no upload at all", "name: x\npermissions:\n  contents: read\njobs:\n  a:\n    runs-on: x\n", True),
        ("commented-out upload", "name: x\njobs:\n  a:\n    runs-on: x\n    steps:\n      - run: echo\n        # uses: github/codeql-action/upload-sarif@v4\n", True),
    ]
    failures = 0
    for label, text, should_pass in cases:
        ok = not audit_text(text, label)
        if ok != should_pass:
            failures += 1
            print(f"  [FAIL] {label}: expected {'pass' if should_pass else 'reject'}")
        else:
            print(f"  [ok] {label}")
    print(f"self-test: {len(cases) - failures}/{len(cases)} passed")
    return 0 if failures == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="audit .github/")
    group.add_argument("--self-test", action="store_true", help="run synthetic cases")
    args = parser.parse_args(argv)

    if args.self_test:
        return _self_test()

    problems = audit_surface()
    if problems:
        for problem in problems:
            print(f"  [fail] {problem}")
        print(f"SARIF permission guard: FAIL ({len(problems)} problem(s))")
        return 2
    print("SARIF permission guard: PASS (every SARIF upload may write security events)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
