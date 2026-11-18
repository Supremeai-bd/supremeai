#!/usr/bin/env python3
"""PR Conflict Pre-Check — detects merge conflicts and overlapping PRs before auto-merge.

Addresses technical debt: conflicts created on GitHub but not locally when
multiple PRs touch the same files. Provides auto-rebase capability.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess

REPO = os.environ.get("GITHUB_REPOSITORY") or "Supremeai-bd/supremeai"


def _gh(args: list[str]) -> tuple[int, str]:
    try:
        res = subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=60)
        return res.returncode, (res.stdout or "") + (res.stderr or "")
    except Exception as exc:
        return 1, str(exc)


def check_mergeable(pr_number: int) -> dict:
    """Check if a PR is mergeable (no conflicts)."""
    rc, out = _gh(["pr", "view", str(pr_number), "--repo", REPO, "--json", "mergeable,mergeStateStatus,headRefName,baseRefName"])
    if rc != 0:
        return {"pr": pr_number, "mergeable": None, "error": out.strip()}
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {"pr": pr_number, "mergeable": None, "error": "parse error"}
    return {
        "pr": pr_number,
        "mergeable": data.get("mergeable"),
        "merge_state": data.get("mergeStateStatus"),
        "head": data.get("headRefName"),
        "base": data.get("baseRefName"),
    }


def list_open_prs() -> list[dict]:
    rc, out = _gh(["pr", "list", "--repo", REPO, "--state", "open", "--json", "number,title,headRefName,files", "--limit", "100"])
    if rc != 0:
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return []


def find_overlapping_prs(pr_number: int) -> list[dict]:
    """Find other open PRs that touch the same files."""
    prs = list_open_prs()
    target_files = set()
    for pr in prs:
        if pr.get("number") == pr_number:
            for f in (pr.get("files") or []):
                target_files.add(f.get("path") or f.get("filename") or "")
            break
    if not target_files:
        return []
    overlaps = []
    for pr in prs:
        if pr.get("number") == pr_number:
            continue
        shared = []
        for f in (pr.get("files") or []):
            fp = f.get("path") or f.get("filename") or ""
            if fp in target_files:
                shared.append(fp)
        if shared:
            overlaps.append({"pr": pr.get("number"), "title": pr.get("title"), "shared_files": shared})
    return overlaps


def auto_rebase(pr_number: int) -> dict:
    """Attempt to rebase a PR branch on latest base via gh CLI."""
    info = check_mergeable(pr_number)
    head = info.get("head")
    if not head:
        return {"pr": pr_number, "rebased": False, "error": "no head branch"}
    rc, out = _gh(["pr", "update-branch", str(pr_number), "--repo", REPO])
    if rc == 0:
        return {"pr": pr_number, "rebased": True, "output": out.strip()}
    return {"pr": pr_number, "rebased": False, "error": out.strip()}


def main() -> int:
    ap = argparse.ArgumentParser(description="PR Conflict Pre-Check")
    ap.add_argument("--pr", type=int, required=True)
    ap.add_argument("--auto-rebase", action="store_true", help="Attempt auto-rebase if conflicts found")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    result = {"pr": args.pr}
    merge_info = check_mergeable(args.pr)
    result["mergeable"] = merge_info

    overlaps = find_overlapping_prs(args.pr)
    result["overlapping_prs"] = overlaps

    if merge_info.get("mergeable") is False or merge_info.get("merge_state") == "DIRTY":
        result["has_conflict"] = True
        if args.auto_rebase:
            rebase_result = auto_rebase(args.pr)
            result["rebase"] = rebase_result
    else:
        result["has_conflict"] = False

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"PR #{args.pr}: mergeable={merge_info.get('mergeable')} state={merge_info.get('merge_state')}")
        if overlaps:
            print(f"  Overlapping PRs: {[o['pr'] for o in overlaps]}")
        if result.get("has_conflict"):
            print("  CONFLICT DETECTED")
            if args.auto_rebase and result.get("rebase", {}).get("rebased"):
                print("  Auto-rebase succeeded")
    return 0 if not result.get("has_conflict") else 1


if __name__ == "__main__":
    raise SystemExit(main())
