import assert from "node:assert/strict";
import { resolveServiceTarget, resolveServiceIdentity, loadAuthoritativeServices, findServiceRegistryPath } from "./src/diagnostics/service_manifest.js";
import { pingRedis } from "./src/adapters/redis/index.js";
import { probeServiceDependencies, probeSchemaParity } from "./src/diagnostics/dependency_graph.js";

async function runTests() {
  console.log("Running Canonical Resolver & Diagnostic Fidelity Verification...");

  // 1. One Canonical Service Resolver - core target resolution
  const core = resolveServiceTarget("core");
  assert.ok(core, "core target must be resolved");
  assert.equal(core.name, "core");
  assert.equal(core.renderAccountId, "render-primary");
  assert.ok(core.runtimeUrl && core.runtimeUrl.includes("supremeai-primary"), "core runtimeUrl must be non-empty and valid");
  assert.ok(core.renderServiceId && core.renderServiceId.startsWith("srv-"), "core renderServiceId must be valid srv- ID");

  const coreIdentity = resolveServiceIdentity("core");
  assert.ok(coreIdentity, "core identity must be resolved");
  assert.equal(coreIdentity.verified, true, `core identity must be verified: ${coreIdentity.verificationError}`);
  assert.ok(["registry", "env", "default"].includes(coreIdentity.source));

  // 2. Alias resolution
  const primaryAlias = resolveServiceTarget("primary");
  assert.ok(primaryAlias, "primary alias must resolve to core");
  assert.equal(primaryAlias.name, "core");

  const apiTarget = resolveServiceTarget("backend-api");
  assert.ok(apiTarget, "backend-api alias must resolve to api");
  assert.equal(apiTarget.name, "api");
  assert.equal(apiTarget.renderAccountId, "render-api");
  assert.ok(apiTarget.runtimeUrl && apiTarget.runtimeUrl.includes("supremeai-api"));

  // 3. Container-safety: even if registry file path was mocked as missing, defaults hold
  const catalog = loadAuthoritativeServices();
  assert.ok(catalog.core, "catalog must contain core");
  assert.ok(catalog.api, "catalog must contain api");
  assert.ok(catalog.worker, "catalog must contain worker");
  assert.ok(catalog.mcp, "catalog must contain mcp");
  assert.ok(catalog.scraper, "catalog must contain scraper");
  assert.ok(catalog.brain, "catalog must contain brain");

  // 4. Redis normalized probe
  const redisRes = await pingRedis();
  assert.ok(redisRes.status === "healthy" || redisRes.status === "fail", "Redis ping status must be healthy or fail");
  assert.ok(typeof redisRes.probe === "string", "Redis probe must be a string");
  assert.ok(typeof redisRes.latencyMs === "number", "Redis latencyMs must be a number");

  // 5. Dependency graph resolution for backend-api
  const depReport = await probeServiceDependencies("backend-api");
  assert.equal(depReport.service, "backend-api");
  const coreDep = depReport.dependencies.find((d) => d.id === "core");
  assert.ok(coreDep, "core must be in backend-api dependencies");
  assert.notEqual(coreDep.error, "No runtime URL configured for service: core", "core must resolve runtime URL");

  const redisDep = depReport.dependencies.find((d) => d.id === "redis");
  assert.ok(redisDep, "redis must be in backend-api dependencies");
  assert.notEqual(redisDep.error, "Redis ping failed", "redis probe must not fail when PONG is returned");

  // 6. Supabase schema parity does not falsely report migration breach when unverified
  const schemaParity = await probeSchemaParity("api");
  assert.ok(schemaParity, "schema parity check must return result");
  assert.ok(["pass", "unknown", "fail"].includes(schemaParity.status));
  if (schemaParity.status === "unknown") {
    assert.ok(
      schemaParity.explanation.includes("unverified") ||
      schemaParity.explanation.includes("inconclusive") ||
      schemaParity.explanation.includes("unauthorized"),
      "unverified schema must give clear non-migration reason",
    );
  }

  console.log("Canonical Resolver & Diagnostic Fidelity Verification passed successfully!");
}

runTests().catch((err) => {
  console.error("Test failure:", err);
  process.exit(1);
});
