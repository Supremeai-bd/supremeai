import { classifyHttpProbe, evidence, type RootEvidence } from "./root-evidence.js";

export interface CloudflareProbeResult {
  providerReachable: boolean;
  httpStatus: number | null;
  body: unknown;
  deployedCommit?: string | null;
  expectedCommit?: string | null;
}

/**
 * Cloudflare API reachability and worker route health are separate checks.
 * A worker 404 is a failure, never a healthy provider result.
 */
export function evaluateCloudflareProbe(result: CloudflareProbeResult): {
  status: "healthy" | "degraded" | "critical" | "unknown";
  checks: RootEvidence[];
} {
  const checks: RootEvidence[] = [
    evidence(
      "cloudflare.provider",
      result.providerReachable ? "pass" : "error",
      undefined,
      result.providerReachable ? undefined : "Cloudflare provider request failed",
    ),
    evidence(
      "cloudflare.worker_route",
      result.httpStatus === null ? "unknown" : classifyHttpProbe(result.httpStatus),
      { httpStatus: result.httpStatus, body: result.body },
      result.httpStatus === 404 ? "Worker route returned Not Found" : undefined,
    ),
  ];

  if (result.deployedCommit || result.expectedCommit) {
    const bothKnown = Boolean(result.deployedCommit && result.expectedCommit);
    checks.push(evidence(
      "cloudflare.release",
      !bothKnown ? "unknown" : result.deployedCommit === result.expectedCommit ? "pass" : "fail",
      { deployedCommit: result.deployedCommit, expectedCommit: result.expectedCommit },
      !bothKnown ? "Cloudflare deployment identity is not configured" : undefined,
    ));
  } else {
    checks.push(evidence("cloudflare.release", "unknown", undefined, "Cloudflare deployment identity is not configured"));
  }

  // Verdict is computed from the REACHABILITY checks only (provider + worker_route).
  // The release-identity check is auxiliary release-tracking evidence: when the
  // worker does not report deployment identity it stays visible below as `unknown`
  // evidence, but it must not gate the provider verdict - otherwise a healthy
  // worker serving HTTP 200 is labelled "unknown" forever and the health engine
  // grows a false failure streak out of indeterminate results.
  const reachability = checks.filter((check) => check.source !== "cloudflare.release");
  const status = reachability.some((check) => check.status === "fail")
    ? "critical"
    : reachability.some((check) => check.status === "error")
      ? "degraded"
      : reachability.some((check) => check.status === "unknown")
        ? "unknown"
        : "healthy";
  return { status, checks };
}

