# SupremeAI Cross-Platform Implementation Baseline

**Date:** 2026-11-06  
**Status:** Phase 0/Phase 1 implementation baseline  
**Scope:** SupremeAI unified monorepo (`core/`, `gateway/`, `browser/`, `vscode/`, `studio/`, infrastructure)

This document converts the cross-platform design direction into the smallest implementation sequence that can be verified against the current repository. It supersedes stale satellite-repository assumptions for this implementation cycle. Historical satellite repositories are not implementation targets.

## 1. Current implementation boundary

The active implementation target is the unified monorepo. Studio remains the primary customer workspace. Mobile, desktop, and VS Code are companion lanes and are not release deliverables until their source, authentication, reproducible build, signing/distribution, and runtime evidence are complete.

The following findings are resolved in the current remediation work and must not be re-opened as active defects:

- Credentialed brain-service CORS uses an explicit header allowlist.
- Production admin-token paths no longer use a `localStorage` JWT fallback.
- The optional JARVIS GitHub token is session-scoped.
- Schedule Watchdog has the required workflow permission and passed its live sweep.
- Dependency Health Scan targets `studio` for pnpm and `core` for Poetry.
- `pnpm audit --prod` reports zero production vulnerabilities after the dependency graph fixes.

The following remain release gates rather than design assumptions:

- Runtime tenant isolation and privileged mutation authorization.
- Backup/restore drill and RPO/RTO ownership.
- Authenticated production chat E2E and browser/accessibility QA.
- Branch-protection/provenance evidence and rollback rehearsal.
- Existing Studio-wide TypeScript/build debt.
- Reproducible mobile, desktop, and VSIX builds.

## 2. Authority and identity model

| Context | Current authority | Scope | Client representation | Required verification |
|---|---|---|---|---|
| Customer workspace | Backend user session | Customer tenant | Studio session/in-memory token or approved cookie session | Login, `/me`, expiry, logout, account switch |
| Tenant administration | Backend admin role plus step-up | One tenant | Admin UI session; no URL token handoff | Cross-tenant denial and mutation audit |
| Global operations | Backend/operator authorization | Platform-wide | Separate operator/admin control-plane context | Global-only action denial for tenant admins |
| Gateway API | Gateway key contract | Gateway request boundary | `X-SupremeAI-Key`; never treated as user identity | 401/403/429 and key-scope tests |
| Companion clients | Same approved user contract | Customer tenant only initially | OS-protected session material; no provider keys | Revocation, account switch, deep-link safety |

Frontend guards are UX boundaries only. Every privileged API and mutation must enforce identity, permission, tenant scope, step-up, and audit behavior server-side.

## 3. Route and permission baseline

The Studio router now places `/cockpit` and `/telemetry` behind `ProtectedRoute` and the existing admin UX boundary. Route policy metadata marks both routes as admin/step-up surfaces. This is defense in depth, not proof of backend authorization.

Before privileged UI expansion, execute the following matrix against the deployed service and direct API routes:

| Actor | `/workspace` | `/admin` | `/cockpit`/`/telemetry` | Tenant mutation | Global mutation |
|---|---:|---:|---:|---:|---:|
| Anonymous | Deny | Deny | Deny | Deny | Deny |
| Customer user | Allow own tenant | Deny | Deny | Deny | Deny |
| Tenant admin | Allow own tenant | Allow scoped admin | Deny unless explicitly granted | Allow own tenant | Deny |
| Global operator/admin | Allow as permitted | Allow | Allow after operator/step-up verification | Allow with scope | Allow with explicit confirmation |
| Expired/revoked session | Deny | Deny | Deny | Deny | Deny |

A passing frontend test is not sufficient for any row. Capture direct backend negative and positive evidence before calling a privileged surface production-ready.

## 4. Contract register

Every data-bearing surface must identify its source contract before implementation:

| Surface | Contract required before build | Minimum states |
|---|---|---|
| Auth | Login/register/me, cookie/token mode, expiry and revocation | Loading, invalid, rate-limited, expired, success |
| Workspace/chat | Gateway URL, request schema, streaming/cancel semantics, correlation ID | Empty, queued, running, partial, failed, complete |
| Runs/inbox | Run identity, tenant scope, status lifecycle, approval authority | Empty, stale, denied, expired, complete |
| Admin/control plane | Role, permission, tenant/global scope, step-up, audit result | Preview, confirm, denied, stale, success, rollback |
| Mobile handoff | Short-lived single-use authorization and canonical deep link | Cancel, expired, wrong account, success |
| Health/status | Canonical readiness endpoint and freshness contract | Ready, degraded, unavailable, stale |

No new UI should display realistic activity, usage, billing, quota, or integration data without an identified endpoint and freshness/error contract.

## 5. Implementation sequence

### Phase 0 — contract and boundary gate

1. Maintain the monorepo as the implementation SSOT.
2. Keep the Studio route and permission inventory synchronized with actual routes.
3. Verify privileged route/API authorization with direct negative and positive tests.
4. Confirm canonical gateway/readiness endpoints and environment configuration.
5. Run dependency and syntax gates in CI from the real package locations.

### Phase 1 — Studio and auth foundation

1. Preserve the customer workspace as the primary product surface.
2. Keep internal cockpit routes authenticated and admin-gated in the UI.
3. Remove unsupported primary CTAs and label staged capabilities.
4. Complete auth expiry, logout, account-switch, and recovery contract work only when backend endpoints exist.
5. Add accessible loading, empty, denied, degraded, and retry states without fabricating data.

### Deferred lanes

Mobile APK, Windows EXE/Tauri, and VSIX implementation remain deferred until the backend/session contract, platform source, reproducible build, secure storage, signing/distribution, and smoke evidence are available. Do not add placeholder approvals, agent controls, or privileged operations to companion clients.

## 6. Release gates

A cross-platform release may claim availability only when all applicable evidence exists:

- Source and branch identity are recorded.
- Auth/session and permission contracts are versioned or referenced.
- Production dependency audit is clean: `pnpm audit --prod` in `studio` and `poetry check` in `core`.
- Route and endpoint authorization tests cover anonymous, customer, tenant-admin, global-admin/operator, and revoked-session cases.
- Tenant isolation, backup/restore, authenticated chat E2E, browser/accessibility, rollback, and capacity evidence are attached where applicable.
- Native artifacts are reproducibly built, signed, and smoke-tested before APK/EXE/VSIX claims.

## 7. Non-goals for this cycle

- No retired satellite-repository recovery work.
- No provider credentials in browser, mobile, desktop, or VSIX clients.
- No raw bearer tokens in URLs, deep links, logs, analytics, or clipboard.
- No invented billing, quota, tenant, plan, recovery, approval, or run APIs.
- No claim that a route, package, README, or build script proves a deployed feature.
