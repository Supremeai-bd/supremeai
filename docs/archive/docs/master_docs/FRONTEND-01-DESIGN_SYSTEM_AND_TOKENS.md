


<!-- ============================================================ -->
<!-- Merged Source: docs/06-frontend.md -->
<!-- ============================================================ -->

# 06 — Frontend

`frontend/` is the `supremeai-studio-client` v2.0.0 package — "SupremeAI Studio Client - Multi-cloud AI orchestration platform web interface". React 19 + TypeScript 5.9 + Vite 7 + Tailwind CSS 4, one build serving both the user portal and the admin console.

## Stack (verified from `package.json` + lockfile)

| Concern | Library |
|---------|---------|
| UI runtime | React `19.2.8`, react-router-dom `^6.30.6` (BrowserRouter) |
| State | **zustand `^5.0.15`** (no Redux) |
| Server data | @tanstack/react-query `^5.102.3`, @tanstack/react-virtual |
| Local-first | **dexie `^4.0.10`** (IndexedDB) + dexie-react-hooks |
| Editor | @monaco-editor/react `^4.7.0` (monaco-editor 0.55.1) |
| Graph/flow | @xyflow/react `12.11.2`, recharts `^3.10.1` |
| Realtime | @microsoft/fetch-event-source (SSE), xterm 5.3, @webcontainer/api 1.6.4 |
| Styling | tailwindcss `^4.3.3` + @tailwindcss/vite, framer-motion, lucide-react, react-resizable-panels, @dnd-kit |
| Cloud | firebase `^12.18.0`, @supabase/supabase-js `^2.112.4`, @upstash/redis |
| Workspace | @supremeai/{core-infrastructure, design-tokens, shared-services, shared-types, ui-components} |

Build tooling: Vite `^7.3.6`, vitest `^3.2.7` (+coverage-v8), Playwright `^1.62.1`, ESLint 9 flat config, knip (dead code), Storybook (partial — 3 stories, no `.storybook/` dir committed).

## Application Structure

```
frontend/src/
├── main.tsx              # Boot: providers → router → GlobalErrorBoundary
├── App.tsx               # <Routes>: landing redirect, auth, workspace, admin, Tier-S, 404
├── auth/                 # identity.ts (JWT role resolution), routePolicies.ts
├── commandcenter/        # AETHEL Command Center (admin ops cockpit)
│   ├── shell/            # CommandCenterApp, LeftRail, CommandBar, BottomDeck
│   ├── modules/          # deck/observe/operate/system/money/secure groups
│   ├── kit/              # KpiTile, DataTable, Sparkline, GaugeRing, ToastStack
│   ├── realtime/         # WebSocketManager, sseBridges, channelRegistry
│   └── state/            # useCommandCenterStore (UI-transient only)
├── components/           # admin/ chat/ editor/ dashboard/ swarm/ graph/ ui/ shell/ core/
├── pages/                # admin/AdminShell, auth/*, user/* (AgentWorkspace, IdeWorkspace,
│                         #   AIStudio, ArchitectTower, SkillCatalog, EvolutionForge…)
├── store/                # 15 zustand stores + slices/ (see below)
├── services/             # apiClient, chatService, adminService, realtime/, audio/
├── hooks/                # useChat, useServerStream, useAdminApi, useSwarmGraph…
├── i18n/                 # custom i18n: config.ts (en|bn|es|zh), translations.ts
├── lib/                  # supabase.client, llm.router, cache.manager, secureSse, etag
├── providers/            # ThemeSyncProvider, MockSwarmProvider (swarm health polling)
├── routes/               # tierSRoutes.tsx (S1–S12)
├── workers/              # logParser.worker.ts (web worker)
└── types/                # chat.ts (single source of truth), schema, swarm, customer
```

## Routing & Guards

Boot providers: ToastProvider → ThemeProvider → `SharedProviders` (react-query + Monaco defaults from `@supremeai/ui-components`) → BrowserRouter → GlobalErrorBoundary → App.

| Route | Access | Notes |
|-------|--------|-------|
| `/` | any | `LandingRedirect`: Guest→`/login`, User→`/workspace`, Admin→`/admin` (via `resolveLandingPath()`) |
| `/login`, `/register` | guest | `GuestRoute` |
| `/workspace/agent`, `/workspace/ide` | user | Monaco-based workspaces (lazy) |
| `/workspace`, `/workspace/live` | user | Dashboard / `LivingDashboardShell` + AIStudio |
| `/integrations`, `/architect-tower`, `/swarm`, `/evolution-forge`, `/skills-catalog` | user | Lazy-loaded feature pages |
| `/billing` | user | `PermissionGuard 'billing.read'` |
| `/admin/*` | admin | `ProtectedRoute` → `RoleGuard admin` → `AdminShell` with **Firebase login → OTP/TOTP step-up → RBAC** |
| `/share/:shareId` | public | Tier-S S1 shared conversations |
| `/prompt-library` | user | Tier-S prompt templates |
| `*` | any | ErrorPage 404 |

Heavy pages are `React.lazy` loaded (AdminShell, AgentWorkspace, AIStudio, IdeWorkspace, SwarmMap, EvolutionForge, …).

## State Management (zustand)

| Store | Hook | Role |
|-------|------|------|
| `authStore.ts` | `useAuthStore` | **Canonical identity/session authority** — role only from backend `/api/v1/auth/*`; token key `supremeai_auth_token` |
| `adminStore.ts` | `useAdminStore` | Admin step-up: OTP state, TOTP setup/verify |
| `chatStore.ts` | `useChatStore` | Conversations (`GET /api/memory/conversations`), messages (cap 1000), streaming flags |
| `unifiedStore.ts` | `useUnifiedStore` | R13 "single source of truth" store (subscribeWithSelector; slices for auth/chat/workspace/theme/admin) — gated by `VITE_UNIFIED_STORE` or `localStorage.UNIFIED_STORE` |
| `tierSStore.ts` | `useTierSStore` | S1 share, S2 reasoning, S3 artifacts, S5 slash menu, S6 search, S12 deep research |
| `useWorkspaceStore`, `useIdeStore`, `useWorkspaceSettingsStore`, `themeStore`, `customerStore`, `dashboardStore`, `sessionCockpitStore`, `useStore` (legacy), `useSupremeStore` | | Feature-scoped stores |
| `slices/` | | `apiSlice`, `workspaceSlice`, `userSlice`, `uiSlice` + `migration_map.ts` (legacy→unified mapping); `localFirstDb.ts` — Dexie tables `chat_messages`, `conversations`, `user_preferences`, `sync_queue` with Supabase background sync |

## Services Layer

- **`services/apiClient.ts`** — central client: `apiClient.get/post/delete`, `ApiError`, p-queue request queue (concurrency `VITE_API_CONCURRENCY` default 3), `getAuthHeaders()` (Bearer preferring admin JWT `supreme_admin_jwt`, CSRF `X-CSRF-Token`, device-fingerprint header), auth-changed event bus, timeout from `VITE_API_TIMEOUT_MS` (60 s).
- **`utils/api.ts`** — URL resolution `USER_BACKEND_URL = VITE_USER_BACKEND || VITE_API_BASE || VITE_API_URL || VITE_BACKEND_URL`; runtime admin routing (`getBackendUrl` inspects path + `window.location.pathname`); relative-base mode for same-origin hosting (`VITE_USE_RELATIVE_PATH=true`); `FrontendCircuitBreaker`; `fetchWithRetry` (retryable 408/429/5xx, exponential backoff + jitter); `checkBackendHealth()` → `/api/v1/health/live`. Production builds **fail fast** with no backend URL.
- **`services/chatService.ts`** — `sendMessageStream()` POST `/api/chat/stream`, SSE `data:` chunk parsing + `[DONE]` sentinel. (`hooks/useChat.ts` implements a parallel streaming path — both hit the same endpoint.)
- **`services/authService.ts`** — admin auth: `firebaseLogin` (`/api/admin/firebase-login`), TOTP setup/verify (7-digit OTP).
- **`services/adminService.ts`** — `/admin-api/health-map`, `/admin-api/costs`, `/admin-api/users`, `/admin-api/deploy`.
- **Realtime** — `services/realtime/WebSocketManager.ts` and `commandcenter/realtime/WebSocketManager.ts` both subclass `BaseWebSocketManager` (`@supremeai/shared-services`): connect `${WS base}/ws/dashboard?token=<admin JWT>`, 30 s heartbeat, max 5 reconnects, payload de-duping (2 s deltas / 30 s full snapshots), React Query invalidation.
- **SSE** — `lib/secureSse.ts` (fetch-event-source with Bearer; manual reconnect control) consumed by `hooks/useServerStream.ts` (`/api/task/stream`).
- Others: `agentService`, `skillsService` (`/api/skills/catalog`), `aiActions` (IDE actions via shared-services), `storageApi` (R2 pre-signed upload via `/api/v1/media/generate-upload-url`), `heartbeat` (anti-sleep ping every 10 min, prod only), `sandbox` (WebContainers), `ciReportService`, `costOptimizer.service`.

## Key Features

- **Chat interface** (`components/chat/ChatInterface.tsx`): streams via SSE; integrates Tier-S panels — Share (S1), Thinking/Reasoning (S2), Artifacts (S3), image upload (S4), slash commands (S5), ⌘K search (S6), export (S7), branch conversations (S11); voice message queue via event bus.
- **Monaco IDE** (`pages/user/IdeWorkspace.tsx`, `AgentWorkspace.tsx`): `components/editor/` — FileExplorer, EditorTabs, AiAssistantBar, AiOutputPanel, `monacoAi.ts` glue.
- **Admin console** (`pages/admin/AdminShell.tsx` → `components/admin/AdminConsole.tsx`): ~30 panels — ModelRouter, SecurityDashboard, RulesEnginePanel, ThreatDetection, RateLimitManager, CICDVisualizer, CloudOrchestrator, ServiceHealthMonitor, UserManager, ConsentMatrixModal, OneClickPatch, ScreencastViewer, BackupRestore, CostAuditor…
- **AETHEL Command Center** (`src/commandcenter/`): module groups DECK/OPERATE/BUILD/OBSERVE/SECURE/MONEY/SYSTEM; data via React Query (`useMetrics` 15 s, `useHealthMap` 45 s); WebSocket status bar; Bengali labels. Note: `tsconfig.app.json` **excludes `src/commandcenter`** from the `typecheck` script.
- **Swarm visualization** (`components/SwarmMap.tsx`): ReactFlow with custom `AgentNode`/`SkillNode`, animated edges, driven by `useSwarmGraph`; health polling `VITE_SWARM_HEALTH_POLL_MS` (default 5 s); hold-to-kill safety button.
- **Voice**: `AudioRecorderService` (MediaRecorder → WS chunks every 500 ms), `AudioPlaybackService`, waveform visualizer.
- **i18n**: fully custom (`src/i18n/`) — locales `en|bn|es|zh` in `translations.ts`, `useTranslation` hook with `{param}` interpolation, locale persisted to `localStorage['supreme_lang']`. (react-i18next is declared in package.json but **not imported anywhere**.)

## Testing

- **Vitest**: jsdom, globals, `src/test/setup.ts`; **72 test files** colocated (`*.test.ts(x)`); coverage v8 with thresholds (lines/functions/branches/statements 10%) — CI enforces `MIN_FRONTEND_COVERAGE=9` and runs `vitest run --coverage`.
- **Type/lint gates**: `tsc --noEmit --strict` (excluding commandcenter), ESLint flat config, knip dead-code check — all in CI `frontend-tests` job.
- **E2E**: Playwright specs in `frontend/e2e/` (`commandcenter.spec.ts`, `multiworkspace.spec.ts`). Caveat: there is no `playwright.config.*` inside `frontend/`; the root config targets `./tests/e2e` (which does not exist) on port 3000, while the specs default to port 4173 — e2e currently runs ad-hoc rather than wired into npm scripts.

## Notable Implementation Details

- **localStorage keys in play**: `supremeai_auth_token`, `supreme_admin_jwt`, `supreme_lang`, `UNIFIED_STORE`, Supabase key `supremai-auth-token` (sic).
- **PWA**: `public/sw.js` + `manifest.json`, registered in production only.
- **CSP**: strict Content-Security-Policy meta tag in `index.html`.
- **Chunking**: manual chunks `vendor-ui` / `vendor-flow` / `vendor-query`, chunk warning limit 600 KB, hidden sourcemaps, console/debugger dropped in prod.
- **Electron option**: `ELECTRON=true` build switches `base` to `./`; desktop scripts (`desktop:dev`/`desktop:build`) run the frontend package with electron.
- **Docker**: `frontend/Dockerfile` — node:20-alpine + pnpm builder → nginx:alpine with SPA fallback and `/api/`, `/admin-api/`, `/ws` proxy to `http://backend:8080`.



<!-- ============================================================ -->
<!-- Merged Source: docs/frontend-migration/PHASE0_INVENTORY.md -->
<!-- ============================================================ -->

# SupremeAI — Phase 0 Frontend Inventory (Single Frontend Role-Based Migration)

**Roadmap:** `SUPREMEAI_SINGLE_FRONTEND_ROLE_BASED_ROADMAP.md` v1.0.0
**Baseline commit:** `4d0903d` (main)
**Purpose:** Ownership map of the current frontend before any architectural change. This document is the exit artifact for Roadmap Phase 0.

---

## 1. Entry points & build infrastructure

| Piece | Location | Notes |
|---|---|---|
| HTML entry | `frontend/index.html` | Single HTML entry, inline CSP, duplicate `/sw.js` registration (inline + main.tsx) |
| JS entry | `frontend/src/main.tsx` | fetch interceptor → heartbeat (PROD) → Firebase init → ToastProvider → ThemeProvider → SharedProviders → BrowserRouter → GlobalErrorBoundary → App |
| Route tree | `frontend/src/App.tsx` | **`VITE_PORTAL_TYPE` ternary at L66/L146 splits the entire route graph** |
| Vite config | `frontend/vite.config.ts` | `IS_ADMIN_PORTAL` (L13) drives fail-fast guards, dev proxy, `build-info.json`, and `outDir` (`dist-admin` vs `dist-user`, L99). `--mode admin` is dead — nothing reads `mode` |
| Build scripts | `frontend/package.json` | `build` = `build:admin && build:user` (two production builds); `build:user` extra-copies `dist-user` → `dist` |
| Render build hook | `scripts/render_build_frontend.sh` | Portal-conditional env validation + `build:admin` XOR `build:user` |
| Firebase hosting | `firebase.template.json` + `.firebaserc` | Two hosting targets: `user` (site `supremeai-a`) and `admin` (site `supremeai-admin`), **both shipping the SAME unified SPA build (`frontend/dist`)** — admin/user separation is runtime route-based, portal-split builds (dist-user/dist-admin) are obsolete and blocked by `scripts/ci/check_single_frontend.py` Gate A (FB-06). Generated at deploy time by `scripts/deploy/generate_firebase_config.py` |
| CI build | `.github/workflows/ci.yml` (build job ~L547) | Runs ONE `vite build` → `frontend/dist`, verifies the build contract, uploads artifact `frontend-dist`; `deploy-frontend` deploys `--only hosting` (same artifact → both hosting targets) |
| CI drift | `.github/workflows/maintenance.yml` (~L444) | Downloads artifact `frontend-dist` which **does not exist** (always falls back to a fresh build) |
| Turbo | `turbo.json` | `VITE_PORTAL_TYPE` in `globalEnv`; `deploy:studio` task references nonexistent `hosting:studio` target |
| Root scripts | `package.json` (root) | `deploy:studio` / `deploy:admin` reference nonexistent hosting targets (`studio` missing entirely) |
| Docker | none for frontend | Backend + mcp-control-plane only |
| Static stubs | `frontend/public/admin.html`, `customer.html` | JS redirect shims to portal sites |

### `VITE_PORTAL_TYPE` behavioral surface (runtime)

| File : Line | Controls |
|---|---|
| `frontend/src/App.tsx:66,146` | The whole route graph (admin-only build vs user build) |
| `frontend/src/utils/api.ts:170-182` | Production fail-fast + `BACKEND_URL` pin (admin vs user backend) |
| `frontend/src/config/commandRegistry.ts:238-240` | `getCurrentPortal()` → ⌘K command filtering |
| `frontend/vite.config.ts:13,27,50-63,99` | Guards, proxy target, outDir |
| Tests stubbing it | `frontend/src/utils/api.test.ts`, `frontend/src/config/commandRegistry.test.ts`, `backend/tests/e2e/{admin,user}-login.spec.ts` |

Other declared-in docs: `backend/core/config_classification.py:135,144`, `specs/001-dynamic-production-configuration/*`, `docs/architecture/*`.

### Environment variables (runtime-relevant)

- Backends: `VITE_ADMIN_BACKEND`, `VITE_USER_BACKEND` / `VITE_API_BASE` / `VITE_API_URL`, `VITE_WS_BASE_URL`, `VITE_USE_RELATIVE_PATH`
- Identity: `VITE_FIREBASE_*` (admin identity provider), `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY`
- Tuning: `VITE_API_CONCURRENCY`, `VITE_API_TIMEOUT_MS`, `VITE_MAX_RETRIES`, `VITE_CIRCUIT_*`
- Known latent bugs (out of scope, documented): `lib/cache.manager.ts` reads non-prefixed `UPSTASH_REDIS_REST_URL/TOKEN` (always undefined); `lib/supabase.client.ts` references `SUPABASE_SERVICE_ROLE_KEY` client-side (undefined by envPrefix, but a standing hazard) and uses typo'd storage key `supremai-auth-token`

---

## 2. Authentication ownership map

### 2.1 Canonical user session — `store/authStore.ts`

- Status machine: `uninitialized → loggedOut | loggedIn` (no role field today)
- Persistence: manual localStorage — `supremeai_auth_token`, `supremeai_auth_user`
- Endpoints: `POST /api/v1/auth/login`, `POST /api/v1/auth/register`, `GET /api/v1/auth/me`
- **Optimistic restore** on reload (deliberate Render cold-start fix — must preserve: only confirmed 401/403 invalidates; transient errors keep session)
- **Backend returns `role`** on login/register/`/auth/me` (`backend/api/routes/auth.py` — `role: primary_role`, `"admin" | "user"`) — today it is misused as a display-name fallback (L187) and never stored
- `logout()` exists but has **no UI caller** (unreachable logout)

### 2.2 Admin elevation — `store/adminStore.ts` (MUST PRESERVE)

- Flow: Firebase `signInWithEmailAndPassword` → `POST /api/admin/firebase-login` → `otp_required` | `totp_setup_required` → `POST /api/admin/firebase-totp-setup` → `POST /api/admin/firebase-totp-verify` → short-lived admin JWT
- Admin JWT stored in `supreme_admin_jwt` (+ legacy duplicate `adminToken` write); role decoded from server-signed JWT claim (in-memory only)
- `adminAuthenticated` is in-memory → every refresh re-demands step-up (secure-by-design; keep)
- **Bug:** `handleAdminLogout` clears `supremeai_auth_token` — destroys the user session too
- RBAC gate: `AdminShell.tsx:111` (`adminRole !== 'admin'` → Access Denied)

### 2.3 Token handling — `services/apiClient.ts`

- `getAuthHeaders()`: admin JWT preferred as Bearer, else user token; CSRF + device fingerprint headers
- `401` → `clearAuthToken()` except `NON_CRITICAL_401_PATHS` allowlist (auto-logout-after-TOTP regression fix — preserve)
- **Desync bug:** `clearAuthToken()` does not reset `authStore.status` → guarded pages stay visible until re-render
- `AUTH_CHANGED_EVENT` ('supremeai:auth-changed') is the cross-cutting reactivity channel (SSE hooks depend on it) — keep
- `utils/apiInterceptor.ts` monkey-patches `window.fetch` → auto `handleAdminLogout()` on critical 401/403 (second logout trigger)

### 2.4 Duplicate/parallel authorities (Phase 9 cleanup candidates)

| Authority | Location | Risk |
|---|---|---|
| Firebase client flow → `customerStore` | `hooks/useAuth.ts` | Hardcoded client-side roles (`'operator'`/`'developer'`) persisted to localStorage |
| Supabase session | `lib/supabase.client.ts` | `persistSession` + `autoRefreshToken` under typo'd key; service-role client stub |
| Dead key | `store/useWorkspaceStore.ts` | Removes `supreme_auth_token` which nothing writes |

### 2.5 Role resolution today (everywhere)

1. `adminStore` — decoded `role` claim from server-signed admin JWT (legitimate)
2. `AdminShell.tsx:111-127` — RBAC gate on that claim
3. `core/Header.tsx:29` — `pathname.startsWith('/admin')` (URL-based, display only)
4. `components/Header.tsx:3` — hostname-based (orphaned)
5. `useAuth.ts:28,112` — hardcoded roles (fake identity data)
6. `authStore.ts:187` — backend role misused as name fallback

---

## 3. UI infrastructure ownership map

### 3.1 The one true shared foundation

`components/layout/DashboardLayout.tsx` — slot API (`header` / `sidebar` / `children` / `isSidebarCollapsed`), spring width animation, semantic tokens. **Both shells already sit on it** (WorkspaceLayout L138, AdminAuthenticated L114).

### 3.2 Live shells

| Shell | Composition |
|---|---|
| User (`WorkspaceLayout`) | DndContext → HITLModal → DashboardLayout(UserSidebar) → dock overlay. **No header.** |
| Admin (`AdminShell` → `AdminConsole` → `AdminAuthenticated`) | DashboardLayout(AdminTopNav, 14 state-driven subtab buttons) → SubTabContent (30 modules via MODULE_MAP, each in `ModuleErrorBoundary`). Login/OTP/TOTP gate + RBAC gate inside. |

### 3.3 Duplicates & orphans (Phase 9 removal candidates)

| Type | Live | Orphaned/duplicate |
|---|---|---|
| Layouts | `layout/DashboardLayout` | `dashboard/DashboardLayout` (own theme engine, zero importers) |
| Headers | `admin/shared/AdminTopNav` | `core/Header` (richest: search trigger + role pills + notifications + avatar — only consumer is the orphaned layout), `dashboard/Header`, root `components/Header`, AETHEL `CommandBar` header |
| Sidebars | `UserSidebar` (in WorkspaceLayout), admin inline sidebar | `core/Sidebar`, `dashboard/Sidebar`, `SidebarSettings`, AETHEL `LeftRail`, `layout/NavRail` (used by Billing/Profile pages) |
| Command palettes | `layout/CommandBar` (global, App L256) | `commandcenter/kit/CommandPalette`, AETHEL palette |
| Theme | `contexts/ThemeProvider` (mounted) | `providers/ThemeSyncProvider` (also mounted — conflicting `<html>` class writes), `store/themeStore` (test-only), local `useState` themes in `AdminShell` + `dashboard/DashboardLayout` |
| Error boundaries | `GlobalErrorBoundary` (main.tsx), `admin/DashboardErrorBoundary` (App root + AdminConsole), `ModuleErrorBoundary` (per admin module) | `components/ErrorBoundary`, `core/ErrorBoundary`, `components/DashboardErrorBoundary` |
| Toast | `contexts/ToastProvider` (single mounted system, `window.showGlobalToast` bridge) | `commandcenter/kit/ToastStack` (orphan) |

### 3.4 Navigation audit (live nav → route reality)

Dead targets in `WorkspaceLayout` `NAV_GROUPS` (50% of non-Workspace items land on 404):
`/projects`, `/activity`, `/marketplace`, `/runs`, `/usage`, `/settings` — classification: **Planned** (no implemented routes); must not render as available functionality.

Valid user routes: `/workspace`, `/workspace/live`, `/workspace/agent`, `/workspace/ide`, `/integrations`, `/architect-tower`, `/swarm`, `/evolution-forge`, `/skills-catalog`, `/billing`, `/profile`, tier-S `/share/:shareId` (intentionally public), `/prompt-library` (**unguarded — fix required**).

Admin navigation is state-driven (14 subtabs + `command-center`), addressed via `supremeai-admin-subtab` CustomEvent from the command registry — every target valid via `MODULE_MAP`.

### 3.5 Shared UI kit (ready, unwired)

`components/ui/`: `PageHeader`, `StatCard`, `Card`, `SpotlightCard`, `Breadcrumb`, `EmptyState`, `Badge`, `Skeleton`, `ActionCard` — built for this consolidation, currently only test consumers.

---

## 4. Role × feature matrix (target state)

| Feature | User | Admin | Shared | Backend authority |
|---|---|---|---|---|
| Workspace / AI Studio / Agents / IDE / Swarm / Evolution Forge / Skills / Integrations | ✓ | ✓ | — | `/api/v1/*` JWT |
| Billing, Profile | ✓ | ✓ | — | `/api/v1/*` JWT |
| Admin Console (all modules) | — | ✓ (+ step-up) | — | `/admin-api/*` + `/api/admin/*` admin JWT |
| Login/Register | ✓ | ✓ | ✓ | public |
| Role switching | n/a | ✓ (pills) | — | never grants privilege — navigation only |

**Invariants carried into implementation:**
1. Backend authorization is authoritative; frontend guards are UX only.
2. Admin step-up (Firebase → OTP/TOTP → admin JWT) is preserved exactly; refresh re-demands step-up.
3. Role for the canonical store comes from backend responses (`/api/v1/auth/*` + server-signed admin JWT claim) — never from localStorage role keys, URL, or UI state.
4. The `NON_CRITICAL_401_PATHS` allowlists and optimistic session restore are preserved (documented regression fixes).
5. Heavy modules stay lazy; Admin chunk must not be eagerly loaded for users.



<!-- ============================================================ -->
<!-- Merged Source: docs/frontend-migration/ROLLOUT.md -->
<!-- ============================================================ -->

# SupremeAI — Single Frontend Migration: Rollout & Validation Guide

**Companion to:** `SUPREMEAI_SINGLE_FRONTEND_ROLE_BASED_ROADMAP.md` + `PHASE0_INVENTORY.md`
**Status:** Implementation Phases 0–7 + 9 (CI gate) complete on `main`. This doc covers Phase 8 (validation) and Phase 10 (production rollout) — the steps that require a live deployment.

---

## 1. What changed (architecture summary)

| Roadmap rule | Status |
|---|---|
| One frontend application / one build | ✅ `pnpm build` → single `dist/` |
| No `VITE_PORTAL_TYPE` | ✅ removed from runtime surface; CI gate enforces |
| One route graph (user + admin) | ✅ `App.tsx` single `<Routes>` with both trees |
| One canonical identity/session | ✅ `authStore` (+ `role`, `permissions` from backend) |
| Admin step-up preserved | ✅ Firebase → `/api/admin/firebase-login` → OTP/TOTP → admin JWT, unchanged; refresh re-demands step-up |
| One shared shell | ✅ `UnifiedAppShell` = `DashboardLayout` + `GlobalHeader` + `RoleAwareNavRail` |
| Backend authoritative | ✅ every privileged API call re-authorized server-side |
| One navigation registry | ✅ `NAVIGATION_REGISTRY` drives sidebars + palette; dead links hidden (`planned`) |
| Lazy loading | ✅ AdminShell is its own lazy chunk (verified: 201 KB / 48 KB gzip, not in initial load) |
| Logout clears contextual state | ✅ unified `clearCanonicalSession()`; admin logout no longer nukes user session |

**New/changed primitives:** `components/shell/{UnifiedAppShell,GlobalHeader,RoleAwareNavRail,shellEvents}`, `config/{navigationRegistry,permissions}`, `auth/{identity,routePolicies}`, `components/core/guards/RoleGuard` (Role + Permission + AccessDenied).

**Guard hierarchy:** `GuestRoute → ProtectedRoute → RoleGuard → PermissionGuard → AdminShell step-up (OTP/TOTP) → Page` for `/admin/*`; `ProtectedRoute → RoleGuard → PermissionGuard → Page` for guarded user routes (e.g. `/billing`).

**Runtime backend selection:** `getApiBaseUrl(path)` picks the admin backend for `/admin-api/*` + `/api/admin/*` paths (or any call made under `/admin/*`) and the user backend otherwise. `VITE_ADMIN_BACKEND` is now optional — when unset, admin-context calls fall back to the user backend (one FastAPI app serves both route families).

---

## 2. Required validation matrix (Phase 8 — run after deploy)

### 2.1 Authentication matrix

| # | Scenario | Expected |
|---|---|---|
| 1 | Guest → `/` | redirect `/login` |
| 2 | Guest → `/workspace` | redirect `/login` |
| 3 | Guest → `/admin` | redirect `/login` (ProtectedRoute) |
| 4 | Guest → `/share/:id` | allowed (public by design) |
| 5 | User login → `/` | redirect `/workspace` |
| 6 | User → `/admin` | **Access Denied** screen (no admin login form shown to plain users) |
| 7 | Admin identity (backend `role=admin`) → `/` | redirect `/admin` |
| 8 | Admin → `/admin` without step-up | Admin login → OTP/TOTP flow |
| 9 | Admin after step-up → all 14 admin modules | render inside shared shell |
| 10 | Refresh on `/admin/*` after step-up | step-up re-demanded (in-memory elevation) |
| 11 | Refresh on `/workspace/agent`, `/billing`, `/profile` | session survives (optimistic restore) |
| 12 | User logout (header profile menu) | session + role cleared → `/login` |
| 13 | Admin logout | admin state cleared; user session reset (`clearCanonicalSession`) |
| 14 | 401 from a critical API | tokens cleared **and** `authStore.status=loggedOut` (desync fix) |

### 2.2 Privilege-escalation attempts (must all fail)

1. URL manipulation: user navigating to `/admin/security` directly → Access Denied.
2. `localStorage`: set `supremeai_auth_user.role='admin'` → no effect (role not read from a role key).
3. Forged role pill/UI state → navigation-only, cannot elevate.
4. Direct admin API call with user JWT → backend 401/403 (backend is the boundary).
5. Expired/stale `supreme_admin_jwt` → `getAdminJwtRole()` returns null (exp checked) → deny.

### 2.3 UX matrix

- Desktop / tablet / mobile widths on `/workspace`, `/workspace/live`, `/admin`.
- Sidebar collapse toggle (header hamburger) — persists via `supremeai-workspace-settings`.
- ⌘K palette: user context shows user nav + shared actions; `/admin/*` context shows admin module commands.
- Role pills (header) visible **only** for admin-authorized identities; switch navigates, never mutates privilege.
- Theme cycle (dark → light → sunset → matrix) from header — one owner now, no flicker fighting.
- Deep links + refresh + back/forward on all routes.

### 2.4 Bundle / performance

- `pnpm build` produces ONE `dist/` with `build-info.json` (`buildType: "unified"`).
- Admin chunk NOT in initial graph (verify via `dist/assets/AdminShell-*.js` being lazy).
- `frontend/scripts/bundle-check.sh` budgets still pass (initial ≤ 250 KB gzip).

---

## 3. Production rollout (Phase 10)

**Do not cut over everything at once.**

1. **Stage 1 — Deploy single build to the existing user Firebase site** (`supremeai-a.web.app`). Validate matrix §2.1 rows 1–5, 11–14 + §2.3.
2. **Stage 2 — Admin validation** on the same URL: full §2.1 rows 6–10 + §2.2.
3. **Stage 3 — User regression:** workspace, AI Studio, agents, IDE, swarm, evolution forge, skills, integrations, billing, profile (§2.3).
4. **Stage 4 — Legacy admin site decommission:** `supremeai-admin.web.app` now has no deploy path. Keep it alive as rollback until Stage 2 passes the observation window, then either delete the site or add a redirect to `/admin` on the main site. Remove the `admin`/`admin-hosting` targets from `.firebaserc` only after that decision.
5. **Monitor:** frontend error telemetry (`/api/telemetry/frontend-error`), 401/403 rates, route failures, chunk-load failures, admin authorization failures.

**Rollback:** every change is a clean commit sequence; revert to `4d0903d` (pre-migration) restores the dual-portal build. The legacy `dist-user`/`dist-admin` artifact flow remains intact in git history for emergency redeploy.

---

## 4. Deliberately deferred (Phase 9 — post-validation cleanup)

Per roadmap rule 20/§22 (only after production validation):

- Orphaned shell duplicates: `components/dashboard/DashboardLayout.tsx`, `core/Header.tsx`, `dashboard/{Header,Sidebar,SidebarSettings}.tsx`, `commandcenter` palette trio, unused ErrorBoundary variants, `NavRail.tsx` (now shell-wrapped pages no longer need it), `AdminTopNav.tsx` (absorbed by GlobalHeader).
- Parallel identity flows: `hooks/useAuth.ts` (hardcoded client roles → `customerStore`), Supabase client session (`supremai-auth-token` typo'd key), dead `supreme_auth_token` key in `useWorkspaceStore`.
- `backend/tests/e2e/{admin,user}-login.spec.ts` portal-build skip logic.
- `frontend/public/{admin,customer}.html` redirect stubs.
- `spec/001-dynamic-production-configuration` + docs references to `VITE_PORTAL_TYPE`.
- Duplicate SW registration (`index.html` inline + `main.tsx`).

The CI gate (`scripts/ci/check_single_frontend.py`) already blocks reintroduction of the split in the runtime surface; extend it to the above files as they are removed.



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/145_frontend_src_pages_BillingPage_tsx.md -->
<!-- ============================================================ -->

# Module 145: `frontend/src/pages/BillingPage.tsx`

- **Category:** Frontend Page / View
- **Relative Path:** `frontend/src/pages/BillingPage.tsx`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 117 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Page / View` ডোমেনের অংশ।
> // apps/studio-client/src/pages/BillingPage.tsx
> // Subscription & Token Billing Page
> // বাংলা মন্তব্য: বিলিং ও সাবস্ক্রিপশন ব্যবস্থাপনা পেজ — সম্পূর্ণ ফ্রি-টিয়ার এবং অন-ডিমান্ড টোকেন প্ল্যান।


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Page / View আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/146_frontend_src_pages_ErrorPage_tsx.md -->
<!-- ============================================================ -->

# Module 146: `frontend/src/pages/ErrorPage.tsx`

- **Category:** Frontend Page / View
- **Relative Path:** `frontend/src/pages/ErrorPage.tsx`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 56 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Page / View` ডোমেনের অংশ।
> // apps/studio-client/src/pages/ErrorPage.tsx
> // Branded Error 404 & 500 Component
> // বাংলা মন্তব্য: সুপ্রিম ব্র্যান্ডিং সম্বলিত ইউজার ফ্রেন্ডলি ৪০৪ ও ৫০০ এরর পেজ।


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Page / View আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/147_frontend_src_pages_ProfilePage_tsx.md -->
<!-- ============================================================ -->

# Module 147: `frontend/src/pages/ProfilePage.tsx`

- **Category:** Frontend Page / View
- **Relative Path:** `frontend/src/pages/ProfilePage.tsx`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 334 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Page / View` ডোমেনের অংশ।
- `ProfilePage.tsx` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Page / View আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/148_frontend_src_pages_PromptTemplatePage_tsx.md -->
<!-- ============================================================ -->

# Module 148: `frontend/src/pages/PromptTemplatePage.tsx`

- **Category:** Frontend Page / View
- **Relative Path:** `frontend/src/pages/PromptTemplatePage.tsx`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 49 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Page / View` ডোমেনের অংশ।
> // ─── Component ───────────────────────────────────────────────────────────


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Page / View আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/149_frontend_src_pages_PublicPages_tsx.md -->
<!-- ============================================================ -->

# Module 149: `frontend/src/pages/PublicPages.tsx`

- **Category:** Frontend Page / View
- **Relative Path:** `frontend/src/pages/PublicPages.tsx`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 73 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Page / View` ডোমেনের অংশ।
- `PublicPages.tsx` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Page / View আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/150_frontend_src_pages_SharedConversationPage_tsx.md -->
<!-- ============================================================ -->

# Module 150: `frontend/src/pages/SharedConversationPage.tsx`

- **Category:** Frontend Page / View
- **Relative Path:** `frontend/src/pages/SharedConversationPage.tsx`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 295 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Page / View` ডোমেনের অংশ।
> // ─── Types ───────────────────────────────────────────────────────────────


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Page / View আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/151_frontend_src_pages_WorkspaceModulePage_tsx.md -->
<!-- ============================================================ -->

# Module 151: `frontend/src/pages/WorkspaceModulePage.tsx`

- **Category:** Frontend Page / View
- **Relative Path:** `frontend/src/pages/WorkspaceModulePage.tsx`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 24 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Page / View` ডোমেনের অংশ।
- `WorkspaceModulePage.tsx` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Page / View আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/152_frontend_src_pages_admin.md -->
<!-- ============================================================ -->

# Module 152: `frontend/src/pages/admin`

- **Category:** Frontend Page / View
- **Relative Path:** `frontend/src/pages/admin`
- **Type:** Directory (প্যাকেজ/সাব-সিস্টেম)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 1 files

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Page / View` ডোমেনের অংশ।
- `admin` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Page / View আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/153_frontend_src_pages_auth.md -->
<!-- ============================================================ -->

# Module 153: `frontend/src/pages/auth`

- **Category:** Frontend Page / View
- **Relative Path:** `frontend/src/pages/auth`
- **Type:** Directory (প্যাকেজ/সাব-সিস্টেম)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 4 files

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Page / View` ডোমেনের অংশ।
- `auth` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Page / View আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/154_frontend_src_pages_user.md -->
<!-- ============================================================ -->

# Module 154: `frontend/src/pages/user`

- **Category:** Frontend Page / View
- **Relative Path:** `frontend/src/pages/user`
- **Type:** Directory (প্যাকেজ/সাব-সিস্টেম)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 18 files

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Page / View` ডোমেনের অংশ।
- `user` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Page / View আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/155_frontend_src_services_adminService_test_ts.md -->
<!-- ============================================================ -->

# Module 155: `frontend/src/services/adminService.test.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/adminService.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 56 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `adminService.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/156_frontend_src_services_adminService_ts.md -->
<!-- ============================================================ -->

# Module 156: `frontend/src/services/adminService.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/adminService.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 36 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
> // Admin operations service for SupremeAI 2.0 Command Center
> // বাংলা মন্তব্য: অ্যাডমিন কমান্ড সেন্টার, ইউজার ম্যানেজমেন্ট ও খরচ মনিটর করার সার্ভিস।


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/157_frontend_src_services_adminTokenStore_test_ts.md -->
<!-- ============================================================ -->

# Module 157: `frontend/src/services/adminTokenStore.test.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/adminTokenStore.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 45 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `adminTokenStore.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/158_frontend_src_services_adminTokenStore_ts.md -->
<!-- ============================================================ -->

# Module 158: `frontend/src/services/adminTokenStore.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/adminTokenStore.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 42 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
> // apps/studio-client/src/services/adminTokenStore.ts
> // 🚨 CRITICAL CHECK: No external imports allowed here to bypass Vite Rollup blocks
> // 🛡️ Zero-Dependency Pure Native JWT Decoder
> // UTF-8 Compliant Native Base64 Parsing


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/159_frontend_src_services_agentService_test_ts.md -->
<!-- ============================================================ -->

# Module 159: `frontend/src/services/agentService.test.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/agentService.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 49 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `agentService.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/160_frontend_src_services_agentService_ts.md -->
<!-- ============================================================ -->

# Module 160: `frontend/src/services/agentService.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/agentService.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 32 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
> // Agent Operations Service for SupremeAI 2.0
> // বাংলা মন্তব্য: এজেন্ট ডিপার্টমেন্ট, টাস্ক এক্সেকিউশন ও এজেন্টদের তথ্য আনার জন্য ব্যবহৃত সার্ভিস।
> // বাংলা মন্তব্য: agentId প্যারামিটার বর্তমানে ব্যবহৃত হচ্ছে না, তাই tsc/eslint warning এড়াতে '_' প্রিফিক্স দেওয়া হলো।


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/161_frontend_src_services_aiActions_test_ts.md -->
<!-- ============================================================ -->

# Module 161: `frontend/src/services/aiActions.test.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/aiActions.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 170 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `aiActions.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/162_frontend_src_services_aiActions_ts.md -->
<!-- ============================================================ -->

# Module 162: `frontend/src/services/aiActions.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/aiActions.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 195 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
> /**
> * AI Actions — Desktop IDE-তে VS Code extension-এর মতো quick AI actions।
> * সবগুলোই @supremeai/shared-services (platform-agnostic core) ব্যবহার করে।
> */


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/166_frontend_src_services_audio.md -->
<!-- ============================================================ -->

# Module 166: `frontend/src/services/audio`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/audio`
- **Type:** Directory (প্যাকেজ/সাব-সিস্টেম)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 2 files

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `audio` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/167_frontend_src_services_authService_test_ts.md -->
<!-- ============================================================ -->

# Module 167: `frontend/src/services/authService.test.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/authService.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 64 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `authService.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/168_frontend_src_services_authService_ts.md -->
<!-- ============================================================ -->

# Module 168: `frontend/src/services/authService.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/authService.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 26 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
> // Authentication Service for SupremeAI 2.0
> // বাংলা মন্তব্য: এটি অ্যাডমিন লগইন ও ফায়ারবেস অথেন্টিকেশন সার্ভিস প্রোভাইড করে।
> // বাংলা মন্তব্য: ফায়ারবেস অথেনটিকেশন, রোল ভেরিফিকেশন এবং টিওটিপি ফ্লো
> // বাংলা মন্তব্য: ফায়ারবেস টিওটিপি ৭ ডিজিট কনফিগারেশন সেটআপ সার্ভিস এন্ডপয়েন্ট
> // বাংলা মন্তব্য: ফায়ারবেস ওটিপি কোড ৭ ডিজিট যাচাইকরণ সার্ভিস এন্ডপয়েন্ট


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/169_frontend_src_services_browserService_test_ts.md -->
<!-- ============================================================ -->

# Module 169: `frontend/src/services/browserService.test.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/browserService.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 79 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `browserService.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/170_frontend_src_services_browserService_ts.md -->
<!-- ============================================================ -->

# Module 170: `frontend/src/services/browserService.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/browserService.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 49 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `browserService.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/171_frontend_src_services_chatService_test_ts.md -->
<!-- ============================================================ -->

# Module 171: `frontend/src/services/chatService.test.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/chatService.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 117 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `chatService.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/172_frontend_src_services_chatService_ts.md -->
<!-- ============================================================ -->

# Module 172: `frontend/src/services/chatService.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/chatService.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 149 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
> // Chat API Service for SupremeAI 2.0
> // বাংলা মонтаব্য: চ্যাট ইন্টারফেস ও স্ট্রিমিং এপিআই এর সাথে যোগাযোগের জন্য ব্যবহৃত সার্ভিস। Prompt-to-Action সাপোর্ট সহ।


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/173_frontend_src_services_ciReportService_test_ts.md -->
<!-- ============================================================ -->

# Module 173: `frontend/src/services/ciReportService.test.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/ciReportService.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 27 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `ciReportService.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/174_frontend_src_services_ciReportService_ts.md -->
<!-- ============================================================ -->

# Module 174: `frontend/src/services/ciReportService.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/ciReportService.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 28 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
> // CI/CD Report operations service for SupremeAI 2.0
> // বাংলা মন্তব্য: ডাটাবেস থেকে সিআই পাইপলাইন রান হিস্ট্রি এবং লগ ফেচ করার সার্ভিস।
> // eslint-disable-next-line @typescript-eslint/no-explicit-any
> // বাংলা মন্তব্য: ব্যাকএন্ডের /admin-api/ci-logs এন্ডপয়েন্ট থেকে সিআই রিপোর্টগুলো পড়া হচ্ছে


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/175_frontend_src_services_controlPlane_test_ts.md -->
<!-- ============================================================ -->

# Module 175: `frontend/src/services/controlPlane.test.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/controlPlane.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 121 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `controlPlane.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/176_frontend_src_services_controlPlane_ts.md -->
<!-- ============================================================ -->

# Module 176: `frontend/src/services/controlPlane.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/controlPlane.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 185 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `controlPlane.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/177_frontend_src_services_costOptimizer_service_test_ts.md -->
<!-- ============================================================ -->

# Module 177: `frontend/src/services/costOptimizer.service.test.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/costOptimizer.service.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 88 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `costOptimizer.service.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/178_frontend_src_services_costOptimizer_service_ts.md -->
<!-- ============================================================ -->

# Module 178: `frontend/src/services/costOptimizer.service.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/costOptimizer.service.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 310 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
> /**
> * SuperAI Cost Optimizer Service (Vite-Compatible)
> *
> * Replaces broken Next.js middleware with Vite-compatible solution.
> * Can be used as:
> * 1. Service worker for SPA
> * 2. Axios interceptor for API calls
> * 3. React Query configuration


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/179_frontend_src_services_heartbeat_test_ts.md -->
<!-- ============================================================ -->

# Module 179: `frontend/src/services/heartbeat.test.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/heartbeat.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 66 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `heartbeat.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/180_frontend_src_services_heartbeat_ts.md -->
<!-- ============================================================ -->

# Module 180: `frontend/src/services/heartbeat.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/heartbeat.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 40 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
> // বাংলা মন্তব্য: এটি একটি গ্লোবাল হার্টবিট সার্ভিস, যা প্রতি ১০ মিনিট অন্তর /api/v1/live ইনফ্রাস্ট্রাকচার প্রোব দিয়ে
> // সার্ভারগুলোকে স্লিপিং মোডে যাওয়া থেকে বিরত রাখে। /health থেকে /api/v1/live তে মাইগ্রেটেড
> // কারণ /api/v1/live শুধু প্রসেস লাইভনেস চেক করে, Redis/DB ডিপেন্ডেন্সি টাচ করে না তাই আরো লাইটওয়েট
> // Initial ping 10 seconds after load
> // Ping every 10 minutes
> // বাংলা মন্তব্য: getApiBaseUrl() ব্যবহার করা হচ্ছে যাতে Firebase Hosting-এ relative path ('') পাওয়া যায়
> // এবং firebase.json proxy rewrites দিয়ে সার্ভার-সাইড প্রক্সি হয় — কোনো CORS/preflight ঝামেলা থাকে না।


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/181_frontend_src_services_policyService_ts.md -->
<!-- ============================================================ -->

# Module 181: `frontend/src/services/policyService.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/policyService.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 13 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `policyService.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/182_frontend_src_services_queryClient_test_ts.md -->
<!-- ============================================================ -->

# Module 182: `frontend/src/services/queryClient.test.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/queryClient.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 66 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `queryClient.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/183_frontend_src_services_queryClient_ts.md -->
<!-- ============================================================ -->

# Module 183: `frontend/src/services/queryClient.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/queryClient.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 78 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
> // 🔬 Evolution v3.0: Enhanced query client with retry + circuit breaker awareness
> /**
> * 🔬 Error classification for smart retries
> */


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/184_frontend_src_services_realtime.md -->
<!-- ============================================================ -->

# Module 184: `frontend/src/services/realtime`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/realtime`
- **Type:** Directory (প্যাকেজ/সাব-সিস্টেম)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 1 files

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `realtime` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/185_frontend_src_services_sandbox_ts.md -->
<!-- ============================================================ -->

# Module 185: `frontend/src/services/sandbox.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/sandbox.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 116 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
> // Wait for initialization to complete


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/186_frontend_src_services_skillsService_test_ts.md -->
<!-- ============================================================ -->

# Module 186: `frontend/src/services/skillsService.test.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/skillsService.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 127 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `skillsService.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/187_frontend_src_services_skillsService_ts.md -->
<!-- ============================================================ -->

# Module 187: `frontend/src/services/skillsService.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/skillsService.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 119 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
> // apps/studio-client/src/services/skillsService.ts
> // বাংলা মন্তব্য: ব্যাকএন্ডের /api/skills/catalog এন্ডপয়েন্ট থেকে
> // রোল-ভিত্তিক স্কিল ক্যাটালগ ফেচ করার সার্ভিস লেয়ার।


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/188_frontend_src_services_socialGrowthService_ts.md -->
<!-- ============================================================ -->

# Module 188: `frontend/src/services/socialGrowthService.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/socialGrowthService.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 29 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `socialGrowthService.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/189_frontend_src_services_storageApi_test_ts.md -->
<!-- ============================================================ -->

# Module 189: `frontend/src/services/storageApi.test.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/storageApi.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 36 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `storageApi.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/190_frontend_src_services_storageApi_ts.md -->
<!-- ============================================================ -->

# Module 190: `frontend/src/services/storageApi.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/storageApi.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 53 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
> // FrR2 Storage API
> // বাংলা মন্তব্য: ১. ব্যাকএন্ড থেকে প্রে-সাইন্ড আপলোড ইউআরএল নিয়ে আসা


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/191_frontend_src_services_supremeShared_test_ts.md -->
<!-- ============================================================ -->

# Module 191: `frontend/src/services/supremeShared.test.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/supremeShared.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 30 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
- `supremeShared.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/192_frontend_src_services_supremeShared_ts.md -->
<!-- ============================================================ -->

# Module 192: `frontend/src/services/supremeShared.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/supremeShared.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 116 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
> /**
> * SupremeAI Shared Services — Desktop (Electron) Integration Bootstrap
> *
> * `@supremeai/shared-services` প্যাকেজ থেকে কোর সার্ভিসগুলো desktop-এ
> * ব্যবহারের জন্য এখানে একবার initialize করা হয়।
> *
> * বাংলা নোট:
> * - Token Provider: `supremeai_auth_token` (localStorage) থেকে token নেয়


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend Service Module আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/193_frontend_src_services_test_budget_check_test_ts.md -->
<!-- ============================================================ -->

# Module 193: `frontend/src/services/test_budget_check.test.ts`

- **Category:** Frontend Service Module
- **Relative Path:** `frontend/src/services/test_budget_check.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 24 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend Service Module` ডোমেনের অংশ।
> // eslint-disable-next-line @typescript-eslint/no-explicit-any


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/194_frontend_src_store_adminStore_test_ts.md -->
<!-- ============================================================ -->

# Module 194: `frontend/src/store/adminStore.test.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/adminStore.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 156 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `adminStore.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/195_frontend_src_store_adminStore_ts.md -->
<!-- ============================================================ -->

# Module 195: `frontend/src/store/adminStore.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/adminStore.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 285 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
> // Validate decoded structure
> // eslint-disable-next-line @typescript-eslint/no-explicit-any


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend State Store আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/196_frontend_src_store_authStore_test_ts.md -->
<!-- ============================================================ -->

# Module 196: `frontend/src/store/authStore.test.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/authStore.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 114 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `authStore.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/197_frontend_src_store_authStore_ts.md -->
<!-- ============================================================ -->

# Module 197: `frontend/src/store/authStore.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/authStore.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 277 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
> // বাংলা মন্তব্য: erasableSyntaxOnly সক্রিয় থাকায় enum-এর বদলে const object + union type ব্যবহার করা হচ্ছে
> // বাংলা মন্তব্য: Single-frontend migration (roadmap Phase 2) — authStore এখন canonical
> // identity/session authority। role শুধুমাত্র backend response (login/register//auth/me)
> // থেকে resolve হয় — localStorage role key, URL বা UI state থেকে কখনোই নয়।


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend State Store আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/198_frontend_src_store_chatStore_test_ts.md -->
<!-- ============================================================ -->

# Module 198: `frontend/src/store/chatStore.test.ts`
> **⚠️ historical (audit 2026-10-10):** this file no longer exists on disk — it was deleted during the store consolidation. Entry kept for provenance; the live state surface is `frontend/src/store/unifiedStore.ts` and `sessionCockpitStore.ts`.


- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/chatStore.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 93 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `chatStore.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/199_frontend_src_store_chatStore_ts.md -->
<!-- ============================================================ -->

# Module 199: `frontend/src/store/chatStore.ts`
> **⚠️ historical (audit 2026-10-10):** this file no longer exists on disk — it was deleted during the store consolidation. Entry kept for provenance; the live state surface is `frontend/src/store/unifiedStore.ts` and `sessionCockpitStore.ts`.


- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/chatStore.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 100 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `chatStore.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend State Store আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/200_frontend_src_store_customerStore_test_ts.md -->
<!-- ============================================================ -->

# Module 200: `frontend/src/store/customerStore.test.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/customerStore.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 50 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `customerStore.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/201_frontend_src_store_customerStore_ts.md -->
<!-- ============================================================ -->

# Module 201: `frontend/src/store/customerStore.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/customerStore.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 83 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
> /** SECURITY FIX (audit P-7): Clears all user data on logout to prevent
> *  data leakage between users on shared devices. */


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend State Store আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/202_frontend_src_store_dashboardStore_test_ts.md -->
<!-- ============================================================ -->

# Module 202: `frontend/src/store/dashboardStore.test.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/dashboardStore.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 51 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `dashboardStore.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/203_frontend_src_store_dashboardStore_ts.md -->
<!-- ============================================================ -->

# Module 203: `frontend/src/store/dashboardStore.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/dashboardStore.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 35 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
> // বাংলা মন্তব্য: সুপ্রিম ড্যাশবোর্ড মোড ('simple' অথবা 'advanced') এবং ইন্টারেক্টিভ চ্যাটের উইন্ডো স্ট্যাটাস


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend State Store আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/204_frontend_src_store_index_test_ts.md -->
<!-- ============================================================ -->

# Module 204: `frontend/src/store/index.test.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/index.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 39 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `index.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/205_frontend_src_store_index_ts.md -->
<!-- ============================================================ -->

# Module 205: `frontend/src/store/index.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/index.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 59 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
> /**
> * R13 FIX: Unified Store Entry Point
> *
> * When UNIFIED_STORE=true env (or localStorage flag) is set, this file
> * re-exports the unified store under the names of the 12 legacy store hooks.
> * Existing imports `import { useChatStore } from '@/store/chatStore'` keep
> * working UNCHANGED because each legacy store file will be replaced with a
> * 1-line re-export shim in Phase 2.


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend State Store আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/206_frontend_src_store_localFirstDb_ts.md -->
<!-- ============================================================ -->

# Module 206: `frontend/src/store/localFirstDb.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/localFirstDb.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 157 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `localFirstDb.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend State Store আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/207_frontend_src_store_sessionCockpitStore_ts.md -->
<!-- ============================================================ -->

# Module 207: `frontend/src/store/sessionCockpitStore.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/sessionCockpitStore.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 157 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
> // eslint-disable-next-line @typescript-eslint/no-explicit-any


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend State Store আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/208_frontend_src_store_slices.md -->
<!-- ============================================================ -->

# Module 208: `frontend/src/store/slices`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/slices`
- **Type:** Directory (প্যাকেজ/সাব-সিস্টেম)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 7 files

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `slices` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend State Store আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/209_frontend_src_store_stateOwnership_ts.md -->
<!-- ============================================================ -->

# Module 209: `frontend/src/store/stateOwnership.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/stateOwnership.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 17 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
> /**
> * Canonical frontend state ownership map.
> *
> * This is intentionally descriptive: it prevents new features from creating
> * another store for state already owned by an existing authority.
> */


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend State Store আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/210_frontend_src_store_themeStore_test_ts.md -->
<!-- ============================================================ -->

# Module 210: `frontend/src/store/themeStore.test.ts`
> **⚠️ historical (audit 2026-10-10):** this file no longer exists on disk — it was deleted during the store consolidation. Entry kept for provenance; the live state surface is `frontend/src/store/unifiedStore.ts` and `sessionCockpitStore.ts`.


- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/themeStore.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 44 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `themeStore.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/211_frontend_src_store_themeStore_ts.md -->
<!-- ============================================================ -->

# Module 211: `frontend/src/store/themeStore.ts`
> **⚠️ historical (audit 2026-10-10):** this file no longer exists on disk — it was deleted during the store consolidation. Entry kept for provenance; the live state surface is `frontend/src/store/unifiedStore.ts` and `sessionCockpitStore.ts`.


- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/themeStore.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 96 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `themeStore.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend State Store আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/212_frontend_src_store_unifiedStore_ts.md -->
<!-- ============================================================ -->

# Module 212: `frontend/src/store/unifiedStore.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/unifiedStore.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 400 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
> /**
> * Unified Store - Single Source of Truth for Cross-Component State
> *
> * This store connects your 20+ crown jewel components!
> *
> * @file frontend/src/store/unifiedStore.ts
> * @description Centralized state management for SupremeAI integration
> * @version 1.0.0


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend State Store আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/213_frontend_src_store_useIdeStore_test_ts.md -->
<!-- ============================================================ -->

# Module 213: `frontend/src/store/useIdeStore.test.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/useIdeStore.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 68 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `useIdeStore.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/214_frontend_src_store_useIdeStore_ts.md -->
<!-- ============================================================ -->

# Module 214: `frontend/src/store/useIdeStore.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/useIdeStore.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 81 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `useIdeStore.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend State Store আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/215_frontend_src_store_useStore_test_ts.md -->
<!-- ============================================================ -->

# Module 215: `frontend/src/store/useStore.test.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/useStore.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 120 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `useStore.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/216_frontend_src_store_useStore_ts.md -->
<!-- ============================================================ -->

# Module 216: `frontend/src/store/useStore.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/useStore.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 165 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
> // বাংলা মন্তব্য: raw fetch() সরিয়ে apiClient ব্যবহার — auth header সব request এ যাবে
> // বাংলা মন্তব্য: আগে duplicate status field ছিল — TypeScript compile error। একটি রাখা হলো।


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend State Store আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/217_frontend_src_store_useSupremeStore_test_ts.md -->
<!-- ============================================================ -->

# Module 217: `frontend/src/store/useSupremeStore.test.ts`
> **⚠️ historical (audit 2026-10-10):** this file no longer exists on disk — it was deleted during the store consolidation. Entry kept for provenance; the live state surface is `frontend/src/store/unifiedStore.ts` and `sessionCockpitStore.ts`.


- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/useSupremeStore.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 12 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `useSupremeStore.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/218_frontend_src_store_useSupremeStore_ts.md -->
<!-- ============================================================ -->

# Module 218: `frontend/src/store/useSupremeStore.ts`
> **⚠️ historical (audit 2026-10-10):** this file no longer exists on disk — it was deleted during the store consolidation. Entry kept for provenance; the live state surface is `frontend/src/store/unifiedStore.ts` and `sessionCockpitStore.ts`.


- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/useSupremeStore.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 15 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `useSupremeStore.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend State Store আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/219_frontend_src_store_useWorkspaceSettingsStore_test_ts.md -->
<!-- ============================================================ -->

# Module 219: `frontend/src/store/useWorkspaceSettingsStore.test.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/useWorkspaceSettingsStore.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 31 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `useWorkspaceSettingsStore.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/220_frontend_src_store_useWorkspaceSettingsStore_ts.md -->
<!-- ============================================================ -->

# Module 220: `frontend/src/store/useWorkspaceSettingsStore.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/useWorkspaceSettingsStore.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 55 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `useWorkspaceSettingsStore.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend State Store আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/221_frontend_src_store_useWorkspaceStore_test_ts.md -->
<!-- ============================================================ -->

# Module 221: `frontend/src/store/useWorkspaceStore.test.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/useWorkspaceStore.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 57 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `useWorkspaceStore.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/222_frontend_src_store_useWorkspaceStore_ts.md -->
<!-- ============================================================ -->

# Module 222: `frontend/src/store/useWorkspaceStore.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/useWorkspaceStore.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **Size / Footprint:** 70 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
> // apps/studio-client/src/store/useWorkspaceStore.ts
> // Zustand Orchestrator for Living Workspace
> // বাংলা মন্তব্য: গ্লোবাল স্টেট ম্যানেজমেন্ট, যা dnd-kit ড্র্যাগ-অ্যান্ড-ড্রপ এবং ডাইনামিক ইন্টিগ্রেশন কন্ট্রোল করবে।
> // Actions


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** SupremeAI প্ল্যাটফর্মে Frontend State Store আর্কিটেকচারাল লেয়ারটিকে মডুলার, ডিকাপল্ড ও আইসোলেটেড রাখার উদ্দেশ্যে।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Active in Codebase (সক্রিয় ও কোডবেসে ব্যবহৃত)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - সিস্টেমের কোর লজিক বা ক্লায়েন্ট ইন্টারেকশনে সরাসরি ব্যবহৃত হচ্ছে।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/223_frontend_src_store_workspaceUiStateStore_test_ts.md -->
<!-- ============================================================ -->

# Module 223: `frontend/src/store/workspaceUiStateStore.test.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/workspaceUiStateStore.test.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 90 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
- `workspaceUiStateStore.test.ts` মূলত সংশ্লিষ্ট সাব-সিস্টেমের স্পেসিফিক কার্যকারিতা সম্পাদন করে।

## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/modules_audit/224_frontend_src_store_workspaceUiStateStore_ts.md -->
<!-- ============================================================ -->

# Module 224: `frontend/src/store/workspaceUiStateStore.ts`

- **Category:** Frontend State Store
- **Relative Path:** `frontend/src/store/workspaceUiStateStore.ts`
- **Type:** Source File (কোড ফাইল)
- **Real-Life Status:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **Size / Footprint:** 152 lines of code

---

## ১. মডিউলটির মূল কাজ কী? (What does it do?)
এই মডিউলটি SupremeAI প্ল্যাটফর্মের `Frontend State Store` ডোমেনের অংশ।
> // ─── Types ───────────────────────────────────────────────────────────────
> // S1: Share


## ২. কেন এটি বানানো হয়েছিল? (Why was it built?)
- **উদ্দেশ্য:** সংশ্লিষ্ট মডিউলটির নির্ভুলতা ও ফাংশনালিটি টেস্ট স্যুট দিয়ে যাচাই (automated testing) করার জন্য।
- আর্কিটেকচারাল ক্ল্যাটার দূর করা এবং কোডের পুনঃব্যবহারযোগ্যতা (reusability) বজায় রাখা।

## ৩. রিয়েল লাইফে এটি কাজ করে কি না? (Does it actually work in real life?)
- **স্ট্যাটাস:** Automated Test Suite (স্বয়ংক্রিয় টেস্ট সুইট - CI/CD তে রান হয়)
- **বাস্তব ব্যবহার ও মূল্যায়ন:**
  - ফাইল বা ডিরেক্টরিটি লোকাল ডিস্কে বিদ্যমান রয়েছে।
  - টেস্ট রানার (Vitest / Pytest) দ্বারা স্বয়ংক্রিয় পাইপলাইনে ব্যবহৃত হয়।



<!-- ============================================================ -->
<!-- Merged Source: docs/ui-ux/SUPREME_UI_DASHBOARD_MASTER.md -->
<!-- ============================================================ -->

# 🎨 SupremeAI Dashboard & Design System Master Plan

**Document Version:** 3.1.0 (Current Codebase-Aligned Canonical Source of Truth)  
**System Phase:** **Phase 3: Self-Evolving & Multi-Agent Swarm**  
**Classification:** Frontend Design System, UI/UX Architecture, Single Frontend & Role-Based Shared Shell

---

## 🎯 0. Core Decision — One Frontend, Role-Based Experience

SupremeAI will use **one frontend application/build** for every authenticated role. User and Admin are **roles/views inside the same frontend**, not two separately deployed frontend applications.

### Non-negotiable architecture

```text
                    SUPREMEAI FRONTEND
                           │
                    Unified Auth State
                           │
                  ┌────────┴────────┐
                  │                 │
              USER ROLE         ADMIN ROLE
                  │                 │
            /workspace          /admin
                  │                 │
             User Views        Admin Views
                  └────────┬────────┘
                           │
                    Shared App Shell
              Header / Nav / Command Bar
              Theme / Notifications / Profile
              Error Boundary / Loading / Toasts
                           │
                    Shared API Client
                           │
                  SupremeAI Backend
```

**Important:** Role-based routing is a UI authorization layer, not the security boundary. The backend remains authoritative for admin permissions and privileged actions.

---

## 🔎 1. Current Codebase Audit — What Exists Today

The current repository already contains most of the building blocks required for the single-frontend architecture, but they are not yet fully consolidated.

### 1.1 Current `App.tsx` state (Single-Frontend Graph Implemented)

`frontend/src/App.tsx` contains a single, unified route graph for all roles:

- React Router routing with lazy loading for heavy workspace/admin pages.
- Shared `ThemeSyncProvider`, `TranslationProvider`, `GlobalConfigInitializer`, `QueryClientProvider` and global `ErrorBoundary`.
- Unified route graph: Public landing, `/workspace`, `/workspace/agent`, `/workspace/ide`, `/integrations`, `/skills-catalog`, `/billing`, `/profile`, and protected `/admin/*` in one app bundle.
- Global `CommandBar` (⌘K / Ctrl+K) accessible across user and admin contexts.
- Strict guard hierarchy: `GuestRoute`, `ProtectedRoute`, `RoleGuard` (`requiredRole`), and `PermissionGuard`.

### 1.2 `VITE_PORTAL_TYPE` Elimination Status (RESOLVED)

`VITE_PORTAL_TYPE` has been completely eliminated from `App.tsx` (single-frontend migration Phase 1). There is now exactly one build and one route graph. Dynamic landing redirection handles role routing:
- Guest → `/` / `/login`
- Authenticated User → `/workspace`
- Authenticated Admin → `/admin`

### 1.3 Shell and Layout Unification

`frontend/src/components/layout/WorkspaceLayout.tsx` provides the shared workspace shell:
- `DashboardLayout` foundation with animated collapsible sidebar.
- Unified `navigationRegistry.ts` as single source of truth for both user and admin sidebars.
- Dynamic Action Dock and HITL modal integration.
- Admin views render inside the same frontend application via lazy-loaded `AdminShell.tsx`.

### 1.4 Admin Architecture & Step-Up Security

`frontend/src/pages/admin/AdminShell.tsx` and `frontend/src/components/admin/AdminConsole.tsx`:
- Authenticated via primary session with server-enforced `RoleGuard(admin)`.
- Secondary step-up security (TOTP 2FA / JIT OTP) preserved for high-risk operations.
- Admin telemetry, live event logs, and operational controls render directly within the unified SPA.

### 1.6 Current authentication guard

`frontend/src/components/core/AuthGuards.tsx` already has a reusable `ProtectedRoute` based on `authStore`.

This should remain the base authentication guard, then be extended with a dedicated role/permission guard for admin routes.

---

## 🏛️ 2. Target Information Architecture — One Shell, Two Role Experiences

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ SUPREMEAI GLOBAL HEADER                                                     │
│ [☰] SupremeAI   [⌘K Search]   [Context/Role]   [Notifications] [Profile]   │
├──────────────┬──────────────────────────────────────────────────────────────┤
│ ROLE-AWARE   │ MAIN VIEWPORT                                                │
│ NAVIGATION   │                                                              │
│              │ Breadcrumb                                                   │
│ USER:        │ Page Header                                                  │
│ • Workspace  │ KPI / Context                                                │
│ • Agents     │ Dynamic Page Content                                         │
│ • Projects   │                                                              │
│ • Skills     │                                                              │
│ • Integrate  │                                                              │
│              │                                                              │
│ ADMIN:       │                                                              │
│ • Overview   │                                                              │
│ • System     │                                                              │
│ • Resources  │                                                              │
│ • Security   │                                                              │
│ • Users      │                                                              │
│ • Evolution  │                                                              │
│              │                                                              │
│ Shared:      │                                                              │
│ • Profile    │                                                              │
│ • Settings   │                                                              │
└──────────────┴──────────────────────────────────────────────────────────────┘
```

The shell is shared; **navigation content and page capabilities are role-aware**.

---

## 🎨 3. Design Aesthetics & Visual Identity

SupremeAI follows a premium **Dark-Neon / Living System** aesthetic.

- **Background:** Dense Dark-Neon (`#09090b` / `slate-950`) with controlled aurora/vignette effects.
- **Admin accent:** Cyber Cyan (`#00F3FF`).
- **User accent:** Hyper Purple (`#A855F7`).
- **Typography:** `Plus Jakarta Sans` / `Inter` for UI; `JetBrains Mono` for code/metrics.
- **Metrics:** `tabular-nums`.
- **Surfaces:** translucent/glass surfaces with restrained borders and blur.

### Role theming rule

Role color is a **context indicator**, not a separate application theme.

- User context → purple accent.
- Admin context → cyan accent.
- Shared components must use semantic design tokens rather than hard-coded role-specific CSS scattered throughout pages.

---

## 🧱 4. Unified Shared Shell Components

Create or consolidate around these components; **do not create duplicate shells**:

1. **`UnifiedAppShell`** — single application-level shell.
2. **`GlobalHeader`** — branding, search, role context, notifications, profile.
3. **`RoleAwareNavRail`** — derives navigation from authenticated role/permissions.
4. **`PageHeader`** — eyebrow, title, subtitle, actions.
5. **`Breadcrumb`** — route-aware navigation context.
6. **`CommandBar`** — global `Ctrl+K` / `⌘K` command palette.
7. **`NotificationCenter`** — user/admin notifications with permission-aware content.
8. **`GlobalStatus`** — backend/core connectivity and degraded-mode status.
9. **`GlobalErrorBoundary`** — application-level crash isolation.
10. **`RoleContext` / `PermissionContext`** — one frontend source for role/capability presentation.

Existing `DashboardLayout`, `WorkspaceLayout`, `CommandBar`, theme providers, and error boundaries should be reused/refactored rather than replaced blindly.

---

## 🔐 5. Authentication, Role & Authorization Model

### 5.1 One identity

There must be one canonical authenticated identity in the frontend:

```text
Auth Store
  ├── user
  ├── session
  ├── role
  ├── permissions/capabilities
  ├── auth status
  └── optional admin step-up status
```

Do not maintain separate independent `userAuthenticated` and `adminAuthenticated` identities for the same browser session.

### 5.2 Role resolution

Preferred order:

1. Authenticate user.
2. Backend/Firebase/auth provider establishes identity.
3. Backend-authoritative role/permissions are resolved.
4. Frontend builds role-aware navigation.
5. User/admin route guards enforce UX access.
6. Backend independently enforces every privileged operation.

### 5.3 Admin step-up

Existing OTP/TOTP functionality must not be weakened during consolidation.

If the backend requires admin step-up authentication, represent it as an additional security state of the same identity/session rather than a second unrelated login system.

Example:

```text
AUTHENTICATED USER
       │
       ├── role=user → normal user capabilities
       │
       └── role=admin
              │
              ├── step-up required → Admin Verification
              └── step-up verified → Admin capabilities
```

### 5.4 Critical security rule

A frontend role switcher must **never** allow a user to become admin by changing local state, URL, localStorage, or a UI pill.

The switcher can only select roles/capabilities that the backend-authenticated identity is actually authorized to use.

---

## 🔀 6. Routing Strategy — Remove Portal Split

### Current

```text
VITE_PORTAL_TYPE=admin → Admin-only route tree
VITE_PORTAL_TYPE=user  → User route tree + /admin
```

### Target

```text
One build
   │
   └── React Router
         ├── /login
         ├── /register
         ├── /workspace/*        → authenticated user capability
         ├── /projects/*         → authenticated capability
         ├── /agents/*           → authenticated capability
         ├── /integrations/*     → authenticated capability
         ├── /settings/*         → authenticated capability
         ├── /profile            → authenticated capability
         └── /admin/*             → admin role + required step-up
```

The same compiled frontend can open `/admin` or `/workspace`; authorization determines what is actually accessible.

### Route guard hierarchy

```text
GuestRoute
   ↓
ProtectedRoute
   ↓
RoleGuard / PermissionGuard
   ↓
Optional StepUpGuard
   ↓
Page
```

Use route metadata instead of scattered role checks where practical:

```ts
{
  path: '/admin/resources',
  requiredRole: 'admin',
  requiredPermission: 'resource.read',
  requiresStepUp: true,
}
```

---

## 🧭 7. Role-Aware Navigation

Navigation should be data-driven and generated from a single registry.

```text
NAVIGATION_REGISTRY
   ├── public
   ├── authenticated
   ├── user
   ├── admin
   └── shared
```

Each item should support:

- `path`
- `label`
- `icon`
- `requiredRole`
- `requiredPermission`
- `featureFlag`
- `availability`
- `badge`
- `priority`

### Important

Do not render every admin item and hide it only with CSS. Unauthorized navigation should not be presented as available functionality.

---

## 🔄 8. Role Switching UX

If the authenticated identity has multiple supported contexts, the header can show:

```text
[ User ▼ ]
   User Workspace
   Admin Console
```

For a normal user with no admin permission:

```text
[ User ]
```

For an admin:

```text
[ Admin ▼ ]
   Admin Console
   User Workspace
```

Switching roles should:

1. Verify the target role is allowed by the canonical auth/permission state.
2. Update UI context.
3. Navigate to the role's canonical landing route.
4. Preserve safe global state such as theme/language where appropriate.
5. Clear role-specific transient state where required.
6. Never fabricate or elevate permissions client-side.

---

## 🧩 9. User Experience Surface

The current user feature inventory already includes:

- Workspace/Home.
- AI Studio / live workspace.
- Agent Workspace.
- IDE Workspace.
- Projects navigation target.
- Activity.
- Skills Catalog.
- Integrations.
- Marketplace navigation target.
- Runs/automation navigation target.
- Usage.
- Billing.
- Settings.
- Profile.
- Swarm Map.
- Architect Tower.
- Evolution Forge.

Before adding new pages, audit whether an existing page/component/store/API already implements the capability.

### User home principle

`/workspace` should remain the user landing surface and should expose the highest-value actions without turning the user experience into an admin control panel.

---

## 🛡️ 10. Admin Experience Surface

The admin console should remain powerful but live inside the same shell.

Admin capabilities may include:

- System overview.
- Resource/provider health.
- Service/deployment operations.
- Skills/capability management.
- Checkpoints and recovery.
- Cost/usage oversight.
- Health maps and telemetry.
- Rules/policy management.
- User/tenant administration.
- Security and audit controls.
- Evolution/self-improvement controls.
- MCP/control-plane operations where authorized.

Admin pages should use the same primitives (`StatCard`, `PageHeader`, `Breadcrumb`, tables, dialogs, command palette, notifications) as user pages.

---

## 🧠 11. Shared vs Role-Specific State

### Global/shared state

Keep only truly cross-application state globally:

- auth/session
- current role/context
- theme
- locale
- global notifications
- server connectivity
- feature flags/config
- command palette state where necessary

### User-scoped state

Examples:

- current workspace
- chat/session state
- project state
- user preferences
- agent interaction state

### Admin-scoped state

Examples:

- admin filters
- operational dashboards
- deployment action status
- administrative search
- system investigation state

Do not merge unrelated user/admin stores merely to achieve “one store”. The goal is **one identity authority and clean state ownership**, not a giant global store.

---

## 🚀 12. Performance & Bundle Strategy

The current `App.tsx` already uses `React.lazy()` for heavy workspace/admin modules. Keep this approach.

Target behavior:

- One frontend build.
- Shared shell loads first.
- Route-level heavy modules lazy-load on demand.
- Admin-only modules are not eagerly loaded for normal users.
- User-only heavy modules are not eagerly loaded on admin landing.
- Avoid importing browser/AI-heavy libraries into the root shell.
- Keep Core frontend bundle lightweight enough for the current deployment architecture.

**Single frontend does not mean one giant JavaScript bundle.** It means one application/deployment artifact with route-level code splitting.

---

## 🌐 13. Dynamic Configuration — No Environment-Based Portal Identity

The following must not determine which application is built:

```text
VITE_PORTAL_TYPE=user
VITE_PORTAL_TYPE=admin
```

Environment variables may still configure infrastructure endpoints, feature flags, analytics, or deployment-specific behavior, but **role identity must come from authenticated runtime state**.

Avoid hardcoded service URLs, role assumptions, provider IDs, and deployment-specific routing inside UI components. Use the existing centralized configuration approach.

---

## 🧪 14. Testing & Acceptance Criteria

The single-frontend migration is not complete until these tests pass.

### Build tests

- One production frontend build succeeds.
- No admin-only build variant.
- No user-only build variant.
- `VITE_PORTAL_TYPE` is absent from production routing logic.

### Authentication tests

- Guest → login → correct landing page.
- User → `/admin` → denied/redirected.
- Admin → `/admin` → allowed.
- Admin → `/workspace` → allowed.
- Refresh preserves authenticated role correctly.
- Logout clears both user and admin contextual state.

### Security tests

- Changing URL cannot elevate role.
- Changing localStorage cannot elevate role.
- Changing role pill/client state cannot elevate role.
- Admin API calls remain backend-authorized.
- Admin step-up remains enforced where required.

### UX tests

- Header is identical structurally across roles.
- Sidebar/navigation changes according to role.
- Role switch preserves shared shell state where safe.
- Unauthorized items are absent, not merely hidden.
- Command Bar respects route/permission visibility.
- Mobile/tablet navigation remains usable.

### Regression tests

- Existing user workspace routes continue to work.
- Existing admin console capabilities continue to work.
- Existing auth flow continues to work.
- Existing theme/locale behavior continues to work.
- Existing error boundaries remain effective.

---

## 🗺️ 15. Implementation Roadmap

### Phase 0 — Inventory & freeze duplication

- Inventory all frontend entry points/build scripts/deployment targets.
- Inventory `authStore`, `adminStore`, role checks, login components, layouts and navigation.
- Identify duplicate user/admin API clients, stores, providers and theme logic.
- Do not create new shell components until existing ones are classified.

### Phase 1 — Remove portal split (P0)

- Remove `VITE_PORTAL_TYPE` routing branch from `App.tsx`.
- Keep one complete route graph.
- Keep admin and user route modules lazy-loaded.
- Ensure one frontend build/deployment artifact.

### Phase 2 — Unify identity/session authority (P0)

- Make `authStore` the canonical identity/session source.
- Integrate admin role information into the canonical auth model.
- Preserve admin OTP/TOTP/step-up behavior.
- Remove duplicate session authority from `adminStore` where it duplicates identity state.

### Phase 3 — Build the role-aware shell (P0)

- Refactor `DashboardLayout`/`WorkspaceLayout` into the shared shell foundation.
- Add `GlobalHeader`.
- Add `RoleAwareNavRail`.
- Add role/permission context.
- Keep existing `CommandBar` global.
- Keep existing Action Dock/HITL behavior where relevant.

### Phase 4 — Convert routes to metadata + guards (P1)

- Add role/permission route metadata.
- Implement `RoleGuard`/`PermissionGuard`.
- Add optional `StepUpGuard` for sensitive admin areas.
- Remove scattered ad-hoc role checks where route metadata is sufficient.

### Phase 5 — Integrate Admin Console into the shell (P1)

- Make `AdminShell` render inside the same `UnifiedAppShell`.
- Reuse shared header/sidebar/page primitives.
- Keep admin-specific data tables, telemetry, controls and dialogs.
- Keep admin error isolation.

### Phase 6 — Navigation consolidation (P1)

- Create one navigation registry.
- Generate User/Admin/Shared navigation from permissions.
- Remove duplicate navigation definitions.
- Verify every navigation target has an implemented route or explicitly tracked backlog item.

### Phase 7 — UX polish & performance (P2)

- Role transition animation.
- Consistent loading/error/empty states.
- Responsive navigation.
- Command Bar command visibility by role.
- Route-level code splitting audit.
- Bundle-size regression budget.

### Phase 8 — Remove legacy split infrastructure (P2)

Only after production validation:

- Remove obsolete portal-specific build scripts.
- Remove obsolete portal-specific deployment configuration.
- Remove duplicate admin/user shell code.
- Update deployment documentation.
- Update CI checks to reject reintroduction of portal splitting.

---

## 📋 16. Definition of Done

The migration is considered complete only when all are true:

- [ ] Exactly one frontend application/build is deployed.
- [ ] No `VITE_PORTAL_TYPE` or equivalent variable controls application identity.
- [ ] User and Admin are runtime roles/contexts in the same app.
- [ ] One canonical authentication/session authority exists.
- [ ] Admin step-up security is preserved.
- [ ] Backend remains authoritative for authorization.
- [ ] One shared application shell is used by both roles.
- [ ] Navigation is role/permission aware.
- [ ] `/workspace` works for authorized users.
- [ ] `/admin/*` works only for authorized admins.
- [ ] Admin can safely access user workspace when permitted.
- [ ] Normal users cannot elevate themselves through frontend state.
- [ ] Existing admin functionality is preserved.
- [ ] Existing user functionality is preserved.
- [ ] Heavy role-specific modules remain lazy-loaded.
- [ ] CI tests the single-build + RBAC contract.
- [ ] Production smoke tests cover both user and admin journeys.

---

## ⚠️ 17. Current Codebase Risks to Track

| Risk | Current state | Priority |
|---|---|---:|
| `VITE_PORTAL_TYPE` splits the route graph | Present in `App.tsx` | **P0** |
| Separate admin auth/session state | Present in `AdminShell`/`adminStore` | **P0** |
| User shell vs Admin shell are still separate | Present | **P0** |
| Role-aware shared navigation | Partial | **P1** |
| Route metadata/permission guards | Partial | **P1** |
| Admin step-up integration with unified auth | Needs consolidation | **P1** |
| Heavy pages lazy-loaded | Already present | 🟢 |
| Global Command Bar | Already mounted globally | 🟢 |
| Shared low-level DashboardLayout | Already present | 🟢 |
| User WorkspaceLayout | Already present, needs promotion to shared foundation | 🟡 |

---

## 🧭 18. Architectural Rules for Future AI Agents

1. **Never create a second frontend just because a role needs different screens.**
2. **Never use a build-time portal variable to decide whether the application is User or Admin.**
3. **Never trust frontend role state for authorization.**
4. **Never create a second authentication authority for Admin if the same identity/session is already authenticated.**
5. **Do not duplicate shells, headers, sidebars, command bars, theme systems or notification systems.**
6. **Reuse existing components before creating new ones.**
7. **Keep role-specific business UI separate where it improves clarity, but keep the shell shared.**
8. **Use lazy loading instead of separate builds to control bundle size.**
9. **Use semantic design tokens instead of scattered hard-coded role colors.**
10. **Do not expose unauthorized navigation merely by hiding it with CSS.**
11. **Every privileged UI action must map to a backend-authorized operation.**
12. **Do not equate “single frontend” with “single monolithic bundle”.**
13. **Do not remove existing security controls during architectural consolidation.**
14. **Before adding a new page/store/service, audit the current codebase for an existing implementation.**
15. **A green frontend build does not prove RBAC correctness; test User/Admin journeys independently.**

---

## 📐 19. Repository Scale ≠ Architectural Complexity

Frontend and repository size must never be judged using raw file count alone.

```text
Architectural Complexity =
  Active Runtime Surface
+ Dependency/Coupling Graph
+ Circular Dependencies
+ Duplicate Systems
+ Unclear Ownership
+ Build/Deploy Coupling
+ Operational Blast Radius
+ Testability
+ Dead / Legacy Code
```

Therefore:

- Do not declare the architecture “too complex” because there are many files.
- Do not merge modules merely to reduce file count.
- Do remove duplicate runtime systems, duplicate auth authorities, duplicate shells and unclear ownership.
- Analyze active production paths separately from archived, experimental and test-only code.

This rule is especially important during the single-frontend migration: **the goal is consolidation of runtime architecture, not artificial reduction of source-file count.**

---

## 🔁 20. Canonical Target Architecture

```text
                    ┌──────────────────────────┐
                    │    SUPREMEAI FRONTEND    │
                    │       ONE BUILD          │
                    └────────────┬─────────────┘
                                 │
                         Canonical Auth
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                USER CONTEXT             ADMIN CONTEXT
                    │                         │
              /workspace                 /admin/*
                    │                         │
                    └────────────┬────────────┘
                                 │
                       UNIFIED APP SHELL
                                 │
             ┌───────────────────┼───────────────────┐
             │                   │                   │
          Header             Nav Rail           Command Bar
             │                   │                   │
             └───────────────────┼───────────────────┘
                                 │
                       Role/Permission Router
                                 │
                         Shared API Client
                                 │
                    SupremeAI Backend APIs
                                 │
                Backend RBAC / Policy / Audit
```

### Final architectural principle

> **One SupremeAI frontend. One shared shell. One canonical identity. Multiple role-aware experiences. Backend-enforced authorization. Lazy-loaded capabilities.**

This supersedes the older two-frontend / portal-specific deployment approach while preserving the existing User and Admin feature surfaces.

---

*Canonical Master Plan — current-codebase-aligned version. Supersedes earlier dashboard/frontend split plans while preserving existing functionality and security controls.*
