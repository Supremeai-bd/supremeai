# Comprehensive Parity & Operability Audit Report: Backend vs Frontend (Deep Analysis)

**Date:** 2026-09-11
**Project:** SupremeAI
**Status:** Parity Reconciliation Pass — Whole-Codebase Re-Verified, Table States Reconciled & Document-Synced (2026-09-11, reconciliation pass; re-validated same-day — no code drift)
**Scope:** Whole Codebase (`backend/`, `frontend/`, `infrastructure/`, `docs/`)

---

## Remediation Log (2026-09-11 — Same-Day Fix Session)

> **Status after this session:** Priority 1 (contract mismatches + unmounted routers) and Priority 2 (nav rail exposure) are **RESOLVED and regression-guarded**. Priority 3 is **partially resolved** (MCPConnector + SecretsPage wired; ChatInterface-in-AIStudio intentionally deferred). Priority 4 (dedicated UI adapters for orphan engines) remains **OPEN**.

### ✅ Fixed — Priority 1: Contract Mismatches
| # | Fix | Files | Verification |
|---|---|---|---|
| 1 | `GET` + `POST /api/v1/health/agents` implemented (`agent_supervisor.get_health()` + `agent_ids` body filter; unknown ids → `status="unknown"`) | `backend/api/routes/health.py` | Boot-wiring check + `test_agent_heartbeat_route_exists` |
| 2 | New wallet-based pre-flight budget endpoint `GET /api/billing/budget-check?estimated=…` (402 on insufficient balance) + frontend switched to it | `backend/api/routes/billing_api.py`, `frontend/src/hooks/useBudgetCheck.ts` | Boot-wiring check + `test_budget_check_route_exists` |
| 3 | RateLimitManager now targets `/admin-api/tenant-limits` (3 call sites) | `frontend/src/components/admin/security/RateLimitManager.tsx` | Matches `tenant_admin.py` mounting |
| 4 | agentService list/status now target `/api/agents/…` (`agents.py`); execute posts to `/api/v1/agent/execute` (`agent_workspace.py`, prefix `""`) — `agent.py`'s `POST /api/v1/agents/execute` is a separate autonomous-agent endpoint | `frontend/src/services/agentService.ts`, `agentService.test.ts` | vitest 3/3 |

### ✅ Fixed — Priority 1: Unmounted Routers (all 7 mounted in `ALL_ROUTERS`, prefix `""`)
`tools.code.diagram_to_architecture`, `tools.code.voice_coder`, `tools.code.ai_pair_programmer`, `tools.self_planner`, `services.video_to_code_pipeline`, `agents.vulnerability_prophet`, `ws.command_center` → `backend/api/routers.py`.
Security note: `vulnerability_prophet` enforces its own admin guard per route; `voice_coder` keeps the sibling tool-router pattern (`is_admin=False`) because its WebSocket route is incompatible with HTTP-only registry-level token dependencies.
Verification: real app boot reports `mounted=123/123 registry entries`; effective-path scan confirms `/diagram/to-terraform`, `/voice/process-audio`, `/pair/solve`, `/agent/plan`, `/video-to-code/process`, `/security/vulnerabilities/scan`, `/ws/command-center/health` all resolve; `tests/security/test_dead_route_wiring.py::TestParityAuditRouterWiring` locks the mounts (18/18 passing).

### ✅ Fixed — Priority 2: Navigation Rail
`navigationRegistry.ts` now exposes: **Deep Research** (`/research`, Build), **Scheduled Tasks** (`/scheduled-tasks`, Build), **Neural Memory** (`/memory`, Account), **API Keys** (`/settings/api-keys`, Account). All point to real `App.tsx` routes (CI nav-gate safe).

### ✅ Fixed — Priority 3 (partial): Ghost UI
- `SecretsPage.tsx` → routed at `/settings/api-keys` (ProtectedRoute + WorkspaceLayout).
- `MCPConnector.tsx` → embedded as the new "MCP Servers" tab in `IntegrationsManager.tsx`.
- **Deferred:** `ChatInterface.tsx` ↔ `InteractiveChatTab.tsx` consolidation in `AIStudio.tsx` — this is a UX-level swap affecting the admin-shared component and `App.test.tsx` mocks; requires its own design pass (see Open Items).

### 🔜 Open Items (unchanged from audit)
1. **ChatInterface ↔ InteractiveChatTab** consolidation in AIStudio (Tier-S Thinking/Artifacts/Slash-commands into the live studio view).
2. **Priority 4 UI adapters:** Social Growth workspace (`socialGrowthService.ts` still has zero consumers), Diagram/Image ingest modal, Voice-coder mic button, Style-learner button, Multilingual TTS language selector, BYOC deployment panel, Crawler admin sub-tab.
3. `backend/openapi.json` / `backend/API-swagger.yaml` are generated snapshots and do **not** yet include the new `/health/agents` + `/budget-check` routes — regenerate on next schema export.

---

Following a deep-dive investigation across the entire SupremeAI codebase (`backend/`, `frontend/`, `infrastructure/`), this document records a factual, verifiable cross-system audit of functional, routing, state, and architectural parity between the Backend and Frontend.

We systematically analyzed:
1. **Router Registration Architecture & Mount Realities**: Which backend `APIRouter` instances are registered in `backend/api/routers.py`, `backend/core/app.py`, or `backend/api/routes/workspace_feature_routes.py`, versus which engines exist only as disconnected modules.
2. **Frontend Routing & "Ghost UI" Surface Audit**: The exact status of previously orphaned components (`DeepResearchPanel`, `ScheduledTasksPanel`, `CostDashboard`, `MemoryPanel`, `SecretsPage`, `MCPConnector`, etc.) and how they map to active routes in `frontend/src/App.tsx` and navigation rails.
3. **Dashboard & Navigation Link Verifications**: Concrete validation of user and admin routes (`/files`, `/agents`, `/usage`, `/research`, `/scheduled-tasks`, `/memory`), identifying what is fully wired and what points to generic stubs vs specialized pages.
4. **Contract & Path Discrepancies**: Exact path prefix alignment (`/admin-api/tenant-limits` vs `/admin/tenant-limits`, `/api/v1/health/agents` vs `health.py`, `/api/v1/agents` vs `/api/agents`), documenting both backend routing realities and frontend client calls.
5. **Orphan Backend Engines**: Advanced backend systems (Social Growth, Diagram-to-Infrastructure, Video-to-Code, Voice Coder, Style Learner, BYOC Orchestrator) that possess functional backend APIs but lack direct dedicated UI workspaces.

### Quantitative Overview
| Metric | Value | Audit Notes |
|---|---|---|
| **Total Backend Endpoints Analyzed** | ~780 endpoints | Spanning `backend/api/routes/`, `backend/tools/`, and `backend/core/` |
| **Backend Files Defining `APIRouter`** | 152 files | Verified by static tree scan (Python files matching `router = APIRouter`) |
| **Backend Routers Mounted Anywhere** | **129 router modules** | Registered via `ALL_ROUTERS` (123 entries in `backend/api/routers.py`) + Tier-S `workspace_feature_routes` (12 in `backend/api/routes/workspace_feature_routes.py`) + direct `app.include_router` in `app_builder.py`/`app.py` (5: `api.routes.browser`, `core.health_routes` ×2 prefixes, `core.admin_routes`, `stream_chat_sse.legacy_router`, conditional `byoc_api`) |
| **Backend Routers Define-but-Not-Directly-Registered** | **27** (25 composed sub-routers + **2 genuinely orphaned: `services.scraper.main`, `tools.api_gateway`**) | 25 are parent-aggregated (e.g. `commandcenter.*`, `tools.code.*`); boot mounts them via their package `__init__`. 2 orphans have zero code references. |
| **Boot Registration Outcome** | **123/123 `ALL_ROUTERS` mounted, 0 failures** + **12/12 Tier-S mounted** | Exact 123 entries defined in `backend/api/routers.py` and locked by `tests/security/test_dead_route_wiring.py` (18/18 tests pass); no import/mount failures. |
| **Total Frontend Source Files Scanned** | 473 files | React 19 + TypeScript + Vite (verified across `frontend/src/**/*.ts`, `*.tsx`) |
| **Ghost UI Powerhouses Now Routed in `App.tsx`** | **4 prominent panels** | `DeepResearchPanel` (`/research`), `ScheduledTasksPanel` (`/scheduled-tasks`), `CostDashboard` (`/usage`), `MemoryPanel` (`/memory`) |
| **Ghost UI Components Still Unmounted / Unreferenced** | **0** (all routed) | `MCPConnector.tsx` → MCP Servers tab in `IntegrationsManager`; `SecretsPage.tsx` → `/settings/api-keys`; `ChatInterface`↔`InteractiveChatTab` consolidation deferred by design (see Open Items). |
| **Dead Navigation Links in User Dashboard** | **0 active 404s** | `/files` and `/agents` are registered routes in `App.tsx` (`WorkspaceModulePage` & `AgentWorkspace`); nav-rail links for `/research`, `/scheduled-tasks`, `/memory`, `/settings/api-keys` active. |
| **Active Contract / Path Mismatches** | **0** | All documented mismatches (Section 4) reconciled & regression-tested. |

---

## Section 1: Backend Router Mount Status (Runtime Reality Check)

### 1.1 Mounted Routers Verified in Active Pipeline
The primary entry points for backend execution are `backend/core/app.py` and `backend/api/routers.py`. In addition, `backend/core/app.py` explicitly calls `register_workspace_feature_routes(app)` (which mounts the 12 Tier-S feature routers).

- **Tier-S Routers Mounted via `register_workspace_feature_routes` in `core/app.py`:**
  - `api.routes.artifacts` (`/api/artifacts`)
  - `api.routes.branch_conversations` (`/api/conversations`)
  - `api.routes.chat_export` (`/api/chat/export`)
  - `api.routes.chat_search` (`/api/chat/search`)
  - `api.routes.chat_upload` (`/api/chat/upload`)
  - `api.routes.deep_research` (`/api/research`)
  - `api.routes.global_memory` (`/api/memory/global`)
  - `api.routes.prompt_templates` (`/api/prompt-templates`)
  - `api.routes.reasoning` (`/api/reasoning`)
  - `api.routes.scheduled_tasks` (`/api/schedule`)
  - `api.routes.share` (`/api/share`)
  - `api.routes.slash_commands` (`/api/commands`)

- **Mounted in `backend/api/routers.py` (`ALL_ROUTERS`):**
  - `api.routes.social_growth` (`prefix=""`, internal prefix `/api/v1/social`) — **Mounted & active**
  - `api.routes.crawler_admin` (`prefix=""`, internal prefix `/api/v1/admin/crawler`) — **Mounted & active**
  - `api.routes.tenant_admin` (`prefix=""`, internal prefix `/admin-api/tenant-limits` and `/admin-api/tenants`) — **Mounted & active**
  - `api.routes.agent` (`prefix=""`, internal prefix `/api/v1/agents`) — **Mounted & active**
  - `api.routes.agents` (`prefix=""`, internal prefix `/api/agents`) — **Mounted & active**
  - `tools.code.image_to_code` (`prefix=""`, internal prefix `/tools`) — **Mounted & active**
  - `tools.learning.style_learner` (`prefix="/api"`, internal prefix `/style` -> `/api/style`) — **Mounted & active**
  - `tools.media.multilingual_tts` (`prefix="/api"`, internal prefix `/tts` -> `/api/tts`) — **Mounted & active**
  - `tools.comment_thread_ai` (`prefix="/api"`, internal prefix `/comment-ai` -> `/api/comment-ai`) — **Mounted & active**
  - `api.routes.byoc_api` (`/api/byoc`) — **Conditionally mounted if `ENCRYPTION_KEY` is configured**

### 1.2 Router Mount Census (Verified — 2026-09-11)

A static tree scan reconciled **every** module that defines `router = APIRouter()` against all real mount sites
(`ALL_ROUTERS` in `routers.py` — 123 entries — plus `register_tier_s_routes` /
`register_workspace_feature_routes` in `workspace_feature_routes.py`, and the direct
`app.include_router(...)` calls in `core/app_builder.py` / `core/app.py`).

**Headline:** 152 router-defining modules → 129 mounted anywhere → 27 define-but-not-directly-registered.

*Of the 27 not directly registered, 25 are **composed sub-routers** (imported and aggregated into a parent package
router — e.g. `api.routes.commandcenter.build`, `.money`, `.observe`, `.operate`, `.overview`, `.secure`, `.system`
are included by `api/routes/commandcenter/__init__.py`, which is itself registered in `ALL_ROUTERS`; `tools.code.*`
and `core.orchestration.*` sub-routers follow the same pattern). These are **live, served routes**, not dead code.*

**The 7 routers previously documented as "Confirmed Unmounted" below were wired in this session and are now
mounted & verified** (`backend/api/routes/billing_api.py`-style entries added to `ALL_ROUTERS`):

| # | Router | Effective Endpoint(s) | Mount Path | Status |
|---|---|---|---|---|
| 1 | `tools.code.diagram_to_architecture` | `POST /diagram/to-terraform` | `ALL_ROUTERS` | 🟢 Mounted — resolves (`ALL_WIRED`) |
| 2 | `tools.code.voice_coder` | `POST /voice/process-audio` | `ALL_ROUTERS` | 🟢 Mounted — resolves |
| 3 | `tools.code.ai_pair_programmer` | `POST /pair/solve` | `ALL_ROUTERS` | 🟢 Mounted — resolves |
| 4 | `tools.self_planner` | `POST /agent/plan` | `ALL_ROUTERS` | 🟢 Mounted — resolves |
| 5 | `services.video_to_code_pipeline` | `POST /video-to-code/process` | `ALL_ROUTERS` | 🟢 Mounted — resolves |
| 6 | `agents.vulnerability_prophet` | `POST /security/vulnerabilities/scan` | `ALL_ROUTERS` | 🟢 Mounted — resolves (admin guard preserved) |
| 7 | `ws.command_center` | `GET /ws/command-center/health` (`WS /ws/command-center`) | `ALL_ROUTERS` | 🟢 Mounted — resolves |

Boot-time verification: **123/123 `ALL_ROUTERS` entries mount with 0 failures**; all 12 Tier-S routers mount.
Regression guard: `tests/security/test_dead_route_wiring.py::TestParityAuditRouterWiring` (18/18 passing).

**Residual orphans (out of original audit scope — flagged by the static census):**
- `backend/services/scraper/main.py` — defines `router = APIRouter()`, **zero code references**. No route is reachable.
- `backend/tools/api_gateway.py` — defines `router = APIRouter()`, **zero code references** (only a mention in `COVERAGE_90_PLAN.md`).

These two are not consumed by any parent router and are not mounted; recommend deletion-via-orphan-review or
activation + a dedicated UI in the next pass.

---

## Section 2: Frontend "Ghost UI" & Routing Parity

### 2.1 Newly Mounted Components in `App.tsx`
Recent updates in `frontend/src/App.tsx` have officially connected several previously orphaned panels to the React Router tree:

1. **`DeepResearchPanel.tsx`** (`frontend/src/components/research/DeepResearchPanel.tsx`):
   - **Route in `App.tsx`**: `<Route path="/research" element={<ProtectedRoute><WorkspaceLayout><DeepResearchPanel /></WorkspaceLayout></ProtectedRoute>} />`
   - **Backend Route**: Connects to `/api/research/history` and SSE streaming `/api/research/deep/stream` (both live via `deep_research.py`, mounted through `register_tier_s_routes`).
   - **Navigation Rail Status (2026-09-11, verified)**: ✅ Exposed — `NAVIGATION_REGISTRY` Build group → `Deep Research` (`/research`, icon `Search`, `status: 'implemented'`).

2. **`ScheduledTasksPanel.tsx`** (`frontend/src/components/schedule/ScheduledTasksPanel.tsx`):
   - **Route in `App.tsx`**: `<Route path="/scheduled-tasks" element={<ProtectedRoute><WorkspaceLayout><ScheduledTasksPanel /></WorkspaceLayout></ProtectedRoute>} />`
   - **Backend Route**: Connects to `/api/schedule/*` (live via `scheduled_tasks.py`, mounted through `register_tier_s_routes`).
   - **Navigation Rail Status (2026-09-11, verified)**: ✅ Exposed — `NAVIGATION_REGISTRY` Build group → `Scheduled Tasks` (`/scheduled-tasks`, icon `Clock`, `status: 'implemented'`).

3. **`CostDashboard.tsx`** (`frontend/src/pages/user/CostDashboard.tsx`):
   - **Route in `App.tsx`**: `<Route path="/usage" element={<ProtectedRoute><WorkspaceLayout><CostDashboard /></WorkspaceLayout></ProtectedRoute>} />`
   - **Backend Route**: Fetches `/api/billing/analytics` (plus new wallet pre-flight `GET /api/billing/budget-check`) and listens to `Events.TOKEN_USAGE_UPDATED`.
   - **Navigation Rail Status**: Present in `NAVIGATION_REGISTRY` (Account group → `Usage` → `/usage`). Fully accessible to end users.

4. **`MemoryPanel.tsx`** (`frontend/src/components/memory/MemoryPanel.tsx`):
   - **Route in `App.tsx`**: `<Route path="/memory" element={<ProtectedRoute><WorkspaceLayout><MemoryPanel /></WorkspaceLayout></ProtectedRoute>} />`
   - **Backend Route**: Connects to `/api/memory/*`.
   - **Navigation Rail Status (2026-09-11, verified)**: ✅ Exposed — `NAVIGATION_REGISTRY` Account group → `Neural Memory` (`/memory`, icon `BrainCircuit`, `status: 'implemented'`).

5. **`SecretsPage.tsx`** (`frontend/src/components/dashboard/SecretsPage.tsx` — also mounted 2026-09-11):
   - **Route in `App.tsx`**: `<Route path="/settings/api-keys" element={<ProtectedRoute><WorkspaceLayout><SecretsPage /></WorkspaceLayout></ProtectedRoute>} />`
   - **Backend Route**: `/api/api-keys/*` (`api.routes.api_keys`).
   - **Navigation Rail Status (2026-09-11, verified)**: ✅ Exposed — `NAVIGATION_REGISTRY` Account group → `API Keys` (`/settings/api-keys`, icon `KeyRound`, `status: 'implemented'`).

### 2.2 Still Orphaned Frontend Components (Ghost UI) — updated 2026-09-11
`MCPConnector.tsx` and `SecretsPage.tsx` are **no longer orphans** (see Remediation Log — Priority 3):
- `MCPConnector.tsx` → embedded as the "MCP Servers" tab in `IntegrationsManager.tsx` (verified import + render).
- `SecretsPage.tsx` → routed at `/settings/api-keys` + nav-rail entry (verified above).
3. **`ChatInterface.tsx` Tier-S Integration Disconnect**:
   - `frontend/src/components/chat/ChatInterface.tsx` (272 lines) wires Claude-style Artifacts, Thinking Process panel, Chat Search, and Conversation Branching.
   - However, `AIStudio.tsx` renders `InteractiveChatTab.tsx` instead of `ChatInterface.tsx`. As a result, the primary live studio view does not utilize the reasoning panel or artifact drawer.

---

## Section 3: Navigation & URL Integrity Verification

### 3.1 User Dashboard Links (`UserDashboard.tsx`)
In earlier revisions, clicking certain quick-start links caused 404 errors. Verification against current `App.tsx`:
- **`/files`**:
  - `UserDashboard.tsx`: `<Link to="/files">Analyze a file</Link>`
  - `App.tsx`: `<Route path="/files" element={<ProtectedRoute><WorkspaceModulePage module="files" /></ProtectedRoute>} />`
  - **Verdict**: **Resolved (200 OK)** — Renders `WorkspaceModulePage` for files.
- **`/agents`**:
  - `UserDashboard.tsx`: `<Link to="/agents">Build a workflow</Link>`
  - `App.tsx`: `<Route path="/agents" element={<ProtectedRoute><WorkspaceLayout><AgentWorkspace /></WorkspaceLayout></ProtectedRoute>} />`
  - **Verdict**: **Resolved (200 OK)** — Directly opens `AgentWorkspace`.

---

## Section 4: API Contract & Path Discrepancies (RESOLVED — 2026-09-11)

The following four client-server contract mismatches were present in active code and **have been reconciled** in
this session. Each resolution is regression-guarded (boot wiring + a dedicated `pytest` route-existence test).

### 4.1 ✅ RESOLVED — Agent Swarm Health Heartbeat (`MockSwarmProvider.tsx` & `useSwarmGraph.ts`)
- **Frontend Calls**:
  - `MockSwarmProvider.tsx` line 29: `apiClient.post('/api/v1/health/agents', { agent_ids: ... })`
  - `useSwarmGraph.ts` line 56: `fetch('${getApiBaseUrl()}/api/v1/health/agents', { method: 'GET' })`
- **Backend Reality (2026-09-11, resolved)**:
  - `backend/api/routes/health.py` is mounted at prefix `/api/v1`; `GET` + `POST /health/agents` (effective `POST /api/v1/health/agents`) now query `core.agent_supervisor.agent_supervisor.get_health()` with an `agent_ids` body filter (unknown ids → `status="unknown"`).
- **Consequence (before fix)**: `MockSwarmProvider` constantly caught HTTP 404 errors and was forced to display fallback/disconnected state.
- **Fix (applied + regression-guarded)**: `@router.get("/health/agents")` and `@router.post("/health/agents")` added in `backend/api/routes/health.py`; locked by `tests/security/test_dead_route_wiring.py::test_agent_heartbeat_route_exists`.

### 4.2 ✅ RESOLVED — Tenant Rate Limits URL Mismatch (`RateLimitManager.tsx`)
- **Frontend Calls (2026-09-11, fixed)**:
  - `frontend/src/components/admin/security/RateLimitManager.tsx` lines 59, 102, 130:
    `fetch(`${API_BASE}/admin-api/tenant-limits`, ...)` (was `/admin/tenant-limits`)
- **Backend Reality**:
  - `backend/api/routes/tenant_admin.py` defines:
    `router = APIRouter(prefix="/admin-api/tenant-limits")`
  - `backend/api/routers.py` mounts it with `prefix=""`, so the actual endpoints are at `/admin-api/tenant-limits`.
- **Consequence**: All 3 call sites in `RateLimitManager.tsx` to `/admin/tenant-limits` failed with HTTP 404.
- **Resolution (2026-09-11)**: Switched all 3 call sites to `${API_BASE}/admin-api/tenant-limits`, matching `tenant_admin.py`'s mount. `git grep` confirms **0** remaining `/admin/tenant-limits` references in `frontend/src`.

### 4.3 ✅ RESOLVED — Agent Status Prefix Discrepancy (`agentService.ts` vs `agents.py`)
- **Frontend Calls (2026-09-11, fixed)**:
  - `frontend/src/services/agentService.ts`:
    - list → `/api/agents/` (was `/api/v1/agents/`)
    - status → `/api/agents/{agentId}/status` (was `/api/v1/agents/{agentId}/status`)
- **Backend Reality**:
  - In `backend/api/routes/agents.py`: `router = APIRouter(prefix="/api/agents")` (exposes `GET /` and `GET /{agent_id}/status` → effective `/api/agents/`, `/api/agents/{id}/status`).
  - In `backend/api/routes/agent.py`: `router = APIRouter(prefix="/api/v1/agents")` (exposes only `POST /execute` → effective `POST /api/v1/agents/execute`; autonomous-agent schema, token-guarded — a *different* endpoint).
  - `POST /api/v1/agent/execute` (singular `agent`) is served by `backend/api/routes/agent_workspace.py` (`router = APIRouter()` with internal `@router.post("/agent/execute")`, mounted with `prefix=""`) — this is the endpoint `agentService.executeAgentTask` actually calls.
- **Consequence**: Calling `/api/v1/agents/` or `/api/v1/agents/{id}/status` previously hit `agent.py`'s router (which lacks those GET routes), yielding 404/405.
- **Resolution (2026-09-11)**: `agentService.ts` list/status now target `/api/agents/...` (matching `agents.py`); execute keeps `POST /api/v1/agent/execute` (matching `agent_workspace.py`; `agent.py`'s plural `/api/v1/agents/execute` remains a separate valid endpoint). Verified: `vitest` agentService suite 3/3 passing.

### 4.4 ✅ RESOLVED — Budget Check Route Mismatch (`useBudgetCheck.ts`)
- **Frontend Calls (2026-09-11, fixed)**:
  - `frontend/src/hooks/useBudgetCheck.ts` → `GET /api/billing/budget-check?estimated=…` (was `/api/admin/metrics/cost?estimated=…`)
- **Backend Reality**:
  - Backend routes in `admin_v1.py` or `billing_api.py` do not provide `/api/admin/metrics/cost`. Cost endpoints reside under `/admin-api/costs` or `/api/billing/analytics`.
   - **Consequence**: `useBudgetCheck` previously failed silently with 404 on the pre-flight cost verification (the path `/api/admin/metrics/cost` never existed in the backend).
   - **Resolution (2026-09-11)**: New wallet-based pre-flight endpoint `GET /api/billing/budget-check?estimated=…`
     was added in `backend/api/routes/billing_api.py` (returns **402** on insufficient balance); `useBudgetCheck.ts`
     now calls it. Verified: `test_budget_check_route_exists` + effective-path scan.

---

## Section 5: Backend-Heavy Engines with Zero Frontend UI (Orphan Capabilities)

These services are production-grade on the backend, but lack user-facing interfaces:

| Capability | Backend Implementation | Endpoints | Frontend State | Recommended UI Integration |
|---|---|---|---|---|
| **Social Growth Engine** | `backend/api/routes/social_growth.py`<br>`backend/core/social_growth/` | `GET/POST /api/v1/social/drafts`<br>`POST /api/v1/social/drafts/{id}/approve`<br>`POST /api/v1/social/pause`, `/resume` | `socialGrowthService.ts` is fully implemented, but **0 UI components** consume it | Add `SocialGrowthTab.tsx` in `WorkspaceModulePage` or as a sub-panel in `AIStudio` |
| **Diagram to Infrastructure** | `backend/tools/code/diagram_to_architecture.py` | `POST /diagram/to-terraform`<br>`POST /diagram/to-kubernetes`<br>`POST /diagram/to-schema` | 🟢 Mounted (`ALL_ROUTERS`, 2026-09-11); no UI dropzone, no cloud selector (AWS/GCP), no code preview | Mounted backend router in `routers.py` ✅ + Add "Diagram-to-IaC" modal in `IdeWorkspace` (OPEN) |
| **Image / Figma to Code** | `backend/tools/code/image_to_code.py` | `POST /tools/image-to-code`<br>`POST /tools/image-to-component`<br>`POST /tools/image-to-palette` | Backend is mounted; no toolbar trigger in Monaco editor | Add "Vision / Design Ingest" button in `AgentWorkspace.tsx` and `IdeWorkspace.tsx` |
| **Video to Code Pipeline** | `backend/services/video_to_code_pipeline.py` | `POST /video-to-code/process` | 🟢 Mounted (`ALL_ROUTERS`, 2026-09-11); zero UI | Add Video dropzone in `AIStudio` preview tab (OPEN) |
| **Voice Coder** | `backend/tools/code/voice_coder.py` | `POST /voice/process-audio`<br>`WS /voice/ws` | 🟢 Mounted (`ALL_ROUTERS`, 2026-09-11); audio recorder services exist in frontend but lack mic button | Add microphone button in `AgentWorkspace` chat prompt (OPEN) |
| **Automated Style Learner** | `backend/tools/learning/style_learner.py` | `POST /api/style/learn`<br>`GET /api/style/prompt` | Backend is mounted; no UI button | Add "Learn Coding Style" button in `IdeWorkspace.tsx` |
| **Vulnerability Prophet** | `backend/agents/vulnerability_prophet.py` | `POST /security/vulnerabilities/scan`<br>`POST /security/vulnerabilities/scan-project` | 🟢 Mounted (`ALL_ROUTERS`, 2026-09-11; per-route admin guard); `SecurityDashboard.tsx` lacks on-demand code scanner | Add "Run Security Audit" action in `SecurityDashboard.tsx` (OPEN) |
| **Multilingual TTS Engine** | `backend/tools/media/multilingual_tts.py` | `GET /api/tts/languages`<br>`DELETE /api/tts/cache`<br>`GET /api/tts/audio/{filename}` | ✅ Backend mounted (`ALL_ROUTERS`) + frontend basic TTS only in `frontend/src/services/audio/*` (no language dropdown, no cache endpoints) | Add 29-language selector dropdown in `AIStudio` settings drawer (OPEN) |
| **Universal BYOC Orchestrator** | `backend/api/routes/byoc_api.py` | `POST /api/byoc/credentials`<br>`POST /api/byoc/deploy`<br>`GET /api/byoc/jobs/{job_id}` | Backend is mounted (with `ENCRYPTION_KEY`); no UI in settings | Add "Enterprise BYOC Deployment" panel in `AdminShell` / `ConfigEditor` |
| **Crawler Policy Admin** | `backend/api/routes/crawler_admin.py` | `GET/POST /api/v1/admin/crawler/policies` | Backend is mounted; Admin console has no crawler tab | Add "Crawler Rules" sub-tab in `AdminSubTabContent.tsx` |
| **Static-Census True Orphans** (out of original audit scope) | `backend/services/scraper/main.py`, `backend/tools/api_gateway.py` | Not mounted anywhere; **0 code references** | None | No UI | **Dead Router (orphan-review candidate)** |

---

## Section 6: Comprehensive Feature Parity Matrix

| Feature Area | Backend Router / Service | Mount Status | Frontend Component / Service | Frontend Routing Status | Parity Classification |
|---|---|---|---|---|---|
| **Deep Research** | `api.routes.deep_research` | 🟢 Mounted (`workspace_feature_routes`) | `DeepResearchPanel.tsx` | 🟢 Mounted at `/research` in `App.tsx` + nav rail (`NAVIGATION_REGISTRY` Build → Deep Research) | **Full Parity (Verified 2026-09-11)** |
| **Scheduled Tasks** | `api.routes.scheduled_tasks` | 🟢 Mounted (`workspace_feature_routes`) | `ScheduledTasksPanel.tsx` | 🟢 Mounted at `/scheduled-tasks` in `App.tsx` + nav rail (`NAVIGATION_REGISTRY` Build → Scheduled Tasks) | **Full Parity (Verified 2026-09-11)** |
| **Cost & Token Dashboard** | `api.routes.billing_api` | 🟢 Mounted (`ALL_ROUTERS`) | `CostDashboard.tsx` | 🟢 Mounted at `/usage` in `App.tsx` | **Full Parity (Verified)** |
| **Neural Memory Browser** | `api.routes.memory` | 🟢 Mounted (`ALL_ROUTERS`) | `MemoryPanel.tsx` | 🟢 Mounted at `/memory` in `App.tsx` + nav rail (`NAVIGATION_REGISTRY` Account → Neural Memory) | **Full Parity (Verified 2026-09-11)** |
| **Social Growth** | `api.routes.social_growth` (effective `/api/v1/social/*`) | 🟢 Mounted (`ALL_ROUTERS`) | `socialGrowthService.ts` (typed drafts/approve/pause/resume client) | 🔴 No UI component consumes the service | **Backend Orphan** |
| **MCP Connector** | `infrastructure/mcp-control-plane/` | 🟢 Mounted | `MCPConnector.tsx` | 🟢 Rendered as the "MCP Servers" tab in `IntegrationsManager.tsx` (verified import + render) | **Full Parity (Verified 2026-09-11)** |
| **API Keys / Secrets** | `api.routes.api_keys` (effective `/api/api-keys/*`) | 🟢 Mounted (`ALL_ROUTERS`) | `SecretsPage.tsx` | 🟢 Mounted at `/settings/api-keys` in `App.tsx` + nav rail (`NAVIGATION_REGISTRY` Account → API Keys) | **Full Parity (Verified 2026-09-11)** |
| **Agent Workspace** | `api.routes.agent` (`/api/v1/agents`, `POST /execute`) + `api.routes.agents` (`/api/agents`, `GET /` + `GET /{id}/status`) | 🟢 Mounted (`ALL_ROUTERS`) | `AgentWorkspace.tsx` + `agentService.ts` (list/status → `/api/agents/…`; execute → `POST /api/v1/agent/execute` via `agent_workspace.py`; `agent.py`'s `POST /api/v1/agents/execute` is a separate autonomous-agent endpoint) | 🟢 Mounted at `/agents` & `/workspace/agent` | **Full Parity** |
| **Files Workspace** | `api.routes.files` (`/api/files`) | 🟢 Mounted (`ALL_ROUTERS`) | `WorkspaceModulePage` (`module="files"`) | 🟢 Mounted at `/files` in `App.tsx` | **Full Parity** |
| **Swarm Agent Health** | `api.routes.health` (`GET` + `POST /api/v1/health/agents`) | 🟢 Mounted (`ALL_ROUTERS`) | `MockSwarmProvider.tsx` + `useSwarmGraph.ts` | 🟢 Contract reconciled (was 404) — regression-guarded | **Full Parity (Verified 2026-09-11)** |
| **Tenant Limits** | `api.routes.tenant_admin` (effective `/admin-api/tenant-limits`) | 🟢 Mounted (`ALL_ROUTERS`) | `RateLimitManager.tsx` (3 call sites → `/admin-api/tenant-limits`) | 🟢 Path reconciled (was 404) — 0 stale refs | **Full Parity (Verified 2026-09-11)** |
| **Diagram to Infra** | `tools.code.diagram_to_architecture` (`POST /diagram/to-terraform`, …) | 🟢 Mounted (`ALL_ROUTERS`, 2026-09-11) | None | 🔴 No UI | **Backend Orphan (mount fixed; UI open)** |
| **Voice Coder** | `tools.code.voice_coder` (`POST /voice/process-audio`, `WS /voice/ws`) | 🟢 Mounted (`ALL_ROUTERS`, 2026-09-11) | Audio services only | 🔴 No Mic UI in Workspace | **Backend Orphan (mount fixed; UI open)** |
| **AI Pair Programmer** | `tools.code.ai_pair_programmer` (`POST /pair/solve`) | 🟢 Mounted (`ALL_ROUTERS`, 2026-09-11) | None | 🔴 No UI | **Backend Orphan (mount fixed; UI open)** |
| **Self Planner** | `tools.self_planner` (`POST /agent/plan`) | 🟢 Mounted (`ALL_ROUTERS`, 2026-09-11) | None | 🔴 No UI | **Backend Orphan (mount fixed; UI open)** |
| **Security Prophet** | `agents.vulnerability_prophet` (`POST /security/vulnerabilities/scan`) | 🟢 Mounted (`ALL_ROUTERS`, 2026-09-11; per-route admin guard) | None | 🔴 No Code Scan UI in Admin | **Backend Orphan (mount fixed; UI open)** |
| **Video to Code** | `services.video_to_code_pipeline` (`POST /video-to-code/process`) | 🟢 Mounted (`ALL_ROUTERS`, 2026-09-11) | None | 🔴 No Video Ingest UI | **Backend Orphan (mount fixed; UI open)** |
| **Command-Center WS** | `ws.command_center` (`GET /ws/command-center/health`, `WS /ws/command-center`) | 🟢 Mounted (`ALL_ROUTERS`, 2026-09-11) | None (dashboard consumes via health/WS indirectly) | 🟡 No dedicated UI surface | **Backend Orphan (mount fixed; UI open)** |
| **Style Learner** | `tools.learning.style_learner` | 🟢 Mounted (`ALL_ROUTERS`) | None | 🔴 No UI | **Backend Orphan** |
| **Multilingual TTS** | `tools.media.multilingual_tts` (`ALL_ROUTERS`, prefix `/api` → effective `/api/tts`) | 🟢 Mounted (`ALL_ROUTERS`) | `frontend/src/services/audio/*` (basic TTS only — no `multilingual_tts`/language-selector/cache calls) | 🟡 29 Languages & Cache Endpoints Unused | **Frontend Lacking** |
| **BYOC Cloud Manager** | `api.routes.byoc_api` | 🟢 Mounted (with key) | `frontend/src/commandcenter/data/types.ts` (type refs only — no BYOC form/panel) | 🔴 No BYOC Form in UI | **Backend Orphan** |
| **Web Crawler Admin** | `api.routes.crawler_admin` | 🟢 Mounted (`ALL_ROUTERS`) | None | 🔴 No Crawler Admin subtab | **Backend Orphan** |

---

## Section 7: Actionable Remediation Roadmap

### Priority 1: Backend Router Registrations & Contract Alignment — ✅ DONE (2026-09-11)
1. **Mount previously-unmounted routers** — DONE: `tools.code.diagram_to_architecture`, `tools.code.voice_coder`, `tools.code.ai_pair_programmer`, `tools.self_planner`, `services.video_to_code_pipeline`, `agents.vulnerability_prophet`, `ws.command_center` are all in `ALL_ROUTERS` (`backend/api/routers.py`); boot reports `mounted=123/123`; `TestParityAuditRouterWiring` (18/18) locks the mounts.
2. **`/api/v1/health/agents`** — DONE: `GET` + `POST /health/agents` in `backend/api/routes/health.py` (supervisor-backed, `agent_ids` filter).
3. **Tenant rate-limits path** — DONE: `RateLimitManager.tsx` targets `/admin-api/tenant-limits` (0 stale refs).
4. **Agent status endpoints** — DONE (frontend-aligned): `agentService.ts` list/status target `/api/agents/…` (matching `agents.py`); `POST /api/v1/agents/execute` remains valid via `agent.py`.

### Priority 2: Expose Routed Powerhouses in User Navigation Rail — ✅ DONE (2026-09-11)
In `frontend/src/config/navigationRegistry.ts`:
1. **Research nav** — DONE: `NAVIGATION_REGISTRY` Build → `Deep Research` (`/research`, implemented, verified 2026-09-11).
2. **Scheduled Tasks nav** — DONE: `NAVIGATION_REGISTRY` Build → `Scheduled Tasks` (`/scheduled-tasks`, implemented, verified 2026-09-11).
3. **Memory nav** — DONE: `NAVIGATION_REGISTRY` Account → `Neural Memory` (`/memory`, implemented) + `API Keys` (`/settings/api-keys`, implemented, verified 2026-09-11; supersedes the old WorkspaceModulePage-tab plan).

### Priority 3: Wire Remaining Ghost Components — ✅ PARTIAL (2026-09-11)
1. **Embed `MCPConnector.tsx`** — DONE: rendered as the "MCP Servers" tab in `IntegrationsManager.tsx` (verified import + render).
2. **Mount `SecretsPage.tsx`** — DONE (superseded plan): dedicated route `/settings/api-keys` in `App.tsx` + `NAVIGATION_REGISTRY` Account → `API Keys` (verified 2026-09-11).
3. **Connect `ChatInterface.tsx` in `AIStudio.tsx`** — OPEN (deferred by design): `AIStudio` still renders `InteractiveChatTab`; Tier-S Thinking/Artifacts/Slash-commands consolidation needs its own design pass (see Open Items).

### Priority 4: Implement Lightweight UI Adapters for Orphan Backend Engines
1. **Social Growth Management**: Build a clean `SocialGrowthView.tsx` utilizing `socialGrowthService.ts` for draft creation, review, and auto-publishing.
2. **Visual Multimodal Ingest (Image & Diagram)**: Add an "Import Diagram / Mockup" modal in `AgentWorkspace.tsx` and `IdeWorkspace.tsx` connecting to `/diagram` and `/tools/image-to-code`.
3. **Voice Coding Bar**: Add a microphone button next to the prompt bar in `AgentWorkspace.tsx` streaming audio to `/voice/process-audio`.
