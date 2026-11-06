import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { RequestContextStore, roleRank, type UserRole } from "../policy/auth.context.js";
import { resolveServiceTarget, resolveServiceIdentity } from "../diagnostics/service_manifest.js";
import { aggregateRootStatus, classifyHttpProbe, evidence, type RootEvidence, type RootEvidenceStatus } from "../diagnostics/root-evidence.js";
import { evaluateCloudflareProbe } from "../diagnostics/cloudflare-evidence.js";
import { redactSensitiveData } from "../diagnostics/redaction.js";
import { diagnoseRelease, type DiagnosticIntent, type DiagnosticTruthMatrix } from "./diagnostic.tools.js";
import { runParityAudit } from "./parity.tools.js";
import { getWorkerStatus } from "../adapters/cloudflare/index.js";
import { generateRemediationPlan } from "../planning/planner.js";
import { savePlan, getPlan } from "../planning/plan_store.js";
import { verifyOutcome } from "../planning/verifier.js";
import { getAccountsForRole } from "../registry/account.registry.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "../../../..");

export type MasterActionMode =
  | "diagnose_only"
  | "plan_remediation"
  | "execute_approved_plan"
  | "verify_action";

export type MasterIncludeLayer =
  | "topology"
  | "runtime"
  | "release"
  | "dependencies"
  | "parity"
  | "graph"
  | "user_journey"
  | "capacity";

export interface DeepDiagnoseInput {
  service?: string;
  scope?: "root" | "service";
  intent?: DiagnosticIntent;
  depth?: "quick" | "deep";
  fresh?: boolean;
  include?: MasterIncludeLayer[];
  incident?: {
    symptoms?: string[];
    startedAt?: string | null;
    correlationId?: string | null;
  };
  action?: MasterActionMode;
  approvalToken?: string | null;
  planId?: string | null;
  evidenceTtlMs?: number;
  maxParallel?: number;
}

export interface CausalHypothesis {
  code: string;
  confidence: number;
  requires: string[];
  disprovedBy: string[];
  explanation: string;
}

export interface DeterministicFinding {
  severity: "critical" | "high" | "medium" | "low";
  code: string;
  message: string;
  evidence?: unknown;
}

function createDiagnosisId(): string {
  const ts = new Date().toISOString().replace(/[-:.]/g, "").slice(0, 15) + "Z";
  const rand = crypto.randomBytes(3).toString("hex");
  return `diag_${ts}_${rand}`;
}

function hashEvidence(payload: unknown): string {
  const canonical = JSON.stringify(payload);
  return "sha256:" + crypto.createHash("sha256").update(canonical).digest("hex");
}

function findGraphJsonPath(): string | null {
  const candidates = [
    path.join(REPO_ROOT, ".cache", "graphify-full", "graphify-out", "graph.json"),
    path.join(REPO_ROOT, ".cache", "graphify", "studio", "graphify-out", "graph.json"),
    path.join(REPO_ROOT, "graphify-out", "graph.json"),
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return null;
}

function inspectCodeGraphStatus(): {
  status: RootEvidenceStatus;
  indexed: boolean;
  graphPath: string | null;
  nodesCount: number;
  edgesCount: number;
  sourceWiringConfidence: "high" | "low";
} {
  const graphPath = findGraphJsonPath();
  if (!graphPath) {
    return {
      status: "unknown",
      indexed: false,
      graphPath: null,
      nodesCount: 0,
      edgesCount: 0,
      sourceWiringConfidence: "low",
    };
  }
  try {
    const raw = fs.readFileSync(graphPath, "utf-8");
    const parsed = JSON.parse(raw) as { nodes?: unknown[]; links?: unknown[]; edges?: unknown[] };
    const nodesCount = Array.isArray(parsed.nodes) ? parsed.nodes.length : 0;
    const edgesCount = Array.isArray(parsed.links)
      ? parsed.links.length
      : Array.isArray(parsed.edges)
        ? parsed.edges.length
        : 0;
    const isValid = nodesCount > 0;
    return {
      status: isValid ? "pass" : "unknown",
      indexed: isValid,
      graphPath: path.relative(REPO_ROOT, graphPath),
      nodesCount,
      edgesCount,
      sourceWiringConfidence: isValid ? "high" : "low",
    };
  } catch {
    return {
      status: "error",
      indexed: false,
      graphPath: path.relative(REPO_ROOT, graphPath),
      nodesCount: 0,
      edgesCount: 0,
      sourceWiringConfidence: "low",
    };
  }
}

/**
 * Deterministic 6-rule Root-Cause & Finding Engine (Section 5 of Master MCP Guide).
 */
export function inferDeterministicFindings(params: {
  targetMapped: boolean;
  identityVerified: boolean;
  truthMatrix: DiagnosticTruthMatrix;
  cloudflareCheck?: { status: string; checks: RootEvidence[] } | null;
  parityResult?: { status: string; releaseGate?: string } | null;
  graphStatus: { indexed: boolean; status: RootEvidenceStatus };
}): DeterministicFinding[] {
  const findings: DeterministicFinding[] = [];

  // Rule 1: Topology failure
  if (!params.targetMapped || !params.identityVerified) {
    findings.push({
      severity: "critical",
      code: "SERVICE_NOT_MAPPED",
      message: "Authoritative canonical service mapping is absent or invalid. No guessed provider target was queried.",
    });
    return findings;
  }

  // Rule 2: Application / Edge route failure
  if (params.truthMatrix.providerHealth === "pass" && params.truthMatrix.serviceHealth === "fail") {
    findings.push({
      severity: "critical",
      code: "APPLICATION_ROUTE_FAILURE",
      message: "Provider API is reachable, but the application runtime health route returned an HTTP failure.",
    });
  }
  const cfWorkerCheck = params.cloudflareCheck?.checks?.find((c) => c.source === "cloudflare.worker_route");
  if (cfWorkerCheck && cfWorkerCheck.status === "fail") {
    findings.push({
      severity: "high",
      code: "EDGE_ROUTE_NOT_FOUND",
      message: "Cloudflare provider is reachable, but the worker route returned HTTP failure (e.g. 404 Not Found).",
      evidence: cfWorkerCheck.value,
    });
  }

  // Rule 3: Release commit mismatch
  if (params.truthMatrix.releaseIntegrity === "fail") {
    findings.push({
      severity: "critical",
      code: "RELEASE_COMMIT_MISMATCH",
      message: "Intended GitHub commit, deployed provider commit, and runtime /release SHA do not match.",
    });
  }

  // Rule 4: Dependency failure
  if (params.truthMatrix.dependencyHealth === "fail") {
    findings.push({
      severity: "critical",
      code: "UPSTREAM_DEPENDENCY_FAILURE",
      message: "One or more critical upstream dependencies failed ground-truth health verification.",
    });
  }

  // Rule 5: Parity / Schema uncertainty or breach
  if (params.truthMatrix.schemaParity === "fail") {
    findings.push({
      severity: "critical",
      code: "SCHEMA_PARITY_BREACH",
      message: "Database schema is missing required core tables or project reference mismatched.",
    });
  } else if (params.truthMatrix.schemaParity === "unknown" || params.parityResult?.status === "unverified") {
    findings.push({
      severity: "medium",
      code: "PARITY_UNVERIFIED",
      message: "Cross-platform or database schema parity could not be fully verified; release gate remains fail-closed.",
    });
  }

  // Rule 6: Code wiring uncertainty
  if (!params.graphStatus.indexed) {
    findings.push({
      severity: "low",
      code: "CODE_INTELLIGENCE_UNAVAILABLE",
      message: "AST knowledge graph (graph.json) is unavailable or empty; source wiring confidence is lowered.",
    });
  }

  return findings;
}

export function inferCausalHypotheses(
  findings: DeterministicFinding[],
  truthMatrix: DiagnosticTruthMatrix,
): CausalHypothesis[] {
  const hypotheses: CausalHypothesis[] = [];

  for (const f of findings) {
    if (f.code === "EDGE_ROUTE_NOT_FOUND") {
      hypotheses.push({
        code: "EDGE_ROUTE_NOT_FOUND",
        confidence: 0.88,
        requires: ["cloudflare.worker_route=fail"],
        disprovedBy: [],
        explanation: "Cloudflare edge worker URL is either undeployed or pointing to an unmapped sub-route.",
      });
    } else if (f.code === "RELEASE_COMMIT_MISMATCH") {
      hypotheses.push({
        code: "STALE_DEPLOYMENT_ACTIVE",
        confidence: 0.93,
        requires: ["releaseIntegrity=fail", "serviceHealth=pass"],
        disprovedBy: truthMatrix.serviceHealth === "fail" ? ["serviceHealth=fail"] : [],
        explanation: "Service is healthy and responding, but serving an older release commit than GitHub main.",
      });
    } else if (f.code === "APPLICATION_ROUTE_FAILURE") {
      hypotheses.push({
        code: "RUNTIME_BOOT_OR_ROUTE_CRASH",
        confidence: 0.85,
        requires: ["providerHealth=pass", "serviceHealth=fail"],
        disprovedBy: [],
        explanation: "Container instance exists on provider, but application HTTP listener or health route is failing.",
      });
    } else if (f.code === "SCHEMA_PARITY_BREACH") {
      hypotheses.push({
        code: "MIGRATION_DRIFT_OR_WRONG_PROJECT",
        confidence: 0.9,
        requires: ["schemaParity=fail"],
        disprovedBy: [],
        explanation: "Target Supabase project is missing expected core tables or migrations have not been applied.",
      });
    }
  }

  return hypotheses;
}

export async function systemDeepDiagnose(rawInput: DeepDiagnoseInput = {}): Promise<Record<string, unknown>> {
  const diagnosisId = createDiagnosisId();
  const observedAt = new Date().toISOString();
  const service = rawInput.service || "api";
  const scope = rawInput.scope || "root";
  const intent: DiagnosticIntent = rawInput.intent || "is_healthy";
  const action: MasterActionMode = rawInput.action || "diagnose_only";
  const include: MasterIncludeLayer[] = rawInput.include || [
    "topology",
    "runtime",
    "release",
    "dependencies",
    "parity",
    "graph",
    "user_journey",
    "capacity",
  ];

  // Phase A: Bootstrap & Canonical Topology Resolution (Rule 1)
  const identity = resolveServiceIdentity(service);
  const target = resolveServiceTarget(service);
  if (!target || (identity && !identity.verified)) {
    const findings = inferDeterministicFindings({
      targetMapped: false,
      identityVerified: false,
      truthMatrix: {
        providerHealth: "unknown",
        serviceHealth: "unknown",
        releaseIntegrity: "unknown",
        dependencyHealth: "unknown",
        schemaParity: "unknown",
        userJourneyHealth: "unknown",
      },
      graphStatus: { indexed: false, status: "unknown" },
    });
    const blockedPayload = {
      diagnosisId,
      status: "unknown" as RootEvidenceStatus,
      verdict: "NO_GO" as const,
      confidence: 0.95,
      observedAt,
      service,
      scope,
      intent,
      topology: null,
      truthMatrix: {
        providerHealth: "unknown",
        serviceHealth: "unknown",
        releaseIntegrity: "unknown",
        dependencyHealth: "unknown",
        schemaParity: "unknown",
        userJourneyHealth: "unknown",
      },
      checks: [evidence("topology.canonical_service", "unknown", { service }, "Service is not mapped in canonical registry")],
      findings,
      hypotheses: [],
      blastRadius: [],
      evidenceHash: hashEvidence({ diagnosisId, service, findings }),
      sourceCommit: null,
      releaseGate: "blocked" as const,
      recommendedNextSteps: [
        `Register '${service}' in config/service_registry.yaml and canonical resolver before running diagnostics.`,
      ],
      remediationPlan: null,
      errors: [identity?.verificationError || `Unmapped canonical service: ${service}`],
    };
    return blockedPayload;
  }

  const topology = {
    name: target.name,
    role: target.role,
    provider: target.platform,
    accountId: target.renderAccountId,
    serviceId: target.renderServiceId,
    runtimeUrl: target.runtimeUrl,
    repository: target.repo,
    branch: target.branch,
  };

  // Phase B–G: Parallel Read-Only Fan-Out across layers
  const store = RequestContextStore.get();
  const registryAccounts = getAccountsForRole(store?.role);
  const availableAccountsCount = registryAccounts.filter((a) => a.available).length;

  const [releaseDiagSettled, paritySettled, cfWorkerSettled] = await Promise.allSettled([
    diagnoseRelease(target.name, intent),
    include.includes("parity") ? runParityAudit() : Promise.resolve(null),
    include.includes("parity") || scope === "root" ? getWorkerStatus() : Promise.resolve(null),
  ]);

  const releaseDiag = releaseDiagSettled.status === "fulfilled" ? releaseDiagSettled.value : null;
  const parityResult = paritySettled.status === "fulfilled" ? paritySettled.value : null;
  const cfWorkerRaw = cfWorkerSettled.status === "fulfilled" ? (cfWorkerSettled.value as Record<string, unknown> | null) : null;

  const cfEvaluated = cfWorkerRaw
    ? evaluateCloudflareProbe({
        providerReachable: cfWorkerRaw.status !== "error",
        httpStatus: typeof cfWorkerRaw.httpStatus === "number" ? cfWorkerRaw.httpStatus : cfWorkerRaw.status === "healthy" ? 200 : null,
        body: cfWorkerRaw.workerResponse,
      })
    : null;

  const graphStatus = include.includes("graph")
    ? inspectCodeGraphStatus()
    : { status: "unknown" as RootEvidenceStatus, indexed: false, graphPath: null, nodesCount: 0, edgesCount: 0, sourceWiringConfidence: "low" as const };

  const truthMatrix: DiagnosticTruthMatrix = (releaseDiag?.truthMatrix as DiagnosticTruthMatrix) ?? {
    providerHealth: "unknown",
    serviceHealth: "unknown",
    releaseIntegrity: "unknown",
    dependencyHealth: "unknown",
    schemaParity: "unknown",
    userJourneyHealth: "unknown",
  };

  // Assemble normalized RootEvidence checks
  const checks: RootEvidence[] = [
    evidence("topology.canonical_service", "pass", topology),
    evidence("root.inventory", availableAccountsCount > 0 ? "pass" : "unknown", {
      availableServices: `${availableAccountsCount}/${registryAccounts.length}`,
    }),
    evidence("runtime.service_health", truthMatrix.serviceHealth as RootEvidenceStatus, {
      runtimeUrl: target.runtimeUrl,
    }),
    evidence("release.integrity", truthMatrix.releaseIntegrity as RootEvidenceStatus, {
      verdict: releaseDiag?.releaseVerdict ?? null,
    }),
    evidence("dependencies.health", truthMatrix.dependencyHealth as RootEvidenceStatus),
    evidence("supabase.schema_parity", truthMatrix.schemaParity as RootEvidenceStatus),
    evidence("runtime.user_journey", truthMatrix.userJourneyHealth as RootEvidenceStatus),
  ];

  if (cfEvaluated) {
    checks.push(...cfEvaluated.checks);
  }

  if (parityResult) {
    const pStatus: RootEvidenceStatus =
      parityResult.status === "parity_verified"
        ? "pass"
        : parityResult.status === "drift_detected"
          ? "fail"
          : "unknown";
    checks.push(evidence("system.parity_audit", pStatus, {
      status: parityResult.status,
      releaseGate: parityResult.releaseGate,
    }));
  }

  if (include.includes("graph")) {
    checks.push(
      evidence(
        "codebase.ast_graph",
        graphStatus.status,
        {
          indexed: graphStatus.indexed,
          graphPath: graphStatus.graphPath,
          nodesCount: graphStatus.nodesCount,
          edgesCount: graphStatus.edgesCount,
          sourceWiringConfidence: graphStatus.sourceWiringConfidence,
        },
        graphStatus.indexed ? undefined : "graph.json not found or empty",
      ),
    );
  }

  const findings = inferDeterministicFindings({
    targetMapped: true,
    identityVerified: true,
    truthMatrix,
    cloudflareCheck: cfEvaluated,
    parityResult,
    graphStatus,
  });

  const hypotheses = inferCausalHypotheses(findings, truthMatrix);

  const rawDeps = (releaseDiag?.evidence as Record<string, unknown> | undefined)?.dependencies as
    | { impactedDownstreamServices?: string[] }
    | undefined;
  const blastRadius = Array.isArray(rawDeps?.impactedDownstreamServices)
    ? rawDeps!.impactedDownstreamServices
    : [];

  // Critical checks for overall status & release gate (exclude optional cloudflare.release unknown if core checks pass)
  const coreChecks: { status: RootEvidenceStatus }[] = [
    { status: truthMatrix.providerHealth as RootEvidenceStatus },
    { status: truthMatrix.serviceHealth as RootEvidenceStatus },
    { status: truthMatrix.releaseIntegrity as RootEvidenceStatus },
    { status: truthMatrix.dependencyHealth as RootEvidenceStatus },
    { status: truthMatrix.schemaParity as RootEvidenceStatus },
  ];
  const cfRouteCheck = cfEvaluated?.checks.find((c) => c.source === "cloudflare.worker_route");
  if (cfRouteCheck) {
    coreChecks.push({ status: cfRouteCheck.status });
  }

  const overallStatus = aggregateRootStatus(coreChecks);
  const releaseGateOpen =
    overallStatus === "healthy" &&
    truthMatrix.releaseIntegrity === "pass" &&
    truthMatrix.schemaParity === "pass" &&
    (!cfRouteCheck || cfRouteCheck.status === "pass");

  const verdict = releaseGateOpen ? "GO" : "NO_GO";
  const releaseGate = releaseGateOpen ? "open" : "blocked";

  const baseConfidence = typeof releaseDiag?.confidence === "number" ? releaseDiag.confidence : 0.85;
  const confidence = graphStatus.indexed ? baseConfidence : Math.min(baseConfidence, 0.75);

  const intendedCheck = Array.isArray(releaseDiag?.checks)
    ? (releaseDiag.checks as Array<{ name?: string; details?: { commit?: string } }>).find((c) => c.name === "intended_source")
    : undefined;
  const sourceCommit = intendedCheck?.details?.commit ?? null;

  const evidenceHash = hashEvidence({
    topology,
    truthMatrix,
    checks,
    findings,
    sourceCommit,
  });

  const recommendedNextSteps: string[] = [];
  for (const f of findings) {
    if (f.code === "RELEASE_COMMIT_MISMATCH") {
      recommendedNextSteps.push(`Redeploy service '${target.name}' (${target.renderServiceId}) to align with source commit ${sourceCommit ?? "HEAD"}.`);
    } else if (f.code === "EDGE_ROUTE_NOT_FOUND") {
      recommendedNextSteps.push("Inspect Cloudflare worker route mapping and custom domain health endpoint.");
    } else if (f.code === "SCHEMA_PARITY_BREACH") {
      recommendedNextSteps.push("Verify Supabase project reference and apply pending database migrations.");
    } else if (f.code === "CODE_INTELLIGENCE_UNAVAILABLE") {
      recommendedNextSteps.push("Run 'graphify extract . --code-only' to generate graphify-out/graph.json.");
    }
  }
  if (overallStatus === "unknown" && recommendedNextSteps.length === 0) {
    recommendedNextSteps.push(
      `Release gate is blocked because one or more truth dimensions are 'unknown' (e.g. provider credentials for '${target.renderAccountId}' or runtime release metadata). Supply complete evidence to unlock GO verdict.`,
    );
  } else if (recommendedNextSteps.length === 0) {
    recommendedNextSteps.push("All core diagnostic layers passed. Continue standard autonomous monitoring.");
  }

  // Action Mode Handling (Section 6 & 7: Safe Autonomy & Post-Action Verification)
  let remediationPlan: unknown = null;
  let verificationResult: unknown = null;

  if (action === "plan_remediation") {
    const primaryFailure = findings[0]?.code || "RELEASE_COMMIT_MISMATCH";
    const generated = generateRemediationPlan(target.name, primaryFailure, {
      diagnosisId,
      evidenceHash,
      sourceCommit,
      truthMatrix,
    });
    savePlan(generated);
    remediationPlan = generated;
  } else if (action === "verify_action") {
    verificationResult = await verifyOutcome("release", target.name, "healthy", [
      { name: "service_health", status: truthMatrix.serviceHealth, value: target.runtimeUrl },
      { name: "release_integrity", status: truthMatrix.releaseIntegrity, value: sourceCommit },
      { name: "schema_parity", status: truthMatrix.schemaParity, value: "supabase-primary" },
    ]);
  } else if (action === "execute_approved_plan") {
    if (!rawInput.approvalToken || !rawInput.planId) {
      recommendedNextSteps.unshift(
        "Execution blocked: execute_approved_plan requires both a valid planId and an explicit approvalToken (fail-closed R2/R3 policy).",
      );
    } else {
      const existingPlan = getPlan(rawInput.planId);
      remediationPlan = existingPlan ?? { error: `Plan not found: ${rawInput.planId}` };
    }
  }

  const errors: string[] = [];
  if (releaseDiagSettled.status === "rejected") errors.push(String(releaseDiagSettled.reason));
  if (paritySettled.status === "rejected") errors.push(String(paritySettled.reason));
  if (cfWorkerSettled.status === "rejected") errors.push(String(cfWorkerSettled.reason));

  return {
    diagnosisId,
    status: overallStatus,
    verdict,
    confidence,
    observedAt,
    service: target.name,
    scope,
    intent,
    action,
    topology,
    truthMatrix,
    codeIntelligence: {
      status: graphStatus.indexed ? "healthy" : "unavailable",
      indexed: graphStatus.indexed,
      graphPath: graphStatus.graphPath,
      nodesCount: graphStatus.nodesCount,
      edgesCount: graphStatus.edgesCount,
      sourceWiringConfidence: graphStatus.sourceWiringConfidence,
    },
    checks,
    findings,
    hypotheses,
    blastRadius,
    evidenceHash,
    sourceCommit,
    releaseGate,
    recommendedNextSteps,
    remediationPlan,
    ...(verificationResult ? { verificationResult } : {}),
    errors,
  };
}

function assertMasterDiagnoseAccess(toolName: string, minRole: UserRole): string | null {
  const store = RequestContextStore.get();
  if (!store) return null; // Allow internal/stdio calls when context store is not wrapping
  return roleRank(store.role) >= roleRank(minRole)
    ? null
    : `Forbidden: tool '${toolName}' requires ${minRole} role or higher (current role: '${store.role}').`;
}

export async function registerMasterDiagnoseTools(server: McpServer): Promise<void> {
  server.registerTool(
    "system_deep_diagnose",
    {
      description:
        "SupremeAI Master Autonomous Diagnostic & Safe Remediation Orchestrator. Correlates 5 layers in parallel (Topology, Runtime, Release SHA, Cross-Platform Parity, and AST Code Intelligence), evaluates deterministic root-cause rules, computes TruthMatrix + EvidenceHash + GO/NO_GO ReleaseGate, and optionally generates an evidence-bound DAG remediation plan.",
      annotations: { readOnlyHint: true, idempotentHint: true },
      inputSchema: {
        service: z.string().default("api").describe("Canonical service name (e.g. 'api', 'mcp', 'core', 'worker')"),
        scope: z.enum(["root", "service"]).default("root").describe("Diagnostic scope ('root' includes full inventory and edge checks)"),
        intent: z
          .enum(["is_healthy", "is_deploy_correct", "root_cause", "release_verify", "incident_timeline", "change_impact"])
          .default("is_healthy")
          .describe("Diagnostic reasoning intent"),
        depth: z.enum(["quick", "deep"]).default("deep"),
        fresh: z.boolean().default(true).describe("Bypass cached observations for live ground-truth probing"),
        include: z
          .array(z.enum(["topology", "runtime", "release", "dependencies", "parity", "graph", "user_journey", "capacity"]))
          .optional()
          .describe("Layers to correlate in fan-out"),
        action: z
          .enum(["diagnose_only", "plan_remediation", "execute_approved_plan", "verify_action"])
          .default("diagnose_only")
          .describe("Execution mode (read-only by default; plan_remediation creates a bound non-executing DAG plan)"),
        approvalToken: z.string().nullable().optional().describe("Explicit approval token required for execute_approved_plan"),
        planId: z.string().nullable().optional().describe("Plan ID when executing or verifying an existing DAG plan"),
        evidenceTtlMs: z.number().int().min(1000).max(300000).default(30000),
        maxParallel: z.number().int().min(1).max(16).default(8),
      },
    },
    async (args) => {
      const denial = assertMasterDiagnoseAccess("system_deep_diagnose", "agent");
      if (denial) return { isError: true, content: [{ type: "text", text: denial }] };

      try {
        const result = await systemDeepDiagnose(args);
        return {
          content: [{ type: "text", text: JSON.stringify(redactSensitiveData(result), null, 2) }],
        };
      } catch (err) {
        return {
          isError: true,
          content: [
            {
              type: "text",
              text: JSON.stringify({
                status: "error",
                verdict: "NO_GO",
                releaseGate: "blocked",
                error: (err as Error).message,
              }),
            },
          ],
        };
      }
    },
  );
}
