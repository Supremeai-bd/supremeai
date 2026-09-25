---
# ── Existing SupremeAI frontmatter (preserved) ──
id: <unique-kebab-id>
subject: "<Plan Name>"
document_role: architecture           # architecture | policy | registry | graph | matrix | guide
planning_authority: "<Circle> Circle"
canonical: true
status: proposed                      # proposed | active | implementing | verifying | stable | blocked | archived
evidence_state: none                  # none | partial | verified
disposition: retain                   # retain | archive | delete
last_verified: <YYYY-MM-DD>
supersedes: []                        # list of legacy doc ids this replaces
superseded_by: []
target_scope: supremeai_internal      # supremeai_internal | combined_ecosystem | user_project

# ── NEW: relationship layer (the part that was missing) ──
plan_id: Pxx                          # registry ID, e.g. P13
domain: <domain>                      # one of the 9 domains
depends_on: []                        # plan_ids this plan needs to be Stable first
enables: []                           # plan_ids this plan makes possible
implemented_by: "Milestone: <name>"   # GitHub milestone / execution vehicle
verified_by: "<audit/test>"           # how we know it works
related_to: []                        # plan_ids that are coupled but not blocking
---

# Plan: <Plan Name>

> **Status:** `<status>` · **Owner:** `<Circle> Circle` · **ID:** `Pxx`

## Purpose

One paragraph. What does this plan make possible, and why does it matter *now*?

## Depends On

- [Pxx — Name](../<domain>/<file>.md) — *why: <one-line reason>*

> If this list is empty, this plan is foundational (like P01). Foundational
> plans carry the highest blast radius — treat every change as a regression risk.

## Enables

- [Pxx — Name](../<domain>/<file>.md) — *how: <one-line reason>*

## Related

- [Pxx — Name](../<domain>/<file>.md) — *coupling: <one-line reason>*

## Source of Truth

This document is the **canonical** definition of `<topic>`. Other documents
must **reference** it (`See: <Plan Name>`) rather than duplicate its content.
If you need to add detail, edit this file — do not create a sibling plan.

## Architecture

### Current state
What exists today (with evidence links to audit reports / tests).

### Target state
What this plan moves toward. Keep it crisp — the *how* lives in milestones.

### Non-goals
Explicitly name what this plan does **not** attempt, to prevent scope creep.

## Execution

See GitHub milestone: **<Milestone name>**

| Milestone | Status | Owner | Tracking |
|-----------|--------|-------|----------|
| <milestone> | 🟦 Active | <Circle> | `<link or issue range>` |

Break the milestone into issues; do not keep implementation detail in this doc.

## Verification

| Check | Type | Passing? | Evidence |
|-------|------|----------|----------|
| <check name> | unit / integration / e2e / audit | ✅ / ⚠️ / ❌ | `<link>` |

A plan reaches **Stable** only when every verification row is ✅ and the
evidence is linked. Until then it stays Active / Implementing / Verifying.

## Legacy documents superseded

This plan consolidates the following legacy files (now archived under
`docs/archive/plans/`):

| Legacy file | Disposition | Note |
|-------------|-------------|------|
| `docs/plans/<old>.md` | archive | superseded by this canonical doc |

## Change log

| Date | Change | Author |
|------|--------|--------|
| <YYYY-MM-DD> | Plan created | <name> |
