import { type EvidenceCheck, type EvidenceStatus, fact, confidenceFor } from "../diagnostics/evidence.js";
import { diagnoseRelease } from "../tools/diagnostic.tools.js";
import { probeSchemaParity } from "../diagnostics/dependency_graph.js";

export interface VerificationReport {
  target: string;
  service?: string;
  expectedOutcome: string;
  actualStatus: EvidenceStatus;
  verdict: "verified" | "rejected" | "unverified";
  confidence: number;
  checks: EvidenceCheck[];
  timestamp: string;
  explanation: string;
}

/**
 * Empirically verifies the outcome of a service state, deployment, or schema migration.
 * Fail-closed doctrine: UNKNOWN or unverified state never produces a "verified" verdict.
 */
export async function verifyOutcome(
  target: "release" | "schema" | "service" | "generic",
  service: string = "api",
  expectedOutcome: string = "healthy",
  factsSupplied?: Array<{ name: string; status: EvidenceStatus; value?: unknown }>,
): Promise<VerificationReport> {
  const timestamp = new Date().toISOString();

  if (target === "release") {
    const diag = await diagnoseRelease(service, "release_verify");
    const verdict = (diag as any).releaseVerdict;
    const isPassing = verdict === "PROCEED_RELEASE_VERIFIED";
    const status: EvidenceStatus = isPassing ? "pass" : "fail";
    const checks = (diag.checks as EvidenceCheck[]) || [];

    return {
      target,
      service,
      expectedOutcome,
      actualStatus: status,
      verdict: isPassing ? "verified" : "rejected",
      confidence: isPassing ? 0.95 : 0.85,
      checks,
      timestamp,
      explanation: isPassing
        ? `Release integrity empirically verified: Git, CI, Render deploy, and runtime release are aligned.`
        : `Release integrity verification rejected: Commit mismatch, failed CI, or unverified runtime detected.`,
    };
  }

  if (target === "schema") {
    const schemaCheck = await probeSchemaParity(service);
    const isPassing = schemaCheck.status === "pass";
    const status: EvidenceStatus = schemaCheck.status;

    return {
      target,
      service,
      expectedOutcome,
      actualStatus: status,
      verdict: isPassing ? "verified" : status === "unknown" ? "unverified" : "rejected",
      confidence: schemaCheck.confidence ?? (isPassing ? 0.90 : 0.20),
      checks: [schemaCheck],
      timestamp,
      explanation: schemaCheck.explanation || (isPassing ? "Schema parity verified." : "Schema parity failed."),
    };
  }

  if (target === "service") {
    const diag = await diagnoseRelease(service, "is_healthy");
    const tm = (diag as any).truthMatrix;
    const isHealthy = tm?.serviceHealth === "pass" && tm?.providerHealth === "pass";
    const status: EvidenceStatus = isHealthy ? "pass" : tm?.serviceHealth === "fail" ? "fail" : "unknown";

    return {
      target,
      service,
      expectedOutcome,
      actualStatus: status,
      verdict: isHealthy ? "verified" : status === "unknown" ? "unverified" : "rejected",
      confidence: isHealthy ? 0.90 : 0.70,
      checks: (diag.checks as EvidenceCheck[]) || [],
      timestamp,
      explanation: isHealthy
        ? `Service ${service} health verified: HTTP endpoint returned 200 OK.`
        : `Service ${service} health verification failed.`,
    };
  }

  // Generic verification against supplied facts
  if (factsSupplied && factsSupplied.length > 0) {
    const allPassed = factsSupplied.every((f) => f.status === "pass");
    const anyFailed = factsSupplied.some((f) => f.status === "fail");
    const status: EvidenceStatus = allPassed ? "pass" : anyFailed ? "fail" : "unknown";
    const evidenceChecks: EvidenceCheck[] = factsSupplied.map((f) => ({
      name: f.name,
      status: f.status,
      confidence: 0.85,
      facts: [fact(f.name, f.status, f.value)],
    }));

    return {
      target,
      service,
      expectedOutcome,
      actualStatus: status,
      verdict: allPassed ? "verified" : anyFailed ? "rejected" : "unverified",
      confidence: confidenceFor(status, []),
      checks: evidenceChecks,
      timestamp,
      explanation: allPassed ? "All supplied evidence checks passed." : "One or more evidence checks failed.",
    };
  }

  return {
    target,
    service,
    expectedOutcome,
    actualStatus: "unknown",
    verdict: "unverified",
    confidence: 0.1,
    checks: [],
    timestamp,
    explanation: "No verifiable evidence or facts provided for generic verification target.",
  };
}

