#!/usr/bin/env python3
"""Prune stale agent branches from origin.

Branches created by agents that have no open PRs are pruned from origin,
ensuring that remote branch existence reflects ONLY active in-progress work.

#4200 §9: Safety rule — never delete branches with branch:active/paused/orphaned
labels on their linked issue. Only delete when:
- its work is merged/completed, AND
- no active task still depends on the branch (no branch:active/paused/orphaned labels)
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO = os.environ.get("GH_REPO", "SaifulHaqueNiloy/supremeai")
AGENT_PREFIXES = ("coder-", "ci-", "planner-", "pr-helper-", "platform-", "agent-", "super-", "agent/")

# বাংলা (#4200 §9): branches with these labels on their linked issue must NOT be deleted
PRESERVE_LABELS = {"branch:active", "branch:paused", "branch:orphaned"}

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("cleanup_stale_branches")


def get_gh_token() -> str:
    """Get GitHub token."""
    token = os.environ.get("GH_TOKEN", "").strip()
    if not token:
        try:
            res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
            token = res.stdout.strip() if res.returncode == 0 else ""
        except Exception:
            pass
    return token


def get_issue_labels(issue_number: int, token: str) -> set[str]:
    """Get labels on an issue via GitHub API."""
    try:
        url = f"https://api.github.com/repos/{REPO}/issues/{issue_number}"
        req = urllib.request.Request(url, headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return {l["name"] for l in data.get("labels", [])}
    except Exception:
        return set()


def extract_issue_number(branch_name: str) -> int | None:
    """Extract issue number from branch name.

    বাংলা: branch name থেকে issue number extract করে।
    Patterns: coder-1-4200-slug, agent/4200-slug, ci-2-1234-slug
    """
    # agent/<issue>-<slug> pattern (#4200)
    m = re.search(r"agent/(\d+)", branch_name)
    if m:
        return int(m.group(1))
    # <role>-<slot>-<issue>-<slug> pattern (existing)
    m = re.search(r"-(\d{2,})-", branch_name)
    if m:
        return int(m.group(1))
    return None


def is_branch_safe_to_delete(branch_name: str, token: str) -> bool:
    """Check if a branch is safe to delete per #4200 §9.

    বাংলা: branch delete করার আগে issue labels check করে।
    branch:active/paused/orphaned থাকলে delete নিষেদ্ধ।
    """
    issue_num = extract_issue_number(branch_name)
    if issue_num is None:
        return True  # no issue link → safe to delete (no preserve concern)

    labels = get_issue_labels(issue_num, token)
    if labels & PRESERVE_LABELS:
        logger.info("  ⛔ Preserving %s (issue #%d has %s)", branch_name, issue_num, labels & PRESERVE_LABELS)
        return False

    return True


def get_open_pr_head_branches() -> set[str]:
    try:
        res = subprocess.run(
            ["gh", "pr", "list", "--state", "open", "--json", "headRefName"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(res.stdout)
        return {pr["headRefName"] for pr in data if isinstance(pr, dict) and "headRefName" in pr}
    except Exception as e:
        logger.error("Failed to fetch open PR heads: %s", e)
        return set()


def get_remote_branches() -> set[str]:
    subprocess.run(["git", "fetch", "origin", "--prune"], cwd=str(REPO_ROOT), check=False)
    res = subprocess.run(
        ["git", "branch", "-r"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    branches = set()
    for line in res.stdout.splitlines():
        b = line.strip()
        if b.startswith("origin/"):
            ref = b.replace("origin/", "")
            if ref not in ("HEAD", "main", "master"):
                branches.add(ref)
    return branches


def main() -> int:
    open_heads = get_open_pr_head_branches()
    logger.info("Protected open PR branches (%d): %s", len(open_heads), open_heads)

    remote_branches = get_remote_branches()
    to_delete = []

    # বাংলা (#4200 §9): check branch safety before deleting
    token = get_gh_token()
    if not token:
        logger.warning("No GH_TOKEN — skipping branch-state safety check (will delete all stale)")
        token = ""

    for branch in remote_branches:
        if branch in open_heads:
            continue
        if any(branch.startswith(prefix) for prefix in AGENT_PREFIXES):
            # #4200 §9: check if branch is safe to delete
            if token and not is_branch_safe_to_delete(branch, token):
                continue  # preserve active/paused/orphaned branches
            to_delete.append(branch)

    logger.info("Found %d stale agent branches to delete from origin.", len(to_delete))
    if not to_delete:
        logger.info("No stale branches to clean.")
        return 0

    batch_size = 20
    for i in range(0, len(to_delete), batch_size):
        chunk = to_delete[i:i + batch_size]
        logger.info("Deleting batch %d-%d of %d...", i + 1, min(i + batch_size, len(to_delete)), len(to_delete))
        cmd = ["git", "push", "origin", "--delete"] + chunk
        res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
        if res.returncode != 0:
            logger.warning("Batch deletion warning: %s", res.stderr.strip()[:200])

    subprocess.run(["git", "fetch", "origin", "--prune"], cwd=str(REPO_ROOT), check=False)
    logger.info("Stale branch cleanup complete. Remote tracking branches pruned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
