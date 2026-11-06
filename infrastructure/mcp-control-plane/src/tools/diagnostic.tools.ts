import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { env } from "../lib/env.js";
import { getLatestDeploy, getServiceHealth, listLogs } from "../adapters/render/index.js";
import { getRepositoryHead, getWorkflowRuns } from "../adapters/github/index.js";
import { RequestContextStore, roleRank, type UserRole } from "../policy/auth.context.js";
import { aggregateStatus, confidenceFor, fact, type EvidenceCheck } from "../diagnostics/evidence.js";
import { resolveServiceTarget, type AuthoritativeServiceTarget } from "../diagnostics/service_manifest.js";
import { redactSensitiveData } from "../diagnostics/redaction.js";

type CheckStatus = "pass" | "fail" | "unknown" | "error";
export type DiagnosticCheck = EvidenceCheck;

interface ServiceTarget extends AuthoritativeServiceTarget {}

function assertDiagnosticAccess(toolName: string, minRole: UserRole): string | null {
  const store = RequestContextStore.get();
  if (!store) return `Forbidden: tool '${toolName}' requires an authenticated request context (default-deny).`;
  return roleRank(store.role) >= roleRank(minRole)
    ? null
    : `Forbidden: tool '${toolName}' requires ${minRole} role or higher (current role: '${store.role}').`;
}

function resolveTarget(service: string): ServiceTarget | null {
  // Use authoritative registry from config/service_registry.yaml first
  const resolved = resolveServiceTarget(service);
  if (resolved) return resolved;

  // Fallback to minimal static defaults if registry is missing
  const targets: Record<string, ServiceTarget> = {
    "backend-api": {
      name: "backend-api",
      role: "Gateway",
      platform: "render",
      renderAccountId: "render-primary",
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
      renderAccountId: "render-primary",
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

function compareCommitEvidence(
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
  try {
    const response = await fetch(`${target.runtimeUrl.replace(/\/$/, "")}/release`, {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(5_000),
    });
    if (!response.ok) return null;
    const body = await response.json() as unknown;
    return body && typeof body === "object" ? body as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

export async function diagnoseRelease(
  service: string,
  intent: "is_deploy_correct" | "root_cause" | "is_healthy" = "is_deploy_correct",
): Promise<Record<string, unknown>> {
  const target = resolveTarget(service);
  if (!target) {
    return {
      status: "unknown",
      service,
      intent,
      findings: [{ severity: "high", code: "SERVICE_NOT_MAPPED", message: "No authoritative service mapping exists; no provider was queried." }],
      checks: [],
    };
  }

  const [head, deploy, health, runtime, logs, runs] = await Promise.allSettled([
    getRepositoryHead(target.repo, target.branch),
    getLatestDeploy(target.renderAccountId, target.renderServiceId),
    getServiceHealth(target.renderAccountId, target.renderServiceId),
    readRuntimeRelease(target),
    listLogs(target.renderAccountId, target.renderServiceId, { type: "app", level: "error", limit: 20 }),
    getWorkflowRuns(target.repo, 5),
  ]);

  const intendedCommit = head.status === "fulfilled" ? shortSha(head.value.sha) : null;
  const deployedCommit = deploy.status === "fulfilled" ? shortSha(deploy.value.commitSha) : null;
  const runtimeBody = runtime.status === "fulfilled" ? runtime.value : null;
  const runtimeCommit = runtimeBody ? shortSha(
    typeof runtimeBody.commit === "string" ? runtimeBody.commit : typeof runtimeBody.commitSha === "string" ? runtimeBody.commitSha : null,
  ) : null;
  const runtimeStatus: CheckStatus = runtime.status === "fulfilled" && runtimeBody ? "pass" : "unknown";
  const healthStatus: CheckStatus = health.status === "fulfilled" ? "pass" : "error";
  const logCount = logs.status === "fulfilled" ? logs.value.count : null;
  const ci = runs.status === "fulfilled" ? extractLatestSuccessfulRun(runs.value, intendedCommit) : { sha: null, conclusion: null, branch: null };
  const ciCommit = ci.sha;

  const checks: EvidenceCheck[] = [
    { name: "provider_health", status: healthStatus, details: health.status === "fulfilled" ? { observed: "Render API returned service data" } : { error: health.reason instanceof Error ? health.reason.message : "health lookup failed" } },
    { name: "intended_source", status: intendedCommit ? "pass" : "unknown", details: { repository: target.repo, branch: target.branch, commit: intendedCommit } },
    { name: "ci_evidence", status: ciCommit ? (ciCommit === intendedCommit ? "pass" : "fail") : "unknown", details: { latestRunCommit: ciCommit, intendedCommit } },
    { name: "runtime_metadata", status: runtimeStatus, details: { url: `${target.runtimeUrl}/release`, commit: runtimeCommit } },
    { name: "recent_error_logs", status: logs.status === "fulfilled" ? (logCount && logCount > 0 ? "fail" : "pass") : "unknown", details: { count: logCount, window: "adapter default" } },
    compareCommitEvidence(intendedCommit, deployedCommit, runtimeCommit),
  ];

  // Intent is a policy selector, not decoration. A root-cause request must
  // include temporal/log evidence; a release request must prove source→CI→deploy→runtime.
  if (intent === "root_cause" && logs.status !== "fulfilled") {
    checks.push({ name: "root_cause_evidence", status: "unknown", confidence: 0.1, facts: [fact("render.logs", "unknown", undefined, "runtime logs unavailable")], explanation: "Root cause cannot be proven without runtime evidence." });
  }
  if (intent === "is_deploy_correct" && ci.conclusion !== "success") {
    checks.push({ name: "ci_gate", status: "unknown", confidence: 0.1, facts: [fact("github.actions", "unknown", { conclusion: ci.conclusion, commit: ciCommit })], explanation: "No successful CI run for the intended commit was proven." });
  }

  const status = aggregateStatus(checks);
  const failed = checks.filter((check) => check.status === "fail");
  const findings = failed.map((check) => ({
    severity: check.name === "release_integrity" ? "critical" : "high",
    code: check.name === "release_integrity" ? "DEPLOYMENT_COMMIT_MISMATCH" : "DIAGNOSTIC_CHECK_FAILED",
    message: check.name === "release_integrity"
      ? "Render may be healthy while the deployed/runtime commit differs from the intended release."
      : `${check.name} failed`,
    evidence: check.details,
  }));

  return {
    status,
    service: target.name,
    repository: target.repo,
    branch: target.branch,
    intent,
    confidence: Math.min(...checks.map((check) => check.confidence ?? 0.8)),
    checks,
    findings,
    evidence: {
      latestDeploy: deploy.status === "fulfilled" ? deploy.value : null,
      latestWorkflowCommit: ciCommit,
      runtimeRelease: runtimeBody,
      recentErrorCount: logCount,
    },
    errors: [head, deploy, health, runtime, logs, runs]
      .filter((item): item is PromiseRejectedResult => item.status === "rejected")
      .map((item) => item.reason instanceof Error ? item.reason.message : "provider lookup failed"),
  };
}

export async function registerDiagnosticTools(server: McpServer): Promise<void> {
  server.registerTool(
    "system.diagnose",
    {
      description: "Evidence-based deployment diagnosis: compares intended GitHub commit, CI, Render deploy, runtime release metadata, health, and recent errors. Healthy provider status alone never produces a healthy release verdict.",
      annotations: { readOnlyHint: true, idempotentHint: true },
      inputSchema: {
        intent: z.enum(["is_deploy_correct", "root_cause", "is_healthy"]).default("is_deploy_correct"),
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
}

export { compareCommitEvidence, resolveTarget };
