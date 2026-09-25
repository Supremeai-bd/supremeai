---
id: codebase-cleanup
subject: "Codebase Cleanup"
document_role: architecture
planning_authority: "Governance Circle"
canonical: true
status: proposed
evidence_state: none
disposition: retain
last_verified: 2026-09-24
supersedes:
  - "docs/plans/phases/plan_inventory_report.md"
  - "docs/plans/phases/plan_reconciliation_register.md"
  - "docs/plans/phases/file_disposition_and_retention_list.md"
  - "docs/plans/CANONICAL_PLANNING_RECONCILIATION_AND_GUARDRAILS_PLAN.md"
superseded_by: []
target_scope: supremeai_internal
plan_id: P12
domain: governance
depends_on: []
enables: []
implemented_by: "Milestone: Doc Consolidation"
verified_by: "lint_plans.py clean + registry ↔ filesystem parity"
related_to: ["P11"]
---

# Plan: Codebase Cleanup

> **Status:** `Proposed` · **Owner:** Governance Circle · **ID:** `P12`
> This plan is the execution sheet for [MIGRATION_MAP.md](../MIGRATION_MAP.md).

## Purpose
Retire the duplicate plans, consolidate the 188-file jungle into the 12-plan
network, and enforce file disposition & retention. The plan that prevents the
documentation jungle from ever regrowing.

## Depends On
*(no upstream — P12 is foundational governance; it can start immediately)*

## Enables
*(terminal — once done, P12 archives itself)*

## Related
- [P11 — Testing & Quality](../governance/testing-quality.md) — *coupling: `lint_plans.py` lives in the quality suite.*

## Source of Truth
This document defines the cleanup. The migration order, disposition rules, and
verification criteria live in [MIGRATION_MAP.md](../MIGRATION_MAP.md); this plan
owns the execution.

## Architecture

### Current state
- 188 plan files; 13 content-derived families; 1 × 305 KB master index.
- Existing `plan_inventory_report.md` and `plan_reconciliation_register.md`
  describe the problem but do not execute the fix.
- `file_disposition_and_retention_list.md` exists but is not enforced.

### Target state
- 12 canonical plan files (P01–P12) + archived legacy under `docs/archive/plans/`.
- `lint_plans.py` extended to check registry ↔ filesystem parity and graph ↔ registry parity.
- Zero `*_v2.md`, `*_final_plan.md`, `*_new_plan.md` filenames.

### Non-goals
- This plan does **not** redefine any technical domain (that's P01–P11).
- This plan does **not** delete audit evidence (audits are retained).

## Execution

See GitHub milestone: **Doc Consolidation**

The migration runs in dependency order (see [MIGRATION_MAP.md](../MIGRATION_MAP.md)):

| Step | Plan cleaned | Legacy docs archived | Status |
|------|--------------|----------------------|--------|
| 1 | P01 Security | ~2 | ⬜ Pending |
| 2 | P03 MCP | ~40 | ⬜ Pending |
| 3 | P08 Infrastructure | ~37 | ⬜ Pending |
| 4 | P02/P04/P05 Intelligence | ~16 | ⬜ Pending |
| 5 | P06/P07 Automation + Experience | ~25 | ⬜ Pending |
| 6 | P09/P10 Observability + Deployment | ~4 | ⬜ Pending |
| 7 | P11 Testing & Quality | ~3 | ⬜ Pending |
| 8 | P12 Cleanup (triage unclassified) | ~33 | ⬜ Pending |

Each step is a separate PR that updates PLAN_REGISTRY.md, PLAN_GRAPH.md, and
PLAN_MATRIX.md in the same commit.

## Verification

| Check | Type | Passing? | Evidence |
|-------|------|----------|----------|
| `lint_plans.py` 0 errors / 0 warnings | lint | ❌ | not yet — cleanup pending |
| Registry ↔ filesystem parity | lint | ❌ | not yet |
| Graph ↔ registry parity | lint | ❌ | not yet |
| Stable plans with un-Stable deps | lint | ❌ | P01 must promote first |
| No versioned filenames | lint | ❌ | 6 found in inventory report |

> P12 stays **Proposed** until the first cleanup PR merges. It reaches
> **Stable** only when the full `lint_plans.py` output is clean.

## Legacy documents superseded

| Legacy file | Disposition | Note |
|-------------|-------------|------|
| `docs/plans/phases/plan_inventory_report.md` | archive | superseded by MIGRATION_MAP.md |
| `docs/plans/phases/plan_reconciliation_register.md` | archive | superseded by PLAN_REGISTRY.md |
| `docs/plans/phases/file_disposition_and_retention_list.md` | archive | superseded by MIGRATION_MAP.md disposition rules |
| `docs/plans/CANONICAL_PLANNING_RECONCILIATION_AND_GUARDRAILS_PLAN.md` | archive | superseded by IMPACT_MAP.md + PLAN_STATUS_LIFECYCLE.md |

## Change log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-24 | Plan created as canonical P12 | Planning Circle |
