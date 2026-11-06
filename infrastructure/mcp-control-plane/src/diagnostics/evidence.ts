export type EvidenceStatus = "pass" | "fail" | "unknown" | "error";

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
