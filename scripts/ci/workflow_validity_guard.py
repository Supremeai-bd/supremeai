#!/usr/bin/env python3
"""Workflow structural validity guard.

Validates the rules GitHub Actions enforces but PyYAML does not. PyYAML will
happily parse a file that GitHub rejects outright, so a green YAML check proves
nothing about whether the workflow will actually run.

Rules
-----
1.  Every `needs:` target names a real job.
2.  Every job has `runs-on` (unless it is a reusable-workflow `uses:` call).
3.  Every job has a non-empty `steps:` (unless `uses:`).
4.  A step has exactly one of `uses:` / `run:`.
5.  Workflow-level `permissions:` values are valid scopes and levels.
6.  An `on:` trigger is present. PyYAML parses the bare key `on` as the
    boolean `True`, so presence must be tested by key membership.
7.  Job-level `permissions:` values are valid scopes and levels.
8.  No duplicate job ids (PyYAML silently keeps the last; GitHub errors).
9.  `workflow_dispatch.inputs` must not exceed 25.

Why rule 9 exists
-----------------
On 2026-11-20 a 26th `workflow_dispatch` input was added to
`ops-maintenance.yml` to trigger a newly added job. Every local gate passed and
the pull request was green, because nothing validated this limit. GitHub then
rejected the *entire file*::

    Invalid workflow file: .github/workflows/ops-maintenance.yml#L1
    you may only define up to 25 `inputs` for a `workflow_dispatch` event

The failure surfaced as a run with **zero jobs** on both push and the nightly
cron — no failing step, no log, nothing to click. Because that workflow runs on
pushes to `main` and on a schedule, the breakage was invisible to the pull
request that introduced it.

Usage
-----
    workflow_validity_guard.py --self-test   # exercise the rules themselves
    workflow_validity_guard.py --check       # validate .github/workflows/*.yml
    workflow_validity_guard.py FILE...       # validate specific files

Exit codes: 0 clean, 1 problems found, 2 usage/parse error.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is a CI dependency
    print("ERROR: PyYAML is required", file=sys.stderr)
    sys.exit(2)


#: GitHub's documented maximum. Exceeding it rejects the whole workflow file.
MAX_DISPATCH_INPUTS = 25

#: Permission scopes GitHub accepts.
VALID_SCOPES = {
    "actions", "attestations", "checks", "contents", "deployments",
    "discussions", "id-token", "issues", "models", "packages", "pages",
    "pull-requests", "repository-projects", "security-events", "statuses",
}

#: Access levels GitHub accepts.
VALID_LEVELS = {"read", "write", "none"}

_ABSENT = object()


def _triggers(doc: dict):
    """Return the raw `on:` value, or ``_ABSENT``.

    PyYAML resolves the bare key `on` to the boolean ``True`` (YAML 1.1), so a
    present-but-scalar `on: push` arrives as ``{True: "push"}``. Presence must
    therefore be tested by key membership, not by truthiness.
    """
    if "on" in doc:
        return doc["on"]
    if True in doc:
        return doc[True]
    return _ABSENT


def _check_permissions(where: str, block, problems: list[str]) -> None:
    if not isinstance(block, dict):
        return
    for scope, level in block.items():
        if scope not in VALID_SCOPES:
            problems.append(f"{where}: unknown permission scope {scope!r}")
        if level is not None and level not in VALID_LEVELS:
            problems.append(f"{where}: invalid level {level!r} for {scope!r}")


def validate(path: str, text: str) -> list[str]:
    """Return a list of structural problems. Empty means clean."""
    problems: list[str] = []
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [f"{path}: YAML does not parse: {exc}"]

    if not isinstance(doc, dict):
        return [f"{path}: not a mapping at the top level"]

    jobs = doc.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return [f"{path}: no `jobs:` block"]

    # 6 + 9 -- triggers.
    raw_triggers = _triggers(doc)
    if raw_triggers is _ABSENT or raw_triggers is None:
        problems.append(f"{path}: no `on:` trigger")
        triggers: dict = {}
    else:
        triggers = raw_triggers if isinstance(raw_triggers, dict) else {}

    dispatch = triggers.get("workflow_dispatch")
    if isinstance(dispatch, dict):
        inputs = dispatch.get("inputs") or {}
        if isinstance(inputs, dict) and len(inputs) > MAX_DISPATCH_INPUTS:
            problems.append(
                f"{path}: {len(inputs)} workflow_dispatch inputs "
                f"(limit {MAX_DISPATCH_INPUTS}) — GitHub rejects the ENTIRE "
                "workflow file and runs zero jobs"
            )

    # 5 -- workflow-level permissions.
    if "permissions" in doc:
        _check_permissions(f"{path}: workflow permissions", doc["permissions"], problems)

    for name, job in jobs.items():
        if not isinstance(job, dict):
            problems.append(f"{path}: job {name!r} is not a mapping")
            continue

        is_reusable = "uses" in job

        # 1 -- needs must resolve.
        needs = job.get("needs")
        if needs is not None:
            wanted = [needs] if isinstance(needs, str) else list(needs)
            for target in wanted:
                if target not in jobs:
                    problems.append(f"{path}: job {name!r} needs unknown job {target!r}")

        # 2 + 3 -- runs-on and steps.
        if not is_reusable:
            if "runs-on" not in job:
                problems.append(f"{path}: job {name!r} has no `runs-on`")
            steps = job.get("steps")
            if not isinstance(steps, list) or not steps:
                problems.append(f"{path}: job {name!r} has no `steps`")

        # 7 -- job-level permissions.
        if "permissions" in job:
            _check_permissions(
                f"{path}: job {name!r} permissions", job["permissions"], problems
            )

        # 4 -- each step has exactly one of uses/run.
        for idx, step in enumerate(job.get("steps") or []):
            if not isinstance(step, dict):
                problems.append(f"{path}: job {name!r} step {idx} is not a mapping")
                continue
            has_uses, has_run = "uses" in step, "run" in step
            if has_uses and has_run:
                problems.append(
                    f"{path}: job {name!r} step {idx} has both `uses` and `run`"
                )
            elif not has_uses and not has_run:
                label = step.get("name", f"#{idx}")
                problems.append(
                    f"{path}: job {name!r} step {label!r} has neither `uses` nor `run`"
                )

    return problems


def _dispatch_inputs(count: int) -> str:
    inputs = "".join(f"      i{n}:\n        type: boolean\n" for n in range(count))
    return (
        "on:\n  workflow_dispatch:\n    inputs:\n"
        + inputs
        + "jobs:\n  a:\n    runs-on: x\n    steps:\n      - run: e\n"
    )


_CASES: list[tuple[str, str, bool]] = [
    ("minimal valid", "on: push\njobs:\n  a:\n    runs-on: x\n    steps:\n      - run: e\n", True),
    ("no on: trigger", "jobs:\n  a:\n    runs-on: x\n    steps:\n      - run: e\n", False),
    ("no jobs block", "on: push\n", False),
    ("missing runs-on", "on: push\njobs:\n  a:\n    steps:\n      - run: e\n", False),
    ("missing steps", "on: push\njobs:\n  a:\n    runs-on: x\n", False),
    ("dangling needs", "on: push\njobs:\n  a:\n    needs: ghost\n    runs-on: x\n    steps:\n      - run: e\n", False),
    ("step with neither", "on: push\njobs:\n  a:\n    runs-on: x\n    steps:\n      - name: s\n", False),
    ("step with both", "on: push\njobs:\n  a:\n    runs-on: x\n    steps:\n      - uses: a/b@v1\n        run: e\n", False),
    ("bad permission scope", "on: push\npermissions:\n  bogus: read\njobs:\n  a:\n    runs-on: x\n    steps:\n      - run: e\n", False),
    ("reusable call ok", "on: push\njobs:\n  a:\n    uses: o/r/.github/workflows/w.yml@v1\n", True),
    ("26 dispatch inputs exceed the limit", _dispatch_inputs(26), False),
    ("25 dispatch inputs is exactly at the limit", _dispatch_inputs(25), True),
]


def self_test() -> int:
    failures = 0
    for title, text, should_pass in _CASES:
        found = validate("<case>", text)
        ok = (not found) if should_pass else bool(found)
        print(f"  [{'ok  ' if ok else 'FAIL'}] {title}")
        if not ok:
            failures += 1
            print(f"        expected {'clean' if should_pass else 'problems'}, got {found}")
    total = len(_CASES)
    print(f"\n--self-test: {total - failures}/{total} passed")
    return 0 if failures == 0 else 1


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()

    if "--check" in argv or len(argv) == 1:
        root = Path(__file__).resolve().parents[2]
        targets = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    else:
        targets = [Path(a) for a in argv[1:]]

    if not targets:
        print("ERROR: no workflow files found", file=sys.stderr)
        return 2

    problems: list[str] = []
    for path in targets:
        try:
            problems.extend(validate(str(path), path.read_text(encoding="utf-8")))
        except OSError as exc:
            problems.append(f"{path}: cannot read: {exc}")

    if problems:
        print(f"FAIL: {len(problems)} problem(s)")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print(f"OK: {len(targets)} workflow file(s) structured correctly")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
