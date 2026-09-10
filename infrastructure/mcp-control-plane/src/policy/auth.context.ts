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
};
