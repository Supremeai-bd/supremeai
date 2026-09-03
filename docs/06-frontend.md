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
