#!/usr/bin/env python3
"""Role-Scoped Branch Slot Acquirer & Heartbeat-Aware Allocator.
================================================================
Implements the SupremeAI Elastic Pool & Slot Governance Law:
1. Infers Role from Task/Issue (planner, coder, pr-helper, ci, platform).
2. Scans for existing slots in that role pool (e.g., coder-1, coder-2, ...).
3. Verifies each slot against occupancy:
   - Live Heartbeat / Active Lease in Node Registry.
   - Open PR targeting main on that branch.
   - Active issue claim locked in status:in-progress.
4. If a slot is occupied, advances to the next slot (coder-2, coder-3...).
5. If all existing slots are busy, dynamically creates the next empty slot (coder-(N+1)).
6. Prepares and checks out the clean branch synced strictly with origin/main.

Usage:
    python scripts/agents/acquire_role_slot.py --issue <issue_number>
    python scripts/agents/acquire_role_slot.py --role coder --dry-run
    python scripts/agents/acquire_role_slot.py --task "Full architecture audit" --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        pass

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Canonical roles recognized in docs/master_docs/AGENT_SLOT_REGISTRY.yaml
VALID_ROLES = ("planner", "coder", "pr-helper", "ci", "platform")

ROLE_PATTERNS = {
    "planner": re.compile(r"(?i)\b(plan|planning|audit|architect|architecture|gap-analysis)\b"),
    "ci": re.compile(r"(?i)\b(ci|cd|pipeline|workflow|pre-commit|pre-push|actions|github-actions)\b"),
    "platform": re.compile(r"(?i)\b(platform|render|supabase|redis|upstash|cloudflare|infisical|sweep|health-check)\b"),
    "pr-helper": re.compile(r"(?i)\b(pr-helper|pr-gate|merge-train|rollup|squash-merge|pr-verifier)\b"),
    # Default is coder
}


@dataclass
class SlotStatus:
    role: str
    index: int
    branch_name: str
    is_occupied: bool
    occupancy_reason: str = ""


def infer_role_from_context(
    title: str = "",
    body: str = "",
    labels: Optional[List[str]] = None,
    explicit_role: Optional[str] = None,
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


import logging

logger = logging.getLogger("acquire_role_slot")

def fetch_open_prs_head_branches(repo_dir: Path = ROOT_DIR) -> Set[str]:
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


def fetch_in_progress_issues_by_slot(repo_dir: Path = ROOT_DIR) -> Dict[str, int]:
    """Fetch issues claimed by agent slots in status:in-progress."""
    slots_busy: Dict[str, int] = {}
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


def fetch_active_mesh_heartbeats(base_url: Optional[str] = None) -> Set[str]:
    """Check backend mesh registry for nodes currently holding active leases."""
    active_nodes: Set[str] = set()
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
        # Mesh server may be offline during local standalone CLI execution — safe fallback
        logger.debug("Mesh registry unavailable: %s", err)
    return active_nodes


def fetch_existing_role_branches(role: str, repo_dir: Path = ROOT_DIR) -> List[int]:
    """Find all existing local or remote branch indices for a role (e.g. coder-1 -> 1)."""
    indices: Set[int] = set()
    pat = re.compile(rf"^(?:remotes/origin/)?{re.escape(role)}-([0-9]+)$")

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
    open_pr_branches: Set[str],
    busy_issue_slots: Dict[str, int],
    active_heartbeats: Set[str],
) -> SlotStatus:
    """Evaluate whether a specific slot (e.g., coder-1) is busy or empty."""
    branch = f"{role}-{index}"

    # 1. Open PR Check
    if branch in open_pr_branches:
        return SlotStatus(
            role=role,
            index=index,
            branch_name=branch,
            is_occupied=True,
            occupancy_reason=f"Active open PR exists for branch '{branch}'",
        )

    # 2. In-Progress Claim Check
    if branch in busy_issue_slots:
        issue_num = busy_issue_slots[branch]
        return SlotStatus(
            role=role,
            index=index,
            branch_name=branch,
            is_occupied=True,
            occupancy_reason=f"Claimed by issue #{issue_num} in status:in-progress",
        )

    # 3. Live Heartbeat Lease Check
    if branch in active_heartbeats:
        return SlotStatus(
            role=role,
            index=index,
            branch_name=branch,
            is_occupied=True,
            occupancy_reason=f"Active heartbeat lease held by node '{branch}'",
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
    repo_dir: Path = ROOT_DIR,
    max_search_cap: int = 100,
) -> SlotStatus:
    """Search for the lowest empty slot in the role pool; if all busy, return next N+1."""
    open_prs = fetch_open_prs_head_branches(repo_dir=repo_dir)
    busy_issues = fetch_in_progress_issues_by_slot(repo_dir=repo_dir)
    active_heartbeats = fetch_active_mesh_heartbeats()
    existing_indices = fetch_existing_role_branches(role, repo_dir=repo_dir)

    # Candidate slot pool starting from index 1 up to max(existing)+1
    highest = max(existing_indices) if existing_indices else 0
    search_limit = max(highest + 1, 1)

    for idx in range(1, search_limit + 1):
        status = evaluate_slot_occupancy(
            role=role,
            index=idx,
            open_pr_branches=open_prs,
            busy_issue_slots=busy_issues,
            active_heartbeats=active_heartbeats,
        )
        if not status.is_occupied:
            return status

    # Fallback: create next sequential slot
    next_idx = search_limit + 1
    return SlotStatus(
        role=role,
        index=next_idx,
        branch_name=f"{role}-{next_idx}",
        is_occupied=False,
        occupancy_reason="",
    )


def checkout_slot_branch(branch_name: str, base_branch: str = "origin/main", repo_dir: Path = ROOT_DIR) -> bool:
    """Checkout the slot branch freshly synced with origin/main."""
    try:
        subprocess.run(["git", "fetch", "origin", "main"], cwd=str(repo_dir), check=True)
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Role-Scoped Branch Slot Acquirer & Heartbeat-Aware Allocator"
    )
    parser.add_argument("--role", choices=VALID_ROLES, help="Explicit role pool")
    parser.add_argument("--issue", type=int, help="GitHub Issue number to claim")
    parser.add_argument("--task", type=str, help="Task description to infer role from")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without checking out branch")
    parser.add_argument("--format", choices=["json", "text"], default="text", help="Output format")

    args = parser.parse_args()

    title = args.task or ""
    body = ""
    labels = []

    if args.issue:
        try:
            res = subprocess.run(
                ["gh", "issue", "view", str(args.issue), "--json", "title,body,labels"],
                cwd=str(ROOT_DIR),
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(res.stdout)
            title = data.get("title", "")
            body = data.get("body", "")
            labels = [lbl.get("name", "") for lbl in data.get("labels", []) if isinstance(lbl, dict)]
        except Exception as e:
            print(f"Warning: could not fetch issue #{args.issue}: {e}", file=sys.stderr)

    role = infer_role_from_context(title=title, body=body, labels=labels, explicit_role=args.role)
    slot = find_next_available_slot(role=role, repo_dir=ROOT_DIR)

    result_payload = {
        "role": role,
        "slot_index": slot.index,
        "branch_name": slot.branch_name,
        "is_occupied": slot.is_occupied,
        "checkout_performed": False,
        "issue": args.issue,
    }

    if not args.dry_run:
        success = checkout_slot_branch(slot.branch_name, repo_dir=ROOT_DIR)
        result_payload["checkout_performed"] = success
        if not success:
            print(f"Failed to checkout {slot.branch_name}", file=sys.stderr)
            return 1

    if args.format == "json":
        print(json.dumps(result_payload, indent=2))
    else:
        print(f"🎯 Assigned Role:   {role}")
        print(f"🌿 Acquired Slot:   {slot.branch_name} (Index: {slot.index})")
        if args.dry_run:
            print("🔍 Mode:            Dry Run (No branch checkout performed)")
        else:
            print(f"✅ Checked out:     {slot.branch_name} (synced cleanly with origin/main)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
