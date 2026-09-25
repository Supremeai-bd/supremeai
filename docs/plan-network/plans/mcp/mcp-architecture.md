---
id: mcp-architecture
subject: "MCP Architecture"
document_role: architecture
planning_authority: "Platform Circle"
canonical: true
status: stable
evidence_state: verified
disposition: retain
last_verified: 2026-09-24
supersedes:
  - "docs/plans/architecture/unified_fastmcp_control_tower_multitenant_master_plan_bn.md"
  - "docs/plans/architecture/federated_capability_circles_topology.md"
  - "docs/plans/architecture/registry_control_in_pipeline_and_dashboard.md"
superseded_by: []
target_scope: combined_ecosystem
plan_id: P03
domain: mcp
depends_on: ["P01"]
enables: ["P04", "P05", "P06", "P07"]
implemented_by: "Milestone: MCP Control Tower"
verified_by: "MCP integration tests + federation e2e"
related_to: ["P02"]
---

# Plan: MCP Architecture

> **Status:** `Stable` · **Owner:** Platform Circle · **ID:** `P03`
> The most mature domain in the repo (41 legacy docs consolidated here).

## Purpose
The Model Context Protocol control tower: a single tool registry, federation
across nodes, and multi-tenant routing. P03 is the highest-leverage enabler in
the network — four other plans depend on it.

## Depends On
- [P01 — Security Guardian](../security/security-guardian.md) — *why: tool execution is arbitrary code; sandboxing + audit flow through P01.*

## Enables
- [P04 — Agent Orchestration](../agents/agent-orchestration.md) — *how: agents discover tools via the registry.*
- [P05 — Memory & Knowledge Engine](../intelligence/memory-knowledge-engine.md) — *how: `qdrant_*` and `memory_*` are MCP tools.*
- [P06 — Browser Automation](../automation/browser-automation.md) — *how: browser tools register here.*
- [P07 — Frontend Evolution](../experience/frontend-evolution.md) — *how: the dashboard renders the live tool registry.*

## Related
- [P02 — Provider Abstraction](../intelligence/provider-abstraction.md) — *coupling: MCP tools that need an LLM call the gateway.*

## Source of Truth
This document defines the MCP control tower. Federation topology, registry
control, and multi-tenant routing are sections here, not separate plans.

## Architecture

### Current state
- `infrastructure/mcp-control-plane/` is implemented with `PROVIDER_NEUTRAL_CONNECTIONS.md` and `FEDERATION.md`.
- `mcp.json` at repo root configures the local tower.
- Federation across free-tier nodes is working but underdocumented as a single source.

### Target state
- One canonical topology diagram (lives here, not in 5 competing docs).
- Registry control enforced in both pipeline and dashboard (the
  `registry_control_in_pipeline_and_dashboard.md` concern becomes a section).
- Federation e2e test runs in CI.

### Non-goals
- This plan does **not** define agent role assignment (that's P04).
- This plan does **not** define the browser tool internals (that's P06).

## Execution

See GitHub milestone: **MCP Control Tower** (largely complete)

| Milestone | Status | Owner | Tracking |
|-----------|--------|-------|----------|
| FastMCP control tower | ✅ Done | Platform | `infrastructure/mcp-control-plane/` |
| Multi-tenant routing | ✅ Done | Platform | *(tests)* |
| Federation e2e in CI | 🟪 Implementing | Quality | *(issue)* |

## Verification

| Check | Type | Passing? | Evidence |
|-------|------|----------|----------|
| MCP integration tests | integration | ✅ | `tests/` |
| Federation e2e | e2e | ⚠️ | exists but not in CI gate |
| Registry ↔ dashboard parity | integration | ✅ | dashboard renders live registry |

> P03 is the only **Stable** plan in the network. It is the reference for what
> "Stable" means: every verification row ✅ with linked evidence.

## Legacy documents superseded

| Legacy file | Disposition | Note |
|-------------|-------------|------|
| `docs/plans/architecture/unified_fastmcp_control_tower_multitenant_master_plan_bn.md` | archive | canonical strategy folded here |
| `docs/plans/architecture/federated_capability_circles_topology.md` | archive | becomes "Federation" section |
| `docs/plans/architecture/registry_control_in_pipeline_and_dashboard.md` | archive | becomes "Registry control" section |
| *(38 more control-tower-mcp family docs)* | archive | each gets `superseded_by: P03` |

## Change log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-24 | Plan created as canonical P03; promoted to Stable | Platform Circle |
