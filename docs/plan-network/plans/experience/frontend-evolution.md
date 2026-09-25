---
id: frontend-evolution
subject: "Frontend Evolution"
document_role: architecture
planning_authority: "Experience Circle"
canonical: true
status: active
evidence_state: partial
disposition: retain
last_verified: 2026-09-24
supersedes:
  - "docs/plans/design/complete_frontend_master_plan_bn.md"
  - "docs/plans/design/supremeai_2_product_ui_ux_completeness_master_plan.md"
  - "docs/plans/design/admin_dashboard_plan.md"
  - "docs/plans/design/intelligent_chat_plan.md"
  - "docs/plans/design/dashboard_tab_design_plan.md"
  - "docs/plans/design/single_frontend_role_based_auth_migration_roadmap.md"
  - "docs/plans/design/customer_onboarding_flow.md"
superseded_by: []
target_scope: user_project
plan_id: P07
domain: experience
depends_on: ["P03", "P04"]
enables: []
implemented_by: "Milestone: Frontend Tier-S Wiring"
verified_by: "E2E / Playwright UI checks + a11y audit"
related_to: ["P10"]
---

# Plan: Frontend Evolution

> **Status:** `Active` · **Owner:** Experience Circle · **ID:** `P07`

## Purpose
A single role-based frontend: dashboard, intelligent chat, admin console, and
onboarding. Consumes the agent (P04) and MCP (P03) APIs. The only plan with
`target_scope: user_project` — this is what end users actually touch.

## Depends On
- [P03 — MCP Architecture](../mcp/mcp-architecture.md) — *why: the dashboard renders the live tool registry.*
- [P04 — Agent Orchestration](../agents/agent-orchestration.md) — *why: chat surfaces agent state + HITL approvals.*

## Enables
*(terminal — the frontend is the user-facing surface)*

## Related
- [P10 — Deployment Safety](../governance/deployment-safety.md) — *coupling: frontend deploys through the canary gate.*

## Source of Truth
This document defines the frontend. Dashboard tabs, chat UX, admin console,
role-based auth, and onboarding are sections here — not 7 separate plans.

## Architecture

### Current state
- The `docs/plans/design/` folder (15 files) is the densest single-topic cluster.
- Two competing "master plans" (`complete_frontend_master_plan_bn.md` and
  `supremeai_2_product_ui_ux_completeness_master_plan.md`) cover the same ground.
- Role-based auth migration roadmap exists but is not yet executed.
- Onboarding flow designed but unverified.

### Target state
- One frontend with role-gated routes (admin / user / viewer).
- Dashboard tabs map 1:1 to domain registries.
- Intelligent chat wired to P04 with HITL approvals inline.
- a11y audit passing (WCAG AA).

### Non-goals
- This plan does **not** define agent behavior (that's P04).
- This plan does **not** define the tool registry (that's P03).

## Execution

See GitHub milestone: **Frontend Tier-S Wiring** (crown-jewel MODULE_10)

| Milestone | Status | Owner | Tracking |
|-----------|--------|-------|----------|
| Role-based auth migration | 🟦 Active | Experience | `single_frontend_role_based_auth_migration_roadmap.md` → fold |
| Dashboard tabs | 🟪 Implementing | Experience | `dashboard_tab_design_plan.md` → fold |
| Intelligent chat | 🟪 Implementing | Experience | `intelligent_chat_plan.md` → fold |
| Admin console | 🟦 Active | Experience | `admin_dashboard_plan.md` → fold |
| Onboarding | ⬜ Proposed | Experience | `customer_onboarding_flow.md` → fold |
| a11y audit | ⬜ Proposed | Quality | *(issue)* |

## Verification

| Check | Type | Passing? | Evidence |
|-------|------|----------|----------|
| Playwright UI suite | e2e | ⚠️ | partial |
| a11y audit (WCAG AA) | audit | ❌ | not yet run |
| Role-gate integration | integration | ⚠️ | partial |

## Legacy documents superseded

| Legacy file | Disposition | Note |
|-------------|-------------|------|
| `docs/plans/design/complete_frontend_master_plan_bn.md` | archive | canonical strategy folded here |
| `docs/plans/design/supremeai_2_product_ui_ux_completeness_master_plan.md` | archive | duplicate master → folded |
| `docs/plans/design/admin_dashboard_plan.md` | archive | becomes "Admin console" section |
| `docs/plans/design/intelligent_chat_plan.md` | archive | becomes "Chat" section |
| `docs/plans/design/dashboard_tab_design_plan.md` | archive | becomes "Dashboard tabs" section |
| `docs/plans/design/single_frontend_role_based_auth_migration_roadmap.md` | archive | becomes "Auth" milestone |
| `docs/plans/design/customer_onboarding_flow.md` | archive | becomes "Onboarding" milestone |
| `docs/plans/design/dashboard_design_mockups.md` | retain | mockups = evidence, stays as asset |

## Change log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-24 | Plan created as canonical P07 | Planning Circle |
