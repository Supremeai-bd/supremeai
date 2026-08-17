# 🏛️ SupremeAI 2.0 — ULTIMATE MASTER BLUEPRINT & PRODUCTION SPECIFICATION

**Document ID:** `docs/SUPREMEAI_MASTER_BLUEPRINT.md`  
**Version:** 2.0-ULTIMATE-FINAL  
**Last Updated:** 2026-07-24  
**Status:** ACTIVE SINGLE SOURCE OF TRUTH (All Admin Plans Consolidated)  
**Philosophy:** *User sees magic, Admin is God, System is invisible, Zero cost, Max performance*  

---

## 📑 TABLE OF CONTENTS
1. [Core Philosophy & Project DNA](#1-core-philosophy--project-dna)
2. [Monorepo System Architecture](#2-monorepo-system-architecture)
3. [Admin's Master Plan & Component Inventory](#3-admins-master-plan--component-inventory)
4. [Headless Zero-Cost Terminal AI Agent](#4-headless-zero-cost-terminal-ai-agent)
5. [Code-to-Database Persistence & Indexing](#5-code-to-database-persistence--indexing)
6. [Multi-Database Federation Layer](#6-multi-database-federation-layer)
7. [Autonomous Web & Mobile UX Architecture](#7-autonomous-web--mobile-ux-architecture)
8. [Security Shield & JIT OTP Defense](#8-security-shield--jit-otp-defense)
9. [Multi-Platform Deployment & Secret Sync](#9-multi-platform-deployment--secret-sync)
10. [Developer Operational Guide](#10-developer-operational-guide)

---

## 1. CORE PHILOSOPHY & PROJECT DNA

SupremeAI 2.0 operates strictly on 7 foundational non-negotiables:

1. **Zero Cost:** Utilize free-tier services and open-source libraries (DeepSeek-V3, Kimi K2.5, Together AI fallback, Supabase, Render, Vercel, Firebase). No paid third-party gateways.
2. **High Scalability & Performance:** Asynchronous non-blocking architecture designed to handle sudden user traffic spikes cleanly with minimal memory overhead.
3. **Zero Breakage & Targeted Delta Patching:** Running production logic, database schemas, and configuration state are preserved flawlessly without duplication.
4. **Human-in-the-Loop with Minimal Effort:** Absolute minimum manual friction. High-privilege destructive actions require JIT OTP verification.
5. **Malware Immunity via JIT Defense:** Assume the local client session might be compromised. Require on-spot JIT OTP verification for sensitive routes (`/billing`, `/admin`, `/payments`).
6. **Self-Healing Engine:** Autonomous central error bus automatically attempts error remediation and self-recovery via `autonoguard_engine.py` and `maintenance_pipeline.py`.
7. **Failure-Aware Context:** System retains past failure history and routes dynamically to prevent repeating failed attempts.

---

## 2. MONOREPO SYSTEM ARCHITECTURE

```
supremeai/
├── admin/                    # Admin god mode portal (god.py)
├── apps/
│   ├── mobile/              # Flutter mobile app (v1.0.1, GoRouter, Material 3)
│   ├── studio-client/        # React 19 / Vite 7 / Tailwind CSS 4 Web & Desktop Client
│   └── web-chat/            # Lightweight Web Chat interface
├── backend/
│   ├── adaptive_engine/     # Intent parser, experience DB, platform learner
│   ├── api/                 # 74 API router modules (auth, swarm, analytics, billing, etc.)
│   ├── brain/               # LiteLLM model router, agent departments, swarm orchestrator
│   ├── core/                # 30+ core resilience modules (CircuitBreaker, Redis manager, AutonoGuard)
│   ├── memory/              # ChromaDB, SQLite, Supabase, vector stores
│   └── tools/               # AI agents (Browser, Vision, Email, GitHub, Codebase Exporter)
├── docs/                    # Single Master Blueprint & architectural specifications
├── evolution/               # Auto skill creator, daily learner, self-learning forge
├── infrastructure/          # Cloudflare CDN worker, Terraform, Firebase config
└── scripts/                 # Bootstrap, deploy, secret sync, and perf benchmark tools
```

---

## 3. ADMIN'S MASTER PLAN & COMPONENT INVENTORY

### 3.1 95+ Active Core Components
- **Multi-Cloud Router:** `backend/core/llm/llm_gateway.py` (Smart LiteLLM dispatch)
- **MCP Client:** `backend/brain/mcp_client.py` (Model Context Protocol native client)
- **Agent Swarm Orchestrator:** `backend/api/routes/swarm.py` & `swarm_orchestrator.py`
- **Semantic Cache:** `backend/core/cache/redis_manager.py` (Upstash / Redis)
- **Unified Circuit Breaker:** `backend/core/resilience/circuit_breaker.py`
- **JIT OTP Defense Shield:** `backend/core/autonoguard_engine.py`

### 3.2 30 Core MCP Servers Integration
Integrated support for GitHub, File System, Terminal, Browser Puppeteer, PostgreSQL, SQLite, Brave Search, Sequential Thinking, Sentry, Vercel, Supabase, and Docker MCP tools.

---

## 4. HEADLESS ZERO-COST TERMINAL AI AGENT

- **Source Specification:** `docs/-01-admin's plan/headless,zro cost terminal base ai agent/`
- **File:** `backend/tools/cli.py` & `backend/tools/computer_agent.py`
- **Features:**
  - Non-GUI headless execution directly from shell terminal.
  - Automatic routing to free-tier LLM endpoints (DeepSeek-V3, Kimi K2.5).
  - Streaming stdout/stderr execution with safety command sanitization.
  - State checkpointing for interrupted terminal sessions.

---

## 5. CODE-TO-DATABASE PERSISTENCE & INDEXING

- **Source Specification:** `docs/-01-admin's plan/CODE_TO_DATABASE/`
- **File:** `backend/tools/knowledge_base_indexer.py` & `backend/memory/chromadb_store.py`
- **Features:**
  - Automatic AST parsing of repository source files.
  - Real-time vector embedding indexing in ChromaDB and SQLite.
  - Enables semantic code search, context extraction, and structural diff tracking across commits.

---

## 6. MULTI-DATABASE FEDERATION LAYER

- **Source Specification:** `docs/-01-admin's plan/MUTLI_DATA_BASE/`
- **File:** `backend/core/cache/redis_manager.py` & `backend/database/pgbouncer_pool.py`
- **Topology:**
  - **Primary Relational DB:** Supabase / PostgreSQL (pooled via PGBouncer).
  - **Distributed Cache:** Redis / Upstash (`set_cache`, `get_cache` async aliases).
  - **Document Store:** GCP Firestore for mobile & web client sync.
  - **Vector DB:** ChromaDB for RAG context retrieval.
  - **Local Persistence:** SQLite for offline desktop/mobile caching.

---

## 7. AUTONOMOUS WEB & MOBILE UX ARCHITECTURE

- **Source Specification:** `docs/-01-admin's plan/dashboard redesign plan/`

### 7.1 Web Client (`apps/studio-client`)
- **`CommandBar.tsx`:** Universal `Ctrl+K` / `Cmd+K` keyboard shortcut action launcher.
- **`NavRail.tsx`:** Collapsible icon navigation drawer.
- **`Skeleton.tsx`:** Animated loading state placeholders.
- **`BillingPage.tsx`:** Subscription and free-tier token usage management (`/billing`).
- **`ProfilePage.tsx`:** User settings and JIT OTP preference management (`/profile`).
- **`ErrorPage.tsx`:** Branded 404 & 500 exception pages.

### 7.2 Flutter Mobile App (`apps/mobile`)
- **`app_router.dart`:** GoRouter type-safe routing with deep linking.
- **`notifications_screen.dart`:** Real-time autonomous notification feed.
- **`quota_screen.dart`:** Token quota and provider usage breakdown.
- **`onboarding_screen.dart`:** 3-step animated onboarding walkthrough.

---

## 8. SECURITY SHIELD & JIT OTP DEFENSE

- **Module:** `backend/core/autonoguard_engine.py`
- **Malware Immunity:**
  - Mandatory JIT OTP prompt triggered when accessing sensitive routes (`/billing`, `/admin`, `/payments`).
  - IP Churn Detection: Tracks IP thrashing (>5 IPs per hour triggers mandatory OTP challenge).
  - AST Security Scanning: Blocks malicious code injection prior to sandbox execution.

---

## 9. MULTI-PLATFORM DEPLOYMENT & SECRET SYNC

- **Specification Document:** `docs/DEPLOYMENT_ARCHITECTURE.md`
- **Topology:**
  - **Render:** Backend API & Celery workers (`api.supremeai.io`).
  - **Vercel:** Primary User Web Application (`studio.supremeai.io`).
  - **Firebase Hosting:** Isolated Admin God-Mode (`admin.supremeai.io`).
  - **Cloudflare CDN:** Edge WAF, SSL termination, and asset caching.
  - **Infisical Cloud:** Centralized vault synced via `python scripts/sync_all_platforms_env.py`.

---

## 10. DEVELOPER OPERATIONAL GUIDE

- **Operational Manual:** `docs/DEVELOPER_GUIDE.md`

### Essential Commands:
```bash
# Bootstrap development environment
python scripts/bootstrap_env.py

# Sync environment secrets across all connected platforms
python scripts/sync_all_platforms_env.py

# Start Backend API
pnpm backend:dev

# Start Web Client
cd apps/studio-client && pnpm dev

# Run unit test suite
poetry run pytest tests/api/test_admin.py tests/api/test_swarm_routes.py tests/test_circuit_breaker.py

# Run performance benchmark against active server
python scripts/benchmark/perf_benchmark.py --url http://127.0.0.1:8000 --requests 50
```

---

_SupremeAI 2.0 — Single Master Specification Document_
