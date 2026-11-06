import assert from "node:assert/strict";
import {
  inferDeterministicFindings,
  inferCausalHypotheses,
  systemDeepDiagnose,
} from "./src/tools/master_diagnose.tools.js";
import { classifyToolCapability } from "./src/policy/mcp-access.js";

async function runTests() {
  // 1. Policy classification check
  const cap = classifyToolCapability("system_deep_diagnose");
  assert.equal(cap.access, "restricted");
  assert.equal(cap.requiredScope, "system:read");
  assert.equal(cap.riskLevel, "R1");
  assert.equal(cap.approvalRequired, false);

  // 2. Rule 1: Unmapped service returns SERVICE_NOT_MAPPED and blocks without querying provider
  const unmapped = await systemDeepDiagnose({ service: "non-existent-service-xyz123" });
  assert.equal(unmapped.status, "unknown");
  assert.equal(unmapped.verdict, "NO_GO");
  assert.equal(unmapped.releaseGate, "blocked");
  assert.ok(Array.isArray(unmapped.findings));
  assert.equal((unmapped.findings as any[])[0]?.code, "SERVICE_NOT_MAPPED");

  // 3. Rule 2 & 3: Deterministic findings & causal hypotheses for Cloudflare 404 + Release mismatch
  const findings = inferDeterministicFindings({
    targetMapped: true,
    identityVerified: true,
    truthMatrix: {
      providerHealth: "pass",
      serviceHealth: "pass",
      releaseIntegrity: "fail",
      dependencyHealth: "pass",
      schemaParity: "pass",
      userJourneyHealth: "pass",
    },
    cloudflareCheck: {
      status: "critical",
      checks: [
        {
          source: "cloudflare.worker_route",
          status: "fail",
          observedAt: new Date().toISOString(),
          value: { httpStatus: 404 },
          reason: "Worker route returned Not Found",
        },
      ],
    },
    parityResult: { status: "parity_verified", releaseGate: "open" },
    graphStatus: { indexed: true, status: "pass" },
  });

  const codes = findings.map((f) => f.code);
  assert.ok(codes.includes("EDGE_ROUTE_NOT_FOUND"), "Should detect EDGE_ROUTE_NOT_FOUND");
  assert.ok(codes.includes("RELEASE_COMMIT_MISMATCH"), "Should detect RELEASE_COMMIT_MISMATCH");

  const hypotheses = inferCausalHypotheses(findings, {
    providerHealth: "pass",
    serviceHealth: "pass",
    releaseIntegrity: "fail",
    dependencyHealth: "pass",
    schemaParity: "pass",
    userJourneyHealth: "pass",
  });
  assert.ok(hypotheses.some((h) => h.code === "EDGE_ROUTE_NOT_FOUND"));
  assert.ok(hypotheses.some((h) => h.code === "STALE_DEPLOYMENT_ACTIVE"));

  console.log("master deep diagnose contract tests passed");
}

runTests().catch((err) => {
  console.error(err);
  process.exit(1);
});
