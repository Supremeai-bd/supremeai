import { resolveServiceTarget, resolveServiceIdentity } from "./service_manifest.js";
import { getHealth as getSupabaseHealth, getDatabaseSchema } from "../adapters/supabase/index.js";
import { type EvidenceCheck, type EvidenceStatus, fact, confidenceFor } from "./evidence.js";

export type DependencyType = "internal_service" | "database" | "cache" | "external_provider";

export interface ServiceDependency {
  id: string;
  name: string;
  type: DependencyType;
  critical: boolean;
  healthEndpoint?: string;
}

export interface DependencyProbeResult {
  id: string;
  name: string;
  type: DependencyType;
  critical: boolean;
  status: EvidenceStatus;
  latencyMs?: number;
  error?: string;
  details?: Record<string, unknown>;
}

export interface ServiceDependencyReport {
  service: string;
  overallStatus: EvidenceStatus;
  dependencies: DependencyProbeResult[];
  impactedDownstreamServices: string[];
}

/**
 * Authoritative system dependency topology across the Pure 2-Repository architecture.
 * Maps upstream dependencies for every service in the monorepo.
 */
export const SERVICE_TOPOLOGY_MAP: Record<string, ServiceDependency[]> = {
  api: [
    { id: "supabase", name: "Supabase PostgREST & Database", type: "database", critical: true },
    { id: "redis", name: "Redis Cache & PubSub", type: "cache", critical: false },
    { id: "core", name: "Primary Core Runtime Node", type: "internal_service", critical: false },
    { id: "infisical", name: "Infisical Secret Vault", type: "external_provider", critical: false },
    { id: "render", name: "Render Cloud Hosting", type: "external_provider", critical: true },
  ],
  "backend-api": [
    { id: "supabase", name: "Supabase PostgREST & Database", type: "database", critical: true },
    { id: "redis", name: "Redis Cache & PubSub", type: "cache", critical: false },
    { id: "core", name: "Primary Core Runtime Node", type: "internal_service", critical: false },
    { id: "infisical", name: "Infisical Secret Vault", type: "external_provider", critical: false },
    { id: "render", name: "Render Cloud Hosting", type: "external_provider", critical: true },
  ],
  core: [
    { id: "supabase", name: "Supabase PostgREST & Database", type: "database", critical: true },
    { id: "brain", name: "Dedicated Tiny AI Brain Node", type: "internal_service", critical: false },
  ],
  worker: [
    { id: "supabase", name: "Supabase PostgREST & Database", type: "database", critical: true },
    { id: "core", name: "Primary Core Runtime Node", type: "internal_service", critical: true },
  ],
  scraper: [
    { id: "api", name: "Public Gateway", type: "internal_service", critical: false },
  ],
  brain: [
    { id: "core", name: "Primary Core Runtime Node", type: "internal_service", critical: false },
  ],
  mcp: [
    { id: "render", name: "Render Cloud API Provider", type: "external_provider", critical: true },
    { id: "github", name: "GitHub API & Actions Provider", type: "external_provider", critical: true },
    { id: "supabase", name: "Supabase PostgREST & Database", type: "database", critical: false },
  ],
  frontend: [
    { id: "api", name: "Public API Gateway", type: "internal_service", critical: true },
    { id: "cloudflare", name: "Studio Edge Proxy", type: "internal_service", critical: false },
  ],
  cloudflare: [
    { id: "frontend", name: "SupremeAI Studio", type: "internal_service", critical: false },
    { id: "api", name: "Public API Gateway", type: "internal_service", critical: false },
  ],
  "ci-runner": [
    { id: "github", name: "GitHub Repository & Actions", type: "external_provider", critical: true },
  ],
};

/**
 * Find all services that depend on the given service (downstream impact).
 */
export function getDownstreamServices(serviceName: string): string[] {
  const downstream: string[] = [];
  for (const [svc, deps] of Object.entries(SERVICE_TOPOLOGY_MAP)) {
    if (deps.some((d) => d.id === serviceName)) {
      downstream.push(svc);
    }
  }
  return downstream;
}

/**
 * Probe a single dependency with fail-closed semantics.
 */
export async function probeDependency(dep: ServiceDependency): Promise<DependencyProbeResult> {
  const start = Date.now();

  if (dep.type === "database" && dep.id === "supabase") {
    try {
      const health = await getSupabaseHealth("supabase-primary");
      const isHealthy = health && typeof health === "object" && (health as any).status === "healthy";
      return {
        id: dep.id,
        name: dep.name,
        type: dep.type,
        critical: dep.critical,
        status: isHealthy ? "pass" : "fail",
        latencyMs: Date.now() - start,
        details: health as Record<string, unknown>,
      };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      const isUnconfigured = msg.includes("not found") || msg.includes("Missing Supabase") || msg.includes("not configured");
      return {
        id: dep.id,
        name: dep.name,
        type: dep.type,
        critical: dep.critical,
        status: isUnconfigured ? "unknown" : "fail",
        latencyMs: Date.now() - start,
        error: msg,
      };
    }
  }

  if (dep.type === "internal_service") {
    const identity = resolveServiceIdentity(dep.id);
    if (!identity || !identity.verified) {
      return {
        id: dep.id,
        name: dep.name,
        type: dep.type,
        critical: dep.critical,
        status: "unknown",
        latencyMs: Date.now() - start,
        error: `configuration_error: ${identity?.verificationError ?? "service identity not verified"}`,
      };
    }
    const target = resolveServiceTarget(dep.id);
    if (!target || !target.runtimeUrl) {
      return {
        id: dep.id,
        name: dep.name,
        type: dep.type,
        critical: dep.critical,
        status: "unknown",
        latencyMs: Date.now() - start,
        error: `No runtime URL configured for service: ${dep.id}`,
      };
    }

    try {
      const url = `${target.runtimeUrl.replace(/\/$/, "")}${target.healthPath}`;
      const res = await fetch(url, {
        headers: { Accept: "application/json, text/plain, */*" },
        signal: AbortSignal.timeout(4_000),
      });

      return {
        id: dep.id,
        name: dep.name,
        type: dep.type,
        critical: dep.critical,
        status: res.status < 400 ? "pass" : "fail",
        latencyMs: Date.now() - start,
        details: { httpStatus: res.status, url },
        error: res.status >= 400 ? `HTTP ${res.status}` : undefined,
      };
    } catch (err) {
      return {
        id: dep.id,
        name: dep.name,
        type: dep.type,
        critical: dep.critical,
        status: "fail",
        latencyMs: Date.now() - start,
        error: err instanceof Error ? err.message : String(err),
      };
    }
  }

  if (dep.type === "cache" && dep.id === "redis") {
    try {
      const { pingRedis } = await import("../adapters/redis/index.js");
      const res = (await pingRedis()) as any;
      const normalizedStatus = String(res?.status ?? "").toUpperCase();
      const normalizedProbe = String(res?.probe ?? res?.ping ?? "").toUpperCase();
      const isHealthy =
        normalizedStatus === "HEALTHY" ||
        normalizedStatus === "PASS" ||
        normalizedStatus === "PONG" ||
        normalizedProbe === "PONG" ||
        normalizedProbe.includes("PONG") ||
        res?.ok === true ||
        res?.pong === true;
      return {
        id: dep.id,
        name: dep.name,
        type: dep.type,
        critical: dep.critical,
        status: isHealthy ? "pass" : "fail",
        latencyMs: res?.latencyMs ?? (Date.now() - start),
        details: typeof res === "object" ? res : { response: res },
        error: isHealthy ? undefined : `Redis ping returned non-healthy response (${res?.status || res?.probe || "failed"})`,
      };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      const isUnconfigured = msg.includes("not configured") || msg.includes("Missing Redis");
      return {
        id: dep.id,
        name: dep.name,
        type: dep.type,
        critical: dep.critical,
        status: isUnconfigured ? "unknown" : "fail",
        latencyMs: Date.now() - start,
        error: msg,
      };
    }
  }

  if (dep.type === "external_provider") {
    // External providers are only "pass" when their credentials are configured.
    // Otherwise report unknown (no evidence) rather than a false green.
    const envKeyMap: Record<string, string> = {
      render: "RENDER_API_KEY",
      github: "GITHUB_TOKEN",
      supabase: "SUPABASE_URL",
      infisical: "INFISICAL_TOKEN",
    };
    const requiredKey = envKeyMap[dep.id];
    let configured = requiredKey ? Boolean(process.env[requiredKey]) : false;
    if (dep.id === "infisical" && !configured) {
      configured = Boolean(process.env["INFISICAL_CLIENT_SECRET"] || process.env["INFISICAL_CLIENT_ID"]);
    }
    return {
      id: dep.id,
      name: dep.name,
      type: dep.type,
      critical: dep.critical,
      status: configured ? "pass" : "unknown",
      latencyMs: Date.now() - start,
      details: { role: "external_provider", credentialConfigured: configured, requiredEnv: requiredKey ?? null },
      ...(configured ? {} : { error: `Missing ${requiredKey ?? "credentials"} for ${dep.id}` }),
    };
  }

  return {
    id: dep.id,
    name: dep.name,
    type: dep.type,
    critical: dep.critical,
    status: "unknown",
    latencyMs: Date.now() - start,
    error: `Unsupported dependency type: ${dep.type}`,
  };
}

/**
 * Concurrently probe all dependencies for a given service.
 */
export async function probeServiceDependencies(serviceName: string): Promise<ServiceDependencyReport> {
  const resolved = resolveServiceTarget(serviceName);
  const normalizedKey = resolved?.name || serviceName;
  const deps = SERVICE_TOPOLOGY_MAP[normalizedKey] ?? SERVICE_TOPOLOGY_MAP[serviceName] ?? [];
  const downstream = getDownstreamServices(normalizedKey);

  if (deps.length === 0) {
    return {
      service: serviceName,
      overallStatus: "pass",
      dependencies: [],
      impactedDownstreamServices: downstream,
    };
  }

  const results = await Promise.allSettled(deps.map((d) => probeDependency(d)));

  const probed: DependencyProbeResult[] = results.map((r, i) => {
    if (r.status === "fulfilled") return r.value;
    return {
      id: deps[i].id,
      name: deps[i].name,
      type: deps[i].type,
      critical: deps[i].critical,
      status: "error",
      error: r.reason instanceof Error ? r.reason.message : String(r.reason),
    };
  });

  // Calculate overall status:
  // - Any critical dependency failure -> "fail"
  // - Any non-critical dependency failure -> "fail" (or "degraded")
  // - Any unknown with no failures -> "unknown"
  // - All pass -> "pass"
  let overallStatus: EvidenceStatus = "pass";
  if (probed.some((p) => p.status === "fail" || p.status === "error")) {
    overallStatus = "fail";
  } else if (probed.some((p) => p.status === "unknown")) {
    overallStatus = "unknown";
  }

  return {
    service: serviceName,
    overallStatus,
    dependencies: probed,
    impactedDownstreamServices: downstream,
  };
}

/**
 * Probe database schema parity against expected core entities.
 * Detects SCHEMA_BEHIND_CODE when required tables are missing.
 */
export async function probeSchemaParity(serviceName: string): Promise<EvidenceCheck> {
  const deps = SERVICE_TOPOLOGY_MAP[serviceName] ?? [];
  const hasDbDep = deps.some((d) => d.type === "database");

  if (!hasDbDep) {
    return {
      name: "schema_parity",
      status: "pass",
      confidence: 0.95,
      facts: [fact("service_topology", "pass", { reason: "Service has no database dependencies" })],
      explanation: "Service does not consume database schema.",
      details: { service: serviceName, hasDatabase: false },
    };
  }

  let projectRef = "unknown";
  try {
    const { env } = await import("../lib/env.js");
    if (env.supabase.url) projectRef = new URL(env.supabase.url).hostname.split(".")[0];
  } catch {
    // ignore
  }

  try {
    const schema = (await getDatabaseSchema("supabase-primary")) as { tables?: string[] };
    const tables = schema && Array.isArray(schema.tables) ? schema.tables : [];

    if (tables.length === 0) {
      // Supabase reachable, but public schema has 0 exposed tables or credential cannot list schemas.
      // Distinguish: Supabase HTTP 200 != correct project != migration parity.
      // Do NOT conclude SCHEMA_BEHIND_CODE when project or schema target is unverified.
      return {
        name: "schema_parity",
        status: "unknown",
        confidence: 0.2,
        facts: [fact("supabase.schema", "unknown", { tablesCount: 0, projectRef })],
        explanation: `Supabase PostgREST returned 0 exposed tables for project '${projectRef}'. Schema verification is inconclusive without explicit database inspection.`,
        details: {
          tablesFound: 0,
          reason: "No exposed tables returned by PostgREST schema introspection",
          projectRef,
          accountId: "supabase-primary",
          verificationNote: "Supabase connectivity healthy != correct database project != migration parity. Verify SUPABASE_URL project ref matches expected target before running migrations.",
        },
      };
    }

    // Core expected tables across SupremeAI data model
    const expectedCoreTables = ["tasks", "audit_logs", "agent_sessions", "system_events"];
    const missing = expectedCoreTables.filter((t) => !tables.includes(t));

    const status: EvidenceStatus = missing.length > 0 ? "fail" : "pass";
    const facts = [
      fact("supabase.schema", status, { tablesFound: tables.length, missingCoreTables: missing, projectRef }),
    ];

    return {
      name: "schema_parity",
      status,
      confidence: confidenceFor(status, facts),
      facts,
      explanation: missing.length > 0
        ? `Schema is missing core tables: ${missing.join(", ")}`
        : "Database schema parity verified with core application models.",
      details: {
        totalTables: tables.length,
        missingCoreTables: missing,
        tablesSample: tables.slice(0, 10),
        projectRef,
      },
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    const isUnconfigured = msg.includes("not found") || msg.includes("Missing Supabase") || msg.includes("not configured");
    const isPermission = /401|403|permission|unauthorized|forbidden|invalid api key/i.test(msg);
    const status: EvidenceStatus = isUnconfigured || isPermission ? "unknown" : "fail";

    return {
      name: "schema_parity",
      status,
      confidence: 0.1,
      facts: [fact("supabase.schema", status, { projectRef }, msg)],
      explanation: isUnconfigured
        ? `Supabase credentials unconfigured for project '${projectRef}' (unverified).`
        : isPermission
          ? `Supabase schema inspection unauthorized for project '${projectRef}'. Verify SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY.`
          : `Database schema inspection failed: ${msg}`,
      details: {
        error: msg,
        unconfigured: isUnconfigured,
        permissionDenied: isPermission,
        accountId: "supabase-primary",
        projectRef,
        reason: isPermission ? "SUPABASE_CREDENTIAL_UNVERIFIED" : "SUPABASE_SCHEMA_PROBE_ERROR",
      },
    };
  }
}
