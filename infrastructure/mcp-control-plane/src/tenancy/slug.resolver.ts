/**
 * Personal MCP Gateway Subdomain Slug Resolver & Cross-Verification Gate (Wave 5.3 Phase B).
 *
 * বাংলা মন্তব্য: `Host: <slug>.mcp.supremeai.ai` (অথবা কনফিগার করা MCP গেটওয়ে ডোমেইন)
 * থেকে ভ্যানিটি স্লাগ শনাক্ত করে এবং কলকারীর টোকেন `tenant_id`-এর সাথে ক্রস-ভেরিফাই করে।
 * অন্যের ভ্যানিটি সাবডোমেইনে নিজের টোকেন দিয়ে ঢুকলে সাথে সাথে HTTP 403 ব্লক করা হয়।
 */

import { listTenants, getTenant } from "./tenant.registry.js";

const RESERVED_SUBDOMAINS = new Set([
  "www",
  "api",
  "admin",
  "mcp",
  "gateway",
  "tower",
  "studio",
  "auth",
  "status",
  "docs",
]);

const SLUG_RE = /^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?$/;

export interface SlugVerificationResult {
  isVanitySubdomain: boolean;
  slug: string | null;
  resolvedTenantId: string | null;
  allowed: boolean;
  statusCode?: number;
  error?: string;
}

/**
 * Extract `<slug>` only when the request targets `<slug>.mcp.<root-domain>`
 * (e.g. `niloy.mcp.supremeai.ai` or `niloy.mcp.paykaribazaronline.com`).
 * Standard single-host deployments (`localhost`, `*.onrender.com`, `mcp.supremeai.ai`)
 * return `null` so existing global Control Tower traffic is unaffected.
 */
export function extractVanitySlug(hostHeader?: string): string | null {
  if (!hostHeader) return null;
  const host = hostHeader.trim().toLowerCase().split(":")[0] ?? "";
  if (!host || host === "localhost" || /^\d+\.\d+\.\d+\.\d+$/.test(host)) {
    return null;
  }
  if (host.endsWith(".onrender.com") || host.endsWith(".workers.dev") || host.endsWith(".pages.dev")) {
    return null;
  }

  const configuredDomain = (process.env.MCP_GATEWAY_DOMAIN || "mcp.supremeai.ai")
    .trim()
    .toLowerCase();

  let candidate: string | null = null;
  if (host.endsWith(`.${configuredDomain}`)) {
    candidate = host.slice(0, -(configuredDomain.length + 1));
  } else {
    const mcpMatch = /^([a-z0-9-]+)\.mcp\.[a-z0-9.-]+\.[a-z]{2,}$/.exec(host);
    if (mcpMatch) {
      candidate = mcpMatch[1] ?? null;
    }
  }

  if (!candidate || candidate.includes(".") || RESERVED_SUBDOMAINS.has(candidate)) {
    return null;
  }
  if (!SLUG_RE.test(candidate)) {
    return null;
  }
  return candidate;
}

/**
 * Resolve a vanity slug against the Control Tower tenant registry.
 * Matches exact `tenant.id === slug`, `tenant.id === "tenant_" + slug`, or normalized `tenant.name`.
 */
export function resolveTenantIdForSlug(slug: string): { tenantId: string; suspended: boolean } | null {
  const direct = getTenant(slug) ?? getTenant(`tenant_${slug}`);
  if (direct) {
    return { tenantId: direct.id, suspended: direct.status !== "active" };
  }
  const normalized = slug.toLowerCase();
  for (const t of listTenants()) {
    const nameSlug = t.name.trim().toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "");
    if (nameSlug === normalized) {
      return { tenantId: t.id, suspended: t.status !== "active" };
    }
  }
  return null;
}

/**
 * Enforce subdomain-to-token tenant cross-verification (Phase B security gate).
 */
export function verifyVanitySubdomainAccess(params: {
  hostHeader?: string;
  callerTenantId: string;
  isGlobalAdmin: boolean;
  hasExplicitAuth: boolean;
}): SlugVerificationResult {
  const slug = extractVanitySlug(params.hostHeader);
  if (!slug) {
    return {
      isVanitySubdomain: false,
      slug: null,
      resolvedTenantId: null,
      allowed: true,
    };
  }

  const resolved = resolveTenantIdForSlug(slug);
  if (!resolved) {
    return {
      isVanitySubdomain: true,
      slug,
      resolvedTenantId: null,
      allowed: false,
      statusCode: 404,
      error: `Unknown Personal MCP Gateway slug '${slug}'`,
    };
  }

  if (resolved.suspended) {
    return {
      isVanitySubdomain: true,
      slug,
      resolvedTenantId: resolved.tenantId,
      allowed: false,
      statusCode: 403,
      error: `Personal MCP Gateway '${slug}' is suspended`,
    };
  }

  // Global admin (`*`) may inspect any tenant gateway; authenticated tenant callers
  // MUST match `resolved.tenantId` (prevents cross-tenant subdomain token spoofing).
  if (!params.isGlobalAdmin && params.hasExplicitAuth && params.callerTenantId !== resolved.tenantId) {
    return {
      isVanitySubdomain: true,
      slug,
      resolvedTenantId: resolved.tenantId,
      allowed: false,
      statusCode: 403,
      error: "Forbidden: client token tenant_id does not match vanity MCP gateway slug",
    };
  }

  return {
    isVanitySubdomain: true,
    slug,
    resolvedTenantId: resolved.tenantId,
    allowed: true,
  };
}
