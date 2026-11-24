import assert from "node:assert/strict";
import { RequestContextStore } from "./src/policy/auth.context.js";
import { createTenant } from "./src/tenancy/tenant.registry.js";
import {
  extractVanitySlug,
  verifyVanitySubdomainAccess,
} from "./src/tenancy/slug.resolver.js";

// 1. Subdomain extraction rules
assert.equal(extractVanitySlug("niloy.mcp.supremeai.ai"), "niloy");
assert.equal(extractVanitySlug("NILOY.mcp.paykaribazaronline.com:8443"), "niloy");
assert.equal(extractVanitySlug("localhost:3333"), null);
assert.equal(extractVanitySlug("supremeai-mcp.onrender.com"), null);
assert.equal(extractVanitySlug("api.mcp.supremeai.ai"), null);
assert.equal(extractVanitySlug("admin.mcp.supremeai.ai"), null);

// 2. Provision a test tenant under Global Admin context and verify cross-tenant spoofing protection
const { tenant } = RequestContextStore.run(
  { role: "admin", tenantId: "*", isGlobalAdmin: true, authenticated: true },
  () =>
    createTenant({
      id: "tenant_acme_exec",
      name: "acme-exec",
      ownerEmail: "owner@acme.test",
      type: "customer",
      plan: "pro",
    }),
);

// Unknown slug -> 404
const unknown = verifyVanitySubdomainAccess({
  hostHeader: "ghost-slug.mcp.supremeai.ai",
  callerTenantId: tenant.id,
  isGlobalAdmin: false,
  hasExplicitAuth: true,
});
assert.equal(unknown.allowed, false);
assert.equal(unknown.statusCode, 404);

// Cross-tenant token spoofing -> 403 Forbidden
const spoofed = verifyVanitySubdomainAccess({
  hostHeader: "acme-exec.mcp.supremeai.ai",
  callerTenantId: "tenant_intruder",
  isGlobalAdmin: false,
  hasExplicitAuth: true,
});
assert.equal(spoofed.allowed, false);
assert.equal(spoofed.statusCode, 403);

// Matching tenant -> allowed
const valid = verifyVanitySubdomainAccess({
  hostHeader: "acme-exec.mcp.supremeai.ai",
  callerTenantId: tenant.id,
  isGlobalAdmin: false,
  hasExplicitAuth: true,
});
assert.equal(valid.allowed, true);
assert.equal(valid.resolvedTenantId, tenant.id);

// Global admin -> allowed across any slug
const adminOk = verifyVanitySubdomainAccess({
  hostHeader: "acme-exec.mcp.supremeai.ai",
  callerTenantId: "*",
  isGlobalAdmin: true,
  hasExplicitAuth: true,
});
assert.equal(adminOk.allowed, true);

console.log("[slug-resolver] PASS — vanity subdomain extraction & 403 cross-tenant guard verified");
