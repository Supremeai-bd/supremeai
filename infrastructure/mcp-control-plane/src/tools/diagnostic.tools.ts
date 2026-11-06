import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { env } from "../lib/env.js";
import { getLatestDeploy, getServiceHealth, listLogs } from "../adapters/render/index.js";
import { getRepositoryHead, getWorkflowRuns } from "../adapters/github/index.js";
import { RequestContextStore, roleRank, type UserRole } from "../policy/auth.context.js";

type CheckStatus = "pass" | "fail" | "unknown" | "error";
export interface DiagnosticCheck {
  name: string;
  status: CheckStatus;
  details: Record<string, unknown>;
}

interface ServiceTarget {
  name: string;
  renderAccountId: string;
  renderServiceId: string;
  runtimeUrl: string;
  repo: string;
  branch: string;
}

function assertDiagnosticAccess(toolName: string, minRole: UserRole): string | null {
  const store = RequestContextStore.get();
  if (!store) return `Forbidden: tool '${toolName}' requires an authenticated request context (default-deny).`;
  return roleRank(store.role) >= roleRank(minRole)
    ? null
    : `Forbidden: tool '${toolName}' requires ${minRole} role or higher (current role: '${store.role}').`;
}

function resolveTarget(service: string): ServiceTarget | null {
  // Keep this first slice explicit and fail-closed. Do not silently map an
  // unknown service to the core API or to the GitHub default repository.
  const targets: Record<string, ServiceTarget> = {
    "backend-api": {
      name: "backend-api",
      renderAccountId: "render-primary",
      renderServiceId: env.render.api.serviceId,
      runtimeUrl: env.render.api.url,
      repo: env.github.repo,
      branch: "main",
    },
    api: {
      name: "api",
      renderAccountId: "render-primary",
      renderServiceId: env.render.api.serviceId,
      runtimeUrl: env.render.api.url,
      repo: env.github.repo,
      branch: "main",
    },
  };
  return targets[service] ?? null;
}

function shortSha(value: string | null | undefined): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function extractRunCommit(value: unknown): string | null {
  const root = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const runs = Array.isArray(root.workflow_runs) ? root.workflow_runs : Array.isArray(value) ? value : [];
  const first = runs[0] && typeof runs[0] === "object" ? runs[0] as Record<string, unknown> : {};
  return shortSha(typeof first.head_sha === "string" ? first.head_sha : typeof first.headSha === "string" ? first.headSha : null);
}

function compareCommitEvidence(
  intended: string | null,
  deployed: string | null,
  runtime: string | null,
): DiagnosticCheck {
  if (!intended || !deployed) {
    return { name: "release_integrity", status: "unknown", details: { intendedCommit: intended, deployedCommit: deployed, runtimeCommit: runtime, reason: "required commit evidence unavailable" } };
  }
  const deploymentMatches = intended === deployed;
  const runtimeMatches = !runtime || runtime === deployed;
  return {
    name: "release_integrity",
    status: deploymentMatches && runtimeMatches ? "pass" : "fail",
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

export async function diagnoseRelease(service: string): Promise<Record<string, unknown>> {
  const target = resolveTarget(service);
  if (!target) {
    return {
      status: "unknown",
      service,
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
  const runtimeStatus = runtime.status === "fulfilled" && runtimeBody ? "pass" : "unknown";
  const healthStatus = health.status === "fulfilled" ? "pass" : "error";
  const logCount = logs.status === "fulfilled" ? logs.value.count : null;
  const ciCommit = runs.status === "fulfilled" ? extractRunCommit(runs.value) : null;

  const checks: DiagnosticCheck[] = [
    { name: "provider_health", status: healthStatus, details: health.status === "fulfilled" ? { observed: "Render API returned service data" } : { error: health.reason instanceof Error ? health.reason.message : "health lookup failed" } },
    { name: "intended_source", status: intendedCommit ? "pass" : "unknown", details: { repository: target.repo, branch: target.branch, commit: intendedCommit } },
    { name: "ci_evidence", status: ciCommit ? (ciCommit === intendedCommit ? "pass" : "fail") : "unknown", details: { latestRunCommit: ciCommit, intendedCommit } },
    { name: "runtime_metadata", status: runtimeStatus, details: { url: `${target.runtimeUrl}/release`, commit: runtimeCommit } },
    { name: "recent_error_logs", status: logs.status === "fulfilled" ? (logCount && logCount > 0 ? "fail" : "pass") : "unknown", details: { count: logCount, window: "adapter default" } },
    compareCommitEvidence(intendedCommit, deployedCommit, runtimeCommit),
  ];

  const failed = checks.filter((check) => check.status === "fail");
  const unknown = checks.filter((check) => check.status === "unknown");
  const status = failed.length > 0 ? "critical" : unknown.length > 0 ? "unknown" : "healthy";
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
    async ({ service }) => {
      const denial = assertDiagnosticAccess("system.diagnose", "agent");
      if (denial) return { isError: true, content: [{ type: "text", text: denial }] };
      try {
        const result = await diagnoseRelease(service);
        return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
      } catch (error) {
        return { isError: true, content: [{ type: "text", text: JSON.stringify({ status: "unknown", error: error instanceof Error ? error.message : "diagnostic failed" }) }] };
      }
    },
  );
}

export { compareCommitEvidence, resolveTarget };
