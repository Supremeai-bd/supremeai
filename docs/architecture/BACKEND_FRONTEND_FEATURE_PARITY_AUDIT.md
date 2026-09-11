# Comprehensive Parity & Operability Audit Report: Backend vs Frontend (Deep Analysis)

**Date:** 2026-09-11  
**Project:** SupremeAI  
**Status:** Deep Cross-System Architectural & Runtime Audit Verified  
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
| 4 | agentService list/status now target `/api/agents/…` (`agent.py` keeps only `POST /execute` at `/api/v1/agents`; `/api/v1/agent/execute` remains valid via `agent_workspace.py`) | `frontend/src/services/agentService.ts`, `agentService.test.ts` | vitest 3/3 |

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
| **Backend Files Defining `APIRouter`** | 151 files | Both primary API route modules and tool/agent modules |
| **Backend Routers Mounted in Registry / App** | **110+ router modules** | Registered via `ALL_ROUTERS` in `routers.py`, `admin_router`, and `workspace_feature_routes.py` |
| **Backend Routers Unmounted (Dead at Boot)** | **~25 router modules** | Including `diagram_to_architecture`, `voice_coder`, `ai_pair_programmer`, `vulnerability_prophet`, `video_to_code_pipeline`, `self_planner` |
| **Total Frontend Source Files Scanned** | 475 files | React 19 + TypeScript + Vite |
| **Ghost UI Powerhouses Now Routed in `App.tsx`** | **4 prominent panels** | `DeepResearchPanel` (`/research`), `ScheduledTasksPanel` (`/scheduled-tasks`), `CostDashboard` (`/usage`), `MemoryPanel` (`/memory`) |
| **Ghost UI Components Still Unmounted / Unreferenced** | **`MCPConnector.tsx`, `SecretsPage.tsx`** | Fully written components without route or parent embedding |
| **Dead Navigation Links in User Dashboard** | **0 active 404s** | `/files` and `/agents` are now registered routes in `App.tsx` (`WorkspaceModulePage` & `AgentWorkspace`) |
| **Active Contract / Path Mismatches** | **3 critical paths** | `/api/v1/health/agents` (missing in backend `health.py`), `/admin/tenant-limits` (`RateLimitManager.tsx` calls non-existent prefix), `/api/v1/agents` vs `/api/agents` |

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

### 1.2 Confirmed Unmounted Backend Routers (Inaccessible at Boot)
These modules define FastAPI `APIRouter` instances with substantial logic, but are omitted from both `ALL_ROUTERS` and `register_workspace_feature_routes`:

1. **`backend/agents/vulnerability_prophet.py`**:
   - Router: `prefix="/security/vulnerabilities"` (`POST /security/vulnerabilities/scan`, `POST /security/vulnerabilities/scan-project`)
   - Status: Has a local `register_routes(app)` helper that is never invoked during server bootstrap.
2. **`backend/tools/code/diagram_to_architecture.py`**:
   - Router: `prefix="/diagram"` (`POST /diagram/to-terraform`, `POST /diagram/to-kubernetes`, `POST /diagram/to-schema`, `POST /diagram/api-spec`)
   - Status: Absent from `ALL_ROUTERS`. Endpoints return 404.
3. **`backend/tools/code/voice_coder.py`**:
   - Router: `prefix="/voice"` (`POST /voice/process-audio`, `WS /voice/ws`)
   - Status: Absent from `ALL_ROUTERS`. Endpoints return 404.
4. **`backend/tools/code/ai_pair_programmer.py`**:
   - Router: `prefix="/pair"` (`POST /pair/solve`, `POST /pair/review`)
   - Status: Absent from `ALL_ROUTERS`.
5. **`backend/tools/self_planner.py`**:
   - Router: `prefix="/agent"` (`POST /agent/plan`)
   - Status: Absent from `ALL_ROUTERS`.
6. **`backend/services/video_to_code_pipeline.py`**:
   - Router: `prefix="/video-to-code"` (`POST /video-to-code/process`)
   - Status: Absent from `ALL_ROUTERS`.
7. **`backend/ws/command_center.py`**:
   - Router: `prefix="/ws/command-center"` (`GET /ws/command-center/health`)
   - Status: Absent from `ALL_ROUTERS`.

---

## Section 2: Frontend "Ghost UI" & Routing Parity

### 2.1 Newly Mounted Components in `App.tsx`
Recent updates in `frontend/src/App.tsx` have officially connected several previously orphaned panels to the React Router tree:

1. **`DeepResearchPanel.tsx`** (`frontend/src/components/research/DeepResearchPanel.tsx` — 648 lines):
   - **Route in `App.tsx`**: `<Route path="/research" element={<ProtectedRoute><WorkspaceLayout><DeepResearchPanel /></WorkspaceLayout></ProtectedRoute>} />`
   - **Backend Route**: Connects to `/api/research/history` and SSE streaming `/api/research/deep/stream` (both live via `deep_research.py`).
   - **Navigation Rail Status**: Not yet included in `NAVIGATION_REGISTRY` (`src/config/navigationRegistry.ts`), meaning users can only access it by direct URL `/research` or programmatic navigation.

2. **`ScheduledTasksPanel.tsx`** (`frontend/src/components/schedule/ScheduledTasksPanel.tsx` — 648 lines):
   - **Route in `App.tsx`**: `<Route path="/scheduled-tasks" element={<ProtectedRoute><WorkspaceLayout><ScheduledTasksPanel /></WorkspaceLayout></ProtectedRoute>} />`
   - **Backend Route**: Connects to `/api/schedule/*` (live via `scheduled_tasks.py`).
   - **Navigation Rail Status**: Not yet exposed as a top-level item in `NAVIGATION_REGISTRY`.

3. **`CostDashboard.tsx`** (`frontend/src/pages/user/CostDashboard.tsx` — 212 lines):
   - **Route in `App.tsx`**: `<Route path="/usage" element={<ProtectedRoute><WorkspaceLayout><CostDashboard /></WorkspaceLayout></ProtectedRoute>} />`
   - **Backend Route**: Fetches `/api/billing/analytics` and listens to `Events.TOKEN_USAGE_UPDATED`.
   - **Navigation Rail Status**: Present in `NAVIGATION_REGISTRY` (`Govern` group -> `Usage` -> `/usage`). Fully accessible to end users!

4. **`MemoryPanel.tsx`** (`frontend/src/components/memory/MemoryPanel.tsx` — 487 lines):
   - **Route in `App.tsx`**: `<Route path="/memory" element={<ProtectedRoute><WorkspaceLayout><MemoryPanel /></WorkspaceLayout></ProtectedRoute>} />`
   - **Backend Route**: Connects to `/api/memory/*`.
   - **Navigation Rail Status**: Not yet exposed in `NAVIGATION_REGISTRY` for user context.

### 2.2 Still Orphaned Frontend Components (Ghost UI)
These production-grade components exist in the frontend repository but are not mounted in `App.tsx` or rendered in any parent tab:

1. **`MCPConnector.tsx`** (`frontend/src/components/plugins/MCPConnector.tsx` — 73 lines):
   - Connects external Model Context Protocol (MCP) servers with endpoint validation and token verification.
   - Status: Neither `IntegrationsManager.tsx` nor `PluginMarketplace.tsx` imports or displays `MCPConnector`.
2. **`SecretsPage.tsx`** (`frontend/src/components/dashboard/SecretsPage.tsx` — 179 lines):
   - Full Devin-style API key manager: generates, lists, revokes, and deletes API keys via `/api/api-keys/*`.
   - Status: Completely unrendered in both user settings and `AdminShell`.
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

## Section 4: Broken API Contracts & Path Discrepancies

The following client-server contract mismatches remain in active code and must be reconciled:

### 4.1 Agent Swarm Health Heartbeat (`MockSwarmProvider.tsx` & `useSwarmGraph.ts`)
- **Frontend Calls**:
  - `MockSwarmProvider.tsx` line 29: `apiClient.post('/api/v1/health/agents', { agent_ids: ... })`
  - `useSwarmGraph.ts` line 56: `fetch('${getApiBaseUrl()}/api/v1/health/agents', { method: 'GET' })`
- **Backend Reality**:
  - `backend/api/routes/health.py` is mounted at prefix `/api/v1` (and `/api/v1/health`), exposing `/health`, `/deep`, `/ready`, `/live`.
  - **The route `/health/agents` does NOT exist** in `health.py` or anywhere in `backend/`!
- **Consequence**: `MockSwarmProvider` constantly catches HTTP 404 errors and is forced to display fallback/disconnected state.
- **Fix**: Add `@router.get("/health/agents")` and `@router.post("/health/agents")` in `backend/api/routes/health.py` querying `core.agent_supervisor.agent_supervisor.get_health()`.

### 4.2 Tenant Rate Limits URL Mismatch (`RateLimitManager.tsx`)
- **Frontend Calls**:
  - `frontend/src/components/admin/security/RateLimitManager.tsx` lines 59, 102, 130:
    `fetch('${API_BASE}/admin/tenant-limits', ...)`
- **Backend Reality**:
  - `backend/api/routes/tenant_admin.py` defines:
    `router = APIRouter(prefix="/admin-api/tenant-limits")`
  - `backend/api/routers.py` mounts it with `prefix=""`, so the actual endpoints are at `/admin-api/tenant-limits`.
- **Consequence**: All requests from `RateLimitManager.tsx` to `/admin/tenant-limits` fail with HTTP 404.
- **Fix**: Update `RateLimitManager.tsx` to call `${API_BASE}/admin-api/tenant-limits` (or add an alias route in `tenant_admin.py`).

### 4.3 Agent Status Prefix Discrepancy (`agentService.ts` vs `agents.py`)
- **Frontend Calls**:
  - `frontend/src/services/agentService.ts`:
    - `apiClient.get('/api/v1/agents/')`
    - `apiClient.get('/api/v1/agents/${agentId}/status')`
- **Backend Reality**:
  - In `backend/api/routes/agent.py`: `router = APIRouter(prefix="/api/v1/agents")` (only exposes `POST /execute`).
  - In `backend/api/routes/agents.py`: `router = APIRouter(prefix="/api/agents")` (exposes `GET /` and `GET /{agent_id}/status`).
- **Consequence**: Calling `/api/v1/agents/` or `/api/v1/agents/{id}/status` hits `agent.py`'s router (which lacks those GET routes), yielding 404 or 405 errors.
- **Fix**: Either normalize `agents.py` prefix to `/api/v1/agents` or update `agentService.ts` to call `/api/agents`.

### 4.4 Budget Check Route Mismatch (`useBudgetCheck.ts`)
- **Frontend Calls**:
  - `frontend/src/hooks/useBudgetCheck.ts`: `apiClient.get('/api/admin/metrics/cost?estimated=${estimatedCost}')`
- **Backend Reality**:
  - Backend routes in `admin_v1.py` or `billing_api.py` do not provide `/api/admin/metrics/cost`. Cost endpoints reside under `/admin-api/costs` or `/api/billing/analytics`.
- **Consequence**: `useBudgetCheck` fails silently with 404 on pre-flight cost verification.

---

## Section 5: Backend-Heavy Engines with Zero Frontend UI (Orphan Capabilities)

These services are production-grade on the backend, but lack user-facing interfaces:

| Capability | Backend Implementation | Endpoints | Frontend State | Recommended UI Integration |
|---|---|---|---|---|
| **Social Growth Engine** | `backend/api/routes/social_growth.py`<br>`backend/core/social_growth/` | `GET/POST /api/v1/social/drafts`<br>`POST /api/v1/social/drafts/{id}/approve`<br>`POST /api/v1/social/pause`, `/resume` | `socialGrowthService.ts` is fully implemented, but **0 UI components** consume it | Add `SocialGrowthTab.tsx` in `WorkspaceModulePage` or as a sub-panel in `AIStudio` |
| **Diagram to Infrastructure** | `backend/tools/code/diagram_to_architecture.py` | `POST /diagram/to-terraform`<br>`POST /diagram/to-kubernetes`<br>`POST /diagram/to-schema` | No UI dropzone, no cloud selector (AWS/GCP), no code preview | Mount backend router in `routers.py` + Add "Diagram-to-IaC" modal in `IdeWorkspace` |
| **Image / Figma to Code** | `backend/tools/code/image_to_code.py` | `POST /tools/image-to-code`<br>`POST /tools/image-to-component`<br>`POST /tools/image-to-palette` | Backend is mounted; no toolbar trigger in Monaco editor | Add "Vision / Design Ingest" button in `AgentWorkspace.tsx` and `IdeWorkspace.tsx` |
| **Video to Code Pipeline** | `backend/services/video_to_code_pipeline.py` | `POST /video-to-code/process` | Backend router unmounted; zero UI | Mount router in `routers.py` + Add Video dropzone in `AIStudio` preview tab |
| **Voice Coder** | `backend/tools/code/voice_coder.py` | `POST /voice/process-audio`<br>`WS /voice/ws` | Backend router unmounted; audio recorder services exist in frontend but lack mic button | Mount router in `routers.py` + Add microphone button in `AgentWorkspace` chat prompt |
| **Automated Style Learner** | `backend/tools/learning/style_learner.py` | `POST /api/style/learn`<br>`GET /api/style/prompt` | Backend is mounted; no UI button | Add "Learn Coding Style" button in `IdeWorkspace.tsx` |
| **Vulnerability Prophet** | `backend/agents/vulnerability_prophet.py` | `POST /security/vulnerabilities/scan`<br>`POST /security/vulnerabilities/scan-project` | Backend router unmounted; `SecurityDashboard.tsx` lacks on-demand code scanner | Mount router in `routers.py` + Add "Run Security Audit" action in `SecurityDashboard.tsx` |
| **Multilingual TTS Engine** | `backend/tools/media/multilingual_tts.py` | `GET /api/tts/languages`<br>`DELETE /api/tts/cache`<br>`GET /api/tts/audio/{filename}` | Backend is mounted; frontend only uses basic `/api/voice/stream_audio` | Add 29-language selector dropdown in `AIStudio` settings drawer |
| **Universal BYOC Orchestrator** | `backend/api/routes/byoc_api.py` | `POST /api/byoc/credentials`<br>`POST /api/byoc/deploy`<br>`GET /api/byoc/jobs/{job_id}` | Backend is mounted (with `ENCRYPTION_KEY`); no UI in settings | Add "Enterprise BYOC Deployment" panel in `AdminShell` / `ConfigEditor` |
| **Crawler Policy Admin** | `backend/api/routes/crawler_admin.py` | `GET/POST /api/v1/admin/crawler/policies` | Backend is mounted; Admin console has no crawler tab | Add "Crawler Rules" sub-tab in `AdminSubTabContent.tsx` |

---

## Section 6: Comprehensive Feature Parity Matrix

| Feature Area | Backend Router / Service | Mount Status | Frontend Component / Service | Frontend Routing Status | Parity Classification |
|---|---|---|---|---|---|
| **Deep Research** | `api.routes.deep_research` | 🟢 Mounted (`workspace_feature_routes`) | `DeepResearchPanel.tsx` | 🟢 Mounted at `/research` in `App.tsx` | **Operational (Needs Nav Rail Link)** |
| **Scheduled Tasks** | `api.routes.scheduled_tasks` | 🟢 Mounted (`workspace_feature_routes`) | `ScheduledTasksPanel.tsx` | 🟢 Mounted at `/scheduled-tasks` in `App.tsx` | **Operational (Needs Nav Rail Link)** |
| **Cost & Token Dashboard** | `api.routes.billing_api` | 🟢 Mounted (`ALL_ROUTERS`) | `CostDashboard.tsx` | 🟢 Mounted at `/usage` in `App.tsx` | **Full Parity (Verified)** |
| **Neural Memory Browser** | `api.routes.memory` | 🟢 Mounted (`ALL_ROUTERS`) | `MemoryPanel.tsx` | 🟢 Mounted at `/memory` in `App.tsx` | **Operational (Needs Nav Rail Link)** |
| **Social Growth** | `api.routes.social_growth` | 🟢 Mounted (`ALL_ROUTERS`) | `socialGrowthService.ts` | 🔴 No UI component exists | **Backend Orphan** |
| **MCP Connector** | `infrastructure/mcp-control-plane/` | 🟢 Mounted | `MCPConnector.tsx` | 🔴 Unrendered in any view | **Ghost UI** |
| **API Keys / Secrets** | `api.routes.api_keys` | 🟢 Mounted (`ALL_ROUTERS`) | `SecretsPage.tsx` | 🔴 Unrendered in any view | **Ghost UI** |
| **Agent Workspace** | `api.routes.agent` (`/api/v1/agents`) | 🟢 Mounted (`ALL_ROUTERS`) | `AgentWorkspace.tsx` | 🟢 Mounted at `/agents` & `/workspace/agent` | **Full Parity** |
| **Files Workspace** | `api.routes.files` (`/api/files`) | 🟢 Mounted (`ALL_ROUTERS`) | `WorkspaceModulePage` (`module="files"`) | 🟢 Mounted at `/files` in `App.tsx` | **Full Parity** |
| **Swarm Agent Health** | `api.routes.health` | 🟢 Mounted (`ALL_ROUTERS`) | `MockSwarmProvider.tsx` | 🔴 404 (Missing `/health/agents` in backend) | **Contract Mismatch** |
| **Tenant Limits** | `api.routes.tenant_admin` | 🟢 Mounted (`ALL_ROUTERS`) | `RateLimitManager.tsx` | 🔴 404 (Calls `/admin/tenant-limits` instead of `/admin-api/tenant-limits`) | **Path Mismatch** |
| **Diagram to Infra** | `tools.code.diagram_to_architecture` | 🔴 Unmounted | None | 🔴 No UI | **Double Orphan** |
| **Voice Coder** | `tools.code.voice_coder` | 🔴 Unmounted | Audio services only | 🔴 No Mic UI in Workspace | **Double Orphan** |
| **Security Prophet** | `agents.vulnerability_prophet` | 🔴 Unmounted | None | 🔴 No Code Scan UI in Admin | **Double Orphan** |
| **Video to Code** | `services.video_to_code_pipeline` | 🔴 Unmounted | None | 🔴 No Video Ingest UI | **Double Orphan** |
| **Style Learner** | `tools.learning.style_learner` | 🟢 Mounted (`ALL_ROUTERS`) | None | 🔴 No UI | **Backend Orphan** |
| **Multilingual TTS** | `tools.media.multilingual_tts` | 🟢 Mounted (`ALL_ROUTERS`) | Partial (basic TTS only) | 🟡 29 Languages & Cache Unused | **Frontend Lacking** |
| **BYOC Cloud Manager** | `api.routes.byoc_api` | 🟢 Mounted (with key) | None | 🔴 No BYOC Form in UI | **Backend Orphan** |
| **Web Crawler Admin** | `api.routes.crawler_admin` | 🟢 Mounted (`ALL_ROUTERS`) | None | 🔴 No Crawler Admin subtab | **Backend Orphan** |

---

## Section 7: Actionable Remediation Roadmap

### Priority 1: Backend Router Registrations & Contract Alignment
1. **Mount Unmounted Routers in `backend/api/routers.py`**:
   - Add `tools.code.diagram_to_architecture`, `tools.code.voice_coder`, `tools.code.ai_pair_programmer`, `tools.self_planner`, `services.video_to_code_pipeline`, and `agents.vulnerability_prophet` to `ALL_ROUTERS`.
2. **Implement `/api/v1/health/agents` in `backend/api/routes/health.py`**:
   - Add `@router.get("/health/agents")` and `@router.post("/health/agents")` endpoints calling `agent_supervisor.get_health()` to eliminate the continuous 404 in `MockSwarmProvider` and `useSwarmGraph`.
3. **Harmonize Tenant Rate Limits Path**:
   - Update `RateLimitManager.tsx` to target `/admin-api/tenant-limits` to match `tenant_admin.py` mounting.
4. **Align Agent Status Endpoints**:
   - Expose alias routes `/api/v1/agents/` and `/api/v1/agents/{agent_id}/status` in `agent.py` or route `agents.py` under `/api/v1/agents`.

### Priority 2: Expose Routed Powerhouses in User Navigation Rail
In `frontend/src/config/navigationRegistry.ts`:
1. **Expose Research**: Add an item for Deep Research (`path: '/research'`, icon: `Search`, group: `build` or `extend`, status: `'implemented'`).
2. **Expose Scheduled Tasks**: Add an item for Scheduled Tasks (`path: '/scheduled-tasks'`, icon: `Clock`, group: `build`, status: `'implemented'`).
3. **Expose Memory**: Add an item for Neural Memory (`path: '/memory'`, icon: `BrainCircuit`, group: `govern` or `account`, status: `'implemented'`).

### Priority 3: Wire Remaining Ghost Components
1. **Embed `MCPConnector.tsx`**: Add an "MCP Control Plane" card/tab within `frontend/src/pages/user/IntegrationsManager.tsx`.
2. **Mount `SecretsPage.tsx`**: Add an "API Keys & Secrets" tab in `WorkspaceModulePage` (under settings) or as a sub-tab in user profile.
3. **Connect `ChatInterface.tsx` in `AIStudio.tsx`**: Replace `InteractiveChatTab.tsx` in `AIStudio` or embed the Tier-S Thinking Panel, Artifacts Panel, and Slash Commands into `InteractiveChatTab`.

### Priority 4: Implement Lightweight UI Adapters for Orphan Backend Engines
1. **Social Growth Management**: Build a clean `SocialGrowthView.tsx` utilizing `socialGrowthService.ts` for draft creation, review, and auto-publishing.
2. **Visual Multimodal Ingest (Image & Diagram)**: Add an "Import Diagram / Mockup" modal in `AgentWorkspace.tsx` and `IdeWorkspace.tsx` connecting to `/diagram` and `/tools/image-to-code`.
3. **Voice Coding Bar**: Add a microphone button next to the prompt bar in `AgentWorkspace.tsx` streaming audio to `/voice/process-audio`.
