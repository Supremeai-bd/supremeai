import crypto from "node:crypto";
import type { DeploymentRef } from "./service_manifest.js";

export type EvidenceStatus = "pass" | "fail" | "unknown" | "error";

export type EvidenceErrorClass =
  | "network"
  | "auth"
  | "quota"
  | "schema_drift"
  | "commit_mismatch"
  | "timeout"
  | "unknown";

export interface EvidenceFact {
  source: string;
  observedAt: string;
  status: EvidenceStatus;
  value?: unknown;
  error?: string;
}

export interface EvidenceCheck {
  name: string;
  status: EvidenceStatus;
  // Legacy diagnostic checks may not yet carry normalized facts. They are
  // treated as low-confidence evidence until migrated.
  confidence?: number;
  facts?: EvidenceFact[];
  explanation?: string;
  details?: Record<string, unknown>;
}

/**
 * First-class EvidenceEnvelope (v2) per Kilo-Org audit alignment.
 * Carries explicit canonicalServiceId, freshness, confidence, error classification,
 * and raw vs normalized observation separation.
 */
export interface EvidenceEnvelope<T = unknown> {
  evidenceId: string;
  status: EvidenceStatus;
  canonicalServiceId: string;
  providerId: string;
  deploymentRef?: DeploymentRef;
  observedAt: string;
  checkVersion: string;
  schemaVersion: "v2";
  freshnessMs: number;
  correlationId: string;
  operationId?: string;
  confidence: number;
  errorClass?: EvidenceErrorClass;
  partial?: boolean;
  rawObservation: unknown;
  normalizedObservation: T;
}

export interface CreateEvidenceEnvelopeOptions<T = unknown> {
  status: EvidenceStatus;
  canonicalServiceId: string;
  providerId: string;
  rawObservation: unknown;
  normalizedObservation: T;
  deploymentRef?: DeploymentRef;
  observedAt?: string;
  checkVersion?: string;
  correlationId?: string;
  operationId?: string;
  confidence?: number;
  errorClass?: EvidenceErrorClass;
  partial?: boolean;
}

export function createEvidenceEnvelope<T = unknown>(
  opts: CreateEvidenceEnvelopeOptions<T>,
): EvidenceEnvelope<T> {
  const nowMs = Date.now();
  const observedAtIso = opts.observedAt ?? new Date(nowMs).toISOString();
  const observedMs = Date.parse(observedAtIso);
  const freshnessMs = Number.isNaN(observedMs) ? 0 : Math.max(0, nowMs - observedMs);

  const defaultConfidence =
    opts.status === "pass"
      ? 0.95
      : opts.status === "fail"
        ? 0.90
        : opts.status === "error"
          ? 0.25
          : 0.10;

  return {
    evidenceId: `ev_${crypto.randomBytes(6).toString("hex")}`,
    status: opts.status,
    canonicalServiceId: opts.canonicalServiceId,
    providerId: opts.providerId,
    ...(opts.deploymentRef ? { deploymentRef: opts.deploymentRef } : {}),
    observedAt: observedAtIso,
    checkVersion: opts.checkVersion ?? "2.0.0",
    schemaVersion: "v2",
    freshnessMs,
    correlationId: opts.correlationId ?? `corr_${crypto.randomBytes(4).toString("hex")}`,
    ...(opts.operationId ? { operationId: opts.operationId } : {}),
    confidence: opts.confidence ?? defaultConfidence,
    ...(opts.errorClass ? { errorClass: opts.errorClass } : {}),
    ...(opts.partial !== undefined ? { partial: opts.partial } : {}),
    rawObservation: opts.rawObservation,
    normalizedObservation: opts.normalizedObservation,
  };
}

/**
 * Verifies whether an EvidenceEnvelope is within its allowed freshness window.
 * Fail-closed when timestamp is invalid or exceeds maxAgeMs.
 */
export function isEvidenceFresh(
  envelope: Pick<EvidenceEnvelope, "observedAt" | "status">,
  maxAgeMs = 60_000,
): boolean {
  const ts = Date.parse(envelope.observedAt);
  if (Number.isNaN(ts)) return false;
  const age = Date.now() - ts;
  return age >= -5000 && age <= maxAgeMs;
}

export function fact(
  source: string,
  status: EvidenceStatus,
  value?: unknown,
  error?: string,
): EvidenceFact {
  return { source, observedAt: new Date().toISOString(), status, value, ...(error ? { error } : {}) };
}

/** Unknown evidence must never be promoted to a passing verdict. */
export function aggregateStatus(checks: EvidenceCheck[]): "healthy" | "degraded" | "critical" | "unknown" {
  if (checks.some((c) => c.status === "fail")) return "critical";
  if (checks.some((c) => c.status === "error")) return "degraded";
  if (checks.some((c) => c.status === "unknown")) return "unknown";
  return "healthy";
}

export function confidenceFor(status: EvidenceStatus, facts: EvidenceFact[]): number {
  if (status === "fail") return facts.length >= 2 ? 0.95 : 0.75;
  if (status === "pass") return facts.length >= 2 ? 0.95 : 0.80;
  if (status === "error") return 0.20;
  return 0.10;
}
