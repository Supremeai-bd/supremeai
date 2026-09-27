# SupremeAI — Issue Priority Policy (Claim Order & Auditor Stewardship)

> **Founder directive:** issues are worked in **automatic priority order** — many old issues are
> not that important, a new one can be more important. The **auditor maintains the priorities**;
> every lane **claims from the highest priority first**.
>
> **বাংলা সারমর্ম:** কাজ হবে priority অনুযায়ী — পুরনো মানে গুরুত্বপূর্ণ নয়। Auditor priority ঠিক রাখবে,
> সবাই সর্বোচ্চ priority থেকে claim করবে।
>
> Companion: [`GOLDEN_RULES.md`](GOLDEN_RULES.md) rule 1 · Charter invariant 10 · Tool: `scripts/agents/next_claimable.sh`

---

## 1. The Priority Ladder

| Label | Name | Definition | Examples |
| :--- | :--- | :--- | :--- |
| `P0-critical` | Production is burning | Main is red, security breach, data loss, deployment down, merge train frozen | main CI red, 🔴 incident audits |
| `P1-high` | Blocks the ecosystem or the founder | Deadlocks, founder-directed work, security fixes awaiting merge, slot/claim breakage | merge-train stall, atomic_claim broken, held security PRs |
| `P2-medium` | Normal value work | Features, bug fixes, planned enhancements, docs with behavior impact | typical `fix()`/`feat()` issues |
| `P3-low` | Nice to have | Cleanup, polish, exploratory, nice-to-have docs | refactor suggestions, minor UX |

**Rules of the ladder:**
- Every open, unclaimed issue carries **exactly one** priority label.
- **No label = `P3-low` until triaged.** Unlabeled issues never jump the queue — this is the
  automatic default that makes the ordering safe without any human step.
- **Age never boosts priority.** Old ≠ important (founder's principle). Age is only a tiebreaker
  (FIFO within the same priority) and a de-prioritization signal (Section 4).

## 2. Claim Order (how lanes pick work)

```
1. Higher priority first:      P0-critical → P1-high → P2-medium → P3-low
2. Same priority → oldest first (createdAt ASC — FIFO fairness)
```

Mechanical enforcement — one command shows the exact next issue to claim:

```bash
./scripts/agents/next_claimable.sh <lane>        # planner | coder | ci | pr-helper | browser | platform
```

The script lists the lane's **claimable** issues sorted by the rule above, ending
with the ready-to-paste atomic claim command. **Claimable** = open and NOT
`status:in-progress` (both `status:planned` and `status:unclaimed` mean "awaiting
a claim" — planned is what freshly-triaged auditor work carries; excluding it
would hide new P0/P1 work from every lane). Maintenance ledgers (`type:ledger`)
are never in the queue. **Rule 10 (NEVER IDLE) now means: claim the
highest-priority claimable issue in your lane — not just any issue.**

A lane may skip a priority level ONLY with a stated reason (e.g. capability mismatch,
waiting on a blocker) — commented on the skipped issue. Skipping silently is a rule violation.

## 3. Auditor Stewardship (who keeps priorities truthful)

The **planner lane (auditor)** owns priority correctness:

1. **Triage** new issues promptly: assign the ladder label the issue actually deserves
   (override the P3 default).
2. **Re-score during audits**: priorities drift as reality changes. Every scheduled/deep audit
   re-scores open issues — promotions AND demotions.
3. **Audit trail**: every priority change gets a short reason comment on the issue
   (`priority: P2→P1 — blocks merge train unfreezing (#1870)`). A priority change without a
   reason comment is invalid.
4. **Founder overrides win**: an explicit founder instruction sets priority immediately
   (founder-directed work enters at `P1-high` unless stated otherwise).

## 4. Age Policy (old ≠ important)

| Age (unclaimed) | Action |
| :--- | :--- |
| Any age | Age alone NEVER raises priority |
| 14+ days at P1/P2 | Auditor re-scores at the next audit — if still important, say why; if not, demote |
| 30+ days at P2/P3 | Candidate for `wontfix` review — auditor proposes closing with a reason comment |
| Any age, blocking nothing, superseded | Demote or close (superseded-by link in the reason comment) |

## 5. Automation Boundaries

- **Live (since #1997 implementation, 2026-09-27):**
  - Ordering is enforced mechanically **two ways**: `next_claimable.sh` (per-lane CLI)
    and the **Priority Queue Ledger** — `.github/workflows/priority-queue.yml`
    re-ranks the live queue on **every issue event** (open/close/reopen/relabel)
    and rewrites the ledger issue body. **Founder directive implemented: when the
    #1 issue closes, #2 automatically becomes #1** — the new head even gets a
    promotion comment. Ledger: `scripts/agents/priority_queue_ledger.py`
    (find-by-marker issue `🎯 [PRIORITY-QUEUE-LEDGER]`).
  - **Blocker issues are dedup-guarded**: `create_blocker_issue.py` refuses
    same-title duplicates (the 2026-09-27 triage closed ~80 auto-created duplicate
    conflict trackers born from a broken search phrase), and
    `auto-update-pr-drift.yml` auto-closes conflict trackers once the PR branch
    syncs clean with main.
- **Labels remain the truth**: automation only *sorts* and *publishes* them.
  Stewardship (triage, re-scoring, reason comments) stays with the auditor (§3).
- **Planned (ci lane)**: auto-triage on `issues:opened` — default priority from
  heuristics (security → P1, main-red ci-doctor → P0/P1, epic → P2, ...). Until
  it lands, the §1 default (no label = P3) plus auditor triage applies.

## 6. Change Control

This policy changes like every rule: 1 issue = 1 branch = 1 PR (see
[`RULES_INDEX.md`](RULES_INDEX.md) Layer 3). Priority LABELS on individual issues are changed by
the auditor per Section 3 — label churn is not a rules change.
