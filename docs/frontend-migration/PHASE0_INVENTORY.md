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
| Firebase hosting | `firebase.template.json` + `.firebaserc` | Two hosting targets: `user` → `frontend/dist-user` (site `supremeai-a`), `admin` → `frontend/dist-admin` (site `supremeai-admin`). Generated at deploy time by `scripts/deploy/generate_firebase_config.py` |
| CI build | `.github/workflows/ci.yml` (build job ~L547) | Runs the double build, verifies both `dist-*`, uploads `frontend-dist-user` + `frontend-dist-admin`; `deploy-frontend` deploys both sites |
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
