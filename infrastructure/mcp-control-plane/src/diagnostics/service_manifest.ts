import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { env } from "../lib/env.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "../../../..");

const CANDIDATE_REGISTRY_PATHS = [
  path.join(REPO_ROOT, "config", "service_registry.yaml"),
  path.join(process.cwd(), "config", "service_registry.yaml"),
  path.join(__dirname, "../../../../config", "service_registry.yaml"),
  path.join(__dirname, "../../config", "service_registry.yaml"),
  path.join(__dirname, "../config", "service_registry.yaml"),
  "/app/config/service_registry.yaml",
];

export interface AuthoritativeServiceTarget {
  name: string;
  role: string;
  platform: string;
  renderAccountId: string;
  renderServiceId: string;
  runtimeUrl: string;
  healthPath: string;
  readinessPath: string;
  releasePath: string;
  repo: string;
  branch: string;
  watchPaths?: string[];
  source?: "env" | "registry" | "default";
}

/**
 * Account ID mapping for Render services.
 * Mirrors account.registry.ts Render accounts 1..6 and paykari.
 */
const ACCOUNT_MAP: Record<string, string> = {
  api: "render-api",
  core: "render-primary",
  worker: "render-worker",
  scraper: "render-scraper",
  mcp: "render-mcp",
  brain: "render-brain",
  "ci-runner": "render-ci-runner",
};

/**
 * Environment render object key mapping (e.g. core -> primary, mcp -> controlTower)
 */
const ENV_RENDER_KEY_MAP: Record<string, string> = {
  core: "primary",
  api: "api",
  worker: "worker",
  scraper: "scraper",
  mcp: "controlTower",
  brain: "brain",
  "ci-runner": "ciRunner",
};

/**
 * Embedded SSOT topology defaults.
 * Guarantees containerized runtimes (Docker/Render) resolve canonical URLs, ports,
 * and service IDs even when config/service_registry.yaml is not mounted in the image.
 */
export const CANONICAL_TOPOLOGY_DEFAULTS: Record<string, AuthoritativeServiceTarget> = {
  api: {
    name: "api",
    role: "Public API Gateway & Multi-LLM Provider Router",
    platform: "render",
    renderAccountId: "render-api",
    renderServiceId: env.render.api.serviceId || "srv-dbappass728c7396p580",
    runtimeUrl: env.render.api.url || "https://supremeai-api-ulw0.onrender.com",
    healthPath: "/healthz",
    readinessPath: "/readyz",
    releasePath: "/release",
    repo: "Supremeai-bd/supremeai",
    branch: "main",
    watchPaths: ["gateway/**", "config/routing_policy*", "render.yaml", "scripts/lib/**"],
    source: "default",
  },
  core: {
    name: "core",
    role: "Primary Core Intelligence & Decision Runtime",
    platform: "render",
    renderAccountId: "render-primary",
    renderServiceId: env.render.primary.serviceId || "srv-dau7c9ek1f9s73almn0g",
    runtimeUrl: env.render.primary.url || "https://supremeai-primary-node-5xso.onrender.com",
    healthPath: "/health",
    readinessPath: "/health/ready",
    releasePath: "/release",
    repo: "Supremeai-bd/supremeai",
    branch: "main",
    watchPaths: ["core/**", "backend/**", "requirements*", "pyproject.toml", "Dockerfile", "scripts/lib/**", "scripts/runtime/**"],
    source: "default",
  },
  worker: {
    name: "worker",
    role: "Background Async Task & Webhook Processing Worker",
    platform: "render",
    renderAccountId: "render-worker",
    renderServiceId: env.render.worker.serviceId || "srv-dabm7evqj5pc738jkf30",
    runtimeUrl: env.render.worker.url || "https://supremeai-worker-node.onrender.com",
    healthPath: "/health",
    readinessPath: "/health",
    releasePath: "/release",
    repo: "Supremeai-bd/supremeai",
    branch: "main",
    watchPaths: ["core/**", "render.yaml", "scripts/lib/**"],
    source: "default",
  },
  scraper: {
    name: "scraper",
    role: "Lightweight Stealth Cookie & $0 Web Session Relay",
    platform: "render",
    renderAccountId: "render-scraper",
    renderServiceId: env.render.scraper.serviceId || "srv-dabm7gfqj5pc738jkicg",
    runtimeUrl: env.render.scraper.url || "https://supremeai-scraper-node.onrender.com",
    healthPath: "/health",
    readinessPath: "/health",
    releasePath: "/release",
    repo: "Supremeai-bd/supremeai",
    branch: "main",
    watchPaths: ["browser/**", "core/**", "render.yaml", "scripts/lib/**", "scripts/runtime/**"],
    source: "default",
  },
  mcp: {
    name: "mcp",
    role: "MCP Control Plane & Governed Agent Single Door",
    platform: "render",
    renderAccountId: "render-mcp",
    renderServiceId: env.render.controlTower.serviceId || "srv-dabm7inqj5pc738jkrt0",
    runtimeUrl: env.render.controlTower.url || "https://supremeai-mcp-tower.onrender.com",
    healthPath: "/health",
    readinessPath: "/health",
    releasePath: "/release",
    repo: "Supremeai-bd/supremeai",
    branch: "main",
    watchPaths: ["infrastructure/mcp-control-plane/**", "core/mcp_adapters/**", "mcp.json", "scripts/runtime/**", "render.yaml"],
    source: "default",
  },
  brain: {
    name: "brain",
    role: "Dedicated Tiny AI Brain Node (Qdrant & Small Local Models)",
    platform: "render",
    renderAccountId: "render-brain",
    renderServiceId: env.render.brain.serviceId || "srv-dbirv58ae00c73chgsb0",
    runtimeUrl: env.render.brain.url || "https://supremeai-brain.onrender.com",
    healthPath: "/health",
    readinessPath: "/health",
    releasePath: "/release",
    repo: "Supremeai-bd/supremeai",
    branch: "main",
    watchPaths: ["brain/**", "core/**", "render.yaml", "scripts/lib/**"],
    source: "default",
  },
  "ci-runner": {
    name: "ci-runner",
    role: "Continuous Integration & Autonomous Validation Runner",
    platform: "render",
    renderAccountId: "render-ci-runner",
    renderServiceId: env.render.ciRunner.serviceId || "srv-dbl8tbmtlv9c73bbkvqg",
    runtimeUrl: env.render.ciRunner.url || "https://supremeai-ci-runner.onrender.com",
    healthPath: "/health",
    readinessPath: "/health",
    releasePath: "/release",
    repo: "Supremeai-bd/supremeai",
    branch: "main",
    watchPaths: ["scripts/ci/**", "tests/**", ".github/**", "render.yaml"],
    source: "default",
  },
  frontend: {
    name: "frontend",
    role: "SupremeAI Studio Public Mission Control UI",
    platform: "cloudflare",
    renderAccountId: "none",
    renderServiceId: "",
    runtimeUrl: "https://studio.supremeai.lat",
    healthPath: "/release",
    readinessPath: "/release",
    releasePath: "/release",
    repo: "Supremeai-bd/supremeai",
    branch: "main",
    watchPaths: ["studio/**", "src/**"],
    source: "default",
  },
  cloudflare: {
    name: "cloudflare",
    role: "Global Zero-Trust & Keepwarm Mesh Edge Proxy",
    platform: "cloudflare",
    renderAccountId: "none",
    renderServiceId: "",
    runtimeUrl: "https://studio.supremeai.lat",
    healthPath: "/health",
    readinessPath: "/health",
    releasePath: "/release",
    repo: "Supremeai-bd/supremeai",
    branch: "main",
    watchPaths: ["infrastructure/cloudflare*/**"],
    source: "default",
  },
};

/**
 * Find the first existing service registry path on disk.
 */
export function findServiceRegistryPath(): string | null {
  for (const candidate of CANDIDATE_REGISTRY_PATHS) {
    if (fs.existsSync(candidate)) return candidate;
  }
  return null;
}

/**
 * Lightweight, zero-dependency YAML service registry parser.
 * Reads config/service_registry.yaml directly to provide authoritative topology,
 * falling back gracefully to typed canonical topology defaults if the file is absent.
 */
export function loadAuthoritativeServices(): Record<string, AuthoritativeServiceTarget> {
  const result: Record<string, AuthoritativeServiceTarget> = {
    ...CANONICAL_TOPOLOGY_DEFAULTS,
  };

  const registryPath = findServiceRegistryPath();
  if (!registryPath) {
    return result;
  }

  try {
    const raw = fs.readFileSync(registryPath, "utf-8");
    const lines = raw.split(/\r?\n/);

    let inServices = false;
    let currentKey = "";
    let currentBlock: Record<string, string> = {};
    let currentLists: Record<string, string[]> = {};
    let currentListKey = "";

    function flush() {
      if (currentKey && currentBlock.render_name) {
        const renderAccountId = ACCOUNT_MAP[currentKey] || "render-primary";
        const envIdVar = currentBlock.canonical_service_id_env;
        const envUrlVar = currentBlock.canonical_url_env;

        let source: "env" | "registry" | "default" = "registry";
        let renderServiceId = "";
        let runtimeUrl = "";

        if (envIdVar && process.env[envIdVar]?.trim()) {
          renderServiceId = process.env[envIdVar]!.trim();
          source = "env";
        } else if (currentBlock.render_service_id) {
          renderServiceId = currentBlock.render_service_id;
        }

        if (envUrlVar && process.env[envUrlVar]?.trim()) {
          runtimeUrl = process.env[envUrlVar]!.trim();
          source = "env";
        } else if (currentBlock.production_url) {
          runtimeUrl = currentBlock.production_url;
        }

        // Fallback to env.render configuration
        const envKey = ENV_RENDER_KEY_MAP[currentKey] || currentKey;
        const envRenderObj = (env.render as Record<string, any>)?.[envKey];
        if (envRenderObj) {
          if (!renderServiceId && envRenderObj.serviceId) renderServiceId = envRenderObj.serviceId;
          if (!runtimeUrl && envRenderObj.url) runtimeUrl = envRenderObj.url;
        }

        // Final fallback to typed defaults
        const defaultTarget = CANONICAL_TOPOLOGY_DEFAULTS[currentKey];
        if (!renderServiceId && defaultTarget?.renderServiceId) {
          renderServiceId = defaultTarget.renderServiceId;
        }
        if (!runtimeUrl && defaultTarget?.runtimeUrl) {
          runtimeUrl = defaultTarget.runtimeUrl;
        }

        result[currentKey] = {
          name: currentKey,
          role: currentBlock.role || defaultTarget?.role || "",
          platform: currentBlock.platform || defaultTarget?.platform || "render",
          renderAccountId,
          renderServiceId,
          runtimeUrl,
          healthPath: currentBlock.health_path || defaultTarget?.healthPath || "/health",
          readinessPath: currentBlock.readiness_path || defaultTarget?.readinessPath || "/health",
          releasePath: currentBlock.release_path || defaultTarget?.releasePath || "/release",
          repo: currentBlock.source_repo || defaultTarget?.repo || "Supremeai-bd/supremeai",
          branch: currentBlock.branch || defaultTarget?.branch || "main",
          watchPaths: currentLists.watch_paths || defaultTarget?.watchPaths || [],
          source,
        };
      }
      currentBlock = {};
      currentLists = {};
      currentListKey = "";
    }

    for (const line of lines) {
      if (line.trim().startsWith("#") || !line.trim()) continue;

      if (line.startsWith("services:")) {
        inServices = true;
        continue;
      }

      if (!inServices) continue;

      const topMatch = line.match(/^  ([a-zA-Z0-9_-]+):$/);
      if (topMatch) {
        flush();
        currentKey = topMatch[1];
        continue;
      }

      if (currentKey) {
        const listItemMatch = line.match(/^\s{6,8}-\s*["']?(.*?)["']?\s*$/);
        if (listItemMatch && currentListKey) {
          if (!currentLists[currentListKey]) currentLists[currentListKey] = [];
          currentLists[currentListKey].push(listItemMatch[1]);
          continue;
        }

        if (line.startsWith("    ")) {
          const propMatch = line.trim().match(/^([a-zA-Z0-9_-]+):\s*(.*)$/);
          if (propMatch) {
            const key = propMatch[1];
            let val = propMatch[2].trim();
            if (val === "" || val === "[]") {
              currentListKey = key;
              currentLists[key] = [];
              continue;
            }
            currentListKey = "";
            if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
              val = val.slice(1, -1);
            }
            currentBlock[key] = val;
          }
        }
      }
    }

    flush();
  } catch (err) {
    // If parsing fails for any reason, typed defaults in result remain authoritative
  }

  return result;
}

export function resolveServiceTarget(serviceName: string): AuthoritativeServiceTarget | null {
  const catalog = loadAuthoritativeServices();
  const normalized = serviceName.trim().toLowerCase();

  // Direct hit or alias resolution
  if (catalog[normalized]) return catalog[normalized];

  if (normalized === "backend-api" || normalized === "gateway") {
    return catalog["api"] ?? null;
  }
  if (normalized === "primary" || normalized === "supremeai-core") {
    return catalog["core"] ?? null;
  }
  if (normalized === "browser") {
    return catalog["scraper"] ?? null;
  }
  if (normalized === "tower" || normalized === "control-tower") {
    return catalog["mcp"] ?? null;
  }
  if (normalized === "tiny-brain") {
    return catalog["brain"] ?? null;
  }

  return null;
}

export interface ServiceIdentity {
  logicalName: string;
  provider: "render" | "cloudflare" | "vercel" | "external";
  accountId: string;
  serviceId: string;
  runtimeUrl: string;
  healthPath: string;
  readinessPath: string;
  releasePath: string;
  repo: string;
  branch: string;
  watchPaths: string[];
  source: "registry" | "env" | "default";
  verified: boolean;
  verificationError?: string;
  registryFound: boolean;
  registryPath: string | null;
}

export function resolveServiceIdentity(serviceName: string): ServiceIdentity | null {
  const target = resolveServiceTarget(serviceName);
  if (!target) return null;

  const errors: string[] = [];
  if (target.platform === "render") {
    if (!target.renderServiceId) {
      errors.push("missing render service id");
    } else if (!/^srv-[a-zA-Z0-9]+$/i.test(target.renderServiceId)) {
      errors.push(`invalid service id format: ${target.renderServiceId}`);
    }
  }

  if (!target.runtimeUrl || !/^https?:\/\//i.test(target.runtimeUrl)) {
    errors.push("missing or invalid runtime url");
  }

  const regPath = findServiceRegistryPath();

  return {
    logicalName: target.name,
    provider: (target.platform as ServiceIdentity["provider"]) || "render",
    accountId: target.renderAccountId,
    serviceId: target.renderServiceId,
    runtimeUrl: target.runtimeUrl,
    healthPath: target.healthPath,
    readinessPath: target.readinessPath,
    releasePath: target.releasePath,
    repo: target.repo,
    branch: target.branch,
    watchPaths: target.watchPaths || [],
    source: target.source || "default",
    verified: errors.length === 0,
    ...(errors.length ? { verificationError: errors.join("; ") } : {}),
    registryFound: Boolean(regPath),
    registryPath: regPath,
  };
}

export interface ServiceRef {
  canonicalServiceId: string;
  providerId: string;
  providerNativeId: string;
  deploymentId?: string;
  deploymentSha?: string;
  environment: "development" | "staging" | "production";
  tenantId?: string;
  region?: string;
  instanceId?: string;
  capabilityVersion: string;
}

export interface DeploymentRef {
  service: ServiceRef;
  artifactDigest?: string;
  runtimeCommit?: string;
  schemaVersion?: string;
  rolloutGeneration?: string;
}

/**
 * Converts a service name or AuthoritativeServiceTarget into a canonical ServiceRef.
 * Prevents ID drift across health probes, diagnostic graphs, and remediation gates.
 */
export function toServiceRef(
  serviceOrTarget: string | AuthoritativeServiceTarget,
  overrides: Partial<ServiceRef> = {},
): ServiceRef | null {
  const target =
    typeof serviceOrTarget === "string"
      ? resolveServiceTarget(serviceOrTarget)
      : serviceOrTarget;
  if (!target) return null;

  return {
    canonicalServiceId: target.name,
    providerId: target.platform || "render",
    providerNativeId: target.renderServiceId,
    environment: overrides.environment ?? "production",
    capabilityVersion: overrides.capabilityVersion ?? "v2",
    ...overrides,
  };
}

/**
 * Builds an immutable DeploymentRef binding a canonical ServiceRef to runtime commit & schema state.
 */
export function toDeploymentRef(
  serviceOrTarget: string | AuthoritativeServiceTarget | ServiceRef,
  meta: Omit<DeploymentRef, "service"> = {},
): DeploymentRef | null {
  const serviceRef =
    typeof serviceOrTarget === "object" && "canonicalServiceId" in serviceOrTarget
      ? serviceOrTarget
      : toServiceRef(serviceOrTarget);
  if (!serviceRef) return null;

  return {
    service: serviceRef,
    ...meta,
  };
}

/**
 * Detects duplicate providerNativeId or runtimeUrl collisions across the service catalog.
 */
export function detectCatalogCollisions(): Array<{
  field: "providerNativeId" | "runtimeUrl";
  value: string;
  services: string[];
}> {
  const catalog = loadAuthoritativeServices();
  const byNativeId = new Map<string, string[]>();
  const byUrl = new Map<string, string[]>();

  for (const [key, entry] of Object.entries(catalog)) {
    if (entry.renderServiceId) {
      const list = byNativeId.get(entry.renderServiceId) ?? [];
      if (!list.includes(entry.name || key)) list.push(entry.name || key);
      byNativeId.set(entry.renderServiceId, list);
    }
    if (entry.runtimeUrl) {
      const normalizedUrl = entry.runtimeUrl.replace(/\/+$/, "").toLowerCase();
      const list = byUrl.get(normalizedUrl) ?? [];
      if (!list.includes(entry.name || key)) list.push(entry.name || key);
      byUrl.set(normalizedUrl, list);
    }
  }

  const collisions: Array<{
    field: "providerNativeId" | "runtimeUrl";
    value: string;
    services: string[];
  }> = [];

  for (const [value, services] of byNativeId.entries()) {
    if (services.length > 1) {
      collisions.push({ field: "providerNativeId", value, services });
    }
  }
  for (const [value, services] of byUrl.entries()) {
    if (services.length > 1) {
      collisions.push({ field: "runtimeUrl", value, services });
    }
  }

  return collisions;
}
