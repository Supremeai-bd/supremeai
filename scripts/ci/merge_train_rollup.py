#!/usr/bin/env python3
"""Batch PR Consolidation Engine (Merge Train & Rollup Consolidator).
===================================================================
Implements concurrency-gated merge queue rollup logic:
1. Discovers PRs in queue (`queue:pending-rollup` label or candidate list).
2. Performs pairwise collision checks via cross_pr_collision_detector.
3. Consolidates non-overlapping candidate PRs into the canonical slot branch (`pr-helper-1`).
4. Triggers / manages single CI execution.
5. In case of CI failure, automatically bisects the batch to isolate failing PR(s).
6. On batch success, merges all member PRs and cascade-closes their linked issues.

Issue: #1711
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ── Ecosystem-First reuse (Step 1: "যা আছে তা দিয়ে কি সম্ভব?") ────────────────
# The canonical multi-agent collision detector already owns "which open PRs
# exist / which files does each touch". We import its primitives instead of
# re-implementing GitHub interrogation, so the merge train and the PR
# collision gate can never disagree on what a collision is.
try:
    from scripts.git.cross_pr_collision_detector import (
        detect_collisions,
    )
    from scripts.git.cross_pr_collision_detector import (
        fetch_open_prs as fetch_open_prs_legacy,
    )
except ImportError:  # pragma: no cover - defensive, repo layout guarantee
    detect_collisions = None  # type: ignore[assignment]
    fetch_open_prs_legacy = None  # type: ignore[assignment]

#: JSON fields the rollup queue actually needs. The legacy detector asks only
#: for number/title/headRefName/author/files/isDraft — that is NOT enough to
#: filter on `queue:pending-rollup` (labels) nor to cascade-close linked issues
#: (body) nor to order FIFO by real enqueue time (createdAt).
ROLLUP_PR_JSON_FIELDS = (
    "number,title,headRefName,headRefOid,author,files,isDraft,labels,body,createdAt"
)

QUEUED_LABEL = "queue:pending-rollup"
#: Members already consolidated into an in-flight batch must never be re-selected
#: (otherwise the next scheduler tick would roll the same PRs into a 2nd batch).
IN_BATCH_LABEL = "queue:in-batch"
EXCLUDE_LABELS = ("queue:hold", "queue:failed", IN_BATCH_LABEL)

#: Sort sentinel that keeps PRs lacking `createdAt` after timestamped ones.
FIFO_SENTINEL = "9999-12-31T23:59:59Z"

#: Canonical slot branch assigned to PR Helper Pool (Role-Scoped Pool Model)
#: per docs/master_docs/AGENT_SLOT_REGISTRY.yaml and AGENTS.md.
#: Constant role name + scaling number: pr-helper-1
CANONICAL_ROLLUP_BRANCH = "pr-helper-1"

ISSUE_KEYWORD_REGEX = re.compile(
    r"(?i)\b(?:close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)\s+#([0-9]+)\b"
)


def fetch_open_prs(repo_dir: Path = ROOT_DIR) -> list[dict]:
    """Fetch open PRs carrying every field the rollup queue requires.

    Primary path: ``gh pr list --json <ROLLUP_PR_JSON_FIELDS>`` so queue labels
    and PR bodies are present. Fallback path: the legacy detector fetch (no
    labels/body) so the engine still degrades safely when ``gh`` is missing or
    unauthenticated instead of raising.
    """
    try:
        res = subprocess.run(
            ["gh", "pr", "list", "--state", "open", "--json", ROLLUP_PR_JSON_FIELDS],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=30,
        )
        stdout = res.stdout or ""
        stderr = res.stderr or ""
        if res.returncode == 0 and stdout.strip():
            data = json.loads(stdout)
            return [pr for pr in data if isinstance(pr, dict)]
        print(
            f"Warning: `gh pr list` returned rc={res.returncode} "
            f"({stderr.strip()[:200]}) — using legacy PR fetch.",
            file=sys.stderr,
        )
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(
            f"Warning: `gh pr list` failed ({exc}) — using legacy PR fetch.",
            file=sys.stderr,
        )

    if fetch_open_prs_legacy is not None:
        return fetch_open_prs_legacy()
    return []


@dataclass
class QueuedPR:
    number: int
    title: str
    head_branch: str
    head_sha: str = ""
    author: str = ""
    files: list[str] = field(default_factory=list)
    linked_issues: list[int] = field(default_factory=list)
    is_draft: bool = False
    labels: list[str] = field(default_factory=list)
    created_at: str = ""


def extract_linked_issues(text: str) -> list[int]:
    """Extract linked issue numbers from PR body or commit text (e.g. 'Fixes #123')."""
    if not text:
        return []
    matches = ISSUE_KEYWORD_REGEX.findall(text)
    return sorted(list({int(m) for m in matches}))


def filter_queued_prs(
    prs: list[dict],
    required_label: str = QUEUED_LABEL,
    exclude_labels: list[str] | None = None,
) -> list[QueuedPR]:
    """Filter raw open PR dicts for candidates waiting in the merge queue.

    Output is ordered FIFO by real enqueue time (`createdAt`), falling back to
    PR number when GitHub did not report a timestamp.
    """
    exclude = set(exclude_labels or EXCLUDE_LABELS)
    queued: list[QueuedPR] = []

    for pr in prs:
        if not isinstance(pr, dict):
            continue
        if pr.get("isDraft", False):
            continue

        pr_labels = [
            lbl["name"] if isinstance(lbl, dict) else str(lbl)
            for lbl in pr.get("labels", [])
        ]
        if any(lbl in exclude for lbl in pr_labels):
            continue

        if required_label and required_label not in pr_labels:
            continue

        files: list[str] = []
        for f in pr.get("files", []):
            if isinstance(f, dict) and "path" in f:
                files.append(f["path"])
            elif isinstance(f, str):
                files.append(f)

        body = pr.get("body", "") or ""
        title = pr.get("title", "") or ""
        linked = extract_linked_issues(f"{title}\n{body}")

        queued.append(
            QueuedPR(
                number=pr.get("number", 0),
                title=title,
                head_branch=pr.get("headRefName", ""),
                head_sha=pr.get("headRefOid", "") or pr.get("headSha", ""),
                author=(pr.get("author", {}) or {}).get("login", "")
                if isinstance(pr.get("author"), dict)
                else str(pr.get("author", "")),
                files=files,
                linked_issues=linked,
                is_draft=pr.get("isDraft", False),
                labels=pr_labels,
                created_at=str(pr.get("createdAt", "") or ""),
            )
        )

    # FIFO by real enqueue time; PR number is the tie-breaker / fallback.
    return sorted(queued, key=lambda x: (x.created_at or FIFO_SENTINEL, x.number))


def find_pairwise_collisions(prs: list[QueuedPR]) -> dict[int, set[int]]:
    """Compute pairwise file collisions among candidate PRs."""
    collisions: dict[int, set[int]] = {pr.number: set() for pr in prs}

    for i in range(len(prs)):
        files_i = set(prs[i].files)
        for j in range(i + 1, len(prs)):
            files_j = set(prs[j].files)
            overlap = files_i.intersection(files_j)
            if overlap:
                collisions[prs[i].number].add(prs[j].number)
                collisions[prs[j].number].add(prs[i].number)

    return collisions


def select_batch_candidates(
    queued_prs: list[QueuedPR], max_batch_size: int = 5
) -> tuple[list[QueuedPR], list[QueuedPR]]:
    """Greedily select non-overlapping PRs in FIFO order up to max_batch_size."""
    selected: list[QueuedPR] = []
    deferred: list[QueuedPR] = []
    claimed_files: set[str] = set()

    for pr in queued_prs:
        if len(selected) >= max_batch_size:
            deferred.append(pr)
            continue

        pr_files = set(pr.files)
        if pr_files.intersection(claimed_files):
            deferred.append(pr)
        else:
            selected.append(pr)
            claimed_files.update(pr_files)

    return selected, deferred


def split_batch_for_bisect(pr_numbers: list[int]) -> tuple[list[int], list[int]]:
    """Bisect a failing batch of PRs into two halves."""
    if not pr_numbers:
        return [], []
    if len(pr_numbers) == 1:
        return pr_numbers, []
    mid = len(pr_numbers) // 2
    return pr_numbers[:mid], pr_numbers[mid:]


class RollupEngine:
    """Dynamic, concurrency-gated merge-queue drain for the merge train."""

    def __init__(self, repo_dir: Path = ROOT_DIR):
        self.repo_dir = repo_dir

    # বাংলা মন্তব্য: Admin কে Telegram-এ alert পাঠানো হবে merge failure/rollback-এ।
    # GH Actions-এ notify_telegram workflow trigger করা হয়, লোকালে env var check-এ fallback।
    def _notify_admin(self, message: str) -> None:
        """Telegram admin alert পাঠানো (non-fatal — failure logged only)।"""
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("ADMIN_TELEGRAM_CHAT_ID", "")
        if not token or not chat_id:
            print(f"[ALERT] {message}", file=sys.stderr)
            return
        try:
            import urllib.parse
            import urllib.request
            payload = urllib.parse.urlencode({
                "chat_id": chat_id,
                "text": f"🚨 *MergeTrain Alert*\n{message}",
                "parse_mode": "Markdown",
            }).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=payload,
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as _e:
            # বাংলা: notification failure কখনো main flow block করবে না
            print(f"[ALERT-FAILED] {message} | err={_e}", file=sys.stderr)

    def rollback_main(self, bad_sha: str | None = None) -> dict[str, Any]:
        """main-এ শেষ commit revert করে CI breakage থেকে রক্ষা করে।

        বাংলা মন্তব্য: post-merge watchdog (main.yml) থেকে call হয়।
        bad_sha দিলে সেই specific commit revert হয়; না দিলে HEAD revert হয়।
        Revert সিদ্ধান্ত admin-এ। Auto-revert করা হয় না — শুধু branch তৈরি পরে admin PR খোলে।
        """
        target = bad_sha or "HEAD"
        revert_branch = f"revert/auto-{target[:8]}-{int(time.time())}"
        try:
            self._run_cmd(["git", "fetch", "origin", "main"])
            self._run_cmd(["git", "checkout", "-B", revert_branch, "origin/main"])
            revert_res = self._run_cmd(
                ["git", "revert", "--no-edit", target],
                check=False,
            )
            if revert_res.returncode != 0:
                msg = f"Rollback failed for {target}: {revert_res.stderr.strip()[:200]}"
                self._notify_admin(msg)
                return {"success": False, "error": msg, "branch": revert_branch}

            push_res = self._run_cmd(
                ["git", "push", "origin", revert_branch],
                check=False,
            )
            if push_res.returncode != 0:
                msg = f"Rollback branch push failed: {push_res.stderr.strip()[:200]}"
                self._notify_admin(msg)
                return {"success": False, "error": msg, "branch": revert_branch}

            msg = (
                f"🔄 Rollback branch `{revert_branch}` created for `{target}`\n"
                f"Admin action required: review and open PR to merge the revert."
            )
            self._notify_admin(msg)
            return {"success": True, "branch": revert_branch, "reverted": target}

        except Exception as exc:
            self._notify_admin(f"Rollback exception for {target}: {exc}")
            return {"success": False, "error": str(exc), "branch": revert_branch}

    # বাংলা মন্তব্য: #2645 — Auto-Revert Watchdog: পোস্ট-মার্জ অ্যানোমালিতে
    # তাৎক্ষণিক revert-PR খোলা (main সরাসরি স্পর্শ নয় — PR রিভিউ-পাথই নিরাপদ)।
    def create_auto_revert_pr(self, bad_sha: str, reason: str, pr_title: str = "") -> dict[str, Any]:
        """ব্যর্থ মার্জের জন্য স্বয়ংক্রিয় revert-PR তৈরি করা (kill-switch সহ)।

        বাংলা মন্তব্য: rollback_main শুধু ব্রাঞ্চ তৈরি করে অ্যাডমিনের হাতে ছেড়ে
        দেয়; এটি এক ধাপ এগিয়ে P0 লেবেলসহ PR খুলে দেয় ও টেলিগ্রামে অ্যালার্ট
        পাঠায়। MERGE_TRAIN_AUTO_REVERT=off দিলে সম্পূর্ণ নিষ্ক্রিয় (fail-safe)।
        """
        if (os.environ.get("MERGE_TRAIN_AUTO_REVERT", "") or "").strip().lower() in (
            "off", "none", "disabled", "0", "false",
        ):
            return {"success": False, "error": "auto-revert disabled (kill-switch)"}

        # ১. প্রথমে বিদ্যমান rollback_main ব্যবহার করে revert-ব্রাঞ্চ তৈরি ও পুশ
        rollback = self.rollback_main(bad_sha=bad_sha)
        if not rollback.get("success"):
            return rollback

        revert_branch = rollback["branch"]
        title = pr_title or f"revert(watchdog): auto-revert {bad_sha[:8]} (post-merge anomaly)"
        body = (
            f"### 🤖 Auto-Revert Watchdog (AI মার্জ-ট্রেইন)\n\n"
            f"- **Reverted SHA**: `{bad_sha}`\n"
            f"- **কারণ**: {reason}\n\n"
            f"#### প্রয়োজনীয় পদক্ষেপ:\n"
            f"১. অ্যানোমালি যাচাই করুন (পোস্ট-মার্জ স্মোক/হেলথ ফেইলিউর)।\n"
            f"২. PR সবুজ হলে merge করে main সুরক্ষিত করুন।\n"
            f"৩. মূল সমস্যা ঠিক করে নতুন PR-এ ফিরিয়ে আনুন।"
        )

        # ২. revert-PR খোলা (gh CLI — ইতিমধ্যে অথেনটিকেটেড কনটেক্সটে চলে)
        try:
            pr_res = self._run_cmd(
                [
                    "gh", "pr", "create",
                    "--base", "main",
                    "--head", revert_branch,
                    "--title", title,
                    "--body", body,
                    "--label", "P0-critical",
                    "--label", "type:revert",
                ],
                check=False,
            )
            if pr_res.returncode != 0:
                msg = f"Auto-revert PR creation failed for {bad_sha}: {pr_res.stderr.strip()[:200]}"
                self._notify_admin(msg)
                return {"success": False, "error": msg, "branch": revert_branch}
            pr_url = pr_res.stdout.strip().splitlines()[-1] if pr_res.stdout else ""
        except Exception as exc:  # noqa: BLE001 — watchdog কখনো মূল ফ্লো ভাঙবে না
            msg = f"Auto-revert PR exception for {bad_sha}: {exc}"
            self._notify_admin(msg)
            return {"success": False, "error": str(exc), "branch": revert_branch}

        # ৩. টেলিগ্রাম বাংলা অ্যালার্ট + রিলিজ-নোট সংযুক্তি
        self._notify_admin(
            f"🚨 Post-merge anomaly! Auto-revert PR opened for {bad_sha[:8]} — {reason}\n{pr_url}"
        )
        return {"success": True, "branch": revert_branch, "pr_url": pr_url, "reverted": bad_sha}

    def _run_cmd(self, cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
        # encoding/errors are explicit: Windows defaults to cp1252, which raises
        # UnicodeDecodeError inside subprocess' reader thread (leaving stdout=None)
        # the moment a PR title/body contains non-ASCII text.
        return subprocess.run(
            cmd,
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=check,
        )

    def validate_batch_collisions(self, prs: list[QueuedPR]) -> dict[int, list[str]]:
        """Deep-validate a candidate batch against *all other* open PRs.

        Delegates to the canonical ``cross_pr_collision_detector.detect_collisions``
        so the merge train cannot drift from the PR-collision gate. Intra-batch
        overlap is already excluded by :func:`select_batch_candidates`, so only
        conflicts with PRs *outside* the batch are reported.

        Returns ``{pr_number: ["PR #123", "branch foo", ...]}``.
        """
        conflicts: dict[int, list[str]] = {}
        if detect_collisions is None:
            return conflicts

        batch_numbers = {pr.number for pr in prs}
        for pr in prs:
            report = detect_collisions(
                target_branch=pr.head_branch,
                target_pr_num=pr.number,
                target_files=pr.files or None,
            )
            outsiders: list[str] = []
            for item in report.direct_collisions:
                if item.colliding_pr is not None and item.colliding_pr in batch_numbers:
                    continue  # intra-batch overlap already handled by scheduling
                label = (
                    f"PR #{item.colliding_pr}"
                    if item.colliding_pr is not None
                    else f"branch {item.colliding_branch}"
                )
                if label not in outsiders:
                    outsiders.append(label)
            if outsiders:
                conflicts[pr.number] = sorted(outsiders)
        return conflicts

    def plan(
        self,
        required_label: str = QUEUED_LABEL,
        max_batch: int = 5,
        deep: bool = False,
    ) -> dict[str, Any]:
        """Inspect queue and plan the next rollup batch."""
        raw_prs = fetch_open_prs()
        queued = filter_queued_prs(raw_prs, required_label=required_label)
        collisions = find_pairwise_collisions(queued)
        selected, deferred = select_batch_candidates(queued, max_batch_size=max_batch)
        external_collisions = self.validate_batch_collisions(selected) if deep else {}

        return {
            "total_queued": len(queued),
            "selected_count": len(selected),
            "deferred_count": len(deferred),
            "selected_prs": [pr.number for pr in selected],
            "deferred_prs": [pr.number for pr in deferred],
            "collision_graph": {k: list(v) for k, v in collisions.items() if v},
            "external_collisions": external_collisions,
            "linked_issues_to_close": sorted(
                {issue for pr in selected for issue in pr.linked_issues}
            ),
            "selected_details": [
                {
                    "number": pr.number,
                    "title": pr.title,
                    "branch": pr.head_branch,
                    "author": pr.author,
                    "files_count": len(pr.files),
                    "linked_issues": pr.linked_issues,
                }
                for pr in selected
            ],
        }

    def create_rollup_branch(
        self,
        pr_numbers: list[int],
        base_branch: str = "origin/main",
        branch_name: str | None = None,
        timestamp: str | None = None,
        deep_validate: bool = True,
        allow_partial: bool = False,
    ) -> dict[str, Any]:
        """Combine selected PRs into the designated slot branch locally.

        Defaults strictly to CANONICAL_ROLLUP_BRANCH (agent-2-pr-helper) per
        docs/master_docs/AGENT_SLOT_REGISTRY.yaml to preserve invariant slot governance.
        """
        if not pr_numbers:
            raise ValueError("No PR numbers provided to rollup")

        deep_conflicts: dict[int, list[str]] = {}
        if deep_validate:
            requested = set(pr_numbers)
            candidates = [
                pr
                for pr in filter_queued_prs(fetch_open_prs(), required_label="")
                if pr.number in requested
            ]
            deep_conflicts = self.validate_batch_collisions(candidates)

        if branch_name:
            batch_branch = branch_name
        elif timestamp:
            batch_branch = f"batch/rollup-{timestamp}"
        else:
            batch_branch = CANONICAL_ROLLUP_BRANCH

        # Ensure committer identity is configured before creating merge commits
        ident_res = self._run_cmd(["git", "config", "user.name"], check=False)
        if not ident_res.stdout.strip():
            self._run_cmd(["git", "config", "user.name", "supremeai-merge-train[bot]"], check=False)
            self._run_cmd(["git", "config", "user.email", "merge-train@supremeai.local"], check=False)

        self._run_cmd(["git", "fetch", "origin", "main"])
        self._run_cmd(["git", "checkout", "-B", batch_branch, base_branch])

        merged_prs: list[int] = []
        failed_prs: list[int] = []

        for pr_num in pr_numbers:
            ref_spec = f"pull/{pr_num}/head:pr-{pr_num}-head"
            fetch_res = self._run_cmd(["git", "fetch", "origin", ref_spec], check=False)
            if fetch_res.returncode != 0:
                print(
                    f"Warning: could not fetch PR #{pr_num} head "
                    f"({fetch_res.stderr.strip()[:200]})",
                    file=sys.stderr,
                )
                failed_prs.append(pr_num)
                continue

            msg = f"chore(rollup): merge PR #{pr_num} into {batch_branch}"
            merge_res = self._run_cmd(
                ["git", "merge", "--no-ff", "-m", msg, f"pr-{pr_num}-head"],
                check=False,
            )
            if merge_res.returncode != 0:
                self._run_cmd(["git", "merge", "--abort"], check=False)
                print(
                    f"Warning: merge conflict for PR #{pr_num} — deferred to bisect "
                    f"({merge_res.stderr.strip()[:200]})",
                    file=sys.stderr,
                )
                failed_prs.append(pr_num)
            else:
                merged_prs.append(pr_num)

        success = (
            len(merged_prs) > 0
            if allow_partial
            else (len(merged_prs) > 0 and len(failed_prs) == 0)
        )
        # বাংলা মন্তব্য: batch-এ কোনো PR fail হলে admin-কে সাথে সাথে alert দাও।
        # rollback_main() call করার সিদ্ধান্ত admin-এর — auto-revert নয়।
        if failed_prs:
            self._notify_admin(
                f"Batch rollup on `{batch_branch}` failed for PR(s): "
                f"{failed_prs}. Merged OK: {merged_prs}. "
                f"Run `rollback_main` if main was already pushed."
            )
        return {
            "batch_branch": batch_branch,
            "merged_prs": merged_prs,
            "failed_prs": failed_prs,
            "external_collisions": deep_conflicts,
            "success": success,
            # বাংলা: rollback প্রয়োজন হলে এই key দিয়ে caller জানতে পারবে
            "needs_rollback": not success and len(merged_prs) > 0,
        }


    def land_rollup(self, pr_numbers: list[int], batch_pr_number: int | None = None) -> dict[str, Any]:
        """Post-merge cascade: auto-close linked issues and member PRs."""
        closed_issues: list[int] = []
        merged_member_prs: list[int] = []

        for pr_num in pr_numbers:
            try:
                view_res = self._run_cmd(
                    ["gh", "pr", "view", str(pr_num), "--json", "title,body,state,mergedAt"],
                    check=False,
                )
                if view_res.returncode == 0 and view_res.stdout.strip():
                    data = json.loads(view_res.stdout)
                    linked = extract_linked_issues(f"{data.get('title', '')}\n{data.get('body', '')}")

                    if data.get("state") == "OPEN":
                        ref_text = f"batch PR #{batch_pr_number}" if batch_pr_number else "batch rollup integration"
                        close_msg = (
                            f"Merged and consolidated into `main` via {ref_text}. "
                            "Closing PR as part of Batch PR Consolidation Engine."
                        )
                        self._run_cmd(
                            ["gh", "pr", "close", str(pr_num), "--comment", close_msg],
                            check=False,
                        )
                        merged_member_prs.append(pr_num)
                    else:
                        merged_member_prs.append(pr_num)

                    for issue_num in linked:
                        issue_msg = (
                            f"Resolved and auto-closed by Batch PR Consolidation Engine "
                            f"(via merged PR #{pr_num})."
                        )
                        close_issue = self._run_cmd(
                            ["gh", "issue", "close", str(issue_num), "--comment", issue_msg],
                            check=False,
                        )
                        if close_issue.returncode == 0:
                            closed_issues.append(issue_num)

                    # Label cleanup via REST API: `gh pr edit --remove-label`
                    # silently no-ops in this environment (GraphQL projectCards
                    # deprecation path, issue #2042) — and landed member PRs are
                    # CLOSED by now, yet must still shed their queue labels so no
                    # later drain cycle can mistake them for pending work.
                    repo = os.environ.get("GH_REPO", "SaifulHaqueNiloy/supremeai")
                    for label in (QUEUED_LABEL, IN_BATCH_LABEL):
                        self._run_cmd(
                            [
                                "gh",
                                "api",
                                "-X",
                                "DELETE",
                                f"repos/{repo}/issues/{pr_num}/labels/{quote(label, safe='')}",
                            ],
                            check=False,
                        )
            except (subprocess.SubprocessError, ValueError, KeyError, OSError) as e:
                print(f"Warning handling PR #{pr_num}: {e}", file=sys.stderr)

        return {
            "merged_member_prs": merged_member_prs,
            "closed_issues": closed_issues,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# #2645: স্মার্ট ব্যাচিং (Rollup vs Single-Flight) + Auto-Revert Watchdog
# ═══════════════════════════════════════════════════════════════════════════════
# বাংলা মন্তব্য: ছোট নিরীহ পরিবর্তন (ডকস/টাইপো/ক্লিনআপ) ৩-৪টা একসাথে রোলআপ-ব্যাচে
# মার্জ হয় (CI বিল্ড-মিনিট ~৭৫% সাশ্রয়); কোর/ঝুঁকিপূর্ণ পরিবর্তন কখনোই ব্যাচে যায়
# না — সিঙ্গেল-ফ্লাইট আইসোলেশন (isolation)। পোস্ট-মার্জ অ্যানোমালিতে ওয়াচডগ
# তাৎক্ষণিক revert-PR খোলে (main সুরক্ষিত), টেলিগ্রামে বাংলা অ্যালার্ট যায়।

# বাংলা মন্তব্য: এই ডিরেক্টরিগুলো স্পর্শ করা PR কখনো rollup-ব্যাচে যাবে না
# (smart_priority_merger-এর SemanticRiskClassifier এর সাথে SSOT-সামঞ্জস্য)
ROLLUP_EXCLUDED_DIRS = (
    "backend/auth",
    "backend/payments",
    "backend/alembic_migrations",
    "backend/core/db",
    ".github/workflows",
    "config/",
)

ROLLUP_MAX_DIFF_LINES = 100


def touches_excluded_dir(files: list[str]) -> bool:
    """ফাইল-তালিকা কি ব্যাচ-বর্জিত (excluded) ডিরেক্টরি স্পর্শ করে? (pure)"""
    for path in files or []:
        lowered = str(path).strip().lower()
        if any(lowered.startswith(d) for d in ROLLUP_EXCLUDED_DIRS):
            return True
    return False


def is_rollup_eligible(pr: QueuedPR, diff_lines: int | None = None) -> bool:
    """PR ছোট-নিরীহ rollup-ব্যাচের যোগ্য কি না (pure হিউরিস্টিক)।

    বাংলা মন্তব্য: ডকস/ক্লিনআপ টাইটেল, ছোট diff, কোর-ডির স্পর্শ নেই — তিন
    শর্তই মিললে কেবল ব্যাচযোগ্য। ডিফল্টে অজানা diff হলে রক্ষণাবেক্ষণমূলক অনুমান।
    """
    title = (pr.title or "").lower()
    benign_terms = (
        "docs", "typo", "readme", "comment", "cleanup", "chore",
        "prune", "rename", "docstring", "skipped_tests",
    )
    is_benign = any(t in title for t in benign_terms)
    if not is_benign:
        return False
    if touches_excluded_dir(pr.files):
        return False
    if diff_lines is not None and diff_lines > ROLLUP_MAX_DIFF_LINES:
        return False
    return True


def plan_single_flight_vs_rollup(
    queued_prs: list[QueuedPR],
    diff_lines_by_pr: dict[int, int] | None = None,
    max_batch: int = 4,
) -> dict[str, Any]:
    """সিঙ্গেল-ফ্লাইট বনাম রোলআপ-ব্যাচ পরিকল্পনা (pure নির্ণয়ের উপর গঠিত)।

    বাংলা মন্তব্য: ফেরত dict — `single_flight` = আলাদা আলাদা মার্জ প্রয়োজন
    (কোর/ঝুঁকি), `rollup_batch` = একসাথে মার্জযোগ্য ছোট PR-দের তালিকা,
    `deferred` = ফাইল-ওভারল্যাপে বাদ পড়া। ব্যাচ-সদস্যদের মধ্যে ফাইল-ওভারল্যাপ
    select_batch_candidates দিয়েই বাদ যায় (Ecosystem-First reuse)।
    """
    diff_lines_by_pr = diff_lines_by_pr or {}
    eligible = [
        pr for pr in queued_prs
        if is_rollup_eligible(pr, diff_lines_by_pr.get(pr.number))
    ]
    single_flight = [pr for pr in queued_prs if pr not in eligible]

    selected, deferred = select_batch_candidates(eligible, max_batch_size=max_batch)
    return {
        "single_flight": [pr.number for pr in single_flight],
        "rollup_batch": [pr.number for pr in selected],
        "deferred": [pr.number for pr in deferred],
    }


def build_bengali_release_note(merged_prs: list[QueuedPR]) -> str:
    """মার্জ-হওয়া PR-দের জন্য টেমপ্লেট-ভিত্তিক বাংলা রিলিজ-নোট গঠন (pure)।

    বাংলা মন্তব্য: AI-polish ঐচ্ছিক — key না থাকলেও সুন্দর বাংলা নোট তৈরি হয়
    (নেটওয়ার্ক-নিরপেক্ষ; টেস্টেবল)।
    """
    if not merged_prs:
        return "📭 এই ব্যাচে কোনো মার্জ হয়নি।"
    lines = ["🚀 **SupremeAI মার্জ-ট্রেইন রিলিজ নোট**", ""]
    for pr in merged_prs:
        lines.append(f"- #{pr.number}: {pr.title}")
    lines += [
        "",
        f"মোট {len(merged_prs)}টি PR সফলভাবে প্রোডাকশনে ল্যান্ড করেছে। সব গেট সবুজ ✅",
        "_বাংলা মন্তব্য: এই নোট মার্জ-ট্রেইন স্বয়ংক্রিয়ভাবে তৈরি করেছে।_ 🇧🇩",
    ]
    return "\n".join(lines)


# বাংলা মন্তব্য: RollupEngine-এ auto-revert PR মেথড যোগ (ম্যানুয়াল rollback_main
# এর পাশে — পার্থক্য: এটি স্বয়ংক্রিয়ভাবে PR খোলে + লেবেল + টেলিগ্রাম অ্যালার্ট)


def _pr_number(value: str) -> int:
    """Accept a bare PR number or a full GitHub PR URL (issue #2042).

    The merge-train workflow passes ``needs.rollup.outputs.batch_pr`` as a URL
    (e.g. ``https://github.com/o/r/pull/2037``) and the Tier-3 approval comment
    copy/paste command does the same — argparse must not crash on either form.
    """
    digits = value.rstrip("/").rsplit("/", 1)[-1]
    if not digits.isdigit():
        raise argparse.ArgumentTypeError(f"expected a PR number or PR URL, got {value!r}")
    return int(digits)


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch PR Consolidation Engine (Merge Train)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_p = subparsers.add_parser("plan", help="Plan next rollup batch from merge queue")
    plan_p.add_argument("--label", default=QUEUED_LABEL, help="Queue label to filter by")
    plan_p.add_argument("--max-batch", type=int, default=5, help="Max PRs per batch")
    plan_p.add_argument("--format", choices=["json", "text"], default="text")
    plan_p.add_argument(
        "--deep",
        action="store_true",
        help="Also validate the batch against every other open PR (extra gh calls)",
    )

    build_p = subparsers.add_parser("build", help="Create rollup batch branch")
    build_p.add_argument("--prs", type=_pr_number, nargs="+", required=True, help="PR numbers (or PR URLs) to rollup")
    build_p.add_argument("--base", default="origin/main", help="Base ref to branch off")
    build_p.add_argument(
        "--skip-deep-validation",
        action="store_true",
        help="Skip cross-PR collision validation (faster, less safe)",
    )
    build_p.add_argument(
        "--branch",
        default=CANONICAL_ROLLUP_BRANCH,
        help=f"Canonical slot branch to rollup into (default: {CANONICAL_ROLLUP_BRANCH} per AGENT_SLOT_REGISTRY.yaml)",
    )
    build_p.add_argument(
        "--allow-partial",
        action="store_true",
        help="Succeed if at least one PR merged cleanly (conflicting PRs quarantined)",
    )

    bisect_p = subparsers.add_parser("bisect", help="Bisect failing batch PRs into two halves")
    bisect_p.add_argument("--prs", type=_pr_number, nargs="+", required=True, help="PR numbers (or PR URLs) that failed in batch")

    land_p = subparsers.add_parser("land", help="Cascade close batched PRs and their linked issues")
    land_p.add_argument("--prs", type=_pr_number, nargs="+", required=True, help="PR numbers (or PR URLs) included in batch")
    land_p.add_argument(
        "--batch-pr",
        type=_pr_number,
        default=None,
        help="Batch rollup PR number or URL (optional) — the workflow hands us the URL form",
    )

    args = parser.parse_args()
    engine = RollupEngine()

    if args.command == "plan":
        result = engine.plan(
            required_label=args.label,
            max_batch=args.max_batch,
            deep=args.deep,
        )
        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            print("Merge Train Queue Plan:")
            print(f"  Total Queued: {result['total_queued']}")
            print(f"  Selected for Rollup: {result['selected_prs']}")
            print(f"  Deferred (Collisions/Limit): {result['deferred_prs']}")
            print(f"  Linked Issues to Close: {result['linked_issues_to_close']}")
            if result['collision_graph']:
                print(f"  Intra-batch Collisions: {result['collision_graph']}")
            if result['external_collisions']:
                print(f"  External PR Collisions: {result['external_collisions']}")

    elif args.command == "build":
        result = engine.create_rollup_branch(
            pr_numbers=args.prs,
            base_branch=args.base,
            branch_name=args.branch,
            deep_validate=not args.skip_deep_validation,
            allow_partial=args.allow_partial,
        )
        print(json.dumps(result, indent=2))
        if not result["success"]:
            return 1

    elif args.command == "bisect":
        h1, h2 = split_batch_for_bisect(args.prs)
        print(json.dumps({"half_1": h1, "half_2": h2}, indent=2))

    elif args.command == "land":
        result = engine.land_rollup(pr_numbers=args.prs, batch_pr_number=args.batch_pr)
        print(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())

