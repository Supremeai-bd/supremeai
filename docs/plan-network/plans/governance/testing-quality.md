---
id: testing-quality
subject: "Testing & Quality"
document_role: architecture
planning_authority: "Quality Circle"
canonical: true
status: verifying
evidence_state: verified
disposition: retain
last_verified: 2026-09-24
supersedes:
  - "docs/plans/SOFTWARE_ENGINEERING_EXCELLENCE_PLAN.md"
  - "docs/plans/PR_GUARDIAN_ANALYSIS_PLAN.md"
  - "docs/SKIPPED_TESTS.md"
superseded_by: []
target_scope: supremeai_internal
plan_id: P11
domain: governance
depends_on: ["P08"]
enables: []
implemented_by: "Milestone: Quality Gate"
verified_by: "CI green + coverage ≥ target + audit sign-off"
related_to: ["P10", "P12"]
---

# Plan: Testing & Quality

> **Status:** `Verifying` · **Owner:** Quality Circle · **ID:** `P11`

## Purpose
The verification backbone: unit / integration / e2e, PR Guardian, coverage
targets, and the skipped-test registry. Every plan in the network eventually
flows evidence through P11 to reach Stable.

## Depends On
- [P08 — Infrastructure Optimization](../infrastructure/infrastructure-optimization.md) — *why: CI runs on this pipeline.*

## Enables
*(terminal — P11 is the verification sink the whole network depends on)*

## Related
- [P10 — Deployment Safety](../governance/deployment-safety.md) — *coupling: the quality signal feeds the deployment gate.*
- [P12 — Codebase Cleanup](../governance/codebase-cleanup.md) — *coupling: lint_plans.py lives here.*

## Source of Truth
This document defines testing & quality. PR Guardian, coverage policy, and the
skipped-test registry are sections here, not separate plans.

## Architecture

### Current state
- `playwright.config.ts` + `playwright-ct.config.ts` configured.
- `SKIPPED_TESTS.md` (25 KB) tracks every skipped test with a reason.
- PR Guardian analysis plan exists; Software Engineering Excellence plan exists.
- Coverage targets defined but not enforced as a hard gate.

### Target state
- PR Guardian blocks any PR that drops coverage below target.
- Skipped-test registry auto-checked: no skip without a linked issue.
- Every plan's Verification table feeds a rollup dashboard here.

### Non-goals
- This plan does **not** define the CI infrastructure (that's P08).
- This plan does **not** define deployment gating (that's P10).

## Execution

See GitHub milestone: **Quality Gate**

| Milestone | Status | Owner | Tracking |
|-----------|--------|-------|----------|
| PR Guardian | 🟪 Implementing | Quality | `PR_GUARDIAN_ANALYSIS_PLAN.md` → fold |
| Coverage gate | 🟦 Active | Quality | *(issue)* |
| Skipped-test registry | ✅ Done | Quality | `docs/SKIPPED_TESTS.md` (retain) |
| Engineering excellence checklist | 🟦 Active | Quality | `SOFTWARE_ENGINEERING_EXCELLENCE_PLAN.md` → fold |

## Verification

| Check | Type | Passing? | Evidence |
|-------|------|----------|----------|
| CI green on main | integration | ✅ | CI |
| Coverage ≥ target | metric | ⚠️ | target not yet enforced |
| Skipped-test registry audit | audit | ✅ | `SKIPPED_TESTS.md` |
| PR Guardian in CI | integration | ⚠️ | partial |

## Legacy documents superseded

| Legacy file | Disposition | Note |
|-------------|-------------|------|
| `docs/plans/SOFTWARE_ENGINEERING_EXCELLENCE_PLAN.md` | archive | becomes "Excellence checklist" section |
| `docs/plans/PR_GUARDIAN_ANALYSIS_PLAN.md` | archive | becomes "PR Guardian" section |
| `docs/SKIPPED_TESTS.md` | retain | live registry = evidence |

## Change log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-24 | Plan created as canonical P11 | Planning Circle |
