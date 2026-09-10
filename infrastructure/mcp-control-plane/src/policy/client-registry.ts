import { createHash, randomBytes } from "node:crypto";
import { env } from "../lib/env.js";
import type { UserRole } from "./auth.context.js";
import { createClientRegistryStore, type PersistedClientRecord } from "./client-registry.store.js";

export type ClientRole = UserRole;
export type ClientProtocol = "streamable-http" | "sse" | "stdio" | "custom";
export type ClientStatus = "pending" | "active" | "revoked" | "expired";

export interface ExternalClient {
  id: string;
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
const persist = () => registryStore.save([...clients.values()].map((client) => ({ ...client })) as PersistedClientRecord[]);

export function registerClient(name: string, role: ClientRole = "viewer", scopes: string[] = [], expiresAt?: string, provider = "generic", protocol: ClientProtocol = "streamable-http") {
  const token = `mcp_${randomBytes(32).toString("base64url")}`;
  const now = new Date().toISOString();
  const client: StoredClient = { id: `client_${randomBytes(10).toString("hex")}`, name, provider, protocol, role, scopes, createdAt: now, updatedAt: now, expiresAt, status: "pending", tokenHash: digest(token) };
  clients.set(client.id, client);
  persist();
  return { client: sanitize(client), token };
}

export function resolveClient(token: string): ExternalClient | undefined {
  const match = [...clients.values()].find((client) => client.tokenHash === digest(token));
  if (!match || match.status !== "active") return undefined;
  if (match.expiresAt && Date.parse(match.expiresAt) <= Date.now()) { match.status = "expired"; persist(); return undefined; }
  match.lastSeenAt = new Date().toISOString();
  match.updatedAt = match.lastSeenAt;
  persist();
  return sanitize(match);
}

export function listClients() { return [...clients.values()].map(sanitize); }
export function approveClient(id: string) { const client = clients.get(id); if (!client || client.status !== "pending") return undefined; client.status = "active"; client.updatedAt = new Date().toISOString(); persist(); return sanitize(client); }
export function changeClientRole(id: string, role: ClientRole) { const client = clients.get(id); if (!client || client.status === "revoked" || client.status === "expired") return undefined; client.role = role; client.scopes = defaultClientScopes(role); client.updatedAt = new Date().toISOString(); persist(); return sanitize(client); }
export function revokeClient(id: string) { const client = clients.get(id); if (!client) return false; client.status = "revoked"; client.updatedAt = new Date().toISOString(); persist(); return true; }
export function rotateClient(id: string) { const client = clients.get(id); if (!client || client.status !== "active") return undefined; const token = `mcp_${randomBytes(32).toString("base64url")}`; client.tokenHash = digest(token); client.updatedAt = new Date().toISOString(); persist(); return { client: sanitize(client), token }; }
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
