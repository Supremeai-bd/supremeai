import assert from "node:assert/strict";
import {
  SERVICE_TOPOLOGY_MAP,
  getDownstreamServices,
  probeSchemaParity,
  probeServiceDependencies,
} from "./src/diagnostics/dependency_graph.js";
import {
  compareCommitEvidence,
  diagnoseRelease,
  resolveTarget,
} from "./src/tools/diagnostic.tools.js";

async function runTests() {
  console.log("Running Phase 1 & Phase 2 diagnostic contract tests...");

  // 1. Topology & Downstream Mapping Tests
  assert.ok(SERVICE_TOPOLOGY_MAP.api, "API service must exist in topology map");
  assert.ok(SERVICE_TOPOLOGY_MAP.core, "Core service must exist in topology map");
  assert.ok(SERVICE_TOPOLOGY_MAP.worker, "Worker service must exist in topology map");

  const apiDownstream = getDownstreamServices("api");
  assert.ok(apiDownstream.includes("frontend"), "Frontend must depend on API downstream");
  assert.ok(apiDownstream.includes("scraper"), "Scraper must depend on API downstream");

  // 2. Schema Parity Tests
  // Service without DB dependency -> must pass immediately
  const scraperParity = await probeSchemaParity("scraper");
  assert.equal(scraperParity.status, "pass");
  assert.equal(scraperParity.name, "schema_parity");

  // Service with DB dependency (api) -> must return pass or unknown (never crash)
  const apiParity = await probeSchemaParity("api");
  assert.ok(
    apiParity.status === "pass" || apiParity.status === "unknown" || apiParity.status === "fail",
    "API schema parity check must return valid EvidenceStatus",
  );

  // 3. Dependency Probing Tests
  const depReport = await probeServiceDependencies("api");
  assert.equal(depReport.service, "api");
  assert.ok(Array.isArray(depReport.dependencies));
  assert.ok(depReport.dependencies.length >= 2, "API should have at least supabase and core dependencies");
  assert.ok(
    ["pass", "fail", "unknown"].includes(depReport.overallStatus),
    "Overall dependency status must be valid",
  );

  // 4. Commit Evidence Matching
  const match = compareCommitEvidence("sha-123", "sha-123", "sha-123");
  assert.equal(match.status, "pass");

  const mismatch = compareCommitEvidence("sha-new", "sha-old", "sha-old");
  assert.equal(mismatch.status, "fail");

  const unk = compareCommitEvidence("sha-new", null, null);
  assert.equal(unk.status, "unknown");

  // 5. Target Resolution
  const apiTarget = resolveTarget("api");
  assert.ok(apiTarget, "API target should resolve from authoritative manifest");
  assert.equal(apiTarget?.name, "api");
  assert.ok(Array.isArray(apiTarget?.watchPaths), "API target must have watchPaths array");

  // 6. Unmapped Service Diagnostic
  const unmapped = await diagnoseRelease("non-existent-service", "is_deploy_correct");
  assert.equal(unmapped.status, "unknown");
  assert.equal((unmapped as any).truthMatrix.providerHealth, "unknown");
  assert.equal((unmapped as any).truthMatrix.serviceHealth, "unknown");
  assert.equal((unmapped as any).truthMatrix.releaseIntegrity, "unknown");

  // 7. Full Diagnostic Sweep with 6 Truth Dimensions & Intents
  // Intent: is_deploy_correct
  const diagDeploy = await diagnoseRelease("api", "is_deploy_correct");
  assert.ok(diagDeploy.truthMatrix, "Truth matrix must be present");
  const truths = (diagDeploy as any).truthMatrix;
  assert.ok(truths.providerHealth, "providerHealth dimension must exist");
  assert.ok(truths.serviceHealth, "serviceHealth dimension must exist");
  assert.ok(truths.releaseIntegrity, "releaseIntegrity dimension must exist");
  assert.ok(truths.dependencyHealth, "dependencyHealth dimension must exist");
  assert.ok(truths.schemaParity, "schemaParity dimension must exist");
  assert.ok(truths.userJourneyHealth, "userJourneyHealth dimension must exist");

  // Intent: release_verify
  const diagRelease = await diagnoseRelease("api", "release_verify");
  assert.ok(diagRelease.releaseVerdict, "releaseVerdict must be generated for release_verify intent");
  assert.ok(
    ["PROCEED_RELEASE_VERIFIED", "REJECT_RELEASE_INTEGRITY_DRIFT"].includes(diagRelease.releaseVerdict as string),
    "releaseVerdict must be either PROCEED or REJECT",
  );

  // Intent: root_cause
  const diagRoot = await diagnoseRelease("api", "root_cause");
  assert.ok(diagRoot.rootCauseReport, "rootCauseReport must exist for root_cause intent");
  const report = diagRoot.rootCauseReport as any;
  assert.ok(report.primaryFailureLayer, "primaryFailureLayer must be identified");
  assert.ok(report.remediationSummary, "remediationSummary must be provided");

  // Intent: incident_timeline
  const diagTimeline = await diagnoseRelease("api", "incident_timeline");
  assert.ok(diagTimeline.incidentTimeline, "incidentTimeline must exist for incident_timeline intent");
  const timeline = diagTimeline.incidentTimeline as any;
  assert.ok("postDeployErrorCount" in timeline, "postDeployErrorCount must be tracked");
  assert.ok("regressionCorrelation" in timeline, "regressionCorrelation must be computed");

  // Intent: change_impact
  const diagImpact = await diagnoseRelease("api", "change_impact");
  assert.ok(diagImpact.changeImpact, "changeImpact must exist for change_impact intent");
  const impact = diagImpact.changeImpact as any;
  assert.ok(Array.isArray(impact.watchPaths), "watchPaths must be populated");
  assert.ok(Array.isArray(impact.downstreamDependents), "downstreamDependents must be populated");
  assert.ok(impact.blastRadiusAssessment, "blastRadiusAssessment must be present");

  console.log("Phase 1 & Phase 2 contract tests passed successfully!");
}

runTests().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
