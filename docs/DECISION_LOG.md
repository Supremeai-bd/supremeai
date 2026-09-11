# Decision Log (ADR) — Architecture Decision Records

> **[🤖 AI AGENT INSTRUCTION]** 
> This is the canonical SupremeAI Architecture Decision Records (ADR) file.
> 1. Add new architectural decisions to the TOP of the list (reverse chronological).
> 2. Maintain the format: Date, Status, Context, Decision, Consequences.
> 3. DO NOT modify past decisions unless the context explicitly supersedes it.
>
> **Single Source of Truth:** [`STATUS.md`](file:///f:/supremeai/STATUS.md) | [`CHECKPOINT.md`](file:///f:/supremeai/CHECKPOINT.md)  
> **Consolidated Authorities:** Unifies `architecture_decision_records.md`, `PLUGIN_ARCHITECTURE_DECISION.md`, `PLUGIN_SDK.md`, `CONVENTIONS.md`, `ADR-001-firestore-for-tenancy.md`, `DFD-001-new-user-signup.md`, and `SEQ-001-canary-deployment.md`.

---

## 2026-09-11 — Single-Frontend & Unified App Shell Migration
- **Date:** 2026-09-11
- **Status:** Adopted & Implemented
- **Context:** Separate builds/portals (`VITE_PORTAL_TYPE=admin` vs `user`) caused architectural drift, duplicated auth stores, and deployment fragmentation.
- **Decision:** Eliminate portal-type build branching. Compile exactly ONE frontend application where User and Admin are role-aware views inside the same shared shell (`WorkspaceLayout` / `UnifiedAppShell`). Navigation is dynamically generated from `navigationRegistry.ts`, and permissions are strictly enforced on backend routes.
- **Consequences:** Dramatically simplified deployment on Firebase Hosting; eliminated dead links and ghost UI panels; zero client-side privilege escalation risk.

## 2026-08-30 — Plugin Ecosystem & Declarative MCP Architecture
- **Date:** 2026-08-30
- **Status:** Adopted
- **Context:** Expanding agent capabilities to thousands of tools without allowing arbitrary unsandboxed third-party script execution on the backend.
- **Decision:** Adopt declarative Model Context Protocol (MCP) plugins. Community and external plugins submit declarative JSON manifests and connect via remote HTTPS MCP servers. No raw Python/JS uploads permitted on backend. Enforce strict SSRF protection on all user-submitted MCP URLs.
- **Consequences:** Safe, scalable ecosystem leveraging native MCP protocol; preserves GitHub OAuth and native integration stability.

## 2026-08-20 — Asynchronous Database Layer with SQLAlchemy 2.0 & asyncpg
- **Date:** 2026-08-20
- **Status:** Adopted
- **Context:** Synchronous database drivers (`psycopg2`) blocked FastAPI's async event loop during high concurrent traffic.
- **Decision:** Migrate all PostgreSQL operations to `asyncpg` via SQLAlchemy 2.0 async engine and Supabase PostgREST async client.
- **Consequences:** Maximum throughput on Render's free tier with zero event-loop stalls.

## 2026-08-18 — Global Logging Standardization via Loguru
- **Date:** 2026-08-18
- **Status:** Adopted
- **Context:** Python's built-in `logging` module required excessive boilerplate, lacked structured JSON formatting, and was non-trivial in async contexts.
- **Decision:** Adopt `loguru` globally as the backend logging standard, configured with thread-safe structured outputs.
- **Consequences:** Consistent log formatting, seamless error-bus tracking, and effortless log aggregation.

## 2026-08-16 — Brand Exclusivity & Thin Client Architecture
- **Date:** 2026-08-16
- **Status:** Adopted
- **Context:** The SupremeAI VS Code Extension and clients previously contained logic to fall back to OpenRouter API configurations directly, leaking vendor branding.
- **Decision:** All clients (VS Code extension, web, desktop) MUST act exclusively as 100% thin clients connecting to SupremeAI backend. Users only see the "SupremeAI Brand". The backend secretly routes all models.
- **Consequences:** Shielded users from backend complexities and enforced complete brand dominance.

## 2026-08-16 — The Eternal Brain Architecture (Model-Agnostic)
- **Date:** 2026-08-16
- **Status:** Adopted
- **Context:** Clarifying SupremeAI's core purpose: not an LLM wrapper, but an autonomous self-evolving intelligence.
- **Decision:** SupremeAI is strictly "Model-Agnostic". Third-party LLMs are temporary compute muscle. All task results, code patterns, and experiences are saved to vector memory (`ai_memory` / pgvector) to build SupremeAI's independent brain.
- **Consequences:** Backend decoupled from vendor APIs; dynamic model fallback ensures zero downtime.

## 2026-07-08 — Multi-Tenant Architecture & Production Migration (Render + Supabase)
- **Date:** 2026-07-08 (Updated 2026-08-30)
- **Status:** Adopted (Superseded Cloud Run/GCP with Render + Supabase)
- **Context:** Multi-tenant provisioning and data isolation required a scalable, zero-cost architecture.
- **Decision:** Canonical deployment is Render (Docker runtime) + PostgreSQL/Supabase (pgvector) + Redis (Upstash) + Firebase Hosting for SPA.
- **Consequences:** Zero-infrastructure-cost operation compliant with free-tier quotas; durable Postgres RLS replaces legacy Cloud Run / Firestore lock-in.

---

## Coding Conventions & Repository Standards

1. **Naming Conventions:**
   - Variables/Functions: `camelCase` (TypeScript) / `snake_case` (Python)
   - Classes/Interfaces: `PascalCase`
   - Constants: `UPPER_SNAKE_CASE`
   - Files: `kebab-case` (Frontend) / `snake_case.py` (Backend)
2. **Directory Structure:** Strict monorepo layout (`backend/`, `frontend/`, `packages/`, `tools/`, `scripts/`, `docs/`).
3. **General Rules:**
   - TypeScript strict mode (`strict: true`).
   - Zero hardcoded secrets (centralized in Infisical / `.env`).
   - "No dead code, only unused code": Do not delete dormant code without rigorous verification and fallback wiring.
