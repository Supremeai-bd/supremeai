export type RootEvidenceStatus = "pass" | "fail" | "unknown" | "error";

export interface RootEvidence {
  source: string;
  status: RootEvidenceStatus;
  observedAt: string;
  value?: unknown;
  reason?: string;
}

export function evidence(
  source: string,
  status: RootEvidenceStatus,
  value?: unknown,
  reason?: string,
): RootEvidence {
  return {
    source,
    status,
    observedAt: new Date().toISOString(),
    ...(value === undefined ? {} : { value }),
    ...(reason ? { reason } : {}),
  };
}

/** A provider being reachable is not equivalent to its application being healthy. */
export function classifyHttpProbe(
  statusCode: number,
  expected: number[] = [200],
): RootEvidenceStatus {
  if (expected.includes(statusCode)) return "pass";
  if (statusCode >= 400 && statusCode < 500) return "fail";
  if (statusCode >= 500) return "error";
  return "unknown";
}

/** Root readiness is strict: unknown evidence cannot produce a green verdict. */
export function aggregateRootStatus(
  checks: Array<{ status: RootEvidenceStatus }>,
): "healthy" | "degraded" | "critical" | "unknown" {
  if (checks.some((check) => check.status === "fail")) return "critical";
  if (checks.some((check) => check.status === "error")) return "degraded";
  if (checks.some((check) => check.status === "unknown")) return "unknown";
  return "healthy";
}

