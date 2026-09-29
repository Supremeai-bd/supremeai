#!/usr/bin/env python3
"""Role-Scoped Branch Slot Acquirer & Dynamic Gap Allocator (Branch-as-Lease).
================================================================================
Implements the SupremeAI Elastic Pool & Slot Governance Law + the Flexible
Group Branching Protocol (#2378):
1. Infers Role from Task/Issue (coder, planner, pr-helper, ci, platform).
2. Performs `git fetch origin --prune` to synchronize active remote branches.
3. Flexible Context-Aware Workflow (#2378):
   - Connected Work  (issue carries a `group:<name>` label):
       1 Group Issue Set -> 1 SHARED group branch `group/<name>` -> 1 PR.
       The group branch is shared across agents: if it exists remotely it is
       checked out as-is (prior group commits preserved), else created from
       origin/main. NEVER reset to main mid-group.
   - Independent Work (no group label) — classic Branch-as-Lease below.
4. Checks for occupied slot indices across:
   - Remote branches on origin matching `<role>-<N>(-.*)?`
   - Open PR head branches matching `<role>-<N>(-.*)?`
   - In-progress issues assigned to `<role>-<N>`
   - Active heartbeat leases in the mesh registry.
5. Finds the lowest available slot gap (first free integer >= 1).
   - If slots 1-9 are active, allocates slot 10.
   - If slot 3 completed (branch merged/deleted), allocates gap 3.
6. Generates the branch name:
   - With issue: `<role>-<slot_index>-<issue#>-<slug>`
   - Without issue: `<role>-<slot_index>`
7. Prepares and checks out the clean branch synced strictly with origin/main.
8. Upon PR merge or close, the branch is deleted, instantly freeing the slot.

Usage:
    python scripts/agents/acquire_role_slot.py --issue 2275
    python scripts/agents/acquire_role_slot.py --role coder --dry-run
    python scripts/agents/acquire_role_slot.py --issue 2378 --dry-run   # group:* issue -> shared group branch
    python scripts/agents/acquire_role_slot.py --task "Full architecture audit" --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        pass

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

VALID_ROLES = ("planner", "coder", "pr-helper", "ci", "platform")

# Flexible Group Branching Protocol (#2378): issue label prefix -> shared group branch.
GROUP_LABEL_PREFIX = "group:"
GROUP_BRANCH_PREFIX = "group/"

ROLE_PATTERNS = {
    "planner": re.compile(r"(?i)\b(plan|planning|audit|architect|architecture|gap-analysis)\b"),
    "ci": re.compile(r"(?i)\b(ci|cd|pipeline|workflow|pre-commit|pre-push|actions|github-actions)\b"),
    "platform": re.compile(r"(?i)\b(platform|render|supabase|redis|upstash|cloudflare|infisical|sweep|health-check)\b"),
    "pr-helper": re.compile(r"(?i)\b(pr-helper|pr-gate|merge-train|rollup|squash-merge|pr-verifier)\b"),
}

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("acquire_role_slot")


@dataclass
class SlotStatus:
    role: str
    index: int
    branch_name: str
    is_occupied: bool
    occupancy_reason: str = ""


def make_branch_slug(text: str, max_words: int = 4, max_len: int = 30) -> str:
    """Convert issue title or task text into a clean, concise branch slug."""
    if not text:
        return ""
    cleaned = re.sub(r"^[a-zA-Z0-9_-]+(?:\([^)]+\))?:\s*", "", text)
    cleaned = re.sub(r"\[[^\]]+\]", "", cleaned)
    cleaned = re.sub(r"#\d+", "", cleaned)
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", cleaned).strip("-").lower()
    parts = [p for p in cleaned.split("-") if p][:max_words]
    slug = "-".join(parts)
    return slug[:max_len].rstrip("-")


def extract_group_name(labels: list[Any] | None) -> str | None:
    """Return the group name when the issue carries a `group:<name>` label (#2378).

    # বাংলা মন্তব্য: group:pipeline-governance লেবেল থাকলে 'pipeline-governance'
    # রিটার্ন হয় — অর্থাৎ Connected Work মডেল: ১ গ্রুপ ব্রাঞ্চ, ১ গ্রুপ PR।
    """
    for lbl in labels or []:
        name = lbl.get("name", "") if isinstance(lbl, dict) else str(lbl or "")
        if name.startswith(GROUP_LABEL_PREFIX):
            group = name[len(GROUP_LABEL_PREFIX):].strip()
            if group:
                return group
    return None


def load_group_dependencies(repo_dir: Path = ROOT_DIR) -> dict[str, str]:
    """Load group dependency map (child_group -> predecessor_group) from rules.yml (#2408).

    # বাংলা মন্তব্য: Predecessor Group Merge Hold Engine (#2408):
    # কোনো গ্রুপ অন্য গ্রুপের ওপর নির্ভরশীল হলে (যেমন foundation-closeout -> pipeline-governance)
    # পূর্ববর্তী গ্রুপ সম্পূর্ণ না হওয়া পর্যন্ত পরবর্তী গ্রুপ কিউতে প্রায়োরিটি পাবে না এবং PR হোল্ডে থাকবে।
    """
    rules_path = repo_dir / ".github" / "constitution" / "rules.yml"
    deps: dict[str, str] = {"foundation-closeout": "pipeline-governance"}
    if rules_path.exists():
        try:
            import yaml
            with open(rules_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                poly = data.get("predecessor_policy") or {}
                if "group_dependencies" in poly and isinstance(poly["group_dependencies"], dict):
                    deps.update(poly["group_dependencies"])
        except Exception:
            pass
    return deps


def extract_slot_index(ref: str, role: str) -> int | None:
    """Extract slot index if ref matches role pattern (e.g. coder-1, coder-2-2253-fix, origin/coder-3)."""
    clean = ref.strip().lstrip("* ").strip()
    pat = re.compile(rf"^(?:remotes/origin/|origin/)?{re.escape(role)}-([0-9]+)(?:-.*)?$")
    m = pat.match(clean)
    if m:
        return int(m.group(1))
    return None


def infer_role_from_context(
    title: str = "",
    body: str = "",
    labels: list[str] | None = None,
    explicit_role: str | None = None,
) -> str:
    """Infer the appropriate agent role from issue metadata or user task description."""
    if explicit_role:
        normalized = explicit_role.strip().lower()
        if normalized in VALID_ROLES:
            return normalized
        if normalized.startswith("plan"):
            return "planner"
        if normalized.startswith("code") or normalized.startswith("solve"):
            return "coder"
        if normalized.startswith("ci"):
            return "ci"
        if normalized.startswith("plat"):
            return "platform"
        if normalized.startswith("pr"):
            return "pr-helper"

    lbls = [l.lower() for l in (labels or [])]
    for lbl in lbls:
        if "plan" in lbl or "audit" in lbl:
            return "planner"
        if "ci" in lbl or "workflow" in lbl or "pipeline" in lbl:
            return "ci"
        if "platform" in lbl or "infrastructure" in lbl:
            return "platform"
        if "pr-helper" in lbl or "gate" in lbl:
            return "pr-helper"
        if "coder" in lbl or "solver" in lbl or "bug" in lbl or "feature" in lbl:
            return "coder"

    text = f"{title} {body}"
    for role, pat in ROLE_PATTERNS.items():
        if pat.search(text):
            return role

    return "coder"


def fetch_open_prs_head_branches(repo_dir: Path = ROOT_DIR) -> set[str]:
    """Fetch head branches of all open PRs."""
    try:
        res = subprocess.run(
            ["gh", "pr", "list", "--state", "open", "--json", "headRefName"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=20,
        )
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            return {pr.get("headRefName", "") for pr in data if isinstance(pr, dict)}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as err:
        logger.debug("Failed to fetch open PRs: %s", err)
    return set()


def fetch_in_progress_issues_by_slot(repo_dir: Path = ROOT_DIR) -> dict[str, int]:
    """Fetch issues claimed by agent slots in status:in-progress."""
    slots_busy: dict[str, int] = {}
    try:
        res = subprocess.run(
            ["gh", "issue", "list", "--label", "status:in-progress", "--json", "number,assignees,title,body"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=20,
        )
        if res.returncode == 0 and res.stdout.strip():
            issues = json.loads(res.stdout)
            for iss in issues:
                num = iss.get("number", 0)
                for a in iss.get("assignees", []):
                    login = a.get("login", "")
                    if login:
                        slots_busy[login] = num
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as err:
        logger.debug("Failed to fetch in-progress issues: %s", err)
    return slots_busy


def fetch_active_mesh_heartbeats(base_url: str | None = None) -> set[str]:
    """Check backend mesh registry for nodes currently holding active leases."""
    active_nodes: set[str] = set()
    mesh_url = base_url or os.environ.get("SUPREME_MESH_URL")
    if not mesh_url:
        return active_nodes

    try:
        import urllib.request
        req = urllib.request.Request(f"{mesh_url}/api/v1/nodes", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                nodes = data.get("nodes", [])
                for n in nodes:
                    if n.get("lease_active", False):
                        node_id = n.get("node_id", "")
                        if node_id:
                            active_nodes.add(node_id)
    except Exception as err:
        logger.debug("Mesh registry unavailable: %s", err)
    return active_nodes


def fetch_existing_role_branches(role: str, repo_dir: Path = ROOT_DIR) -> list[int]:
    """Find all existing local or remote branch indices for a role (e.g. coder-1 -> 1)."""
    indices: set[int] = set()
    pat = re.compile(rf"^(?:remotes/origin/|origin/)?{re.escape(role)}-([0-9]+)(?:-.*)?$")

    try:
        res = subprocess.run(
            ["git", "branch", "-a", "--list", f"*{role}-*"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=15,
        )
        if res.returncode == 0:
            for raw_line in res.stdout.splitlines():
                line = raw_line.strip().lstrip("* ").strip()
                m = pat.match(line)
                if m:
                    indices.add(int(m.group(1)))
    except (OSError, subprocess.SubprocessError) as err:
        logger.debug("Failed to list role branches: %s", err)

    return sorted(list(indices))


def evaluate_slot_occupancy(
    role: str,
    index: int,
    open_pr_branches: set[str],
    busy_issue_slots: dict[str, int],
    active_heartbeats: set[str],
) -> SlotStatus:
    """Evaluate whether a specific slot (e.g., coder-1) is busy or empty."""
    branch = f"{role}-{index}"

    # 1. Open PR Check
    for ref in open_pr_branches:
        if extract_slot_index(ref, role) == index or ref == branch:
            return SlotStatus(
                role=role,
                index=index,
                branch_name=branch,
                is_occupied=True,
                occupancy_reason=f"Active open PR exists for branch '{ref}'",
            )

    # 2. In-Progress Claim Check
    for assignee, iss_num in busy_issue_slots.items():
        if extract_slot_index(assignee, role) == index or assignee == branch:
            return SlotStatus(
                role=role,
                index=index,
                branch_name=branch,
                is_occupied=True,
                occupancy_reason=f"Claimed by issue #{iss_num} in status:in-progress",
            )

    # 3. Live Heartbeat Lease Check
    for node in active_heartbeats:
        if extract_slot_index(node, role) == index or node == branch:
            return SlotStatus(
                role=role,
                index=index,
                branch_name=branch,
                is_occupied=True,
                occupancy_reason=f"Active heartbeat lease held by node '{node}'",
            )

    return SlotStatus(
        role=role,
        index=index,
        branch_name=branch,
        is_occupied=False,
        occupancy_reason="",
    )


def find_next_available_slot(
    role: str,
    issue: int | None = None,
    title: str = "",
    repo_dir: Path = ROOT_DIR,
) -> SlotStatus:
    """Search for the lowest available slot gap (first free integer >= 1)."""
    # Synchronize remote branches
    try:
        subprocess.run(["git", "fetch", "origin", "--prune"], cwd=str(repo_dir), check=False, capture_output=True)
    except Exception:
        pass

    open_prs = fetch_open_prs_head_branches(repo_dir=repo_dir)
    busy_issues = fetch_in_progress_issues_by_slot(repo_dir=repo_dir)
    active_heartbeats = fetch_active_mesh_heartbeats()
    existing_indices = set(fetch_existing_role_branches(role, repo_dir=repo_dir))

    # Check candidate slots sequentially starting from 1 to find first gap
    candidate = 1
    while True:
        status = evaluate_slot_occupancy(
            role=role,
            index=candidate,
            open_pr_branches=open_prs,
            busy_issue_slots=busy_issues,
            active_heartbeats=active_heartbeats,
        )
        if not status.is_occupied and candidate not in existing_indices:
            break
        candidate += 1

    selected_index = candidate

    # Format branch name: <lane>-<N>-<issue#>-<slug>
    if issue:
        slug = make_branch_slug(title)
        branch_name = f"{role}-{selected_index}-{issue}-{slug}" if slug else f"{role}-{selected_index}-{issue}"
    elif title:
        slug = make_branch_slug(title)
        branch_name = f"{role}-{selected_index}-{slug}" if slug else f"{role}-{selected_index}"
    else:
        branch_name = f"{role}-{selected_index}"

    return SlotStatus(
        role=role,
        index=selected_index,
        branch_name=branch_name,
        is_occupied=False,
        occupancy_reason="",
    )


def checkout_group_branch(group_name: str, repo_dir: Path = ROOT_DIR) -> bool:
    """Share-or-create the group branch (Connected Work model, #2378).

    # বাংলা মন্তব্য: গ্রুপ ব্রাঞ্চ রিমোটে থাকলে তার head থেকেই checkout হয় —
    # গ্রুপের আগের এজেন্টদের কমিট সংরক্ষিত থাকে। না থাকলে origin/main থেকে
    # তৈরি হয়। slot-branch-এর মতো reset-to-main কখনোই নয় — গ্রুপ কমিট ধ্বংস হবে।
    """
    branch = f"{GROUP_BRANCH_PREFIX}{group_name}"
    try:
        probe = subprocess.run(
            ["git", "ls-remote", "--exit-code", "--heads", "origin", branch],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if probe.returncode == 0:
            subprocess.run(
                ["git", "fetch", "origin", branch],
                cwd=str(repo_dir), check=False, capture_output=True, timeout=60,
            )
            base = f"origin/{branch}"
        else:
            base = "origin/main"
        res = subprocess.run(
            ["git", "checkout", "-B", branch, base],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.returncode == 0
    except (subprocess.SubprocessError, OSError) as e:
        print(f"Error checking out group branch {branch}: {e}", file=sys.stderr)
        return False


def checkout_slot_branch(branch_name: str, base_branch: str = "origin/main", repo_dir: Path = ROOT_DIR) -> bool:
    """Checkout the slot branch cleanly synced with origin/main."""
    try:
        subprocess.run(["git", "fetch", "origin", "main"], cwd=str(repo_dir), check=True, capture_output=True)
        res = subprocess.run(
            ["git", "checkout", "-B", branch_name, base_branch],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.returncode == 0
    except (subprocess.SubprocessError, OSError, Exception) as e:
        print(f"Error checking out branch {branch_name}: {e}", file=sys.stderr)
        return False


def find_next_unclaimed_issue(role: str | None = None, repo_dir: Path = ROOT_DIR) -> dict[str, Any] | None:
    """Autonomous Queue Resolver: Find the highest priority unclaimed issue for role.

    Precedence order (SupremeAI Constitution & GSPQ):
    1. P0-critical
    2. Active group sequences (group:step-2, group:step-3, sorted by seq:N)
    3. P1-high
    4. P2-medium
    5. Oldest issue first
    """
    try:
        res = subprocess.run(
            ["gh", "issue", "list", "--state", "open", "--limit", "400", "--json", "number,title,body,labels,createdAt"],
            cwd=str(repo_dir),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        issues = json.loads(res.stdout)
    except Exception as e:
        logger.warning(f"Could not query GitHub issues for auto-discovery: {e}")
        return None

    claimable = []
    for i in issues:
        lbls = [l.get("name", "") if isinstance(l, dict) else str(l) for l in i.get("labels", [])]
        # Skip in-progress, has-pr, and ledger issues
        if "status:in-progress" in lbls or "has-pr" in lbls or "type:ledger" in lbls:
            continue
        # If role specified, match explicit handoff or generic pool
        if role:
            handoffs = [l for l in lbls if l.startswith("handoff:")]
            if handoffs and f"handoff:{role}" not in handoffs:
                continue
        claimable.append((i, lbls))

    if not claimable:
        return None

    group_deps = load_group_dependencies(repo_dir=repo_dir)

    # Collect all groups present across open issues to detect in-flight predecessor groups
    active_open_groups: set[str] = set()
    for item in issues:
        l_names = [l.get("name", "") if isinstance(l, dict) else str(l) for l in item.get("labels", [])]
        grp = extract_group_name(l_names)
        if grp:
            active_open_groups.add(grp)

    def priority_sort_key(item):
        i, lbls = item
        num = i["number"]
        created = i.get("createdAt", "")
        if "P0-critical" in lbls:
            return (0, 0, created, num)

        grp = extract_group_name(lbls)
        seq_num = 99
        for l in lbls:
            m = re.search(r"seq:(\d+)", l)
            if m:
                seq_num = int(m.group(1))
                break

        if grp:
            pred_grp = group_deps.get(grp)
            # বাংলা মন্তব্য: Predecessor Group Merge Hold Engine (#2408):
            # যদি এই গ্রুপের predecessor গ্রুপ এখনো ওপেন থাকে, তবে আগে predecessor শেষ হতে হবে।
            pred_active = bool(pred_grp and pred_grp in active_open_groups)
            group_tier = 2 if pred_active else 1
            return (group_tier, seq_num, created, num)

        if "P1-high" in lbls:
            return (3, 0, created, num)
        if "P2-medium" in lbls:
            return (4, 0, created, num)
        return (5, 0, created, num)

    claimable.sort(key=priority_sort_key)
    top_issue, top_lbls = claimable[0]
    return {
        "number": top_issue["number"],
        "title": top_issue.get("title", ""),
        "body": top_issue.get("body", ""),
        "labels": top_lbls,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Role-Scoped Branch Slot Acquirer & Dynamic Gap Allocator (Branch-as-Lease)"
    )
    parser.add_argument("--role", choices=VALID_ROLES, help="Explicit role pool")
    parser.add_argument("--issue", type=int, help="GitHub Issue number to claim (optional: auto-discovered if omitted)")
    parser.add_argument("--task", type=str, help="Task description to infer role from")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without checking out branch")
    parser.add_argument("--format", choices=["json", "text"], default="text", help="Output format")

    args = parser.parse_args()

    title = args.task or ""
    body = ""
    labels = []
    auto_discovered = False

    if args.issue:
        try:
            res = subprocess.run(
                ["gh", "issue", "view", str(args.issue), "--json", "title,body,labels"],
                cwd=str(ROOT_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
            )
            data = json.loads(res.stdout)
            title = data.get("title", "")
            body = data.get("body", "")
            labels = [lbl.get("name", "") for lbl in data.get("labels", []) if isinstance(lbl, dict)]
        except Exception as e:
            print(f"Warning: could not fetch issue #{args.issue}: {e}", file=sys.stderr)
    elif not args.task:
        # Autonomous Queue Resolver: Auto-discover the next priority unclaimed issue for role
        discovered = find_next_unclaimed_issue(role=args.role, repo_dir=ROOT_DIR)
        if discovered:
            args.issue = discovered["number"]
            title = discovered["title"]
            body = discovered.get("body", "")
            labels = discovered.get("labels", [])
            auto_discovered = True

    role = infer_role_from_context(title=title, body=body, labels=labels, explicit_role=args.role)

    # Flexible Group Branching (#2378): group:* label -> shared group branch.
    group_name = extract_group_name(labels)

    result_payload = {
        "role": role,
        "workflow": "group" if group_name else "independent",
        "group_name": group_name,
        "slot_index": None,
        "branch_name": "",
        "is_occupied": False,
        "checkout_performed": False,
        "issue": args.issue,
        "auto_discovered": auto_discovered,
    }

    if group_name:
        # Connected Work: ১ গ্রুপ ব্রাঞ্চ শেয়ার — slot-gap স্ক্যান অপ্রাসঙ্গিক।
        branch_name = f"{GROUP_BRANCH_PREFIX}{group_name}"
        result_payload["branch_name"] = branch_name
        if not args.dry_run:
            success = checkout_group_branch(group_name, repo_dir=ROOT_DIR)
            result_payload["checkout_performed"] = success
            if not success:
                print(f"Failed to checkout {branch_name}", file=sys.stderr)
                return 1
    else:
        slot = find_next_available_slot(role=role, issue=args.issue, title=title, repo_dir=ROOT_DIR)
        result_payload["slot_index"] = slot.index
        branch_name = slot.branch_name
        result_payload["branch_name"] = branch_name
        result_payload["is_occupied"] = slot.is_occupied
        if not args.dry_run:
            success = checkout_slot_branch(slot.branch_name, repo_dir=ROOT_DIR)
            result_payload["checkout_performed"] = success
            if not success:
                print(f"Failed to checkout {slot.branch_name}", file=sys.stderr)
                return 1

    if args.format == "json":
        print(json.dumps(result_payload, indent=2))
    else:
        if auto_discovered:
            print(f"⚡ [Autonomous Queue Resolver] Next priority issue: #{args.issue} ({title})")
        print(f"🎯 Assigned Role:   {role}")
        if group_name:
            print("🤝 Workflow:        Connected Group Work (#2378) — shared group branch, 1 group PR")
            print(f"🌿 Group Branch:    {branch_name}")
        else:
            print(f"🌿 Acquired Slot:   {branch_name} (Slot Gap Index: {result_payload['slot_index']})")
        if args.dry_run:
            print("🔍 Mode:            Dry Run (No branch checkout performed)")
        elif group_name:
            shared = "shared from remote group head" if result_payload["checkout_performed"] else "(dry-run)"
            print(f"✅ Checked out:     {branch_name} {shared}")
        else:
            print(f"✅ Checked out:     {branch_name} (synced cleanly with origin/main)")
        if args.issue:
            print(f"👉 Next Step:       ./scripts/ci/atomic_claim.sh {args.issue} {role}-{result_payload['slot_index'] or ''}")
        else:
            print("💡 No unclaimed issues found. Dual-State Loop: Check open PRs with 'gh pr list --state open' for Peer Review.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
