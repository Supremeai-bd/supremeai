import crypto from "node:crypto";
import {
  createEvidenceEnvelope,
  type EvidenceEnvelope,
  type EvidenceStatus,
} from "./evidence.js";
import {
  resolveServiceTarget,
  toDeploymentRef,
  toServiceRef,
  type DeploymentRef,
} from "./service_manifest.js";
import { probeServiceDependencies, probeSchemaParity } from "./dependency_graph.js";
import { getLatestDeploy, getServiceHealth } from "../adapters/render/index.js";
import { getRepositoryHead, getWorkflowRuns } from "../adapters/github/index.js";

export interface ReleaseCandidate {
  releaseId: string;
  canonicalServiceId: string;
  deploymentRef: DeploymentRef | null;
  sourceCommit: string | null;
  ciRunId: string | null;
  artifactDigest?: string;
  redisParityResult: EvidenceEnvelope;
  supabaseParityResult: EvidenceEnvelope;
  deploymentIds: string[];
  runtimeCommits: Record<string, string | null>;
  smokeTestResult: EvidenceEnvelope;
  finalStatus: "candidate" | "verified" | "blocked" | "rolled_back";
}

export interface ReleaseVerifyOverrides {
  sourceCommit?: string | null;
  ciRunId?: string | null;
  runtimeCommit?: string | null;
  deploymentId?: string | null;
  redisStatus?: EvidenceStatus;
  supabaseStatus?: EvidenceStatus;
  smokeStatus?: EvidenceStatus;
}

/**
 * Computes an immutable ReleaseCandidate verification record.
 * Marks finalStatus = "verified" ONLY when sourceCommit, runtimeCommit,
 * Redis parity, Supabase schema parity, and smoke health all align cleanly.
 */
export async function verifyReleaseCandidate(
  serviceName: string,
  overrides?: ReleaseVerifyOverrides,
): Promise<ReleaseCandidate> {
  const target = resolveServiceTarget(serviceName);
  const serviceRef = target ? toServiceRef(target) : null;
  const canonicalId = serviceRef?.canonicalServiceId ?? serviceName;
  const correlationId = `rel_${crypto.randomBytes(4).toString("hex")}`;

  let sourceCommit: string | null = overrides?.sourceCommit ?? null;
  let ciRunId: string | null = overrides?.ciRunId ?? null;
  let runtimeCommit: string | null = overrides?.runtimeCommit ?? null;
  let deploymentId: string | null = overrides?.deploymentId ?? null;

  if (!overrides && target) {
    try {
      const head: any = await getRepositoryHead(target.branch || "main");
      sourceCommit = head?.sha ?? head?.commit?.sha ?? null;
    } catch {
      sourceCommit = null;
    }

    try {
      const runs: any = await getWorkflowRuns(target.branch || "main", 5);
      const firstRun = Array.isArray(runs?.workflow_runs) ? runs.workflow_runs[0] : null;
      if (firstRun) {
        ciRunId = String(firstRun.id ?? "");
      }
    } catch {
      ciRunId = null;
    }

    try {
      const deploy = await getLatestDeploy(target.renderAccountId, target.renderServiceId);
      deploymentId = deploy?.id ?? null;
      runtimeCommit = deploy?.commitSha ?? null;
    } catch {
      runtimeCommit = null;
    }
  }

  const deploymentRef = serviceRef
    ? toDeploymentRef(serviceRef, {
        ...(runtimeCommit ? { runtimeCommit } : {}),
      })
    : null;

  // Redis Parity Evidence
  let redisStatus: EvidenceStatus = overrides?.redisStatus ?? "unknown";
  let redisRaw: unknown = {};
  if (!overrides?.redisStatus) {
    try {
      const depReport = await probeServiceDependencies(canonicalId);
      const redisDep = depReport.dependencies.find((d) => d.id.includes("redis"));
      redisStatus = redisDep?.status ?? "unknown";
      redisRaw = redisDep ?? {};
    } catch (err) {
      redisStatus = "error";
      redisRaw = { error: String(err) };
    }
  }

  const redisParityResult = createEvidenceEnvelope({
    status: redisStatus,
    canonicalServiceId: canonicalId,
    providerId: "redis",
    ...(deploymentRef ? { deploymentRef } : {}),
    correlationId,
    rawObservation: redisRaw,
    normalizedObservation: { service: canonicalId, redisStatus },
  });

  // Supabase Schema Parity Evidence
  let supabaseStatus: EvidenceStatus = overrides?.supabaseStatus ?? "unknown";
  let supabaseRaw: unknown = {};
  if (!overrides?.supabaseStatus) {
    try {
      const parity = await probeSchemaParity(canonicalId);
      supabaseStatus = parity.status;
      supabaseRaw = parity;
    } catch (err) {
      supabaseStatus = "error";
      supabaseRaw = { error: String(err) };
    }
  }

  const supabaseParityResult = createEvidenceEnvelope({
    status: supabaseStatus,
    canonicalServiceId: canonicalId,
    providerId: "supabase",
    ...(deploymentRef ? { deploymentRef } : {}),
    correlationId,
    rawObservation: supabaseRaw,
    normalizedObservation: { service: canonicalId, supabaseStatus },
  });

  // Smoke Test Evidence
  let smokeStatus: EvidenceStatus = overrides?.smokeStatus ?? "unknown";
  let smokeRaw: unknown = {};
  if (!overrides?.smokeStatus && target) {
    try {
      const health: any = await getServiceHealth(target.renderAccountId, target.renderServiceId);
      smokeStatus = health?.lastDeployStatus === "live" || health?.service ? "pass" : "fail";
      smokeRaw = health;
    } catch (err) {
      smokeStatus = "error";
      smokeRaw = { error: String(err) };
    }
  }

  const commitMatched = Boolean(sourceCommit && runtimeCommit && sourceCommit === runtimeCommit);
  const smokeTestResult = createEvidenceEnvelope({
    status: smokeStatus,
    canonicalServiceId: canonicalId,
    providerId: serviceRef?.providerId ?? "render",
    ...(deploymentRef ? { deploymentRef } : {}),
    correlationId,
    ...(sourceCommit && runtimeCommit && sourceCommit !== runtimeCommit
      ? { errorClass: "commit_mismatch" }
      : {}),
    rawObservation: smokeRaw,
    normalizedObservation: {
      commitMatched,
      sourceCommit,
      runtimeCommit,
    },
  });

  let finalStatus: ReleaseCandidate["finalStatus"] = "candidate";
  if (
    redisParityResult.status === "fail" ||
    supabaseParityResult.status === "fail" ||
    smokeTestResult.status === "fail" ||
    (sourceCommit && runtimeCommit && sourceCommit !== runtimeCommit)
  ) {
    finalStatus = "blocked";
  } else if (
    commitMatched &&
    redisParityResult.status === "pass" &&
    supabaseParityResult.status === "pass" &&
    smokeTestResult.status === "pass"
  ) {
    finalStatus = "verified";
  }

  return {
    releaseId: `rc_${crypto.randomBytes(6).toString("hex")}`,
    canonicalServiceId: canonicalId,
    deploymentRef,
    sourceCommit,
    ciRunId,
    redisParityResult,
    supabaseParityResult,
    deploymentIds: deploymentId ? [deploymentId] : [],
    runtimeCommits: { [canonicalId]: runtimeCommit },
    smokeTestResult,
    finalStatus,
  };
}
