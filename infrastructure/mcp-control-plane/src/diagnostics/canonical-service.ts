import { env } from "../lib/env.js";

export interface CanonicalServiceTarget {
  name: string;
  provider: "render";
  accountId: string;
  serviceId: string;
  runtimeUrl: string;
  repository: string;
  branch: string;
}

/**
 * Every diagnostic path must use this resolver. No path may invent a provider
 * service ID or silently fall back to the primary service.
 */
export function resolveCanonicalService(name: string): CanonicalServiceTarget | null {
  const targets: Record<string, CanonicalServiceTarget> = {
    api: {
      name: "api",
      provider: "render",
      accountId: "render-api",
      serviceId: env.render.api.serviceId,
      runtimeUrl: env.render.api.url,
      repository: env.github.repo,
      branch: "main",
    },
    "backend-api": {
      name: "backend-api",
      provider: "render",
      accountId: "render-api",
      serviceId: env.render.api.serviceId,
      runtimeUrl: env.render.api.url,
      repository: env.github.repo,
      branch: "main",
    },
    mcp: {
      name: "mcp",
      provider: "render",
      accountId: "render-mcp",
      serviceId: env.render.controlTower.serviceId,
      runtimeUrl: env.render.controlTower.url,
      repository: env.github.repo,
      branch: "main",
    },
  };
  return targets[name] ?? null;
}

export function assertCanonicalService(target: CanonicalServiceTarget): void {
  if (!target.serviceId || /^(xxx|unknown|null|undefined)$/i.test(target.serviceId)) {
    throw new Error(`Invalid canonical Render service ID for ${target.name}`);
  }
  if (!/^https?:\/\//i.test(target.runtimeUrl)) {
    throw new Error(`Invalid runtime URL for ${target.name}`);
  }
}

