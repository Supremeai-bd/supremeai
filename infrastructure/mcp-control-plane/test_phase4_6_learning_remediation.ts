import assert from "node:assert/strict";
import { recordLearning, recallLearnings, learningStats, evaluateLearning } from "./src/learning/learning_gate.js";
import { savePlan, getPlan, listPlans, updatePlanStatus } from "./src/planning/plan_store.js";
import { createCustomPlan } from "./src/planning/planner.js";

async function runTests() {
  console.log("Running Phase 4 & Phase 6 Learning Gate, Plan Store, & Safe Remediation tests...");

  // 1. Learning Gate Quality Progression
  // a) No verifier -> candidate
  const candidate = recordLearning({
    tier: "semantic",
    fact: "Supabase primary database holds system audit logs and tasks",
    evidence: { probe: "openapi" },
  });
  assert.equal(candidate.status, "candidate");
  assert.equal(candidate.verifiedBy, null);

  // b) Supplied verifier -> trusted
  const trusted = recordLearning({
    tier: "procedural",
    fact: "To remediate commit mismatch, trigger render deployment and verify runtime release endpoint",
    evidence: { planId: "plan-123" },
    verifiedBy: "system.verify",
  });
  assert.equal(trusted.status, "trusted");
  assert.equal(trusted.verifiedBy, "system.verify");
  assert.ok(trusted.promotedAt);

  // c) Direct Contradiction -> quarantined
  // Existing trusted fact: "To remediate commit mismatch, trigger render deployment and verify runtime release endpoint"
  // Contradicting candidate: "never trigger render deployment to remediate commit mismatch"
  const contradictionEval = evaluateLearning({
    tier: "procedural",
    fact: "never trigger render deployment to remediate commit mismatch and verify",
    evidence: {},
    verifiedBy: "human-admin",
  });
  assert.equal(contradictionEval.status, "quarantined");
  assert.ok(contradictionEval.contradictionWith);

  // d) 3-Tier Recall
  const semanticRecall = recallLearnings({ tier: "semantic" });
  assert.ok(semanticRecall.length > 0);

  const stats = learningStats();
  assert.ok(stats.total >= 2);
  assert.ok(stats.byTier.semantic >= 1);
  assert.ok(stats.byTier.procedural >= 1);

  // 2. Durable Plan Store State
  const plan = createCustomPlan("Test plan store persistence", "api", [
    { id: "s1", title: "Step 1", tool: "system.diagnose" },
  ]);
  savePlan(plan);

  const fetched = getPlan(plan.planId);
  assert.ok(fetched);
  assert.equal(fetched?.planId, plan.planId);
  assert.equal(fetched?.status, "draft");

  updatePlanStatus(plan.planId, "completed");
  const updated = getPlan(plan.planId);
  assert.equal(updated?.status, "completed");

  const recentPlans = listPlans(5);
  assert.ok(recentPlans.length > 0);
  assert.ok(recentPlans.some((p) => p.planId === plan.planId));

  console.log("Phase 4 & Phase 6 contract tests passed successfully!");
}

runTests().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});

