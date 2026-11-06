import assert from "node:assert/strict";
import { aggregateStatus, confidenceFor, fact, type EvidenceCheck } from "./src/diagnostics/evidence.js";
import { compareCommitEvidence } from "./src/tools/diagnostic.tools.js";

// Golden incident dataset (INC-001..) — deterministic, no network.
interface GoldenCase {
  id: string;
  name: string;
  checks: EvidenceCheck[];
  expectedStatus: "healthy" | "degraded" | "critical" | "unknown";
  expectedFalseHealthy: boolean;
}

const cases: GoldenCase[] = [
  {
    id: "INC-001",
    name: "old commit deployed",
    checks: [compareCommitEvidence("new-sha", "old-sha", "old-sha")],
    expectedStatus: "critical",
    expectedFalseHealthy: false,
  },
  {
    id: "INC-002",
    name: "runtime drift",
    checks: [compareCommitEvidence("sha-1", "sha-1", "sha-old")],
    expectedStatus: "critical",
    expectedFalseHealthy: false,
  },
  {
    id: "INC-003",
    name: "schema behind",
    checks: [{ name: "schema_parity", status: "fail", confidence: 0.85, facts: [fact("supabase.schema", "fail", { missing: ["tasks"] })], explanation: "missing tables" }],
    expectedStatus: "critical",
    expectedFalseHealthy: false,
  },
  {
    id: "INC-004",
    name: "redis down",
    checks: [{ name: "dependency_health", status: "fail", confidence: 0.9, facts: [fact("redis", "fail", undefined, "connection refused")], explanation: "redis unreachable" }],
    expectedStatus: "critical",
    expectedFalseHealthy: false,
  },
  {
    id: "INC-005",
    name: "stale cache",
    checks: [{ name: "recent_error_logs", status: "fail", confidence: 0.7, facts: [fact("render.logs", "fail", { count: 12 })], explanation: "post-deploy errors" }],
    expectedStatus: "critical",
    expectedFalseHealthy: false,
  },
  {
    id: "INC-006",
    name: "ci passed wrong branch",
    checks: [{ name: "ci_evidence", status: "fail", confidence: 0.9, facts: [fact("github.actions", "fail", { branch: "feature/x", targetBranch: "main" })], explanation: "branch mismatch" }],
    expectedStatus: "critical",
    expectedFalseHealthy: false,
  },
  {
    id: "INC-007",
    name: "provider healthy false positive",
    checks: [
      { name: "provider_health", status: "pass", confidence: 0.8, facts: [fact("render", "pass", { suspended: "false" })], explanation: "render api ok" },
      compareCommitEvidence("new-sha", "old-sha", "old-sha"),
    ],
    expectedStatus: "critical",
    expectedFalseHealthy: true,
  },
  {
    id: "INC-008",
    name: "frontend api mismatch",
    checks: [{ name: "service_health", status: "fail", confidence: 0.85, facts: [fact("runtime.http", "fail", { status: 502 })], explanation: "502" }],
    expectedStatus: "critical",
    expectedFalseHealthy: false,
  },
  {
    id: "INC-009",
    name: "all unknown",
    checks: [{ name: "runtime_metadata", status: "unknown", confidence: 0.1, facts: [fact("runtime.release", "unknown", undefined, "timeout")], explanation: "timeout" }],
    expectedStatus: "unknown",
    expectedFalseHealthy: false,
  },
  {
    id: "INC-010",
    name: "healthy aligned",
    checks: [compareCommitEvidence("sha-abc", "sha-abc", "sha-abc")],
    expectedStatus: "healthy",
    expectedFalseHealthy: false,
  },
];

function runEval() {
  console.log("Running Phase 5 diagnostic golden-incident eval...");
  let passed = 0;
  let falseHealthy = 0;
  let unknownHonesty = 0;
  let unknownTotal = 0;

  for (const c of cases) {
    const status = aggregateStatus(c.checks);
    const ok = status === c.expectedStatus;
    if (ok) passed++;
    if (c.expectedFalseHealthy && status === "healthy") falseHealthy++;
    if (c.expectedStatus === "unknown") {
      unknownTotal++;
      if (status === "unknown") unknownHonesty++;
    }
    console.log(`${c.id} ${c.name}: ${status} ${ok ? "✓" : "✗ (expected " + c.expectedStatus + ")"}`);
  }

  const accuracy = passed / cases.length;
  const falseHealthyRate = falseHealthy / cases.length;
  const unknownHonestyRate = unknownTotal > 0 ? unknownHonesty / unknownTotal : 1;

  console.log(`\nMetrics:`);
  console.log(`  top-1 status accuracy: ${(accuracy * 100).toFixed(1)}% (${passed}/${cases.length})`);
  console.log(`  false-healthy rate: ${(falseHealthyRate * 100).toFixed(1)}% (target 0%)`);
  console.log(`  unknown honesty rate: ${(unknownHonestyRate * 100).toFixed(1)}% (target 100%)`);

  assert.equal(falseHealthy, 0, "False-healthy rate must be 0");
  assert.equal(unknownHonesty, unknownTotal, "Unknown honesty must be 100%");
  assert.ok(accuracy >= 0.9, "Status accuracy must be >= 90%");

  // Confidence sanity: fail cases should have confidence >= 0.75 when >=2 facts
  const failFacts = [fact("github", "pass", { sha: "abc" }), fact("render", "fail", { sha: "old" })];
  assert.ok(confidenceFor("fail", failFacts) >= 0.75);

  console.log("\nPhase 5 diagnostic golden-incident eval passed.");
}

runEval();
