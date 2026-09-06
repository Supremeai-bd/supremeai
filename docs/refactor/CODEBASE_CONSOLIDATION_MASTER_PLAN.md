# SupremeAI Codebase Consolidation Master Plan

## Goal

Make SupremeAI easier for humans and AI agents to understand, maintain and extend **without materially reducing its capability surface**.

## Core principle

> **Build less. Reuse more. Connect more. Simplify the structure, not the capability.**

The repository's stated philosophy is capability-before-construction: discover and compose what already exists before creating something new. This refactor must apply the same principle to the codebase itself.

## Important restriction: no dead-code cleanup

This plan deliberately excludes dead-code removal.

AI agents must NOT delete code merely because it is:

- not imported directly
- not visible in the main UI
- not called in a static search
- not covered by an obvious test
- apparently unused

SupremeAI contains capabilities that may be intentionally dormant, queryable, dynamically loaded, externally exposed, planned, experimental, or waiting for integration. Such assets require human intervention.

## What we ARE reducing

Reduce:

- duplicate implementations
- duplicate UI patterns
- duplicate API wrappers
- duplicate state logic
- excessive file fragmentation
- unclear folder boundaries
- giant mixed-responsibility files
- repeated configuration/utility code
- unnecessary root-level clutter

Do NOT reduce:

- capabilities
- providers
- agents
- tools
- MCP functionality
- browser/research functionality
- memory/learning assets
- governance/security assets
- recovery/failover mechanisms
- future capability assets

## Refactoring order

### Phase 0 — Freeze feature expansion

For the consolidation period, avoid adding new features unless required to unblock the refactor.

### Phase 1 — Inventory

Create a capability map:

```text
Capability → Current files → Entry points → Consumers → Runtime registration → Tests → Proposed destination
```

Create this before moving anything.

### Phase 2 — Establish canonical boundaries

Define:

- one frontend API client boundary
- one frontend auth/state boundary
- one realtime boundary
- one backend router registry
- one orchestration boundary
- one capability registry
- one shared security boundary
- one observability boundary

### Phase 3 — Consolidate frontend

Follow `FRONTEND_SIMPLIFICATION_PLAN.md`.

Priority: duplicated components → services → state → pages → feature folders.

### Phase 4 — Consolidate backend

Follow `BACKEND_SIMPLIFICATION_PLAN.md`.

Priority: duplicate routers → duplicate services → shared utilities → capability boundaries → orchestration.

### Phase 5 — Repository organization

Follow `ROOT_STRUCTURE_ORGANIZATION_PLAN.md`.

Move scripts, docs, development tooling and operational assets into predictable locations. Root should contain only files that genuinely need to be root-level.

### Phase 6 — Verification

After each batch:

1. lint
2. typecheck
3. unit tests
4. integration/API tests
5. frontend route smoke test
6. backend startup test
7. worker startup test
8. security checks
9. capability inventory comparison

## File reduction strategy

Use this decision tree:

```text
Is this capability unique?
 ├─ Yes → preserve; organize it.
 └─ No
     ↓
Is it duplicate implementation?
 ├─ Yes → choose canonical implementation and consolidate.
 └─ No
     ↓
Is it a tiny piece of a larger domain?
 ├─ Yes → merge into the domain module when safe.
 └─ No → keep separate.
```

## AI-agent safety protocol

Before any move/merge, the agent must report:

- files affected
- capability affected
- imports found
- dynamic/runtime references considered
- route/worker/MCP/config references considered
- tests affected
- proposed destination
- rollback plan

If uncertainty exists, stop that item and mark it `HUMAN REVIEW`.

## Definition of success

The refactor is successful when:

- the repository is easier to navigate
- related functionality is physically grouped
- duplicate logic is reduced
- frontend and backend boundaries are obvious
- root directory is clean
- AI agents can find capabilities quickly
- existing user/admin functionality still works
- existing capability assets are preserved
- CI/security/testing remain healthy

## Final target

```text
                 SUPREMEAI
                     │
        ┌────────────┴────────────┐
        │                         │
   Stable Core              Capability Library
        │                         │
  Orchestration          Browser / Research / MCP
  Policy                 Agents / Memory / Tools
  Verification           Providers / Automation
  Recovery               Governance / Evolution
        │                         │
        └────────────┬────────────┘
                     │
              Clean interfaces
                     │
             Predictable repository
```

The core becomes smaller and more understandable while the capability library remains broad.
