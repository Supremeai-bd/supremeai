# SupremeAI Codebase Consolidation & Structural Simplification Master Plan

> **Document Version:** 2.0.0 (Consolidated Canonical Architecture Refactor Plan)  
> **Target Alignment:** [`docs/architecture/SUPREMEAI_CORE_CONSTITUTION.md`](file:///f:/supremeai/docs/architecture/SUPREMEAI_CORE_CONSTITUTION.md)  
> **Single Source of Truth:** [`STATUS.md`](file:///f:/supremeai/STATUS.md) | [`CHECKPOINT.md`](file:///f:/supremeai/CHECKPOINT.md)  
> **Consolidated Authorities:** Unifies `BACKEND_SIMPLIFICATION_PLAN.md`, `FRONTEND_SIMPLIFICATION_PLAN.md`, and `ROOT_STRUCTURE_ORGANIZATION_PLAN.md`.

---

## 1. Goal & Core Principles

### Goal
Make SupremeAI easier for humans and AI agents to understand, maintain, and extend **without materially reducing its capability surface**.

### Core Principle
> **"Build less. Reuse more. Connect more. Simplify the structure, not the capability."**

The repository's stated philosophy is capability-before-construction: discover and compose what already exists before creating something new. This refactor applies the same principle to the codebase itself.

### Important Restriction: "No Dead Code, Only Unused Code"
This plan strictly enforces the repository core directive:
- AI agents must NOT delete code merely because it is temporarily uncalled, unimported, or not visible in the main UI.
- SupremeAI contains capabilities that may be intentionally dormant, queryable, dynamically loaded, externally exposed, planned, experimental, or waiting for integration.
- Focus exclusively on:
  - Consolidating duplicate implementations.
  - Eliminating competing abstractions.
  - Grouping fragmented directories into predictable domain modules.
  - Cleaning unnecessary root-level clutter.

---

## 2. Target System Topology

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
              Clean Interfaces
                     │
             Predictable Monorepo
```

---

## 3. Backend Simplification Blueprint

### 3.1 Target Directory Shape
```text
backend/
├── app/                         # application bootstrap
│   ├── main.py
│   ├── router_registry.py
│   └── dependencies.py
├── api/
│   ├── routes/                  # thin HTTP/WebSocket boundaries
│   └── schemas/
├── core/
│   ├── config/
│   ├── security/
│   ├── database/
│   ├── observability/
│   └── runtime/
├── capabilities/
│   ├── chat/
│   ├── research/
│   ├── browser/
│   ├── agents/
│   ├── memory/
│   ├── automation/
│   ├── artifacts/
│   └── mcp/
├── orchestration/
│   ├── planner.py
│   ├── capability_registry.py
│   ├── executor.py
│   ├── verifier.py
│   └── recovery.py
├── integrations/
│   ├── llm/
│   ├── providers/
│   ├── redis/
│   ├── storage/
│   └── external/
├── workers/
├── models/
└── tests/
```

### 3.2 Key Backend Execution Rules
1. **Preserve API contracts:** Auth, tenant isolation, security controls, background jobs, MCP, browser automation, memory, and failover must remain unbroken.
2. **Router consolidation:** Register routers through canonical registries (`backend/api/routers.py` and `app_builder.py`).
3. **Backward-compatible facades:** Retain compatibility facades temporarily when moving core modules to prevent breaking dynamic consumers.

---

## 4. Frontend Simplification Blueprint

### 4.1 Target Directory Shape
```text
frontend/src/
├── app/                    # bootstrap, router, providers, global error handling
├── features/
│   ├── auth/
│   ├── chat/
│   ├── research/
│   ├── browser/
│   ├── agents/
│   ├── memory/
│   ├── automation/
│   ├── artifacts/
│   ├── admin/
│   └── settings/
├── shared/
│   ├── ui/                 # reusable visual primitives
│   ├── forms/
│   ├── tables/
│   ├── modals/
│   ├── layout/
│   └── hooks/
├── core/
│   ├── api/
│   ├── auth/
│   ├── realtime/
│   ├── state/
│   ├── i18n/
│   └── config/
├── pages/                  # route-level composition shells
└── types/
```

### 4.2 Key Frontend Execution Rules
1. **Single-Build, Shared Shell:** User and Admin exist inside one frontend build (`App.tsx` + `WorkspaceLayout.tsx` + `AdminShell.tsx`).
2. **Navigation Source of Truth:** `navigationRegistry.ts` generates all visible navigation; no duplicate nav arrays.
3. **Component Consolidation:**
   - Merge similar dashboard cards into shared card primitives.
   - Standardize table and list patterns around `@tanstack/react-query` + shared views.

---

## 5. Repository Root & File Organization

### 5.1 Target Root
A file should stay at root only if standard tooling expects it, it is a primary project manifest, or it is a top-level project contract:

```text
supremeai/
├── README.md
├── LICENSE
├── AGENTS.md
├── pyproject.toml / poetry.lock
├── package.json / pnpm-workspace.yaml / turbo.json
├── docker-compose.yml / Dockerfile
├── .gitignore / .dockerignore / .env.example
├── .github/
├── .agents/
├── backend/
├── frontend/
├── packages/
├── database/
├── scripts/
├── infrastructure/
├── docs/
└── tests/
```

### 5.2 Move Candidates & Guidelines
1. **One-off scripts:** Move ad-hoc root scripts into `scripts/ops/`, `scripts/ci/`, or `scripts/maintenance/`.
2. **Scattered configuration:** Consolidate tooling configs into standard standard tool files.
3. **Generated artifacts:** Route all test outputs and temporary runs into `.system_generated/` or `tmp/` (gitignored).

---

## 6. Phased Execution Roadmap

1. **Phase 1 — Inventory & Capability Ledger:** Map every capability, consumer, and test before moving.
2. **Phase 2 — Canonical Boundaries:** Enforce single auth store, single router registry, and unified nav registry.
3. **Phase 3 — Frontend Feature Folders:** Group components, hooks, and services by feature domain.
4. **Phase 4 — Backend Capability Domain Grouping:** Group engines under capabilities and orchestration layers.
5. **Phase 5 — Repository Root Cleanliness:** Move non-essential root files into `scripts/` or `infrastructure/`.
6. **Phase 6 — Verification & Quality Gates:** Pass full test suite (`pytest`, `vitest`, `tsc`, and build smoke tests).
