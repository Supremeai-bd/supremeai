# Canonical Control Plane

This document records the migration boundary for the user/admin simplification work.

## Frontend authorities

| Concern | Canonical authority | Compatibility rule |
| --- | --- | --- |
| Identity and session | `frontend/src/store/authStore.ts` | Do not read role from URL or ad-hoc storage keys. |
| Admin step-up | `frontend/src/store/adminStore.ts` | Keep separate from regular user session until backend unification is complete. |
| Route UX policy | `frontend/src/auth/routePolicies.ts` | Backend authorization remains final. |
| Visible navigation | `frontend/src/config/navigationRegistry.ts` | Deprecated advanced routes remain routable but are not shown in core user navigation. |
| Command access | `frontend/src/config/commandRegistry.ts` | Commands are filtered by runtime portal context. |
| User shell | `frontend/src/components/layout/WorkspaceLayout.tsx` | Routes through `UnifiedAppShell`. |
| Shared UI state | `frontend/src/hooks/useWorkspaceSettings.ts` | Do not create another sidebar/settings store. |
| Server data | TanStack Query hooks | Do not mirror query data into Zustand without a documented reason. |

## User information architecture

Core user navigation exposes workspace, AI studio, agents, skills, integrations, marketplace, usage, billing, profile, code editor, and settings. Swarm, evolution, architect tower, and similar operational surfaces remain available only through compatibility URLs while their ownership is reviewed.

## Admin information architecture

The admin portal remains the privileged control plane. Operations, security, governance, and core canvas are grouped through the canonical navigation registry and retain server-side RBAC, tenant isolation, step-up authentication, approval checks, and audit requirements.

## Backend migration rule

Existing API route files are not deleted in bulk. Future consolidation must assign each route to one domain owner: identity, tenant, capability, agents, execution, memory, integrations, billing, security, operations, or audit. Duplicate dependencies must migrate to the canonical authentication, tenant-context, authorization, risk/approval, and audit path before removal.
