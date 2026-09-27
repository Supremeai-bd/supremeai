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
 * Boot-time hydration (#1421). Runs AFTER the Infisical secrets pull so the
 * Upstash chain env (service env + vault imports) is fully populated, then:
 *  1. hydrates the in-memory map from the store (network-backed stores fetch
 *     the authoritative copy here),
 *  2. optionally seeds well-known infrastructure clients from
 *     `MCP_CLIENT_SEEDS_JSON` (declarative re-creation without manual
 *     register+approve round-trips) — array of
 *     `{id, name, role, token, provider?, protocol?, scopes?, tenantId?, status?, expiresAt?}`,
 *  3. logs which backend is active — LOUD warning when memory-only in
 *     production, because registrations would be lost on restart/redeploy.
 */
export async function initClientRegistry(): Promise<{ backend: string; loaded: number; seeded: number }> {
  let loaded = 0;
  try {
    const records = typeof registryStore.loadAsync === "function" ? await registryStore.loadAsync() : registryStore.load();
    clients.clear();
    for (const record of records) clients.set(record.id, record as StoredClient);
    loaded = records.length;
  } catch (err) {
    console.error(`[client-registry] hydration FAILED (${err instanceof Error ? err.message : String(err)}) — continuing with current snapshot`);
  }

  let seeded = 0;
  const seedsRaw = process.env.MCP_CLIENT_SEEDS_JSON;
  if (seedsRaw) {
    try {
      const seeds = JSON.parse(seedsRaw) as Array<Record<string, unknown>>;
      if (!Array.isArray(seeds)) throw new Error("MCP_CLIENT_SEEDS_JSON must be an array");
      for (const seed of seeds) {
        const id = typeof seed.id === "string" ? seed.id.trim() : "";
        const name = typeof seed.name === "string" ? seed.name : "";
        const token = typeof seed.token === "string" ? seed.token : "";
        const role = (typeof seed.role === "string" ? seed.role : "viewer") as ClientRole;
        if (!id || !name || !token || clients.has(id)) continue;
        const now = new Date().toISOString();
        clients.set(id, {
          id,
          tenantId: typeof seed.tenantId === "string" ? seed.tenantId : "tenant_default",
          name,
          provider: typeof seed.provider === "string" ? seed.provider : "generic",
          protocol: (typeof seed.protocol === "string" ? seed.protocol : "streamable-http") as ClientProtocol,
          role,
          scopes: Array.isArray(seed.scopes) ? (seed.scopes as string[]) : defaultClientScopes(role),
          createdAt: now,
          updatedAt: now,
          expiresAt: typeof seed.expiresAt === "string" ? seed.expiresAt : undefined,
          status: (typeof seed.status === "string" ? seed.status : "active") as ClientStatus,
          tokenHash: digest(token),
        });
        seeded += 1;
      }
    } catch (err) {
      console.error(`[client-registry] seed parsing FAILED (${err instanceof Error ? err.message : String(err)})`);
    }
    if (seeded > 0) persist();
  }

  const backend = registryStore.backend || "memory";
  if (backend === "memory" && process.env.NODE_ENV === "production") {
    console.error("[client-registry] ⚠️  MEMORY-BACKED registry in production — client registrations WILL BE LOST on restart/redeploy. Provide Upstash chain env or set MCP_CLIENT_REGISTRY_FILE.");
  } else {
    console.error(`[client-registry] backend=${backend} clients=${clients.size}${seeded > 0 ? ` seeded=${seeded}` : ""}`);
  }
  return { backend, loaded, seeded };
}

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

export function getClient(id: string): ExternalClient | undefined {
  const match = clients.get(id);
  return match ? sanitize(match) : undefined;
}

/**
 * Dynamic auto-registration for no-auth AI clients (#1767).
 * When an external AI connects via No Auth, this creates or reuses an active guest record
 * in the database registry so it can be viewed and upgraded dynamically by admins.
 *
 * AUDIT-FIX (#1787 Gap 3): আগে শুধু preferredId (IP-based `guest_<provider>_<ip>`)
 * দিয়ে duplicate check করা হতো। কিন্তু দুটো আলাদা IP থেকে একই name দিয়ে
 * দুটো guest client register হতে পারত — যা admin-এর জন্য বিভ্রান্তিকর। এখন
 * name-based duplicate check যোগ করা হয়েছে: যদি একই name-এ কোনো existing
 * client থাকে, সেটি reuse করা হয় (preferredId যাই হোক না কেন)।
 */
export function getOrCreateGuestClient(
  preferredId: string,
  name: string,
  provider = "generic",
  protocol: ClientProtocol = "sse",
  tenantId = "tenant_default"
): ExternalClient {
  // AUDIT-FIX (#1787 Gap 3): name-based duplicate check.
  // প্রথমে preferredId দিয়ে দেখি (fast path)। না থাকলে name দিয়ে দেখি —
  // যদি name match করে, সেই existing client reuse করি (id যাই হোক)।
  const existingById = clients.get(preferredId);
  if (existingById) {
    existingById.lastSeenAt = new Date().toISOString();
    existingById.updatedAt = existingById.lastSeenAt;
    persist();
    return sanitize(existingById);
  }

  // AUDIT-FIX (#1787): name-based lookup — একই name-এ আরেকটা client থাকলে
  // সেটি reuse করি, নতুন entry তৈরি করি না। এতে admin dashboard-এ একই
  // AI এর জন্য duplicate rows দেখা যাবে না।
  const existingByName = [...clients.values()].find(
    (c) => c.name === name && c.tenantId === tenantId
  );
  if (existingByName) {
    existingByName.lastSeenAt = new Date().toISOString();
    existingByName.updatedAt = existingByName.lastSeenAt;
    persist();
    return sanitize(existingByName);
  }

  // AUDIT-FIX (#2030): Name auto-increment — if "z.ai" is taken, try "z.ai-2", "z.ai-3", etc.
  // This lets agents connect with a simple base name and get a unique identity automatically.
  let finalName = name;
  let counter = 2;
  while ([...clients.values()].some((c) => c.name === finalName && c.tenantId === tenantId)) {
    finalName = `${name}-${counter}`;
    counter++;
  }

  const token = `mcp_${randomBytes(32).toString("base64url")}`;
  const now = new Date().toISOString();
  const client: StoredClient = {
    id: preferredId,
    tenantId,
    name: finalName,  // AUDIT-FIX (#2030): use auto-incremented name
    provider,
    protocol,
    role: "viewer",
    scopes: defaultClientScopes("viewer"),
    createdAt: now,
    updatedAt: now,
    status: "active",
    tokenHash: digest(token),
  };
  clients.set(client.id, client);
  persist();
  return sanitize(client);
}
