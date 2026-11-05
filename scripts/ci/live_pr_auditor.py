#!/usr/bin/env python3
"""live_pr_auditor.py — Guardian gate: audit open PRs across the 3 primary repos.

Pure functions operate on PR dicts so the gate is fully offline-testable. A thin
CLI reads a JSON file (--input) of PR records and reports violations.

PR record shape (all fields optional except number/repo):
  {
    "repo": "Supremeai-bd/supremeai",
    "number": 123,
    "title": "...",
    "body": "PR description",
    "draft": false,
    "base": "main",
    "head": "feat/x",
    "commits_behind": 0,
    "checks": [{"name": "ci", "conclusion": "success"}],
    "files": ["scripts/ci/foo.py"]
  }
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ISSUE_RE = re.compile(r"(Closes|Fixes|Refs|Resolves)\s+#\d+", re.IGNORECASE)
REFLECTION_RE = re.compile(r"##\s+Reflection Evidence", re.IGNORECASE)
VERIFY_RE = re.compile(r"(3[- ]?Tier|Test Evidence)", re.IGNORECASE)
DOMAIN_PREFIXES = ("studio/", "gateway/", "core/", "browser/", "vscode/")


def _violations_for_pr(pr: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    repo = pr.get("repo", "?")
    num = pr.get("number", "?")
    tag = f"{repo}#{num}"
    body = pr.get("body") or ""

    if pr.get("draft"):
        errs.append(f"{tag}: draft PR must not be merged")
    if not ISSUE_RE.search(body):
        errs.append(f"{tag}: missing issue reference (Closes/Fixes/Refs/Resolves #N)")
    if not REFLECTION_RE.search(body):
        errs.append(f"{tag}: missing '## Reflection Evidence' header")
    if not VERIFY_RE.search(body):
        errs.append(f"{tag}: missing '3-Tier Verify' or 'Test Evidence' section")

    behind = pr.get("commits_behind", 0) or 0
    try:
        if int(behind) > 0:
            errs.append(f"{tag}: stale base ({behind} commit(s) behind main)")
    except (TypeError, ValueError):
        pass

    for check in pr.get("checks") or []:
        conclusion = (check.get("conclusion") or "").lower()
        if conclusion in ("failure", "cancelled", "timed_out", "action_required"):
            errs.append(f"{tag}: CI check '{check.get('name', '?')}' is {conclusion}")

    # cross-domain contamination on changed files
    branch = pr.get("head") or ""
    domain = None
    for d in ("studio", "gateway", "core", "browser", "vscode"):
        if f"/{d}-" in branch or f"/{d}/" in branch:
            domain = d
            break
    if domain:
        for f in pr.get("files") or []:
            fn = str(f).replace("\\", "/")
            if fn.startswith(("docs/", "tests/", ".agents/", "scripts/ci/")):
                continue
            for other in ("studio", "gateway", "core", "browser", "vscode"):
                if other != domain and fn.startswith(f"{other}/"):
                    errs.append(f"{tag}: cross-domain collision '{fn}' on {domain}-scoped PR")

    return errs


def audit_prs(prs: list[dict[str, Any]]) -> dict[str, Any]:
    all_errors: list[str] = []
    audited = 0
    for pr in prs or []:
        audited += 1
        all_errors.extend(_violations_for_pr(pr))
    return {"audited": audited, "violations": all_errors, "ok": not all_errors}


def load_input(path: str) -> list[dict[str, Any]]:
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    data = json.loads(raw)
    if isinstance(data, dict):
        # allow {"prs": [...]} or {"pull_requests": [...]}
        for key in ("prs", "pull_requests", "pullRequests"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]
    if isinstance(data, list):
        return data
    return []


def self_test() -> int:
    fails = 0
    good = {
        "repo": "r", "number": 1, "draft": False,
        "body": "Closes #1\n## Reflection Evidence\n3-Tier Verify passed",
        "commits_behind": 0,
        "checks": [{"name": "ci", "conclusion": "success"}],
        "head": "feat/foo", "files": ["scripts/ci/x.py"],
    }
    if _violations_for_pr(good):
        fails += 1
        print("FAIL good-pr")
    else:
        print("PASS good-pr")
    bad = {
        "repo": "r", "number": 2, "draft": True,
        "body": "no ref",
        "commits_behind": 3,
        "checks": [{"name": "ci", "conclusion": "failure"}],
        "head": "feat/studio-x", "files": ["core/engine/y.py"],
    }
    v = _violations_for_pr(bad)
    expected_min = 5
    if len(v) < expected_min:
        fails += 1
        print(f"FAIL bad-pr (got {len(v)}, want >= {expected_min}): {v}")
    else:
        print(f"PASS bad-pr ({len(v)} violations)")
    res = audit_prs([good, bad])
    if res["audited"] != 2 or res["ok"]:
        fails += 1
        print("FAIL audit-summary")
    else:
        print("PASS audit-summary")
    print("self-test: %d failure(s)" % fails)
    return 0 if fails == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=None, help="JSON file of PR records")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.input:
        print("live_pr_auditor: no --input provided; use --self-test", file=sys.stderr)
        return 2
    prs = load_input(args.input)
    res = audit_prs(prs)
    print(json.dumps(res, indent=2))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
