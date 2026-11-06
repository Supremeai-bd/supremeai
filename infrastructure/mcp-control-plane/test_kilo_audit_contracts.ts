import assert from "node:assert/strict";
import {
  toServiceRef,
  toDeploymentRef,
  detectCatalogCollisions,
} from "./src/diagnostics/service_manifest.js";
import {
  createEvidenceEnvelope,
  isEvidenceFresh,
} from "./src/diagnostics/evidence.js";
import { evaluateActionPolicy } from "./src/policy/permission_policy.js";
import { verifyReleaseCandidate } from "./src/diagnostics/release_verifier.js";

async function runTests() {
  console.log("=== Running Kilo-Org Audit Alignment Contract Tests ===");

  // 1. Canonical ServiceRef & Alias Equivalence
  const apiRef1 = toServiceRef("api");
  const apiRef2 = toServiceRef("backend-api");
  const apiRef3 = toServiceRef("gateway");
  assert.ok(apiRef1, "api ServiceRef should resolve");
  assert.ok(apiRef2, "backend-api ServiceRef should resolve");
  assert.ok(apiRef3, "gateway ServiceRef should resolve");
  assert.equal(apiRef1.canonicalServiceId, "api");
  assert.equal(apiRef2.canonicalServiceId, "api");
  assert.equal(apiRef3.canonicalServiceId, "api");
  assert.equal(apiRef1.providerNativeId, apiRef2.providerNativeId);
  console.log("  [PASS] 1. Canonical ServiceRef alias normalization ('backend-api' / 'gateway' -> 'api')");

  // 2. DeploymentRef & Catalog Collision Detection
  const deployRef = toDeploymentRef("mcp", {
    runtimeCommit: "7f1d72649",
    schemaVersion: "v2",
  });
  assert.ok(deployRef);
  assert.equal(deployRef.service.canonicalServiceId, "mcp");
  assert.equal(deployRef.runtimeCommit, "7f1d72649");

  const collisions = detectCatalogCollisions();
  assert.equal(collisions.length, 0, `Expected 0 catalog collisions, got: ${JSON.stringify(collisions)}`);
  console.log("  [PASS] 2. DeploymentRef & Zero Catalog Collisions verified");

  // 3. First-Class EvidenceEnvelope & Freshness Guard
  const freshEnv = createEvidenceEnvelope({
    status: "pass",
    canonicalServiceId: "api",
    providerId: "render",
    deploymentRef: deployRef,
    rawObservation: { httpStatus: 200 },
    normalizedObservation: { healthy: true },
  });
  assert.equal(freshEnv.schemaVersion, "v2");
  assert.ok(freshEnv.evidenceId.startsWith("ev_"));
  assert.equal(isEvidenceFresh(freshEnv, 60_000), true);

  const staleEnv = createEvidenceEnvelope({
    status: "pass",
    canonicalServiceId: "api",
    providerId: "render",
    observedAt: new Date(Date.now() - 120_000).toISOString(),
    rawObservation: {},
    normalizedObservation: {},
  });
  assert.equal(isEvidenceFresh(staleEnv, 60_000), false, "Evidence older than 60s must be rejected");
  console.log("  [PASS] 3. First-Class EvidenceEnvelope v2 & Freshness Guard verified");

  // 4. Scoped Permission Policy (allow / ask / deny)
  // Diagnostician cannot mutate
  const diagMutate = evaluateActionPolicy({
    agentRole: "diagnostician",
    action: "redeploy",
    serviceRef: apiRef1,
  });
  assert.equal(diagMutate.effect, "deny");

  // Planner cannot mutate
  const plannerMutate = evaluateActionPolicy({
    agentRole: "planner",
    action: "restart",
    serviceRef: apiRef1,
  });
  assert.equal(plannerMutate.effect, "deny");

  // Remediator with stale evidence -> deny (fail-closed)
  const remStale = evaluateActionPolicy({
    agentRole: "remediator",
    action: "restart",
    serviceRef: apiRef1,
    evidence: [staleEnv],
    hasHumanApprovalToken: true,
    hasIdempotencyKey: true,
  });
  assert.equal(remStale.effect, "deny");
  assert.ok(remStale.reasons.includes("STALE_EVIDENCE_REJECTED"));

  // Remediator missing human approval -> ask
  const remNoApproval = evaluateActionPolicy({
    agentRole: "remediator",
    action: "restart",
    serviceRef: apiRef1,
    evidence: [freshEnv],
    hasHumanApprovalToken: false,
    hasIdempotencyKey: true,
  });
  assert.equal(remNoApproval.effect, "ask");
  assert.ok(remNoApproval.reasons.includes("HUMAN_APPROVAL_REQUIRED"));

  // Remediator with all gates satisfied -> allow
  const remAllow = evaluateActionPolicy({
    agentRole: "remediator",
    action: "restart",
    serviceRef: apiRef1,
    evidence: [freshEnv],
    hasHumanApprovalToken: true,
    hasIdempotencyKey: true,
    schemaParityStatus: "pass",
  });
  assert.equal(remAllow.effect, "allow");
  console.log("  [PASS] 4. Scoped Permission Engine (allow / ask / deny) fail-closed rules verified");

  // 5. Immutable ReleaseCandidate Verifier
  const verifiedRc = await verifyReleaseCandidate("api", {
    sourceCommit: "abc1234",
    runtimeCommit: "abc1234",
    ciRunId: "998877",
    deploymentId: "dep-123",
    redisStatus: "pass",
    supabaseStatus: "pass",
    smokeStatus: "pass",
  });
  assert.equal(verifiedRc.finalStatus, "verified");

  const mismatchRc = await verifyReleaseCandidate("api", {
    sourceCommit: "abc1234",
    runtimeCommit: "def5678",
    redisStatus: "pass",
    supabaseStatus: "pass",
    smokeStatus: "pass",
  });
  assert.equal(mismatchRc.finalStatus, "blocked");
  assert.equal(mismatchRc.smokeTestResult.errorClass, "commit_mismatch");
  console.log("  [PASS] 5. Immutable ReleaseCandidate Verifier (verified vs commit_mismatch blocked)");

  console.log("=== ALL KILO AUDIT CONTRACT TESTS PASSED ===");
}

runTests().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});

