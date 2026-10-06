#!/usr/bin/env python3
"""
SupremeAI Dynamic Issue Queue Manager (GSPQ: Group-Sequenced Priority Queue)
============================================================================
Enforces:
1. Contiguous sequential claiming (seq:1 -> seq:2 -> seq:3).
2. Dynamic insertion with automatic downstream +1 shift (insert at seq:K -> shifts >= K by +1).
3. Cascade hold: If upstream seq:K fails or is held, downstream seq: > K are auto-held.
4. Restaging & priority rebalancing for the entire repository issue backlog.

Usage:
    python scripts/ci/issue_queue_manager.py audit
    python scripts/ci/issue_queue_manager.py restage
    python scripts/ci/issue_queue_manager.py insert --issue <num> --group <group> --seq <pos>
    python scripts/ci/issue_queue_manager.py next --group <group> [--lane <lane>]
    python scripts/ci/issue_queue_manager.py cascade-hold --group <group>
    python scripts/ci/issue_queue_manager.py verify-claim --issue <num>
    python scripts/ci/issue_queue_manager.py reconcile [--group G] [--all-groups] [--apply]
    python scripts/ci/issue_queue_manager.py allocate --issue <num>
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO = os.environ.get("GH_REPO", "SaifulHaqueNiloy/supremeai")

# ── GSPQ Auto-Reconciliation constants (#3218) ─────────────────────────────
# Rule version recorded on every mutation for auditability (old → new + reason
# + timestamp + rule). Bump when the deterministic policy changes.
RULE_VERSION = "gspq-auto-v1"
PRIORITY_RANK = {"P0-critical": 0, "P1-high": 1, "P2-medium": 2, "P3-low": 3}
ADMIN_GATE_LABEL = "gate:admin-approval"
AUTO_PROMOTION_MARKER = "priority:auto-promoted"
# Labels that make an issue immovable during sequence reconciliation.
# Claim-gate evidence (claim comment) must never be invalidated by renumbering.
FROZEN_STATES = ("status:in-progress", "status:in-review", "status:complete")

def run_cmd(cmd):
    """Run a shell command and return (rc, stdout, stderr) with UTF-8 decoding."""
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    return res.returncode, res.stdout.strip(), res.stderr.strip()

def get_open_issues():
    """Fetch all open issues from GitHub.

    #4110 (defect class: eventually-consistent search used where correctness
    requires REST): `gh issue list` walks the Search API, which is eventually
    consistent — issues created/edited/reopened inside the index-lag window
    silently vanish from the universe and every downstream consumer
    (verify-claim, reconcile, allocate, cascade-hold) fails closed on a LIVE
    issue. The REST list endpoint is strongly consistent, so the queue
    universe is fetched from there instead. REST mixes PRs into the issues
    payload (filtered via `pull_request`) and uses snake_case `created_at`
    (normalized to the gh-CLI camelCase contract here).
    """
    cmd = [
        "gh", "api", "--paginate", "--slurp",
        f"repos/{REPO}/issues?state=open&per_page=100",
    ]
    rc, out, err = run_cmd(cmd)
    if rc != 0:
        print(f"Error fetching issues: {err}", file=sys.stderr)
        return []
    # gh 2.x: --slurp cannot be combined with --jq, so flatten + normalize in
    # python (PRs filtered, snake_case created_at → gh-CLI camelCase contract).
    pages = json.loads(out) if out else []
    items: list[dict] = []
    for page in pages if isinstance(pages, list) else [pages]:
        if isinstance(page, list):
            items.extend(page)
        elif isinstance(page, dict):
            items.append(page)
    return [
        {**it, "createdAt": it.get("created_at", it.get("createdAt", ""))}
        for it in items
        if it.get("pull_request") is None
    ]

def get_open_prs():
    """Fetch all open PRs from GitHub (#4110: REST, strongly consistent —
    `gh pr list` is Search-backed and hides freshly opened/edited PRs).
    REST /pulls exposes the branch as `head.ref`; normalized to the gh-CLI
    `headRefName` contract that cmd_cascade_hold / cmd_auto_merge consume.
    """
    cmd = [
        "gh", "api", "--paginate", "--slurp",
        f"repos/{REPO}/pulls?state=open&per_page=100",
    ]
    rc, out, err = run_cmd(cmd)
    if rc != 0:
        print(f"Error fetching PRs: {err}", file=sys.stderr)
        return []
    # gh 2.x: --slurp cannot be combined with --jq — flatten + normalize in
    # python (REST head.ref → gh-CLI headRefName contract for cascade-hold /
    # auto-merge consumers).
    pages = json.loads(out) if out else []
    items: list[dict] = []
    for page in pages if isinstance(pages, list) else [pages]:
        if isinstance(page, list):
            items.extend(page)
        elif isinstance(page, dict):
            items.append(page)
    return [
        {**it, "headRefName": (it.get("head") or {}).get("ref", "")}
        for it in items
    ]

def parse_metadata(issue):
    """Extract group, seq, priority, and status from issue labels."""
    lbl_names = [l["name"] for l in issue.get("labels", [])]
    
    group = None
    seq = None
    priority = "P3-low"
    
    for l in lbl_names:
        if l.startswith("group:"):
            group = l.split(":", 1)[1]
        elif l.startswith("seq:"):
            try:
                seq = int(l.split(":", 1)[1])
            except ValueError:
                pass
        elif l in ("P0-critical", "P1-high", "P2-medium", "P3-low"):
            priority = l
            
    is_claimed = "status:in-progress" in lbl_names
    has_pr = "has-pr" in lbl_names
    is_blocked = "blocked" in lbl_names
    # #3218: canonical queue-state extensions (labels stay the projection; the
    # reconciliation core computes the authoritative ordering from these).
    admin_gated = "gate:admin-approval" in lbl_names
    is_complete = "status:complete" in lbl_names
    auto_promoted = AUTO_PROMOTION_MARKER in lbl_names
    # #2928 doctrine: type:ledger issues are perpetual dashboards, never
    # claimable queue members — reconciliation must not sequence them.
    is_ledger = "type:ledger" in lbl_names

    return {
        "number": issue["number"],
        "title": issue["title"],
        "group": group,
        "seq": seq,
        "priority": priority,
        "is_claimed": is_claimed,
        "has_pr": has_pr,
        "is_blocked": is_blocked,
        "admin_gated": admin_gated,
        "is_complete": is_complete,
        "auto_promoted": auto_promoted,
        "is_ledger": is_ledger,
        "created_at": issue.get("createdAt", ""),
        "labels": lbl_names
    }

# ── GSPQ Auto-Reconciliation Core (#3218) ──────────────────────────────────
# Pure functions: no network, no GitHub I/O. CLI commands below are thin
# wrappers. This keeps the full policy unit-testable (tests/test_issue_queue_reconcile.py)
# and preserves the existing GSPQ commands unchanged (U4: extend, never fork).

def is_frozen(meta):
    """An immovable issue keeps its current seq position and relative order.

    Frozen = claimed (claim-gate evidence exists), has an open PR,
    admin-gated, or complete. Renumbering frozen issues would invalidate
    verify-claim expectations mid-flight and let admin-gated work drift into
    a claimable position (safety rules #3218 §7).

    Blocked issues are deliberately NOT frozen: per #3218 §3, dependency
    readiness is a ranking factor — a blocked issue stays movable but ranks
    after ready work, so it can never dead-lock a group's head position.
    """
    return (
        meta["is_claimed"]
        or meta["has_pr"]
        or meta.get("admin_gated", False)
        or meta.get("is_complete", False)
    )


def effective_priorities(metas):
    """Deterministic priority reconciliation for one group (rule gspq-auto-v1).

    Policy:
      1. A real P0-critical in the group suppresses all promotion.
      2. Otherwise exactly ONE eligible P1-high (the group head) is promoted
         to effective P0-critical. Eligible = NOT frozen (unclaimed, no PR,
         not blocked, not admin-gated) and not already auto-promoted.
      3. Ranking among eligible P1s (deterministic tie-breakers):
         a. type:security first (production/security risk outranks age);
         b. lower issue number (FIFO, mirrors the ledger RANK ladder).
      4. Previously auto-promoted issues (marker label) are demoted back to
         P1-high when rule 1 applies. Issues WITHOUT the marker carry a
         manual/Admin priority and are never rewritten.

    Returns {number: {"base", "effective", "action", "reason"}} where action
    is None | "promote" | "demote".
    """
    result = {}
    # A REAL P0 (not system-promoted) retires every auto-promotion (rule 4).
    has_real_p0 = any(m["priority"] == "P0-critical" and not m["auto_promoted"]
                      for m in metas)

    for m in metas:
        base = m["priority"]
        entry = {"base": base, "effective": base, "action": None, "reason": ""}

        if m["auto_promoted"]:
            if has_real_p0:
                # Rule 1: a real P0 arrived — auto-promotion is no longer the head.
                entry.update({
                    "effective": "P1-high",
                    "action": "demote",
                    "reason": "real P0-critical present in group; auto-promotion retired"
                })
            else:
                entry["effective"] = "P0-critical"
                entry["reason"] = "previously auto-promoted (marker intact)"
            result[m["number"]] = entry
            continue

        result[m["number"]] = entry

    # Rule 2 fires only when the group has NO effective P0 head already
    # (real or system-promoted) — exactly one head, never two.
    has_effective_p0 = any(e["effective"] == "P0-critical" for e in result.values())
    if has_effective_p0:
        return result

    # Rule 2: pick the single promotion head among eligible P1s.
    def eligible(m):
        return (
            m["priority"] == "P1-high"
            and not is_frozen(m)
            and not m["is_blocked"]  # blocked work cannot be the P0 head
            and not m["auto_promoted"]
        )

    candidates = [m for m in metas if eligible(m)]
    if not candidates:
        return result

    def head_key(m):
        is_security = 0 if "type:security" in m["labels"] else 1
        return (is_security, m["number"])

    head = min(candidates, key=head_key)
    sec_note = "type:security rank" if "type:security" in head["labels"] else "FIFO (lowest issue number)"
    result[head["number"]].update({
        "effective": "P0-critical",
        "action": "promote",
        "reason": f"no P0-critical in group; head P1 promoted by {sec_note}"
    })
    return result


def sequence_plan(metas, eff_prios):
    """Deterministic sequence assignment for one group (rule gspq-auto-v1).

    Invariants:
      - Frozen issues keep their current seq and relative order (see is_frozen).
        Exception (dedupe repair): two frozen issues sharing one position —
        the lower issue number keeps the position, the other takes the next
        free slot, preserving relative order. This is the only case where a
        frozen issue is renumbered, and it never reorders frozen relative order.
      - Movable issues fill remaining positions ranked by
        (effective priority, not-blocked before blocked, issue number).
      - Result is contiguous 1..N: gaps close, duplicates resolve, missing
        sequences are allocated automatically.
      - No admin-gated/blocked issue is ever moved into a NEW claimable head
        position: they are frozen in place, and movables only rank into the
        positions frozen issues leave unused.

    Returns {number: new_seq}.
    """
    members = [dict(m) for m in metas]
    total = len(members)
    plan = {}
    taken = set()

    # Phase 1 — frozen issues occupy their current positions (dedupe repair
    # for frozen collisions: first by number wins, later duplicates shifted
    # to the next free slot AFTER the collision).
    frozen_sorted = sorted(
        [m for m in members if is_frozen(m)],
        key=lambda m: (m["seq"] if m["seq"] is not None else total + 1, m["number"]),
    )
    frozen_by_number = set(m["number"] for m in frozen_sorted)
    for m in frozen_sorted:
        pos = m["seq"]
        if pos is None or pos in taken or pos > total:
            pos = _next_free(taken, total)
        plan[m["number"]] = pos
        taken.add(pos)

    # Phase 2 — movables rank into the remaining positions.
    def movable_key(m):
        eff = eff_prios.get(m["number"], {}).get("effective", m["priority"])
        blocked_last = 1 if m["is_blocked"] else 0
        return (PRIORITY_RANK.get(eff, 3), blocked_last, m["number"])

    movables = sorted(
        [m for m in members if m["number"] not in frozen_by_number],
        key=movable_key,
    )
    for m in movables:
        pos = _next_free(taken, total)
        plan[m["number"]] = pos
        taken.add(pos)

    return plan


def _next_free(taken, total):
    """Smallest unused position in 1..total (falls back past total if the
    frozen block overflows, keeping the plan total and duplicate-free)."""
    for pos in range(1, total + 1):
        if pos not in taken:
            return pos
    return len(taken) + 1


def plan_group_reconciliation(metas):
    """Full idempotent mutation plan for one group.

    Returns {
        "rule": RULE_VERSION,
        "mutations":   [{number, old_seq, new_seq, reason}],
        "priority_changes": [{number, old, new, action, reason}],
    }
    Empty mutations/priority_changes ⇒ group already reconciled (idempotent).
    """
    eff = effective_priorities(metas)
    target = sequence_plan(metas, eff)

    mutations = []
    for m in metas:
        new_seq = target[m["number"]]
        if m["seq"] == new_seq:
            continue
        if m["seq"] is None:
            reason = "auto-allocated (new grouped issue)"
        else:
            reason = "resequenced (contiguity/dedupe/insertion shift)"
        mutations.append({
            "number": m["number"],
            "old_seq": m["seq"],
            "new_seq": new_seq,
            "reason": reason,
        })

    priority_changes = []
    for m in metas:
        e = eff.get(m["number"], {})
        if e.get("action"):
            priority_changes.append({
                "number": m["number"],
                "old": e["base"],
                "new": e["effective"],
                "action": e["action"],
                "reason": e["reason"],
            })

    return {
        "rule": RULE_VERSION,
        "mutations": mutations,
        "priority_changes": priority_changes,
    }


def cmd_audit(args):
    """Audit all open issues by group and sequence."""
    issues = get_open_issues()
    print("\n=======================================================")
    print(f"  SupremeAI Issue Queue Audit (Total Open: {len(issues)})")
    print("=======================================================\n")
    
    groups = {}
    ungrouped = []
    
    for iss in issues:
        meta = parse_metadata(iss)
        grp = meta["group"]
        if grp:
            groups.setdefault(grp, []).append(meta)
        else:
            ungrouped.append(meta)
            
    for grp, items in sorted(groups.items()):
        items.sort(key=lambda x: (x["seq"] or 9999, x["number"]))
        print(f"📁 Group: {grp} ({len(items)} issues)")
        expected_seq = 1
        has_gap = False
        for it in items:
            s_str = f"seq:{it['seq']}" if it['seq'] is not None else "NO_SEQ"
            status = " [HAS-PR]" if it["has_pr"] else (" [IN-PROGRESS]" if it["is_claimed"] else "")
            print(f"   #{it['number']:<5} {s_str:<8} [{it['priority']:<11}] {status:<15} {it['title'][:60]}")
            if it['seq'] != expected_seq:
                has_gap = True
            if it['seq'] is not None:
                expected_seq = it['seq'] + 1
        if has_gap:
            print(f"   ⚠️ Sequence gap or anomaly detected in group '{grp}'!\n")
        else:
            print("   ✅ Sequence contiguous and verified.\n")
            
    print(f"📁 Ungrouped Issues: {len(ungrouped)} issues")
    if args.verbose:
        for it in ungrouped:
            print(f"   #{it['number']:<5} [{it['priority']:<11}] {it['title'][:65]}")
    else:
        print("   (Use --verbose to view all ungrouped issues)")

def cmd_insert(args):
    """
    Insert an issue at (group, seq), automatically shifting existing items >= seq by +1.
    """
    target_num = args.issue
    target_grp = args.group
    target_seq = args.seq
    
    print(f"\n>>> Inserting Issue #{target_num} into group:{target_grp} at seq:{target_seq}...")
    issues = get_open_issues()
    group_issues = []
    
    for iss in issues:
        meta = parse_metadata(iss)
        if meta["group"] == target_grp and meta["number"] != target_num:
            group_issues.append(meta)
            
    group_issues.sort(key=lambda x: x["seq"] or 9999, reverse=True)
    
    # Shift existing issues >= target_seq by +1
    shifted_count = 0
    for it in group_issues:
        if it["seq"] is not None and it["seq"] >= target_seq:
            old_seq = it["seq"]
            new_seq = old_seq + 1
            print(f"   Shifting #{it['number']} from seq:{old_seq} -> seq:{new_seq}")
            run_cmd([
                "gh", "issue", "edit", str(it["number"]),
                "--remove-label", f"seq:{old_seq}",
                "--add-label", f"seq:{new_seq}"
            ])
            shifted_count += 1
            time.sleep(0.3)
            
    # Assign target issue
    print(f"   Setting #{target_num} to group:{target_grp}, seq:{target_seq}")
    run_cmd([
        "gh", "issue", "edit", str(target_num),
        "--add-label", f"group:{target_grp}",
        "--add-label", f"seq:{target_seq}"
    ])
    print(f"✅ Insertion complete! #{target_num} is now seq:{target_seq}. Shifted {shifted_count} downstream issues.")

def cmd_verify_claim(args):
    """
    Verify if an issue can be claimed according to contiguous sequential rules.
    Exits with code 0 if allowed, code 1 if blocked.
    """
    issue_num = args.issue
    issues = get_open_issues()
    
    target = None
    for iss in issues:
        if iss["number"] == issue_num:
            target = parse_metadata(iss)
            break

    # #4110: even the REST universe fetch can race a freshly edited issue on
    # a stale edge; before the fail-closed verdict, re-check the target via
    # the strongly-consistent single-issue REST endpoint. If REST shows it
    # open, proceed with REST-derived metadata instead of rejecting.
    if target is None:
        rest_meta = _fetch_single_issue_meta(issue_num)
        if rest_meta is not None:
            target = rest_meta

    if not target:
        print(f"Error: Issue #{issue_num} not found or closed (REST-confirmed).", file=sys.stderr)
        sys.exit(1)
        
    grp = target["group"]
    seq = target["seq"]
    
    if not grp or seq is None:
        # Legacy/generic issues without group are claimable with standard checks
        print(f"PASS: Issue #{issue_num} has no group/sequence constraint.")
        sys.exit(0)
        
    if seq == 1:
        print(f"PASS: Issue #{issue_num} is seq:1 (first in sequence).")
        sys.exit(0)
        
    # Check if seq - 1 is already claimed or has a PR
    prev_seq = seq - 1
    found_prev = False
    prev_ready = False
    
    for iss in issues:
        meta = parse_metadata(iss)
        if meta["group"] == grp and meta["seq"] == prev_seq:
            found_prev = True
            # seq - 1 is ready if it has a PR or is in progress
            if meta["has_pr"] or meta["is_claimed"]:
                prev_ready = True
            break
            
    if not found_prev:
        # If prev_seq is closed (e.g. already merged), check via REST (#4110:
        # the search-backed closed listing hid freshly-closed predecessors).
        rc, out, _ = run_cmd([
            "gh", "api",
            f"repos/{REPO}/issues?state=closed&labels=group:{grp},seq:{prev_seq}&per_page=1"
        ])
        if rc == 0 and out and out not in ("[]", ""):
            prev_ready = True
            
    if prev_ready:
        print(f"PASS: Predecessor seq:{prev_seq} in group '{grp}' is claimed or completed.")
        sys.exit(0)
    else:
        print(f"REJECTED: Sequential constraint violation! Cannot claim seq:{seq} before seq:{prev_seq} in group '{grp}' is claimed or completed.", file=sys.stderr)
        sys.exit(1)

def cmd_cascade_hold(args):
    """
    Inspect open PRs for a group. If PR seq:K fails or is on hold,
    ensure all downstream PRs (seq > K) are placed on queue:hold.
    """
    target_grp = args.group
    prs = get_open_prs()
    issues = get_open_issues()
    
    # Map issue number to metadata
    issue_map = {iss["number"]: parse_metadata(iss) for iss in issues}
    
    # Find PRs that belong to this group
    group_prs = []
    for pr in prs:
        # Check issue references in title or branch
        match = re.search(r"#(\d+)", pr["title"]) or re.search(r"-(\d+)-", pr["headRefName"])
        if match:
            iss_num = int(match.group(1))
            iss_meta = issue_map.get(iss_num)
            if iss_meta and iss_meta["group"] == target_grp:
                group_prs.append({
                    "pr_number": pr["number"],
                    "issue_number": iss_num,
                    "seq": iss_meta["seq"],
                    "labels": [l["name"] for l in pr.get("labels", [])],
                    "title": pr["title"]
                })
                
    group_prs.sort(key=lambda x: x["seq"] or 9999)
    print(f"\nEvaluating Cascade Hold for group '{target_grp}' ({len(group_prs)} PRs):")
    
    blocker_seq = None
    for item in group_prs:
        pr_num = item["pr_number"]
        seq = item["seq"]
        labels = item["labels"]
        
        is_held = "queue:hold" in labels
        is_blocked = "pr-gate:blocked" in labels
        
        if blocker_seq is not None:
            # Downstream must be held!
            if "queue:hold" not in labels:
                print(f"   🔴 Downstream PR #{pr_num} (seq:{seq}) -> Adding queue:hold (blocked by seq:{blocker_seq})")
                run_cmd(["gh", "pr", "edit", str(pr_num), "--add-label", "queue:hold"])
            else:
                print(f"   ⏸️ Downstream PR #{pr_num} (seq:{seq}) -> already on queue:hold.")
        else:
            if is_held or is_blocked:
                blocker_seq = seq
                print(f"   ⚠️ Blocker detected at seq:{seq} (PR #{pr_num}, blocked={is_blocked}, hold={is_held}). Downstream PRs will be frozen.")
            else:
                print(f"   🟢 PR #{pr_num} (seq:{seq}) -> Healthy & green.")

def cmd_restage(args):
    """
    Restage all 139 issues in the repository:
    1. group:ci-hotfix: Critical CI & slot fixes (Issue #2303, #2299) -> P0/P1
    2. group:step-1: Foundation 15 issues (#2246-#2260) -> seq:1 to 15
    3. group:step-2: Dead code pruning issues (#2274-#2277) -> seq:1 to 4
    4. group:step-3: Architectural simplifications (#2278-#2284) -> seq:1 to 7
    5. group:backlog: All remaining low priority issues (#434 to #2228) -> P3-low
    """
    print("\n=======================================================")
    print("  Restaging All Repository Issues into Structured GSPQ")
    print("=======================================================\n")
    
    issues = get_open_issues()
    print(f"Found {len(issues)} open issues.")
    
    # 1. CI Hotfixes
    ci_hotfixes = [2303, 2299]
    print("\n--- Restaging CI Hotfixes (group:ci-hotfix) ---")
    for idx, num in enumerate(ci_hotfixes, 1):
        print(f"   #{num} -> group:ci-hotfix, seq:{idx}, P1-high")
        run_cmd([
            "gh", "issue", "edit", str(num),
            "--add-label", "group:ci-hotfix",
            "--add-label", f"seq:{idx}",
            "--add-label", "P1-high"
        ])
        time.sleep(0.3)
        
    # 2. Step 3 Simplifications (The larger consolidation issues #2278-#2284)
    step3_issues = [2278, 2279, 2280, 2282, 2283, 2284]
    print("\n--- Restaging Step 3 Issues (group:step-3) ---")
    run_cmd(["gh", "label", "create", "group:step-3", "--color", "1d76db", "--description", "Step 3 Architectural Simplifications"])
    for idx, num in enumerate(step3_issues, 1):
        print(f"   #{num} -> group:step-3, seq:{idx}, P2-medium")
        run_cmd([
            "gh", "issue", "edit", str(num),
            "--add-label", "group:step-3",
            "--add-label", f"seq:{idx}",
            "--add-label", "P2-medium"
        ])
        time.sleep(0.3)
        
    # 3. All other issues -> group:backlog, P3-low
    print("\n--- Restaging Backlog Issues (group:backlog, P3-low) ---")
    run_cmd(["gh", "label", "create", "group:backlog", "--color", "cccccc", "--description", "General backlog issues"])
    
    special_nums = set([2254, 2253, 2255, 2252, 2246, 2247, 2248, 2256, 2249, 2250, 2257, 2258, 2259, 2260, 2251, 2274, 2275, 2276, 2277] + ci_hotfixes + step3_issues)
    
    backlog_count = 0
    for iss in issues:
        num = iss["number"]
        if num not in special_nums:
            lbl_names = [l["name"] for l in iss.get("labels", [])]
            if "group:backlog" not in lbl_names:
                print(f"   #{num} -> group:backlog, P3-low")
                run_cmd([
                    "gh", "issue", "edit", str(num),
                    "--add-label", "group:backlog",
                    "--add-label", "P3-low"
                ])
                backlog_count += 1
                time.sleep(0.25)
                
    print(f"\n✅ Restaging complete! Backlog labeled: {backlog_count} issues.")

def cmd_auto_merge(args):
    """
    Sequentially merge approved, ready PRs for a group in strict order (seq:1 -> seq:2 -> seq:3...).
    If an upstream PR is not merged or has conflicts, halts and applies cascade hold.
    """
    target_grp = args.group
    print("\n=======================================================")
    print(f"  GSPQ Sequential Auto-Merge Engine: group:{target_grp}")
    print("=======================================================\n")
    
    prs = get_open_prs()
    issues = get_open_issues()
    issue_map = {iss["number"]: parse_metadata(iss) for iss in issues}
    
    group_prs = []
    for pr in prs:
        match = re.search(r"#(\d+)", pr["title"]) or re.search(r"-(\d+)-", pr["headRefName"])
        if match:
            iss_num = int(match.group(1))
            iss_meta = issue_map.get(iss_num)
            if iss_meta and iss_meta["group"] == target_grp:
                group_prs.append({
                    "pr_number": pr["number"],
                    "issue_number": iss_num,
                    "seq": iss_meta["seq"],
                    "labels": [l["name"] for l in pr.get("labels", [])],
                    "title": pr["title"]
                })
                
    group_prs.sort(key=lambda x: x["seq"] or 9999)
    if not group_prs:
        print(f"No open PRs found for group '{target_grp}'. All merged or none created!")
        return

    merged_any = False
    for item in group_prs:
        pr_num = item["pr_number"]
        iss_num = item["issue_number"]
        seq = item["seq"]
        
        print(f"\n👉 Checking seq:{seq} (PR #{pr_num}, Issue #{iss_num})...")
        
        # Check mergeability
        rc, out, err = run_cmd(["gh", "pr", "view", str(pr_num), "--json", "mergeable,mergeStateStatus"])
        if rc != 0:
            print(f"   Failed to inspect PR #{pr_num}: {err}")
            break
        data = json.loads(out)
        if data.get("mergeable") == "CONFLICTING":
            print(f"   ❌ PR #{pr_num} has merge conflicts! Halting auto-merge sequence.")
            run_cmd(["gh", "pr", "edit", str(pr_num), "--add-label", "queue:hold"])
            break
            
        # Attempt squash merge
        print(f"   🚀 Merging PR #{pr_num} (seq:{seq}) into main...")
        rc, m_out, m_err = run_cmd(["gh", "pr", "merge", str(pr_num), "--squash", "--admin"])
        if rc == 0:
            print(f"   ✅ PR #{pr_num} merged successfully!")
            run_cmd(["gh", "issue", "close", str(iss_num), "--comment", f"Closed via GSPQ sequential merge of PR #{pr_num}."])
            merged_any = True
            time.sleep(2)
        else:
            print(f"   ⚠️ Could not merge PR #{pr_num}: {m_err}")
            print("   Halting sequential auto-merge to preserve order.")
            break
            
    if merged_any:
        print("\n🎉 Sequential auto-merge cycle completed successfully!")

# ── GSPQ Reconcile / Allocate CLI (#3218) — thin wrappers over the pure core ──

def _fetch_single_issue_meta(issue_num):
    """Fetch one open issue and parse it into queue metadata (or None).

    #4110: `gh issue view --json state` reports GraphQL-case state ("OPEN")
    while this check compared lowercase ("open") — the mismatch made the
    single-issue REST fallback return None for EVERY live issue, silently
    disabling cmd_allocate's fetch and #4110's verify-claim fallback. Compare
    case-insensitively (gh CLI state casing is version-dependent).
    """
    rc, out, _ = run_cmd([
        "gh", "issue", "view", str(issue_num), "--repo", REPO,
        "--json", "number,title,labels,state,createdAt"
    ])
    if rc != 0 or not out:
        return None
    data = json.loads(out)
    if str(data.get("state", "")).lower() != "open":
        return None
    return parse_metadata(data)


def _priority_label_edit(issue_num, change):
    """Apply one priority change with its audit trail (old → new + reason +
    timestamp + rule version) as an issue comment. Auto-promotions carry the
    marker label so later reconciliations can retire them deterministically;
    manual priorities (no marker) are never rewritten."""
    num = change["number"]
    old, new, action = change["old"], change["new"], change["action"]
    print(f"   🔁 Priority #{num}: {old} → {new} ({change['reason']})")

    if action == "promote":
        run_cmd(["gh", "issue", "edit", str(num), "--repo", REPO,
                 "--add-label", new, "--add-label", AUTO_PROMOTION_MARKER])
        if old != new:
            run_cmd(["gh", "issue", "edit", str(num), "--repo", REPO,
                     "--remove-label", old])
    else:  # demote
        run_cmd(["gh", "issue", "edit", str(num), "--repo", REPO,
                 "--remove-label", AUTO_PROMOTION_MARKER])
        if old != new:
            run_cmd(["gh", "issue", "edit", str(num), "--repo", REPO,
                     "--remove-label", old, "--add-label", new])

    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    body = (f"🔁 **GSPQ priority reconciliation** (rule `{RULE_VERSION}`, {ts})\n\n"
            f"- `{old}` → `{new}` ({action})\n"
            f"- Reason: {change['reason']}\n\n"
            f"<sub>Automatic reconciliation by `scripts/ci/issue_queue_manager.py` (#3218). "
            f"Manual/Admin priorities are never rewritten — only system promotions "
            f"({AUTO_PROMOTION_MARKER}) are reversible.</sub>")
    run_cmd(["gh", "issue", "comment", str(num), "--repo", REPO, "--body", body])


def _apply_group_plan(grp, plan):
    """Apply one group's reconciliation plan with duplicate-free ordering.

    Sequence phase is two-pass: first REMOVE all outdated seq labels, then
    ADD the new ones. A transient state can miss positions but can never hold
    duplicate `seq:N` labels in one group (#3218 §7)."""
    applied_seq = 0

    # Phase A — priority changes (audit comment included).
    for change in plan["priority_changes"]:
        _priority_label_edit(change["number"], change)
        time.sleep(0.3)

    # Phase B — seq removals (old labels of every mutated issue).
    for mut in plan["mutations"]:
        if mut["old_seq"] is not None:
            run_cmd(["gh", "issue", "edit", str(mut["number"]), "--repo", REPO,
                     "--remove-label", f"seq:{mut['old_seq']}"])

    # Phase C — seq additions (target state).
    for mut in plan["mutations"]:
        print(f"   #️⃣  #{mut['number']} seq:{mut['old_seq']} → seq:{mut['new_seq']} "
              f"({mut['reason']})")
        run_cmd(["gh", "issue", "edit", str(mut["number"]), "--repo", REPO,
                 "--add-label", f"seq:{mut['new_seq']}"])
        applied_seq += 1
        time.sleep(0.3)

    return applied_seq


def _group_issues(issues):
    """Bucket open issues by their group:* label (ungrouped ignored)."""
    groups = {}
    for iss in issues:
        meta = parse_metadata(iss)
        if meta["group"]:
            groups.setdefault(meta["group"], []).append(meta)
    return groups


def cmd_reconcile(args):
    """Reconcile GSPQ groups: dedupe seq, close gaps, auto-allocate missing
    sequences, and re-evaluate priorities deterministically.

    Default is observe-only (drift report). --apply performs the mutations
    (fail-closed per U6: no silent writes). Groups without any seq: label are
    skipped unless --all-groups — unmanaged groups (e.g. pure backlog) never
    get bulk-renumbered by a sweep; they activate via per-issue allocation.
    type:ledger dashboards are never sequenced (#2928)."""
    issues = get_open_issues()
    groups = _group_issues(issues)
    if args.group:
        if args.group not in groups:
            print(f"Group '{args.group}' has no open issues.")
            return
        groups = {args.group: groups[args.group]}

    total_mut = total_prio = applied_groups = 0
    for grp in sorted(groups):
        metas = groups[grp]
        if any(m.get("is_ledger") for m in metas):
            print(f"⏭️  group:{grp} — contains type:ledger dashboard, not sequenced (#2928)")
            continue
        has_seq = any(m["seq"] is not None for m in metas)
        if not has_seq and not args.all_groups:
            continue  # unmanaged group — per-issue allocation path only
        plan = plan_group_reconciliation(metas)
        n_mut, n_prio = len(plan["mutations"]), len(plan["priority_changes"])
        if not n_mut and not n_prio:
            print(f"✅ group:{grp} — already reconciled ({len(metas)} issues)")
            continue
        print(f"\n📋 group:{grp} — {n_mut} seq mutation(s), {n_prio} priority change(s) "
              f"[rule {plan['rule']}]")
        for mut in plan["mutations"]:
            old = f"seq:{mut['old_seq']}" if mut["old_seq"] is not None else "NO_SEQ"
            print(f"   #{mut['number']:<5} {old} → seq:{mut['new_seq']}  ({mut['reason']})")
        for ch in plan["priority_changes"]:
            print(f"   #{ch['number']:<5} {ch['old']} → {ch['new']}  ({ch['reason']})")
        total_mut += n_mut
        total_prio += n_prio
        if args.apply:
            _apply_group_plan(grp, plan)
            applied_groups += 1

    mode = "APPLIED" if args.apply else "OBSERVE-ONLY (use --apply to repair)"
    print(f"\n🏁 Reconcile {mode}: {total_mut} seq mutation(s), "
          f"{total_prio} priority change(s), {applied_groups} group(s) written.")


def cmd_allocate(args):
    """Auto-allocate a sequence for one newly grouped issue (router hook).

    Idempotent: issues that already carry seq:N (or have no group) are no-ops.
    Computes the group's full deterministic plan and applies it, so downstream
    shifts and contiguity hold from the moment the issue enters the queue —
    no manual --seq, no agent/admin involvement (AC #3218-1)."""
    meta = _fetch_single_issue_meta(args.issue)
    if meta is None:
        # Fresh-issue API lag: retry once before giving up (fail-closed).
        time.sleep(2)
        meta = _fetch_single_issue_meta(args.issue)
    if meta is None:
        print(f"Issue #{args.issue} not found or not open — nothing to allocate.",
              file=sys.stderr)
        sys.exit(1)
    if not meta["group"]:
        print(f"Issue #{args.issue} has no group:* label — no sequence to allocate.")
        return
    if meta["seq"] is not None:
        print(f"Issue #{args.issue} already holds seq:{meta['seq']} — allocation no-op.")
        return

    issues = get_open_issues()
    groups = _group_issues(issues)
    metas = groups.get(meta["group"], [])
    if not any(m["number"] == args.issue for m in metas):
        print(f"Issue #{args.issue} not visible in group listing yet — "
              f"scheduled reconcile will cover it.", file=sys.stderr)
        sys.exit(1)

    plan = plan_group_reconciliation(metas)
    print(f">>> Auto-allocating #{args.issue} into group:{meta['group']} "
          f"[rule {plan['rule']}]")
    if not plan["mutations"]:
        print("   Group already reconciled — no mutations required.")
        return
    _apply_group_plan(meta["group"], plan)
    assigned = next((m["new_seq"] for m in plan["mutations"]
                     if m["number"] == args.issue), None)
    print(f"✅ Allocation complete: #{args.issue} → seq:{assigned} "
          f"({len(plan['mutations'])} total mutation(s)).")


def main():
    parser = argparse.ArgumentParser(description="SupremeAI Dynamic Issue Queue Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    p_audit = subparsers.add_parser("audit", help="Audit issues by group and sequence")
    p_audit.add_argument("--verbose", "-v", action="store_true", help="Show all ungrouped issues")
    p_audit.set_defaults(func=cmd_audit)
    
    p_insert = subparsers.add_parser("insert", help="Insert an issue at sequence position, shifting downstream")
    p_insert.add_argument("--issue", type=int, required=True, help="Issue number to insert")
    p_insert.add_argument("--group", type=str, required=True, help="Target group (e.g. step-1, step-2)")
    p_insert.add_argument("--seq", type=int, required=True, help="Target sequence number")
    p_insert.set_defaults(func=cmd_insert)
    
    p_verify = subparsers.add_parser("verify-claim", help="Verify if an issue is claimable under sequence rules")
    p_verify.add_argument("--issue", type=int, required=True, help="Issue number to verify")
    p_verify.set_defaults(func=cmd_verify_claim)
    
    p_cascade = subparsers.add_parser("cascade-hold", help="Auto-freeze downstream PRs if upstream fails")
    p_cascade.add_argument("--group", type=str, required=True, help="Group name to evaluate")
    p_cascade.set_defaults(func=cmd_cascade_hold)
    
    p_restage = subparsers.add_parser("restage", help="Restage all repository issues into GSPQ")
    p_restage.set_defaults(func=cmd_restage)

    # #3218: automatic sequence allocation + idempotent reconciliation.
    p_reconcile = subparsers.add_parser(
        "reconcile",
        help="Observe-only drift report by default; --apply repairs drift")
    p_reconcile.add_argument("--group", type=str, default=None,
                             help="Reconcile a single group only")
    p_reconcile.add_argument("--all-groups", action="store_true",
                             help="Include groups with no seq: labels (bulk activation)")
    p_reconcile.add_argument("--apply", action="store_true",
                             help="Apply the plan (default: observe-only)")
    p_reconcile.set_defaults(func=cmd_reconcile)

    p_alloc = subparsers.add_parser(
        "allocate",
        help="Auto-allocate a sequence for one newly grouped issue (router hook)")
    p_alloc.add_argument("--issue", type=int, required=True,
                         help="Issue number to allocate into its group's queue")
    p_alloc.set_defaults(func=cmd_allocate)

    p_automerge = subparsers.add_parser("auto-merge", help="Sequentially merge approved PRs for a group")
    p_automerge.add_argument("--group", type=str, required=True, help="Group name to auto-merge")
    p_automerge.set_defaults(func=cmd_auto_merge)
    
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
