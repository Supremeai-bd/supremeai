import { AsyncLocalStorage } from "node:async_hooks";
import type { ToolProfile } from "./tool-visibility.js";

// #110 & #474: Canonical 4-Tier RBAC Ladder
// Consolidated from legacy 6 tiers to 4 clean roles:
// 1. viewer (Rank 0) — strictly public observability & read-only tools
// 2. agent (Rank 1) — autonomous work-order claiming, reflection & bridge PR submission
// 3. admin (Rank 2) — infrastructure management, deployments & slot provisioning
// 4. supremeadmin (Rank 3) — secret rotation, kill-switches & policy overrides
export type UserRole =
  | "supremeadmin"
  | "admin"
  | "agent"
  | "viewer"
  | "repo_viewer" // backward-compatibility alias mapped to viewer
  | "restricted_viewer"; // backward-compatibility alias mapped to viewer

export const ROLE_RANK: Readonly<Record<UserRole, number>> = {
  viewer: 0,
  restricted_viewer: 0,
  repo_viewer: 0,
  agent: 1,
  admin: 2,
  supremeadmin: 3,
} as const;

/** #110: rank accessor with fail-closed viewer default. */
export function roleRank(role: UserRole | undefined | null): number {
  return role ? (ROLE_RANK[role] ?? 0) : 0;
}

export type AccessMode = "public_viewer" | UserRole;

export interface RequestContext {
  role: UserRole;
  accessMode?: AccessMode;
  authenticated?: boolean;
  tenantBound?: boolean;
  requestId?: string;
  clientId?: string;
  scopes?: string[];
  /** Owner tenant of the current caller (client/tenant-admin). */
  tenantId?: string;
  /** True only for the global SupremeAI admin (MCP_ADMIN_KEY). */
  isGlobalAdmin?: boolean;
  /** Tenant type (admin vs customer). */
  tenantType?: "admin" | "customer";
  /**
   * Verified Slot Architecture (#48): slot / registry-client identity bound
   * to this request. Set for credential-verified sessions only.
   */
  slotId?: string;
  /** True only when the slot credential verified against the live registry. */
  slotVerified?: boolean;
  /** Audit-safe credential fingerprint (never the raw credential). */
  credentialId?: string;
  /**
   * Tool Exposure Policy: the client's curated tool-surface profile. Absent
   * or undefined = full RBAC surface (no discovery filtering beyond RBAC).
   * Derived from the registry client record at every transport entry point.
   */
  toolProfile?: ToolProfile;
}

const asyncLocalStorage = new AsyncLocalStorage<RequestContext>();

/**
 * Options for RequestContextStore.getRole().
 */
export interface GetRoleOptions {
  /**
   * Explicit opt-in for genuinely trusted, transport-internal call paths
   * (stdio). HTTP request paths must NEVER pass this — they always run inside
   * a RequestContextStore carrying the caller's real role (#698). The stdio
   * entry point (index.ts startStdioServer) establishes an explicit admin
   * context per inbound message instead of relying on this flag.
   */
  trustedInternal?: boolean;
}

export const RequestContextStore = {
  run<T>(context: RequestContext, fn: () => T): T {
    return asyncLocalStorage.run(context, fn);
  },

  get(): RequestContext | undefined {
    return asyncLocalStorage.getStore();
  },

  /**
   * SECURITY (#698): fail-CLOSED. When no RequestContextStore exists the
   * caller is NOT a known, trusted transport — return "viewer" (which denies
   * privileged operations: action execution, tenant management, approvals)
   * instead of the old fail-open "admin" default. Genuinely trusted internal
   * paths must opt in explicitly via { trustedInternal: true }.
   */
  getRole(options?: GetRoleOptions): UserRole {
    const store = asyncLocalStorage.getStore();
    if (store) return store.role;
    return options?.trustedInternal === true ? "admin" : "viewer";
  },

  getTenantId(): string | undefined {
    return asyncLocalStorage.getStore()?.tenantId;
  },

  isGlobalAdmin(): boolean {
    return asyncLocalStorage.getStore()?.isGlobalAdmin === true;
  },
};
