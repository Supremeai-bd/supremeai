---
id: agent-orchestration
subject: "Agent Orchestration"
document_role: architecture
planning_authority: "Intelligence Circle"
canonical: true
status: active
evidence_state: partial
disposition: retain
last_verified: 2026-09-24
supersedes:
  - "docs/plans/MULTI_AGENT_MESH_MASTER_PLAN.md"
  - "docs/plans/architecture/EXTERNAL_AGENT_ORCHESTRATION_LAYER_PLAN.md"
  - "docs/plans/architecture/living_autonomous_intelligence_synthesis.md"
  - "docs/plans/features/Plan_01_Dynamic_AI_Agent_System.md"
superseded_by: []
target_scope: combined_ecosystem
plan_id: P04
domain: agents
depends_on: ["P01", "P02", "P03"]
enables: ["P05", "P07"]
implemented_by: "Milestone: Agent Role System"
verified_by: "Agent integration tests + HITL review"
related_to: ["P06", "P10"]
---

# Plan: Agent Orchestration

> **Status:** `Active` · **Owner:** Intelligence Circle · **ID:** `P04`

## Purpose
Define how AI agents work together: **planner / executor / reviewer** roles,
the multi-agent mesh, and the autonomous coding workflow. The single most
referenced concept in the legacy docs — previously fragmented across at least
four "master" plans.

## Depends On
- [P01 — Security Guardian](../security/security-guardian.md) — *why: HITL approval + capability scoping.*
- [P02 — Provider Abstraction](../intelligence/provider-abstraction.md) — *why: agents call the gateway, never a vendor SDK.*
- [P03 — MCP Architecture](../mcp/mcp-architecture.md) — *why: agents discover tools via the registry.*

## Enables
- [P05 — Memory & Knowledge Engine](../intelligence/memory-knowledge-engine.md) — *how: agents persist episodes via memory tools.*
- [P07 — Frontend Evolution](../experience/frontend-evolution.md) — *how: the dashboard surfaces agent state + approvals.*

## Related
- [P06 — Browser Automation](../automation/browser-automation.md) — *coupling: agents delegate browser tasks to P06.*
- [P10 — Deployment Safety](../governance/deployment-safety.md) — *coupling: agent-authored PRs pass through the pre-push gate.*

## Source of Truth
This document defines agent orchestration. Planner/executor/reviewer roles,
the mesh topology, and the coding workflow are sections here — not separate plans.

## Architecture

### Current state
- Role assignments documented in `docs/plans/phases/agent_roles_and_team_assignments.md`.
- `MULTI_AGENT_MESH_MASTER_PLAN.md` and `EXTERNAL_AGENT_ORCHESTRATION_LAYER_PLAN.md` describe overlapping topologies.
- HITL approval scaffolding exists (crown-jewel MODULE_17) but is not wired into the workflow end-to-end.

### Target state
- One role model: planner (decomposes), executor (codes), reviewer (audits).
- Mesh topology with explicit edges, not prose.
- HITL gate mandatory for any agent action with `target_scope: user_project`.

### Non-goals
- This plan does **not** define which LLM provider (that's P02).
- This plan does **not** define memory internals (that's P05).

## Execution

See GitHub milestone: **Agent Role System**

| Milestone | Status | Owner | Tracking |
|-----------|--------|-------|----------|
| Role model + interfaces | 🟦 Active | Intelligence | *(issue)* |
| Mesh topology | 🟪 Implementing | Intelligence | `MULTI_AGENT_MESH_MASTER_PLAN.md` → fold here |
| HITL gate e2e | ⬜ Proposed | Intelligence + Governance | crown-jewel MODULE_17 |

## Verification

| Check | Type | Passing? | Evidence |
|-------|------|----------|----------|
| Planner/executor/reviewer integration | integration | ⚠️ | partial |
| HITL approval audit trail | audit | ❌ | not yet end-to-end |
| Agent integration test suite | e2e | ⚠️ | partial |

## Legacy documents superseded

| Legacy file | Disposition | Note |
|-------------|-------------|------|
| `docs/plans/MULTI_AGENT_MESH_MASTER_PLAN.md` | archive | topology folded here |
| `docs/plans/architecture/EXTERNAL_AGENT_ORCHESTRATION_LAYER_PLAN.md` | archive | becomes "External agents" section |
| `docs/plans/architecture/living_autonomous_intelligence_synthesis.md` | archive | vision-level; principles move to `vision/principles.md` |
| `docs/plans/features/Plan_01_Dynamic_AI_Agent_System.md` | archive | becomes "Dynamic agent system" section |

## Change log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-24 | Plan created as canonical P04 | Planning Circle |
