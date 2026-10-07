#!/usr/bin/env python3
"""Prune stale agent branches from origin — FAIL-CLOSED (#4200 §9, #4204).

Branches created by agents that have no open PRs are pruned from origin,
ensuring that remote branch existence reflects ONLY active in-progress work.

#4200 §9 safety contract (corrected by #4204 — fail-closed):
A branch may be deleted ONLY when ALL of the following are PROVABLE:

  1. A GitHub token is available (else: abort — delete NOTHING, exit 2).
  2. The open-PR head list was fetched (else: abort — delete NOTHING, exit 2).
  3. The linked issue's labels were fetched (else: PRESERVE that branch).
  4. No preserve label (`branch:active/paused/orphaned`) on the linked issue.
  5. The work is merged/completed, proven by either:
       - a merged PR whose head was this branch (squash-safe), OR
       - the branch head is an ancestor of origin/main (direct-push case).

Any unprovable condition ⇒ PRESERVE. "No open PR" alone is NOT "merged".
Uncertainty never resolves to deletion (#4200: branches are persistent
workspaces; agents are replaceable workers).
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import urllib.parse
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


def get_issue_labels(issue_number: int, token: str) -> set[str] | None:
    """Get labels on an issue via GitHub API.

    বাংলা (#4204): ব্যর্থ হলে খালি set নয় — `None` দেয়। `None` মানে
    "যাচাই করা অসম্ভব" → caller ওই branch-টিকে PRESERVE করবে (fail-closed)।
    """
    try:
        url = f"https://api.github.com/repos/{REPO}/issues/{issue_number}"
        req = urllib.request.Request(url, headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return {l["name"] for l in data.get("labels", [])}
    except Exception as e:
        logger.warning("  label fetch failed for issue #%d: %s", issue_number, e)
        return None


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


def get_pr_merge_state(branch_name: str, token: str) -> str | None:
    """Merge-proof via GitHub PR history (squash-merge safe).

    Returns one of: "merged" | "closed" | "open" | "none" | None.
    None = verification unavailable → caller must PRESERVE (#4204).
    """
    try:
        head = urllib.parse.quote(f"{REPO}:{branch_name}", safe="")
        url = (f"https://api.github.com/repos/{REPO}/pulls?state=all"
               f"&head={head}&per_page=20")
        req = urllib.request.Request(url, headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            prs = json.loads(resp.read())
        if not isinstance(prs, list):
            return None
        if any(p.get("merged_at") for p in prs):
            return "merged"
        if any(p.get("state") == "closed" and not p.get("merged_at") for p in prs):
            return "closed"
        if any(p.get("state") == "open" for p in prs):
            return "open"
        return "none"
    except Exception as e:
        logger.warning("  PR-history fetch failed for %s: %s", branch_name, e)
        return None


def is_ancestor_of_main(branch_name: str) -> bool | None:
    """Direct-push merge proof: is origin/<branch> an ancestor of origin/main?

    None = git could not answer (missing ref, git error) → do NOT delete.
    """
    try:
        res = subprocess.run(
            ["git", "merge-base", "--is-ancestor", f"origin/{branch_name}", "origin/main"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=False,
        )
    except Exception:
        return None
    if res.returncode == 0:
        return True
    if res.returncode == 1:
        return False
    return None


def decide_deletion(branch_name: str, *, labels: set[str] | None, pr_state: str | None,
                    ancestor: bool | None) -> tuple[bool, str]:
    """Pure deletion decision core (#4204) — zero IO, fully unit-testable.

    Contract (all unprovable paths resolve to PRESERVE):
      labels is None                    → preserve (label-verification-unavailable)
      labels ∩ PRESERVE_LABELS          → preserve (preserve-label present)
      pr_state is None                  → preserve (merge-proof-unavailable)
      pr_state == "merged"              → DELETE (merged-pr)
      pr_state == "closed"              → preserve (closed-unmerged-pr-preserved)
      pr_state == "open"                → preserve (open-pr-preserved, defensive)
      pr_state == "none":
        ancestor is None                → preserve (merge-proof-unavailable)
        ancestor is True                → DELETE (merged-ancestor)
        ancestor is False               → preserve (unmerged-work-preserved)
    """
    if labels is None:
        return False, "label-verification-unavailable"
    hits = labels & PRESERVE_LABELS
    if hits:
        return False, f"preserve-label:{','.join(sorted(hits))}"
    if pr_state is None:
        return False, "merge-proof-unavailable"
    if pr_state == "merged":
        return True, "merged-pr"
    if pr_state == "closed":
        return False, "closed-unmerged-pr-preserved"
    if pr_state == "open":
        return False, "open-pr-preserved"
    # pr_state == "none"
    if ancestor is None:
        return False, "merge-proof-unavailable"
    if ancestor:
        return True, "merged-ancestor"
    return False, "unmerged-work-preserved"


def is_branch_safe_to_delete(branch_name: str, token: str) -> bool:
    """IO-backed fail-closed wrapper (#4204) around decide_deletion().

    Kept for #4202 API compatibility (tests/test_branch_lifecycle.py).
    Returns True ONLY when deletion is provably safe (#4200 §9):
    labels verified + no preserve label + merged/completed proof.
    Any unprovable condition → False (preserve).
    """
    issue_num = extract_issue_number(branch_name)
    labels = set() if issue_num is None else get_issue_labels(issue_num, token)
    pr_state = get_pr_merge_state(branch_name, token)
    ancestor = (is_ancestor_of_main(branch_name)
                if pr_state in (None, "none") else None)
    safe, reason = decide_deletion(branch_name, labels=labels, pr_state=pr_state,
                                   ancestor=ancestor)
    if not safe:
        logger.info("  ⛔ Preserving %s (%s)", branch_name, reason)
    return safe


def get_open_pr_head_branches() -> set[str]:
    """Open-PR head branches. Raises on failure — callers must abort (fail-closed).

    #4204: আগের fail-open `return set()` বাদ — খালি set মানে "সব branch
    unprotected", যা mass-deletion-এর দিকে যেত। এখন exception → main() abort।
    """
    res = subprocess.run(
        ["gh", "pr", "list", "--state", "open", "--json", "headRefName"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        raise RuntimeError(f"gh pr list failed: {res.stderr.strip()[:200]}")
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError as err:
        raise RuntimeError(f"gh pr list returned non-JSON output: {err}") from err
    return {pr["headRefName"] for pr in data if isinstance(pr, dict) and "headRefName" in pr}


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


def _delete_branches(branches: list[str]) -> None:
    batch_size = 20
    for i in range(0, len(branches), batch_size):
        chunk = branches[i:i + batch_size]
        logger.info("Deleting batch %d-%d of %d...", i + 1, min(i + batch_size, len(branches)), len(branches))
        cmd = ["git", "push", "origin", "--delete"] + chunk
        res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
        if res.returncode != 0:
            logger.warning("Batch deletion warning: %s", res.stderr.strip()[:200])


def main() -> int:
    # #4204 fail-closed gate 1: no token → no verification → no deletion
    token = get_gh_token()
    if not token:
        logger.critical("FAIL-CLOSED (#4204): no GH_TOKEN — branch-state/merge-proof checks "
                        "cannot run. Deleting NOTHING. Re-run with GH_TOKEN set.")
        return 2

    # #4204 fail-closed gate 2: open-PR list unverifiable → nothing is provably stale
    try:
        open_heads = get_open_pr_head_branches()
    except Exception as e:
        logger.critical("FAIL-CLOSED (#4204): cannot verify open PR heads (%s) — deleting NOTHING.", e)
        return 2

    logger.info("Protected open PR branches (%d): %s", len(open_heads), open_heads)

    remote_branches = get_remote_branches()
    to_delete: list[str] = []
    preserved = 0

    for branch in remote_branches:
        if branch in open_heads:
            continue
        if not any(branch.startswith(prefix) for prefix in AGENT_PREFIXES):
            continue

        issue_num = extract_issue_number(branch)
        labels = set() if issue_num is None else get_issue_labels(issue_num, token)
        pr_state = get_pr_merge_state(branch, token)
        ancestor = (is_ancestor_of_main(branch)
                    if pr_state in (None, "none") else None)
        safe, reason = decide_deletion(branch, labels=labels, pr_state=pr_state, ancestor=ancestor)
        if safe:
            logger.info("  🗑️  delete %s (proof: %s)", branch, reason)
            to_delete.append(branch)
        else:
            preserved += 1
            logger.info("  ⛔ Preserving %s (%s)", branch, reason)

    logger.info("Found %d provably-merged agent branches to delete; %d preserved (fail-closed).",
                len(to_delete), preserved)
    if to_delete:
        _delete_branches(to_delete)
        subprocess.run(["git", "fetch", "origin", "--prune"], cwd=str(REPO_ROOT), check=False)
        logger.info("Stale branch cleanup complete. Remote tracking branches pruned.")
    else:
        logger.info("No provably-merged branches to clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
