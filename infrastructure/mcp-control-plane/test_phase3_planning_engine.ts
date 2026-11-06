import assert from "node:assert/strict";
import {
  validateDAG,
  generateRemediationPlan,
  createCustomPlan,
  type PlanStep,
} from "./src/planning/planner.js";
import { verifyOutcome } from "./src/planning/verifier.js";

async function runTests() {
  console.log("Running Phase 3 DAG planning engine & verifier contract tests...");

  // 1. Linear DAG Validation
  const linearSteps: PlanStep[] = [
    {
      id: "step-1",
      title: "Step 1",
      tool: "tool-1",
      params: {},
      dependsOn: [],
      timeoutMs: 5000,
      retryPolicy: { maxRetries: 1, backoffMs: 1000 },
      idempotencyKey: "k1",
      approvalRequired: false,
      expectedEvidence: { type: "test", checkName: "c1", description: "d1" },
    },
    {
      id: "step-2",
      title: "Step 2",
      tool: "tool-2",
      params: {},
      dependsOn: ["step-1"],
      timeoutMs: 5000,
      retryPolicy: { maxRetries: 1, backoffMs: 1000 },
      idempotencyKey: "k2",
      approvalRequired: false,
      expectedEvidence: { type: "test", checkName: "c2", description: "d2" },
    },
  ];

  const linearResult = validateDAG(linearSteps);
  assert.equal(linearResult.valid, true);
  assert.equal(linearResult.executionWaves.length, 2);
  assert.deepEqual(linearResult.executionWaves[0], ["step-1"]);
  assert.deepEqual(linearResult.executionWaves[1], ["step-2"]);

  // 2. Diamond DAG (Parallel Execution Waves)
  const diamondSteps: PlanStep[] = [
    {
      id: "root",
      title: "Root",
      tool: "t",
      params: {},
      dependsOn: [],
      timeoutMs: 5000,
      retryPolicy: { maxRetries: 1, backoffMs: 1000 },
      idempotencyKey: "k-root",
      approvalRequired: false,
      expectedEvidence: { type: "t", checkName: "c", description: "d" },
    },
    {
      id: "branch-a",
      title: "Branch A",
      tool: "t",
      params: {},
      dependsOn: ["root"],
      timeoutMs: 5000,
      retryPolicy: { maxRetries: 1, backoffMs: 1000 },
      idempotencyKey: "k-a",
      approvalRequired: false,
      expectedEvidence: { type: "t", checkName: "c", description: "d" },
    },
    {
      id: "branch-b",
      title: "Branch B",
      tool: "t",
      params: {},
      dependsOn: ["root"],
      timeoutMs: 5000,
      retryPolicy: { maxRetries: 1, backoffMs: 1000 },
      idempotencyKey: "k-b",
      approvalRequired: false,
      expectedEvidence: { type: "t", checkName: "c", description: "d" },
    },
    {
      id: "join",
      title: "Join",
      tool: "t",
      params: {},
      dependsOn: ["branch-a", "branch-b"],
      timeoutMs: 5000,
      retryPolicy: { maxRetries: 1, backoffMs: 1000 },
      idempotencyKey: "k-join",
      approvalRequired: false,
      expectedEvidence: { type: "t", checkName: "c", description: "d" },
    },
  ];

  const diamondResult = validateDAG(diamondSteps);
  assert.equal(diamondResult.valid, true);
  assert.equal(diamondResult.executionWaves.length, 3);
  assert.deepEqual(diamondResult.executionWaves[0], ["root"]);
  assert.equal(diamondResult.executionWaves[1].length, 2);
  assert.ok(diamondResult.executionWaves[1].includes("branch-a"));
  assert.ok(diamondResult.executionWaves[1].includes("branch-b"));
  assert.deepEqual(diamondResult.executionWaves[2], ["join"]);

  // 3. Circular Dependency Detection
  const circularSteps: PlanStep[] = [
    {
      id: "loop-1",
      title: "Loop 1",
      tool: "t",
      params: {},
      dependsOn: ["loop-2"],
      timeoutMs: 5000,
      retryPolicy: { maxRetries: 1, backoffMs: 1000 },
      idempotencyKey: "l1",
      approvalRequired: false,
      expectedEvidence: { type: "t", checkName: "c", description: "d" },
    },
    {
      id: "loop-2",
      title: "Loop 2",
      tool: "t",
      params: {},
      dependsOn: ["loop-1"],
      timeoutMs: 5000,
      retryPolicy: { maxRetries: 1, backoffMs: 1000 },
      idempotencyKey: "l2",
      approvalRequired: false,
      expectedEvidence: { type: "t", checkName: "c", description: "d" },
    },
  ];

  const circularResult = validateDAG(circularSteps);
  assert.equal(circularResult.valid, false);
  assert.ok(circularResult.cycles && circularResult.cycles.length > 0);

  // 4. Remediation Plan Synthesis
  const releasePlan = generateRemediationPlan("api", "RELEASE_COMMIT_MISMATCH");
  assert.ok(releasePlan.planId.startsWith("plan-"));
  assert.equal(releasePlan.intent, "remediation");
  assert.equal(releasePlan.targetService, "api");
  assert.equal(releasePlan.steps.length, 3);
  assert.equal(releasePlan.steps[1].approvalRequired, true, "Deployment step must require approval");
  assert.ok(releasePlan.steps[1].rollbackAction, "Deployment step must have a rollback action");

  const schemaPlan = generateRemediationPlan("api", "SCHEMA_PARITY_BREACH");
  assert.equal(schemaPlan.steps.length, 2);
  assert.equal(schemaPlan.steps[0].tool, "supabase.schema_inspect");

  // 5. Custom Plan Creation
  const customPlan = createCustomPlan("Optimize gateway routes", "api", [
    { id: "analyze", title: "Analyze metrics", tool: "system.diagnose" },
    { id: "patch", title: "Apply patch", tool: "render.env_vars_set", dependsOn: ["analyze"] },
  ]);
  assert.equal(customPlan.goal, "Optimize gateway routes");
  assert.equal(customPlan.executionWaves.length, 2);

  // 6. Verification Gate Contract Tests
  // Generic target with all passing facts
  const passGeneric = await verifyOutcome("generic", "api", "all_passed", [
    { name: "test_suite", status: "pass", value: { passed: 42 } },
    { name: "lint", status: "pass", value: { clean: true } },
  ]);
  assert.equal(passGeneric.verdict, "verified");
  assert.equal(passGeneric.actualStatus, "pass");

  // Generic target with failed fact
  const failGeneric = await verifyOutcome("generic", "api", "expect_pass", [
    { name: "smoke", status: "fail", value: { error: "HTTP 502" } },
  ]);
  assert.equal(failGeneric.verdict, "rejected");
  assert.equal(failGeneric.actualStatus, "fail");

  // Generic target without facts -> unverified (fail-closed)
  const unverifiedGeneric = await verifyOutcome("generic", "api", "expect_pass");
  assert.equal(unverifiedGeneric.verdict, "unverified");
  assert.equal(unverifiedGeneric.actualStatus, "unknown");

  // Schema target
  const schemaVerify = await verifyOutcome("schema", "api");
  assert.ok(["verified", "rejected", "unverified"].includes(schemaVerify.verdict));

  console.log("Phase 3 DAG planning engine & verifier tests passed successfully!");
}

runTests().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});

