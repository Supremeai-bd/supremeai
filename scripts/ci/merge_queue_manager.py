#!/usr/bin/env python3
"""Merge Queue Manager - priority-ordered auto-merge queue.

# বাংলা: PR-গুলো priority/group/seq অনুসারে merge queue-তে সাজায়।
# P0 আগে merge হবে, P1 পরে, same-group-এ seq:1 আগে, seq:2 পরে।
# Admin দেখেই বুঝবে কোন PR আগে, কোনটা পরে, কোনটা hold-এ।
#
# Usage:
#     python scripts/ci/merge_queue_manager.py --plan
#     python scripts/ci/merge_queue_manager.py --execute [--limit 3]
#     python scripts/ci/merge_queue_manager.py --hold <PR-number>
#     python scripts/ci/merge_queue_manager.py --release <PR-number>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any

REPO = os.environ.get("GH_REPO", "SaifulHaqueNiloy/supremeai")

PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def gh(*args: str) -> str:
    """Run gh CLI."""
    try:
        r = subprocess.run(
            ["gh", *args, "--repo", REPO],
            capture_output=True, text=True, timeout=15, check=False,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def get_open_prs() -> list[dict[str, Any]]:
    """Fetch all open PRs with labels."""
    raw = gh("pr", "list", "--state", "open", "--json",
             "number,title,headRefName,labels,createdAt", "--limit", "50")
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def extract_pr_priority(labels: list[dict]) -> str:
    """Extract priority from PR labels."""
    for l in labels:
        name = l.get("name", "")
        if name in PRIORITY_RANK:
            return name[:2]  # "P0-critical" -> "P0"
    return "P3"


def extract_pr_group(labels: list[dict]) -> str:
    """Extract group from PR labels."""
    for l in labels:
        name = l.get("name", "")
        if name.startswith("group:"):
            return name[6:]
    return ""


def extract_pr_seq(labels: list[dict]) -> int:
    """Extract seq from PR labels."""
    for l in labels:
        name = l.get("name", "")
        m = re.match(r"seq:(\d+)", name)
        if m:
            return int(m.group(1))
    return 0


def has_queue_hold(labels: list[dict]) -> bool:
    """Check if PR has queue:hold label."""
    return any(l.get("name") == "queue:hold" for l in labels)


def plan_merge_queue(prs: list[dict]) -> list[dict]:
    """Sort PRs into merge queue order.

    Order: priority (P0 first) -> group (no-group first) -> seq (0 first) -> oldest
    """
    items = []
    for pr in prs:
        labels = pr.get("labels", [])
        priority = extract_pr_priority(labels)
        group = extract_pr_group(labels)
        seq = extract_pr_seq(labels)
        held = has_queue_hold(labels)

        items.append({
            "number": pr.get("number"),
            "title": pr.get("title", ""),
            "branch": pr.get("headRefName", ""),
            "priority": priority,
            "group": group,
            "seq": seq,
            "held": held,
            "created_at": pr.get("createdAt", ""),
            "merge_position": 0,  # assigned below
        })

    # Sort: priority -> has_group (no-group first) -> group name -> seq -> created_at
    items.sort(key=lambda x: (
        PRIORITY_RANK.get(x["priority"], 3),
        0 if not x["group"] else 1,
        x["group"],
        x["seq"],
        x["created_at"],
    ))

    # Assign merge positions
    for i, item in enumerate(items):
        item["merge_position"] = i + 1

    return items


def can_merge(item: dict, all_items: list[dict]) -> tuple[bool, str]:
    """Check if a PR can be merged (position #1 + not held + predecessor merged)."""
    if item["merge_position"] != 1:
        return False, f"position #{item['merge_position']} (waiting for #1 to merge)"

    if item["held"]:
        return False, f"queue:hold (group seq predecessor not merged)"

    # Check group predecessor: if this is seq:2, is seq:1 merged?
    if item["group"] and item["seq"] > 1:
        predecessor_seq = item["seq"] - 1
        # Check if predecessor PR exists and is merged
        # (in a real implementation, we'd check GitHub for the merged PR)
        # For now: assume predecessor is merged if not in current open PR list
        predecessor_open = any(
            i["group"] == item["group"] and i["seq"] == predecessor_seq
            for i in all_items
        )
        if predecessor_open:
            return False, f"seq:{predecessor_seq} still open (group sequential block)"

    return True, "ready to merge"


def execute_merge(pr_number: int) -> bool:
    """Merge a PR via gh CLI (squash)."""
    result = gh("pr", "merge", str(pr_number), "--squash", "--delete-branch")
    return bool(result)


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge Queue Manager (#2925)")
    parser.add_argument("--plan", action="store_true", help="Show merge queue order")
    parser.add_argument("--execute", action="store_true", help="Merge #1 in queue")
    parser.add_argument("--limit", type=int, default=1, help="Max PRs to merge")
    parser.add_argument("--hold", type=int, help="Add queue:hold to PR")
    parser.add_argument("--release", type=int, help="Remove queue:hold from PR")
    args = parser.parse_args()

    if args.hold:
        gh("pr", "edit", str(args.hold), "--add-label", "queue:hold")
        print(f"PR #{args.hold}: queue:hold added")
        return 0

    if args.release:
        gh("pr", "edit", str(args.release), "--remove-label", "queue:hold")
        print(f"PR #{args.release}: queue:hold removed")
        return 0

    prs = get_open_prs()
    if not prs:
        print("No open PRs.")
        return 0

    queue = plan_merge_queue(prs)

    if args.plan or not args.execute:
        print(f"\n{'='*70}")
        print(f"  Merge Queue ({len(queue)} PRs)")
        print(f"{'='*70}")
        print(f"{'Pos':>3}  {'PR':>5}  {'Pri':>3}  {'Group':>15}  {'Seq':>3}  {'Hold':>4}  {'Status':>10}  Title")
        print(f"{'-'*100}")
        for item in queue:
            can, reason = can_merge(item, queue)
            status = "MERGE" if can else "HOLD"
            print(f"{item['merge_position']:>3}  #{item['number']:>4}  {item['priority']:>3}  "
                  f"{item['group'][:15] or '-':>15}  {item['seq'] or '-':>3}  "
                  f"{'YES' if item['held'] else '-':>4}  {status:>10}  {item['title'][:40]}")
        print(f"\nNext to merge: #{queue[0]['number'] if queue else 'N/A'}")
        return 0

    if args.execute:
        merged = 0
        for item in queue[:args.limit]:
            can, reason = can_merge(item, queue)
            if can:
                print(f"Merging PR #{item['number']} ({item['priority']} {item['title'][:40]})...")
                if execute_merge(item["number"]):
                    print(f"  Merged!")
                    merged += 1
                else:
                    print(f"  Merge failed")
            else:
                print(f"PR #{item['number']}: HOLD ({reason})")
        print(f"\nMerged {merged} PR(s).")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
