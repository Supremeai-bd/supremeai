---
name: deployment-release-verification
description: Verify production deployment provenance, commit alignment, Redis parity, and Supabase schema parity using immutable ReleaseCandidate evidence envelopes.
---

# Deployment & Release Verification Skill

Use this skill whenever verifying whether a SupremeAI service deployment matches the intended source commit, or when a service reports `/healthz` HTTP 200 but exhibits runtime drift, stale behavior, or dependency failures.

## 1. Trigger Conditions
- A deployment completed on Render, Cloudflare, or GitHub Actions and requires release verification.
- A service's `/healthz` endpoint passes, but behavior does not match `origin/main`.
- Before executing any remediation (`restart`, `redeploy`, `rollback`).

## 2. Prerequisites
- Authenticated MCP Control Plane context (`agent` or `admin` role).
- Target service mapped in [`service_manifest.ts`](../../../../infrastructure/mcp-control-plane/src/diagnostics/service_manifest.ts).

## 3. Allowed Tools
- `system.verify_release` (read-only immutable `ReleaseCandidate` probe)
- `system.diagnose` with `intent: "release_verify"` or `intent: "root_cause"`
- `system.execute` (plan-only or human-approved remediation gate)

## 4. Evidence Schema (`ReleaseCandidate`)
Every verification produces an immutable `ReleaseCandidate` record containing:
- `canonicalServiceId`: normalized service identifier (`api`, `core`, `mcp`, `worker`, `scraper`, `brain`).
- `sourceCommit` vs `runtimeCommits[service]`: exact SHA comparison.
- `redisParityResult`: `EvidenceEnvelope` v2 (`status`, `freshnessMs`, `confidence`).
- `supabaseParityResult`: `EvidenceEnvelope` v2 verifying core tables (`tasks`, `audit_logs`, `agent_sessions`, `system_events`).
- `finalStatus`: `"verified" | "blocked" | "candidate" | "rolled_back"`.

## 5. Competing Hypotheses Checklist
When `finalStatus !== "verified"`, evaluate in order:
1. **H1 — Commit Drift (`errorClass: "commit_mismatch"`):** Render deployment is still serving an older commit or a build failed silently.
2. **H2 — Service ID Alias Drift:** Calling code queried a legacy service alias; verify `deploymentRef.service.providerNativeId`.
3. **H3 — Schema Behind Code (`SCHEMA_BEHIND_CODE`):** Code merged to `main` expects new tables/columns not yet applied to the target Supabase project.
4. **H4 — Cache / Codec Drift:** Redis responds `PONG`, but cached payloads use an older `schemaHash` (quarantined by `decodeRedisPayload`).

## 6. Stop Conditions (Fail-Closed)
- **STOP immediately** if `canonicalServiceId` or `providerNativeId` cannot be verified.
- **STOP immediately** if `supabaseParityResult.status === "fail"` — never restart a compute node to fix a missing database migration.
- **STOP immediately** if evidence `freshnessMs > 60000` (stale observation).

## 7. Verification & Rollback Protocol
1. Run `system.verify_release({ service: "<service>" })`.
2. Confirm `finalStatus === "verified"` and `smokeTestResult.normalizedObservation.commitMatched === true`.
3. If `finalStatus === "blocked"` due to a bad rollout, invoke `system.execute` with `action: "rollback"`, explicit `rollbackTargetCommit`, `idempotencyKey`, and human `approvalToken`.

