import { AsyncLocalStorage } from "node:async_hooks";

export type UserRole = "admin" | "agent" | "viewer";
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
