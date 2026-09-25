import { createHash, randomBytes, timingSafeEqual } from "node:crypto";
import { env } from "../lib/env.js";
import type { UserRole } from "./auth.context.js";
import { createClientRegistryStore, type PersistedClientRecord } from "./client-registry.store.js";

export type ClientRole = UserRole;
export type ClientProtocol = "streamable-http" | "sse" | "stdio" | "custom";
export type ClientStatus = "pending" | "active" | "revoked" | "expired";

export interface ExternalClient {
  id: string;
  /** Owner tenant. Каждый admin/customer видит только своих клиентов. */
  tenantId: string;
  name: string;
  provider: string;
  protocol: ClientProtocol;
  role: ClientRole;
  scopes: string[];
  createdAt: string;
  updatedAt: string;
  expiresAt?: string;
  lastSeenAt?: string;
  status: ClientStatus;
}

interface StoredClient extends ExternalClient { tokenHash: string; }

const clients = new Map<string, StoredClient>();
const registryStore = createClientRegistryStore(process.env.MCP_CLIENT_REGISTRY_FILE);
for (const record of registryStore.load()) clients.set(record.id, record as StoredClient);
const digest = (value: string) => createHash("sha256").update(value).digest("hex");

/**
 * Timing-safe equality for token-hash comparison (#698). Both sides are
 * fixed-length sha256 hex digests; the length guard keeps timingSafeEqual from
 * throwing if a stored hash were ever corrupt/short.
 */
function digestEquals(a: string, b: string): boolean {
  const ab = Buffer.from(a, "utf8");
  const bb = Buffer.from(b, "utf8");
  return ab.length === bb.length && timingSafeEqual(ab, bb);
}

const persist = () => registryStore.save([...clients.values()].map((client) => ({ ...client })) as PersistedClientRecord[]);

export function registerClient(
  name: string,
  role: ClientRole = "viewer",
  scopes: string[] = [],
  expiresAt?: string,
  provider = "generic",
  protocol: ClientProtocol = "streamable-http",
  tenantId = "tenant_default",
  customId?: string
) {
  const token = `mcp_${randomBytes(32).toString("base64url")}`;
  const now = new Date().toISOString();
  let id = customId?.trim();
  if (id) {
    if (clients.has(id)) {
      throw new Error(`Client ID '${id}' is already registered`);
    }
  } else {
    id = `client_${randomBytes(10).toString("hex")}`;
  }
  const client: StoredClient = { id, tenantId, name, provider, protocol, role, scopes, createdAt: now, updatedAt: now, expiresAt, status: "pending", tokenHash: digest(token) };
  clients.set(client.id, client);
  persist();
  return { client: sanitize(client), token };
}

export function deleteClient(id: string, tenantId?: string): boolean {
  const client = clients.get(id);
  assertTenantScope(client, tenantId);
  if (!client) return false;
  const removed = clients.delete(id);
  persist();
  return removed;
}


export function resolveClient(token: string): ExternalClient | undefined {
  // #698: timing-safe token-hash comparison (no early-exit string equality).
  const tokenDigest = digest(token);
  const match = [...clients.values()].find((client) => digestEquals(client.tokenHash, tokenDigest));
  if (!match || match.status !== "active") return undefined;
  if (match.expiresAt && Date.parse(match.expiresAt) <= Date.now()) { match.status = "expired"; persist(); return undefined; }
  match.lastSeenAt = new Date().toISOString();
  match.updatedAt = match.lastSeenAt;
  persist();
  return sanitize(match);
}

/** Tenant isolation: global admin видит всех, tenant admin — только своих. */
export function listClients(tenantId?: string, includeRevoked = false) {
  const scope = tenantId ?? "*";
  return [...clients.values()]
    .filter((client) => (scope === "*" || client.tenantId === scope) && (includeRevoked || client.status !== "revoked"))
    .map(sanitize);
}

export function countClientsByTenant(tenantId: string): number {
  return [...clients.values()].filter((client) => client.tenantId === tenantId && client.status !== "revoked").length;
}

function assertTenantScope(client: StoredClient | undefined, tenantId?: string): void {
  if (!tenantId || tenantId === "*") return; // global admin
  if (!client) return;
  if (client.tenantId !== tenantId) throw new Error("Forbidden: client belongs to another tenant");
}

export function approveClient(id: string, tenantId?: string) {
  const client = clients.get(id);
  assertTenantScope(client, tenantId);
  if (!client || client.status !== "pending") return undefined;
  client.status = "active";
  client.updatedAt = new Date().toISOString();
  persist();
  return sanitize(client);
}

export function changeClientRole(id: string, role: ClientRole, tenantId?: string) {
  const client = clients.get(id);
  assertTenantScope(client, tenantId);
  if (!client || client.status === "revoked" || client.status === "expired") return undefined;
  client.role = role;
  client.scopes = defaultClientScopes(role);
  client.updatedAt = new Date().toISOString();
  persist();
  return sanitize(client);
}

export function changeClientProvider(id: string, provider: string, tenantId?: string) {
  const client = clients.get(id);
  assertTenantScope(client, tenantId);
  if (!client) return undefined;
  client.provider = provider;
  client.updatedAt = new Date().toISOString();
  persist();
  return sanitize(client);
}

export function revokeClient(id: string, tenantId?: string) {
  const client = clients.get(id);
  assertTenantScope(client, tenantId);
  if (!client) return false;
  client.status = "revoked";
  client.updatedAt = new Date().toISOString();
  persist();
  return true;
}

export function rotateClient(id: string, tenantId?: string) {
  const client = clients.get(id);
  assertTenantScope(client, tenantId);
  if (!client || client.status !== "active") return undefined;
  const token = `mcp_${randomBytes(32).toString("base64url")}`;
  client.tokenHash = digest(token);
  client.updatedAt = new Date().toISOString();
  persist();
  return { client: sanitize(client), token };
}

export function hasClientRegistry() { return Boolean(env.mcpAdminKey); }
function sanitize(client: StoredClient): ExternalClient { const { tokenHash: _tokenHash, ...safe } = client; return safe; }

export function defaultClientScopes(role: ClientRole): string[] {
  if (role === "viewer") return ["health:read", "system:read", "audit:read"];
  if (role === "agent") return ["health:read", "system:read", "audit:read", "tools:execute", "approvals:request"];
  return ["*"];
}

export function roleAllows(role: ClientRole, required: "viewer" | "agent" | "admin") {
  return role === "admin" || role === required || (role === "agent" && required === "viewer");
}

export function scopeAllows(scopes: string[], required: string) { return scopes.includes("*") || scopes.includes(required); }
