---
id: memory-knowledge-engine
subject: "Memory & Knowledge Engine"
document_role: architecture
planning_authority: "Knowledge Circle"
canonical: true
status: active
evidence_state: partial
disposition: retain
last_verified: 2026-09-24
supersedes:
  - "docs/plans/features/PLAN_003_AIDER_STYLE_REPO_MAP.md"
  - "docs/plans/features/PLAN_004_LETTA_STYLE_MEMORY_DISTILLATION.md"
  - "docs/plans/features/PLAN_006_MEM0_STYLE_MEMORY_CONSOLIDATION.md"
  - "docs/plans/features/Plan_03_Continuous_Learning.md"
superseded_by: []
target_scope: supremeai_internal
plan_id: P05
domain: intelligence
depends_on: ["P03", "P04"]
enables: []
implemented_by: "Milestone: Memory Consolidation"
verified_by: "Memory recall tests + consolidation audit"
related_to: ["P04"]
---

# Plan: Memory & Knowledge Engine

> **Status:** `Active` · **Owner:** Knowledge Circle · **ID:** `P05`

## Purpose
Qdrant vector store + episodic graph + semantic memory. The long-term learning
loop that lets agents remember across sessions and avoid repeating mistakes.
Consolidates four overlapping "memory style" feature plans into one engine.

## Depends On
- [P03 — MCP Architecture](../mcp/mcp-architecture.md) — *why: `qdrant_*` and `memory_*` are MCP tools.*
- [P04 — Agent Orchestration](../agents/agent-orchestration.md) — *why: agents are the producers and consumers of memory.*

## Enables
*(currently terminal — future "Autonomous Evolution" plan will depend on P05)*

## Related
- [P04 — Agent Orchestration](../agents/agent-orchestration.md) — *coupling: the learning loop feeds back into agent decisions.*

## Source of Truth
This document defines memory. Aider-style repo maps, Letta-style distillation,
and Mem0-style consolidation are **strategies under this plan**, not separate plans.

## Architecture

### Current state
- Qdrant deployed; `qdrant_upsert` / `qdrant_search` tools working.
- Semantic memory engine (`memory_store_document`, `memory_remember_fact`) working.
- Episodic loop (`memory_record_task`, `memory_get_recent_episodes`) ~98% per legacy `Plan_03`.
- Three "style" plans (Aider / Letta / Mem0) describe the same engine from different angles.

### Target state
- One memory engine with pluggable consolidation strategies.
- Free-tier 512 MB memory-pressure remediation complete (legacy plan folded in).
- Recall test suite asserting "agent remembers X across sessions".

### Non-goals
- This plan does **not** define agent roles (that's P04).
- This plan does **not** define vector DB ops (that's P08).

## Execution

See GitHub milestone: **Memory Consolidation**

| Milestone | Status | Owner | Tracking |
|-----------|--------|-------|----------|
| Qdrant + semantic memory | ✅ Done | Knowledge | working |
| Episodic loop | 🟪 Implementing | Knowledge | `Plan_03_Continuous_Learning.md` → fold |
| 512 MB pressure remediation | 🟦 Active | Knowledge | `free_tier_512mb_memory_pressure_remediation_plan.md` → fold |
| Consolidation strategies | ⬜ Proposed | Knowledge | Aider/Letta/Mem0 → strategies |

## Verification

| Check | Type | Passing? | Evidence |
|-------|------|----------|----------|
| Recall test (cross-session) | integration | ⚠️ | partial |
| Consolidation audit | audit | ❌ | not yet defined |
| 512 MB pressure test | perf | ⚠️ | legacy plan tracks this |

## Legacy documents superseded

| Legacy file | Disposition | Note |
|-------------|-------------|------|
| `docs/plans/features/PLAN_003_AIDER_STYLE_REPO_MAP.md` | archive | becomes "Repo-map strategy" |
| `docs/plans/features/PLAN_004_LETTA_STYLE_MEMORY_DISTILLATION.md` | archive | becomes "Distillation strategy" |
| `docs/plans/features/PLAN_006_MEM0_STYLE_MEMORY_CONSOLIDATION.md` | archive | becomes "Consolidation strategy" |
| `docs/plans/features/Plan_03_Continuous_Learning.md` | archive | becomes "Episodic loop" section |
| `docs/plans/features/free_tier_512mb_memory_pressure_remediation_plan.md` | archive | becomes "Pressure remediation" milestone |

## Change log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-24 | Plan created as canonical P05 | Planning Circle |
