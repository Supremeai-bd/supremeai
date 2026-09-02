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

### 1.1 Current `App.tsx` state

`frontend/src/App.tsx` currently contains:

- React Router routing.
- Shared `ThemeSyncProvider`, `TranslationProvider`, `GlobalConfigInitializer`, `QueryClientProvider` and global `ErrorBoundary`.
- Lazy loading for heavy workspace/admin pages.
- `/admin/*` route already exists inside the normal user-side route tree.
- User routes such as `/workspace`, `/workspace/agent`, `/workspace/ide`, `/integrations`, `/swarm`, `/evolution-forge`, `/skills-catalog`, `/billing`, `/profile`.
- Global `CommandBar` mounted outside the route tree.
- `ProtectedRoute`/`GuestRoute` for authentication.

### 1.2 Current blocker: `VITE_PORTAL_TYPE`

`App.tsx` still contains:

```ts
const PORTAL_TYPE = import.meta.env.VITE_PORTAL_TYPE || 'user';
```

and branches the entire route tree into either **Admin Portal** or **User Portal**.

This is the main remaining architectural contradiction with Zero-Split Build.

**Required change:** remove portal-type build branching. The frontend must always ship the same route/application graph. The authenticated user's role determines which navigation, landing page, and privileged routes are visible/accessible.

### 1.3 Current `WorkspaceLayout`

`frontend/src/components/layout/WorkspaceLayout.tsx` already provides:

- Shared `DashboardLayout` foundation.
- User navigation groups: Workspace, Discover, Automation, Insights, Settings.
- Sidebar collapse behavior.
- Dynamic Action Dock.
- HITL modal integration.
- Drag/drop context.

However, the current `WorkspaceLayout` is still explicitly user-oriented (`UserSidebar`) and is not yet the universal application shell.

### 1.4 Current `DashboardLayout`

`frontend/src/components/layout/DashboardLayout.tsx` already provides a useful low-level shell:

- full-screen surface
- optional header
- animated collapsible sidebar
- main content viewport

This should become the structural foundation for the **UnifiedAppShell**, rather than creating another competing layout system.

### 1.5 Current Admin architecture

`frontend/src/pages/admin/AdminShell.tsx` + `frontend/src/components/admin/AdminConsole.tsx` already provide an admin experience with:

- Admin authentication state.
- Admin role state.
- Admin login/OTP/TOTP flow.
- Skills/checkpoints/cost/health data.
- Deployment trigger.
- Rules editing.
- Admin chat/input state.
- Admin error boundary.

The problem is architectural duplication: AdminShell currently owns a separate `adminAuthenticated/adminRole` state and AdminConsole has its own admin login surface, while the main application already has `authStore` + `ProtectedRoute`.

**Required direction:** preserve required admin step-up security (OTP/TOTP where applicable), but converge identity/session/role ownership into the unified authentication model. Do not maintain two unrelated login/session authorities.

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
