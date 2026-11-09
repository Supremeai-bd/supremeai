import assert from "node:assert/strict";
import { redactSensitiveData, fingerprintSecret } from "./src/diagnostics/redaction.js";
import { runParityAudit } from "./src/tools/parity.tools.js";
import { probeServiceDependencies, SERVICE_TOPOLOGY_MAP } from "./src/diagnostics/dependency_graph.js";
import { resolveServiceTarget } from "./src/diagnostics/service_manifest.js";

async function runTests() {
  console.log("Running Operational Truth & Credential Sanitization Verification...");

  // 1. Strict Credential Drop
  const rawPayload = {
    repository: "Supremeai-bd/supremeai",
    temp_clone_token: "ghs_secret_temporary_token_12345",
    access_token: "gho_access_token_abcde",
    token: "ghp_standard_token_67890",
    client_secret: "secret_client_val",
    password: "super_secret_db_password",
    authorization: "Bearer eyJhbGciOi...",
    cookie: "session=xyz123",
    connectionString: "postgresql://postgres:secret@db.render.com:5432/main",
    apiKeyRef: "infisical:RENDER_API_KEY_5",
    status: "healthy",
  };

  const sanitized = redactSensitiveData(rawPayload) as any;
  assert.equal(sanitized.temp_clone_token, undefined, "temp_clone_token must be strictly dropped");
  assert.equal(sanitized.access_token, undefined, "access_token must be strictly dropped");
  assert.equal(sanitized.token, undefined, "token must be strictly dropped");
  assert.equal(sanitized.client_secret, undefined, "client_secret must be strictly dropped");
  assert.equal(sanitized.password, undefined, "password must be strictly dropped");
  assert.equal(sanitized.authorization, undefined, "authorization must be strictly dropped");
  assert.equal(sanitized.cookie, undefined, "cookie must be strictly dropped");
  assert.ok(sanitized.connectionString.startsWith("sha256:"), "connectionString must be fingerprinted");
  assert.equal(sanitized.apiKeyRef, "infisical:RENDER_API_KEY_5", "Allowlisted non-secret metadata preserved");
  assert.equal(sanitized.status, "healthy", "Non-sensitive status must be preserved");

  // 2. Parity Audit Pure Single-Repository Monorepo SSOT Topology & State Model
  const parityReport = await runParityAudit();
  assert.ok(["unverified", "parity_verified", "drift_detected"].includes(parityReport.status));
  const githubCheck = parityReport.checks.find((c) => c.component === "github_repositories");
  assert.ok(githubCheck, "github_repositories check must exist");
  assert.ok(["configuration_present", "unconfigured", "parity_verified"].includes(githubCheck.status));
  assert.equal((githubCheck.details as any).topology, "Pure Single-Repository Monorepo SSOT Topology");
  assert.ok(Array.isArray((githubCheck.details as any).activeRepositories));
  assert.ok((githubCheck.details as any).activeRepositories.includes("Supremeai-bd/supremeai"));
  assert.ok(!((githubCheck.details as any).activeRepositories.includes("Supremeai-bd/supremeai-studio")));
  assert.ok((githubCheck.details as any).retiredSatellites.includes("supremeai-studio"));

  // 3. Service Manifest Account Resolution for API
  const apiTarget = resolveServiceTarget("api");
  assert.ok(apiTarget, "api service target must be resolved");
  assert.equal(apiTarget.renderAccountId, "render-api", "api service must map to render-api (Account #5)");

  const backendApiTarget = resolveServiceTarget("backend-api");
  assert.ok(backendApiTarget, "backend-api alias must be resolved");
  assert.equal(backendApiTarget.renderAccountId, "render-api", "backend-api alias must map to render-api");

  // 4. Dependency Graph Alias Resolution & Operational Dependencies
  assert.ok(SERVICE_TOPOLOGY_MAP.api.some((d) => d.id === "redis"), "api must declare redis dependency");
  assert.ok(SERVICE_TOPOLOGY_MAP.api.some((d) => d.id === "infisical"), "api must declare infisical dependency");
  assert.ok(SERVICE_TOPOLOGY_MAP.api.some((d) => d.id === "render"), "api must declare render dependency");

  const depReport = await probeServiceDependencies("backend-api");
  assert.equal(depReport.service, "backend-api");
  assert.ok(depReport.dependencies.length >= 3, "backend-api must probe aliased dependencies");
  assert.ok(depReport.dependencies.some((d) => d.id === "supabase"));

  console.log("Operational Truth & Credential Sanitization Verification passed successfully!");
}

runTests().catch((err) => {
  console.error("Test failure:", err);
  process.exit(1);
});
