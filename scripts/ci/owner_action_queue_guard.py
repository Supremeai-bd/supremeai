#!/usr/bin/env python3
"""Lint the Owner Action Queue issue (owner-action-queue v1) - admin-only done edits.

Owner policy: agents may ONLY append new tasks (unique OA-NNN ids, added_by, date);
only the admin may mark a task done. This guard lints the live issue body via the
GitHub API (or --stdin for offline tests) and fails loud on:

- missing/duplicate owner-action-queue v1 marker block
- duplicate task ids (OA-NNN)
- entries missing id/title/added_by/date or with an unknown status
- ``status: done`` without ``done_by: admin`` (agents must never flip to done)
- ``status: pending`` that carries done_by/done_date (pre-marked entry)
- a Done-section entry that still sits in Pending (section/status mismatch)

Usage:
    python scripts/ci/owner_action_queue_guard.py --check                # live issue
    python scripts/ci/owner_action_queue_guard.py --check --issue 966
    python scripts/ci/owner_action_queue_guard.py --self-test            # offline
    cat body.md | python scripts/ci/owner_action_queue_guard.py --stdin  # offline
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

MARKER_OPEN = "<!-- owner-action-queue v1 -->"
MARKER_CLOSE = "<!-- /owner-action-queue v1 -->"
DEFAULT_ISSUE = 966
REPO = os.getenv("GH_REPO") or os.getenv("GITHUB_REPOSITORY") or "Supremeai-bd/supremeai"

ID_RE = re.compile(r"id:\s*(OA-\d+)")
STATUS_RE = re.compile(r"status:\s*(pending|done)")
DONE_BY_RE = re.compile(r"done_by:\s*([A-Za-z_-]+)")
TITLE_RE = re.compile(r"title:\s*([^|]+)")
ADDED_BY_RE = re.compile(r"added_by:\s*([A-Za-z0-9:_-]+)")
DATE_RE = re.compile(r"date:\s*(\d{4}-\d{2}-\d{2})")
ENTRY_RE = re.compile(r"^\s*-\s*\[( |x)\]")


def _extract_block(body: str) -> str:
    start = body.find(MARKER_OPEN)
    if start < 0:
        raise ValueError("missing marker: <!-- owner-action-queue v1 -->")
    end = body.find(MARKER_CLOSE, start)
    if end < 0:
        raise ValueError("unmatched closing marker")
    return body[start + len(MARKER_OPEN) : end]


def lint_queue(body: str) -> list[str]:
    """Return a list of problems; empty list = the queue is well-formed."""
    problems: list[str] = []
    try:
        block = _extract_block(body)
    except ValueError as exc:
        return [str(exc)]

    # Queue entries outside the marker block are invisible to this lint and to
    # the protocol - flag any `- [ ] id: OA-` line before the opening marker.
    preamble = body[: body.find(MARKER_OPEN)]
    for raw_line in preamble.splitlines():
        if ENTRY_RE.match(raw_line) and ID_RE.search(raw_line):
            problems.append(
                f"queue entry found OUTSIDE the marker block (move it inside Pending): {raw_line.strip()[:80]}"
            )

    pending_section, done_section = block, ""
    done_idx = block.lower().find("### done")
    if done_idx >= 0:
        pending_section, done_section = block[:done_idx], block[done_idx:]

    seen_ids: dict[str, str] = {}
    for section_name, section_text, expected_status in (
        ("Pending", pending_section, "pending"),
        ("Done", done_section, "done"),
    ):
        for raw_line in section_text.splitlines():
            if not ENTRY_RE.match(raw_line):
                continue
            line = raw_line.strip()
            id_match = ID_RE.search(line)
            if not id_match:
                problems.append(f"entry without unique id in {section_name}: {line[:80]}")
                continue
            task_id = id_match.group(1)
            if task_id in seen_ids:
                problems.append(
                    f"duplicate task id {task_id} (already used in {seen_ids[task_id]})"
                )
            else:
                seen_ids[task_id] = section_name
            status_match = STATUS_RE.search(line)
            if not status_match:
                problems.append(f"{task_id}: missing status (pending|done)")
                continue
            status = status_match.group(1)
            if status != expected_status:
                problems.append(
                    f"{task_id}: status '{status}' but entry sits in the {section_name} section"
                )
            done_by = DONE_BY_RE.search(line)
            if status == "done" and (not done_by or done_by.group(1).lower() != "admin"):
                problems.append(
                    f"{task_id}: done without done_by: admin - only the admin may mark done"
                )
            if status == "pending" and done_by:
                problems.append(f"{task_id}: pending entry must not carry done_by")
            if not TITLE_RE.search(line):
                problems.append(f"{task_id}: missing title")
            if not ADDED_BY_RE.search(line):
                problems.append(f"{task_id}: missing added_by")
            if not DATE_RE.search(line):
                problems.append(f"{task_id}: missing date")
    if not seen_ids:
        problems.append("queue block contains no task entries")
    return problems


def _fetch_issue_body(issue: int) -> str:
    result = subprocess.run(
        ["gh", "api", f"repos/{REPO}/issues/{issue}", "--jq", ".body"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout or ""


SELF_TEST_BODIES = {
    "clean": (
        "intro text\n"
        "<!-- owner-action-queue v1 -->\n"
        "### Pending\n"
        "- [ ] id: OA-001 | title: set eval secret | added_by: agent:x | date: 2026-11-28 | status: pending\n"
        "### Done (admin-only edits)\n"
        "- [x] id: OA-000 | title: bootstrap | added_by: agent:x | date: 2026-11-27 | done_by: admin | status: done\n"
        "<!-- /owner-action-queue v1 -->\n"
    ),
    "duplicate_id": (
        "<!-- owner-action-queue v1 -->\n"
        "### Pending\n"
        "- [ ] id: OA-001 | title: a | added_by: agent:x | date: 2026-11-28 | status: pending\n"
        "- [ ] id: OA-001 | title: b | added_by: agent:x | date: 2026-11-28 | status: pending\n"
        "<!-- /owner-action-queue v1 -->\n"
    ),
    "agent_marked_done": (
        "<!-- owner-action-queue v1 -->\n"
        "### Pending\n"
        "- [ ] id: OA-002 | title: a | added_by: agent:x | date: 2026-11-28 | status: pending\n"
        "### Done (admin-only edits)\n"
        "- [x] id: OA-003 | title: b | added_by: agent:x | date: 2026-11-28 | status: done\n"
        "<!-- /owner-action-queue v1 -->\n"
    ),
    "no_marker": "just some body without the marker\n",
    "entry_outside_marker": (
        "notes\n"
        "- [ ] id: OA-009 | title: stray | added_by: agent:x | date: 2026-11-28 | status: pending\n"
        "<!-- owner-action-queue v1 -->\n"
        "### Pending\n"
        "- [ ] id: OA-001 | title: real | added_by: agent:x | date: 2026-11-28 | status: pending\n"
        "<!-- /owner-action-queue v1 -->\n"
    ),
}


def self_test() -> int:
    checks = [
        ("clean", []),
        ("duplicate_id", ["duplicate task id OA-001"]),
        ("agent_marked_done", ["done without done_by: admin"]),
        ("no_marker", ["missing marker"]),
        ("entry_outside_marker", ["OUTSIDE the marker block"]),
    ]
    failed = False
    for name, expected in checks:
        problems = lint_queue(SELF_TEST_BODIES[name])
        ok = len(problems) == len(expected) and all(
            any(exp in problem for problem in problems) for exp in expected
        )
        print(f"[{'PASS' if ok else 'FAILED'}] self-test {name}")
        failed = failed or not ok
    print(f"[{'PASS' if not failed else 'FAILED'}] owner-action-queue self-test")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="lint the live issue body")
    parser.add_argument("--issue", type=int, default=DEFAULT_ISSUE)
    parser.add_argument("--stdin", action="store_true", help="lint a body from stdin")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()
    try:
        body = sys.stdin.read() if args.stdin else _fetch_issue_body(args.issue)
    except subprocess.CalledProcessError as exc:
        print(f"::warning::Could not fetch issue #{args.issue}: {exc.stderr[:200]}")
        return 2
    problems = lint_queue(body)
    if problems:
        print(f"[FAILED] Owner Action Queue lint - {len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"[PASS] Owner Action Queue #{args.issue} is well-formed (unique ids, admin-only done)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
