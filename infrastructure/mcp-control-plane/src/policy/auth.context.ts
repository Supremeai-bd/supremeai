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

export const RequestContextStore = {
  run<T>(context: RequestContext, fn: () => T): T {
    return asyncLocalStorage.run(context, fn);
  },

  get(): RequestContext | undefined {
    return asyncLocalStorage.getStore();
  },

  getRole(): UserRole {
    return asyncLocalStorage.getStore()?.role ?? "admin"; // Default to admin for stdio/local
  },

  getTenantId(): string | undefined {
    return asyncLocalStorage.getStore()?.tenantId;
  },

  isGlobalAdmin(): boolean {
    return asyncLocalStorage.getStore()?.isGlobalAdmin === true;
  },
};
