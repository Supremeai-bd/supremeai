---
id: provider-abstraction
subject: "Provider Abstraction"
document_role: architecture
planning_authority: "Intelligence Circle"
canonical: true
status: active
evidence_state: partial
disposition: retain
last_verified: 2026-09-24
supersedes:
  - "docs/plans/architecture/vendor_independent_integration_architecture_plan.md"
  - "docs/plans/features/PLAN_001_ANTHROPIC_PROMPT_CACHING.md"
superseded_by: []
target_scope: supremeai_internal
plan_id: P02
domain: intelligence
depends_on: ["P01"]
enables: ["P04"]
implemented_by: "Milestone: Provider Gateway"
verified_by: "Provider contract tests + failover simulation"
related_to: ["P03"]
---

# Plan: Provider Abstraction

> **Status:** `Active` · **Owner:** Intelligence Circle · **ID:** `P02`

## Purpose
A single provider-neutral gateway so agents never hardcode OpenAI / Anthropic /
Google / local models. Enables transparent failover, prompt caching, cost
control, and the "Provider-neutral" principle from the vision layer.

## Depends On
- [P01 — Security Guardian](../security/security-guardian.md) — *why: every provider key is a secret; rotation + audit flow through P01.*

## Enables
- [P04 — Agent Orchestration](../agents/agent-orchestration.md) — *how: agents call `llm.complete()`, never a vendor SDK directly.*

## Related
- [P03 — MCP Architecture](../mcp/mcp-architecture.md) — *coupling: MCP tools invoke the gateway for any LLM step.*

## Source of Truth
This document defines provider abstraction. Prompt caching, context compaction,
and rate-limit discovery are **milestones under this plan**, not separate plans.

## Architecture

### Current state
- `infrastructure/mcp-control-plane/PROVIDER_NEUTRAL_CONNECTIONS.md` exists.
- Prompt-caching plan (`PLAN_001_ANTHROPIC_PROMPT_CACHING.md`) and context-compaction plan (`PLAN_002`) are written but live as standalone feature docs.
- No single contract test asserting "swap provider, behavior unchanged".

### Target state
- One gateway interface; providers register via config (zero hardcode).
- Failover + retry + cost caps enforced at the gateway.
- Prompt caching, compaction, and limit discovery are pluggable strategies.

### Non-goals
- This plan does **not** define agent role logic (that's P04).
- This plan does **not** define the MCP tool registry (that's P03).

## Execution

See GitHub milestone: **Provider Gateway**

| Milestone | Status | Owner | Tracking |
|-----------|--------|-------|----------|
| Gateway interface | 🟦 Active | Intelligence | *(issue)* |
| Prompt caching (Anthropic) | 🟪 Implementing | Intelligence | `PLAN_001_ANTHROPIC_PROMPT_CACHING.md` |
| Context compaction | ⬜ Proposed | Intelligence | `PLAN_002_CLAUDE_STYLE_CONTEXT_COMPACTION.md` |
| Failover simulation test | ⬜ Proposed | Quality | *(issue)* |

## Verification

| Check | Type | Passing? | Evidence |
|-------|------|----------|----------|
| Provider contract tests | integration | ❌ | *(not yet written)* |
| Failover simulation | e2e | ❌ | *(not yet written)* |
| Zero vendor SDK imports in agents | lint | ⚠️ | partial — needs CI rule |

## Legacy documents superseded

| Legacy file | Disposition | Note |
|-------------|-------------|------|
| `docs/plans/architecture/vendor_independent_integration_architecture_plan.md` | archive | strategy folded here |
| `docs/plans/features/PLAN_001_ANTHROPIC_PROMPT_CACHING.md` | archive | becomes a milestone |
| `docs/plans/features/PLAN_002_CLAUDE_STYLE_CONTEXT_COMPACTION.md` | archive | becomes a milestone |
| `docs/plans/features/Plan_10_API_Limit_Discovery.md` | archive | becomes a milestone |

## Change log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-24 | Plan created as canonical P02 | Planning Circle |
