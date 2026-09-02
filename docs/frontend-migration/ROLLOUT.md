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
