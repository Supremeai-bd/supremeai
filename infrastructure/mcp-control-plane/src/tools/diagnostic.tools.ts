import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { env } from "../lib/env.js";
import { getLatestDeploy, getServiceHealth, listLogs, type RenderLogsResult } from "../adapters/render/index.js";
import { getRepositoryHead, getWorkflowRuns } from "../adapters/github/index.js";
import { RequestContextStore, roleRank, type UserRole } from "../policy/auth.context.js";
import { aggregateStatus, confidenceFor, fact, type EvidenceCheck, type EvidenceStatus } from "../diagnostics/evidence.js";
import { resolveServiceTarget, resolveServiceIdentity, type AuthoritativeServiceTarget } from "../diagnostics/service_manifest.js";
import { redactSensitiveData } from "../diagnostics/redaction.js";
import {
  probeServiceDependencies,
  probeSchemaParity,
  getDownstreamServices,
  type ServiceDependencyReport,
} from "../diagnostics/dependency_graph.js";
import { verifyReleaseCandidate, type ReleaseCandidate } from "../diagnostics/release_verifier.js";

type CheckStatus = EvidenceStatus;
export type DiagnosticCheck = EvidenceCheck;

export interface DiagnosticTruthMatrix {
  providerHealth: EvidenceStatus;
  serviceHealth: EvidenceStatus;
  releaseIntegrity: EvidenceStatus;
  dependencyHealth: EvidenceStatus;
  schemaParity: EvidenceStatus;
  userJourneyHealth: EvidenceStatus;
}

export type DiagnosticIntent =
  | "is_deploy_correct"
  | "root_cause"
  | "is_healthy"
  | "release_verify"
  | "incident_timeline"
  | "change_impact";

interface ServiceTarget extends AuthoritativeServiceTarget {}

function assertDiagnosticAccess(toolName: string, minRole: UserRole): string | null {
  const store = RequestContextStore.get();
  if (!store) return `Forbidden: tool '${toolName}' requires an authenticated request context (default-deny).`;
  return roleRank(store.role) >= roleRank(minRole)
    ? null
    : `Forbidden: tool '${toolName}' requires ${minRole} role or higher (current role: '${store.role}').`;
}

function resolveTarget(service: string): ServiceTarget | null {
  const resolved = resolveServiceTarget(service);
  if (resolved) return resolved;

  const targets: Record<string, ServiceTarget> = {
    "backend-api": {
      name: "backend-api",
      role: "Gateway",
      platform: "render",
      renderAccountId: "render-api",
      renderServiceId: env.render.api.serviceId,
      runtimeUrl: env.render.api.url,
      healthPath: "/healthz",
      readinessPath: "/readyz",
      releasePath: "/release",
      repo: env.github.repo,
      branch: "main",
    },
    api: {
      name: "api",
      role: "Gateway",
      platform: "render",
      renderAccountId: "render-api",
      renderServiceId: env.render.api.serviceId,
      runtimeUrl: env.render.api.url,
      healthPath: "/healthz",
      readinessPath: "/readyz",
      releasePath: "/release",
      repo: env.github.repo,
      branch: "main",
    },
  };
  return targets[service] ?? null;
}

function shortSha(value: string | null | undefined): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function extractLatestSuccessfulRun(
  value: unknown,
  intendedCommit: string | null,
): { sha: string | null; conclusion: string | null; branch: string | null } {
  const root = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const runs = Array.isArray(root.workflow_runs) ? root.workflow_runs : Array.isArray(value) ? value : [];
  const candidates = runs.filter((run) => run && typeof run === "object") as Record<string, unknown>[];
  const matching = candidates.find((run) => {
    const sha = typeof run.head_sha === "string" ? run.head_sha : typeof run.headSha === "string" ? run.headSha : null;
    const conclusion = String(run.conclusion ?? "").toLowerCase();
    return (!intendedCommit || sha === intendedCommit) && conclusion === "success";
  });
  const first = matching ?? candidates[0] ?? {};
  return {
    sha: shortSha(typeof first.head_sha === "string" ? first.head_sha : typeof first.headSha === "string" ? first.headSha : null),
    conclusion: typeof first.conclusion === "string" ? first.conclusion : null,
    branch: typeof first.head_branch === "string" ? first.head_branch : typeof first.headBranch === "string" ? first.headBranch : null,
  };
}

export function compareCommitEvidence(
  intended: string | null,
  deployed: string | null,
  runtime: string | null,
): EvidenceCheck {
  if (!intended || !deployed) {
    return {
      name: "release_integrity",
      status: "unknown",
      confidence: 0.1,
      facts: [fact("comparison", "unknown", undefined, "required commit evidence unavailable")],
      details: { intendedCommit: intended, deployedCommit: deployed, runtimeCommit: runtime, reason: "required commit evidence unavailable" },
    };
  }
  const deploymentMatches = intended === deployed;
  const runtimeMatches = !runtime || runtime === deployed;
  const status: CheckStatus = deploymentMatches && runtimeMatches ? "pass" : "fail";
  const facts = [
    fact("github.intended", intended ? "pass" : "unknown", intended),
    fact("render.deployed", deployed ? "pass" : "unknown", deployed),
    ...(runtime ? [fact("runtime.release", "pass", runtime)] : []),
  ];
  return {
    name: "release_integrity",
    status,
    confidence: confidenceFor(status, facts),
    facts,
    details: {
      intendedCommit: intended,
      deployedCommit: deployed,
      runtimeCommit: runtime,
      deploymentMatches,
      runtimeMatches,
      rule: "intended == deployed == runtime (when runtime metadata is available)",
    },
  };
}

async function readRuntimeRelease(target: ServiceTarget): Promise<Record<string, unknown> | null> {
  if (!target.runtimeUrl) return null;
  try {
    const response = await fetch(`${target.runtimeUrl.replace(/\/$/, "")}${target.releasePath || "/release"}`, {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(4_000),
    });
    if (!response.ok) return null;
    const body = await response.json() as unknown;
    return body && typeof body === "object" ? body as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

async function probeDirectHttpHealth(target: ServiceTarget): Promise<EvidenceCheck> {
  if (!target.runtimeUrl) {
    return {
      name: "service_health",
      status: "unknown",
      confidence: 0.1,
      facts: [fact("runtime.http", "unknown", undefined, "No runtime URL configured")],
      explanation: "No runtime URL configured for service.",
      details: { service: target.name },
    };
  }

  const start = Date.now();
  const url = `${target.runtimeUrl.replace(/\/$/, "")}${target.healthPath || "/health"}`;
  try {
    const response = await fetch(url, {
      headers: { Accept: "application/json, text/plain, */*" },
      signal: AbortSignal.timeout(4_000),
    });
    const latencyMs = Date.now() - start;
    const isPassing = response.status < 400;
    const status: EvidenceStatus = isPassing ? "pass" : "fail";
    const facts = [fact("runtime.http", status, { status: response.status, latencyMs, url })];

    return {
      name: "service_health",
      status,
      confidence: confidenceFor(status, facts),
      facts,
      explanation: isPassing ? `Endpoint responded with HTTP ${response.status} in ${latencyMs}ms` : `Endpoint returned HTTP ${response.status}`,
      details: { url, status: response.status, latencyMs },
    };
  } catch (err) {
    const latencyMs = Date.now() - start;
    const msg = err instanceof Error ? err.message : String(err);
    const facts = [fact("runtime.http", "fail", undefined, msg)];
    return {
      name: "service_health",
      status: "fail",
      confidence: 0.85,
      facts,
      explanation: `HTTP probe failed: ${msg}`,
      details: { url, error: msg, latencyMs },
    };
  }
}

export async function diagnoseRelease(
  service: string,
  intent: DiagnosticIntent = "is_deploy_correct",
): Promise<Record<string, unknown>> {
  const identity = resolveServiceIdentity(service);
  if (identity && !identity.verified) {
    return {
      status: "configuration_error",
      service,
      intent,
      truthMatrix: {
        providerHealth: "unknown",
        serviceHealth: "unknown",
        releaseIntegrity: "unknown",
        dependencyHealth: "unknown",
        schemaParity: "unknown",
        userJourneyHealth: "unknown",
      },
      findings: [{ severity: "high", code: "SERVICE_IDENTITY_INVALID", message: identity.verificationError ?? "Service identity could not be verified." }],
      checks: [],
    };
  }

  const target = resolveTarget(service);
  if (!target) {
    return {
      status: "unknown",
      service,
      intent,
      truthMatrix: {
        providerHealth: "unknown",
        serviceHealth: "unknown",
        releaseIntegrity: "unknown",
        dependencyHealth: "unknown",
        schemaParity: "unknown",
        userJourneyHealth: "unknown",
      },
      findings: [{ severity: "high", code: "SERVICE_NOT_MAPPED", message: "No authoritative service mapping exists; no provider was queried." }],
      checks: [],
    };
  }

  const [head, deploy, health, runtime, directHttp, logs, runs, depReport, schemaCheck] = await Promise.allSettled([
    getRepositoryHead(target.repo, target.branch),
    getLatestDeploy(target.renderAccountId, target.renderServiceId),
    getServiceHealth(target.renderAccountId, target.renderServiceId),
    readRuntimeRelease(target),
    probeDirectHttpHealth(target),
    listLogs(target.renderAccountId, target.renderServiceId, { type: "app", level: "error", limit: 25 }),
    getWorkflowRuns(target.repo, 5),
    probeServiceDependencies(target.name),
    probeSchemaParity(target.name),
  ]);

  const intendedCommit = head.status === "fulfilled" ? shortSha(head.value.sha) : null;
  const deployedCommit = deploy.status === "fulfilled" ? shortSha(deploy.value.commitSha) : null;
  const runtimeBody = runtime.status === "fulfilled" ? runtime.value : null;
  const runtimeCommit = runtimeBody ? shortSha(
    typeof runtimeBody.commit === "string" ? runtimeBody.commit : typeof runtimeBody.commitSha === "string" ? runtimeBody.commitSha : null,
  ) : null;
  const runtimeStatus: CheckStatus = runtime.status === "fulfilled" && runtimeBody ? "pass" : "unknown";
  // Provider health must reflect the actual service state, not just a successful
  // adapter call. A resolved Render response whose service is suspended or missing
  // is not healthy.
  const healthBody = health.status === "fulfilled" ? (health.value as Record<string, unknown> | null) : null;
  const serviceBody = healthBody && typeof healthBody.service === "object" && healthBody.service !== null
    ? (healthBody.service as Record<string, unknown>)
    : null;
  const isRenderConfigError =
    (health.status === "rejected" && /404|configuration_error|not found/i.test(String(health.reason))) ||
    (deploy.status === "rejected" && /404|configuration_error|not found/i.test(String(deploy.reason)));

  const healthStatus: CheckStatus = health.status === "rejected"
    ? (isRenderConfigError ? "unknown" : "fail")
    : serviceBody
      ? (serviceBody.suspended === "suspended" ? "fail" : "pass")
      : "unknown";
  const serviceHttpCheck: EvidenceCheck = directHttp.status === "fulfilled" ? directHttp.value : { name: "service_health", status: "error", details: { error: "Probe failed" } };

  const logResult: RenderLogsResult | null = logs.status === "fulfilled" ? logs.value : null;
  const logCount = logResult ? logResult.count : null;
  const ci = runs.status === "fulfilled" ? extractLatestSuccessfulRun(runs.value, intendedCommit) : { sha: null, conclusion: null, branch: null };
  const ciCommit = ci.sha;

  const depResult: ServiceDependencyReport = depReport.status === "fulfilled"
    ? depReport.value
    : { service: target.name, overallStatus: "unknown", dependencies: [], impactedDownstreamServices: getDownstreamServices(target.name) };

  const schemaParityCheck: EvidenceCheck = schemaCheck.status === "fulfilled"
    ? schemaCheck.value
    : { name: "schema_parity", status: "unknown", details: { error: "Schema parity check could not be executed" } };

  const releaseCheck = compareCommitEvidence(intendedCommit, deployedCommit, runtimeCommit);

  const userJourneyStatus: EvidenceStatus = logResult
    ? (logCount && logCount > 0 ? "fail" : "pass")
    : "unknown";

  // Construct 6-dimension Truth Matrix
  const truthMatrix: DiagnosticTruthMatrix = {
    providerHealth: healthStatus === "pass" ? "pass" : isRenderConfigError ? "unknown" : "fail",
    serviceHealth: serviceHttpCheck.status,
    releaseIntegrity: releaseCheck.status,
    dependencyHealth: depResult.overallStatus,
    schemaParity: schemaParityCheck.status,
    userJourneyHealth: userJourneyStatus,
  };

  const checks: EvidenceCheck[] = [
    {
      name: "provider_health",
      status: healthStatus,
      details: health.status === "fulfilled"
        ? { observed: "Render API returned service data" }
        : isRenderConfigError
          ? { error: "Render API returned 404: service not found on configured account", type: "configuration_error" }
          : { error: health.reason instanceof Error ? health.reason.message : "health lookup failed" },
    },
    serviceHttpCheck,
    { name: "intended_source", status: intendedCommit ? "pass" : "unknown", details: { repository: target.repo, branch: target.branch, commit: intendedCommit } },
    {
      name: "ci_evidence",
      status: !ciCommit
        ? "unknown"
        : ci.conclusion !== "success"
          ? "fail"
          : intendedCommit && ciCommit !== intendedCommit
            ? "fail"
            : ci.branch && ci.branch !== target.branch
              ? "fail"
              : "pass",
      details: { latestRunCommit: ciCommit, intendedCommit, conclusion: ci.conclusion, branch: ci.branch, targetBranch: target.branch },
    },
    { name: "runtime_metadata", status: runtimeStatus, details: { url: `${target.runtimeUrl}/release`, commit: runtimeCommit } },
    { name: "recent_error_logs", status: userJourneyStatus, details: { count: logCount, window: logResult?.window ?? "15m" } },
    releaseCheck,
    {
      name: "dependency_health",
      status: depResult.overallStatus,
      details: { dependencies: depResult.dependencies, downstreamImpact: depResult.impactedDownstreamServices },
    },
    schemaParityCheck,
  ];

  if (isRenderConfigError) {
    checks.push({
      name: "service_configuration",
      status: "fail",
      confidence: 0.95,
      facts: [fact("render.service_lookup", "fail", { error: "Render returned HTTP 404: service not found on configured account" })],
      explanation: `Render service lookup failed for '${target.renderServiceId}' on account '${target.renderAccountId}' (HTTP 404). Configuration error: invalid service ID mapping.`,
      details: {
        service: target.name,
        accountId: target.renderAccountId,
        serviceId: target.renderServiceId,
        type: "configuration_error",
      },
    });
  }

  // Intent Specific Synthesis
  let rootCauseReport: Record<string, unknown> | null = null;
  let releaseVerdict: string | null = null;
  let releaseCandidate: ReleaseCandidate | null = null;
  let incidentTimeline: Record<string, unknown> | null = null;
  let changeImpact: Record<string, unknown> | null = null;

  if (intent === "is_deploy_correct" && ci.conclusion !== "success") {
    checks.push({ name: "ci_gate", status: "unknown", confidence: 0.1, facts: [fact("github.actions", "unknown", { conclusion: ci.conclusion, commit: ciCommit })], explanation: "No successful CI run for the intended commit was proven." });
  }

  if (intent === "release_verify") {
    const isVerified =
      truthMatrix.releaseIntegrity === "pass" &&
      truthMatrix.serviceHealth === "pass" &&
      ci.conclusion === "success" &&
      truthMatrix.userJourneyHealth === "pass" &&
      truthMatrix.dependencyHealth !== "fail" &&
      truthMatrix.schemaParity !== "fail";

    releaseVerdict = isVerified ? "PROCEED_RELEASE_VERIFIED" : "REJECT_RELEASE_INTEGRITY_DRIFT";
    releaseCandidate = await verifyReleaseCandidate(target.name, {
      sourceCommit: intendedCommit,
      runtimeCommit: deployedCommit ?? runtimeCommit,
      ciRunId: ciCommit,
      deploymentId: deploy.status === "fulfilled" ? deploy.value.id : null,
      redisStatus: truthMatrix.dependencyHealth,
      supabaseStatus: truthMatrix.schemaParity,
      smokeStatus: truthMatrix.serviceHealth,
    });
  }

  if (intent === "root_cause") {
    const identifiedLayers: string[] = [];
    if (isRenderConfigError) {
      identifiedLayers.push("CONFIGURATION_ERROR");
      identifiedLayers.push("INVALID_SERVICE_ID_MAPPING");
    }
    if (truthMatrix.releaseIntegrity === "fail") identifiedLayers.push("RELEASE_COMMIT_MISMATCH");
    if (truthMatrix.schemaParity === "fail") identifiedLayers.push("SCHEMA_PARITY_BREACH");
    if (truthMatrix.dependencyHealth === "fail") identifiedLayers.push("UPSTREAM_DEPENDENCY_FAILURE");
    if (truthMatrix.userJourneyHealth === "fail") identifiedLayers.push("RUNTIME_APPLICATION_EXCEPTION");
    if (truthMatrix.providerHealth === "fail" && !isRenderConfigError) identifiedLayers.push("CLOUD_PROVIDER_OUTAGE");
    if (truthMatrix.releaseIntegrity === "unknown" || deployedCommit === null || deploy.status === "rejected") {
      if (!isRenderConfigError) {
        identifiedLayers.push("UNVERIFIED_RELEASE_IDENTITY");
      }
    }

    const primaryFailureLayer = identifiedLayers[0] || (checks.some((c) => c.status === "fail") ? "SYSTEM_DEGRADATION" : "NONE");

    rootCauseReport = {
      primaryFailureLayer,
      contributingFactors: identifiedLayers,
      remediationSummary: primaryFailureLayer === "CONFIGURATION_ERROR"
        ? "Verify Render service ID and account mapping in environment or registry. The configured service ID was not found on the account."
        : primaryFailureLayer === "RELEASE_COMMIT_MISMATCH"
          ? "Redeploy service to match latest tested git commit."
          : primaryFailureLayer === "UNVERIFIED_RELEASE_IDENTITY"
            ? "Verify Render service ID and account mapping. Ensure deployment metadata is accessible."
            : primaryFailureLayer === "SCHEMA_PARITY_BREACH"
              ? "Run missing database migrations against Supabase target."
              : primaryFailureLayer === "UPSTREAM_DEPENDENCY_FAILURE"
                ? "Restore failing upstream dependencies identified in dependency graph."
                : primaryFailureLayer === "RUNTIME_APPLICATION_EXCEPTION"
                  ? "Inspect application error logs for unhandled stack traces."
                  : primaryFailureLayer === "CLOUD_PROVIDER_OUTAGE"
                    ? "Escalate cloud provider outage or check service status."
                    : "No critical failure layer isolated.",
      blockingEvidence: (primaryFailureLayer === "UNVERIFIED_RELEASE_IDENTITY" || primaryFailureLayer === "CONFIGURATION_ERROR" || truthMatrix.releaseIntegrity === "unknown")
        ? {
            isRenderConfigError,
            deployRejection: deploy.status === "rejected" ? String(deploy.reason) : null,
            deployedCommit,
            intendedCommit,
            runtimeReleaseCommit: runtimeCommit,
          }
        : undefined,
    };
  }

  if (intent === "incident_timeline") {
    const deployData = deploy.status === "fulfilled" ? deploy.value : null;
    const deployCreated = deployData?.createdAt ? new Date(deployData.createdAt).getTime() : null;
    const deployFinished = deployData?.finishedAt ? new Date(deployData.finishedAt).getTime() : null;

    const errorEvents = (logResult?.logs || []).map((l) => {
      const logTime = l.timestamp ? new Date(l.timestamp).getTime() : null;
      let phase: "pre_deploy" | "during_deploy" | "post_deploy" | "unknown" = "unknown";
      if (logTime && deployFinished) {
        if (logTime > deployFinished) phase = "post_deploy";
        else if (deployCreated && logTime < deployCreated) phase = "pre_deploy";
        else phase = "during_deploy";
      }
      return {
        timestamp: l.timestamp,
        level: l.level,
        phase,
        message: l.message,
      };
    });

    const postDeployErrors = errorEvents.filter((e) => e.phase === "post_deploy").length;
    const preDeployErrors = errorEvents.filter((e) => e.phase === "pre_deploy").length;

    incidentTimeline = {
      deployCreatedAt: deployData?.createdAt ?? null,
      deployFinishedAt: deployData?.finishedAt ?? null,
      deployStatus: deployData?.status ?? null,
      totalErrorsInWindow: errorEvents.length,
      postDeployErrorCount: postDeployErrors,
      preDeployErrorCount: preDeployErrors,
      regressionCorrelation: postDeployErrors > 0 ? "HIGH_REGRESSION_CORRELATION" : "LOW_REGRESSION_CORRELATION",
      events: errorEvents.slice(0, 15),
    };
  }

  if (intent === "change_impact") {
    changeImpact = {
      service: target.name,
      watchPaths: target.watchPaths || [],
      downstreamDependents: depResult.impactedDownstreamServices,
      blastRadiusAssessment: depResult.impactedDownstreamServices.length > 0
        ? `High blast radius: changes affect ${depResult.impactedDownstreamServices.join(", ")}`
        : "Isolated blast radius: no downstream internal services declared.",
    };
  }

  const status = aggregateStatus(checks);
  const failed = checks.filter((check) => check.status === "fail");
  const findings = failed.map((check) => ({
    severity: check.name === "release_integrity" || check.name === "schema_parity" ? "critical" : "high",
    code: check.name === "release_integrity"
      ? "DEPLOYMENT_COMMIT_MISMATCH"
      : check.name === "schema_parity"
        ? "SCHEMA_BEHIND_CODE"
        : `${check.name.toUpperCase()}_FAILED`,
    message: check.name === "release_integrity"
      ? "Render may be healthy while the deployed/runtime commit differs from the intended release."
      : check.name === "schema_parity"
        ? "Database schema is missing core tables required by code models."
        : `${check.name} failed diagnostic verification`,
    evidence: check.details,
  }));

  return {
    status,
    service: target.name,
    repository: target.repo,
    branch: target.branch,
    intent,
    truthMatrix,
    confidence: Math.min(...checks.map((check) => check.confidence ?? 0.8)),
    checks,
    findings,
    evidence: {
      latestDeploy: deploy.status === "fulfilled" ? deploy.value : null,
      latestWorkflowCommit: ciCommit,
      runtimeRelease: runtimeBody,
      recentErrorCount: logCount,
      dependencies: depResult,
    },
    ...(rootCauseReport ? { rootCauseReport } : {}),
    ...(releaseVerdict ? { releaseVerdict } : {}),
    ...(releaseCandidate ? { releaseCandidate } : {}),
    ...(incidentTimeline ? { incidentTimeline } : {}),
    ...(changeImpact ? { changeImpact } : {}),
    errors: [head, deploy, health, runtime, directHttp, logs, runs, depReport, schemaCheck]
      .filter((item): item is PromiseRejectedResult => item.status === "rejected")
      .map((item) => item.reason instanceof Error ? item.reason.message : "provider lookup failed"),
  };
}

export async function registerDiagnosticTools(server: McpServer): Promise<void> {
  server.registerTool(
    "system.diagnose",
    {
      description: "Evidence-based deployment & system diagnosis across 6 truth dimensions (providerHealth, serviceHealth, releaseIntegrity, dependencyHealth, schemaParity, userJourneyHealth). Supports intents: is_deploy_correct, root_cause, is_healthy, release_verify, incident_timeline, change_impact.",
      annotations: { readOnlyHint: true, idempotentHint: true },
      inputSchema: {
        intent: z.enum([
          "is_deploy_correct",
          "root_cause",
          "is_healthy",
          "release_verify",
          "incident_timeline",
          "change_impact",
        ]).default("is_deploy_correct"),
        service: z.string().default("backend-api"),
      },
    },
    async ({ intent, service }) => {
      const denial = assertDiagnosticAccess("system.diagnose", "agent");
      if (denial) return { isError: true, content: [{ type: "text", text: denial }] };
      try {
        const result = await diagnoseRelease(service, intent);
        return { content: [{ type: "text", text: JSON.stringify(redactSensitiveData(result), null, 2) }] };
      } catch (error) {
        return { isError: true, content: [{ type: "text", text: JSON.stringify({ status: "unknown", error: error instanceof Error ? error.message : "diagnostic failed" }) }] };
      }
    },
  );

  server.registerTool(
    "system.verify_release",
    {
      description: "Computes an immutable ReleaseCandidate provenance record comparing GitHub source commit, Render deployed commit, Redis parity, Supabase schema parity, and smoke health.",
      annotations: { readOnlyHint: true, idempotentHint: true },
      inputSchema: {
        service: z.string().default("api"),
      },
    },
    async ({ service }) => {
      const denial = assertDiagnosticAccess("system.verify_release", "agent");
      if (denial) return { isError: true, content: [{ type: "text", text: denial }] };
      try {
        const rc = await verifyReleaseCandidate(service);
        return { content: [{ type: "text", text: JSON.stringify(redactSensitiveData(rc), null, 2) }] };
      } catch (error) {
        return { isError: true, content: [{ type: "text", text: JSON.stringify({ status: "blocked", error: error instanceof Error ? error.message : "release verification failed" }) }] };
      }
    },
  );
}

export { resolveTarget };
