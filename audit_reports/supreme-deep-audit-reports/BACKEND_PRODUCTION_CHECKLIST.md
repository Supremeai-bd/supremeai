# SupremeAI Backend Production Checklist

Use this checklist against the exact deployed backend image and configuration. Record `PASS`, `FAIL`, `BLOCKED`, or `N/A`, with command output, logs, traces, or operator evidence.

## 1. Test record

- Environment: Production / staging
- API URL:
- WebSocket/SSE URL:
- Image/commit:
- Database/cache/provider versions:
- Tester/date:

## 2. Build, startup, and configuration

- [ ] Dependency lockfile and runtime version are reproducible.
- [ ] Production image builds without test-only or development-only dependencies.
- [ ] Application imports and starts using the production entrypoint.
- [ ] Required environment variables fail startup with a clear aggregated error.
- [ ] Optional services degrade safely without silently disabling core safety controls.
- [ ] `.env.example`, settings, Compose, deployment manifests, and config validators use the same names and precedence.
- [ ] Secrets are injected by the deployment platform and never committed, logged, returned, or exposed in diagnostics.
- [ ] Database migrations are reviewed, ordered, reversible where possible, and applied before dependent code.

## 3. Routing and API contract

- [ ] Every frontend-critical router is mounted by the production application entrypoint.
- [ ] Route prefixes, methods, path parameters, auth requirements, request schemas, response schemas, and error shapes match the frontend contract.
- [ ] Health, readiness, metrics, WebSocket, SSE, upload, callback, and admin routes are intentionally exposed.
- [ ] Unknown routes return the expected safe status and error shape.
- [ ] OpenAPI or equivalent generated contract matches the deployed route set.
- [ ] Request IDs and correlation IDs are generated, propagated, and included in logs/responses where intended.
- [ ] Idempotency is enforced for retries and destructive or billing-sensitive mutations.

## 4. Middleware and security order

- [ ] Proxy/trusted-host handling is explicit and safe.
- [ ] CORS allowlist uses the intended production origins and has deterministic precedence.
- [ ] Preflight permits only required methods and headers, including fingerprint, CSRF, auth, request, and correlation headers.
- [ ] Authentication runs before protected handlers and rejects expired/invalid sessions.
- [ ] Authorization and tenant/user scoping are enforced server-side on every private query and mutation.
- [ ] CSRF protection is applied to cookie-authenticated state-changing requests where required.
- [ ] Rate limits cover authentication, AI/provider, upload, admin, and expensive operations.
- [ ] Input validation, file type/size limits, output encoding, SSRF protections, and path traversal protections are active.
- [ ] Anti-hacking, device fingerprint, JIT/step-up, and audit middleware are wired into the routes that require them.
- [ ] Security headers, trusted proxy behavior, request-size limits, and timeout limits are configured for production.

## 5. Core service behavior

- [ ] AI/model routing handles provider success, timeout, rate limit, malformed response, and provider outage safely.
- [ ] Streaming/WebSocket connections enforce authorization, cancellation, backpressure, idle timeout, and cleanup.
- [ ] Projects, files, conversations, memory, agents, research, schedules, runs, usage, billing, settings, and API keys persist correctly where enabled.
- [ ] File uploads use validated content types, bounded sizes, safe storage paths, malware/scanning policy, access control, and cleanup.
- [ ] Background jobs have retry limits, idempotency, visibility, dead-letter/failure handling, and cancellation semantics.
- [ ] Provider credentials are encrypted or delegated to the approved secret mechanism and are never returned in full.
- [ ] MCP connections validate endpoint, authentication, scope, health, timeout, and tenant ownership.
- [ ] Optional scraper and telemetry failures do not take down core customer operations.

## 6. Data protection and isolation

- [ ] User A cannot read or mutate User B projects, files, conversations, memory, runs, schedules, keys, or billing data.
- [ ] Admin access uses explicit roles and permissions; privileged actions are audited.
- [ ] Sensitive fields are excluded from ordinary logs, traces, metrics, error responses, and analytics.
- [ ] Retention, deletion, export, and consent behavior matches the approved privacy policy.
- [ ] Encryption in transit and at rest is enabled for production dependencies.
- [ ] Backups are encrypted, retained according to policy, and tested by a restore drill.
- [ ] Destructive operations have confirmation, authorization, idempotency, and recovery procedures.

## 7. Health, observability, and operations

- [ ] Liveness is lightweight and does not depend on every external provider.
- [ ] Readiness reflects dependencies required to serve traffic and has documented degraded states.
- [ ] Health responses do not expose secrets, internal topology, or sensitive provider details.
- [ ] Metrics, structured logs, traces, request IDs, and error rates are available without leaking sensitive data.
- [ ] Alerts exist for availability, latency, error rate, auth abuse, queue failure, provider failure, storage, database, and certificate expiry.
- [ ] Alert routing has an owner, escalation path, and tested notification channel.
- [ ] Logs and metrics have retention limits and access controls.
- [ ] Deployment, rollback, migration, backup, restore, and incident procedures are documented and rehearsed.

## 8. Compose and deployment verification

- [ ] Production Compose/manifests reference existing files, images, networks, volumes, and healthcheck commands.
- [ ] Service ports and reverse-proxy routes match the public deployment contract.
- [ ] Dependency conditions do not create startup deadlocks.
- [ ] Core profile starts without optional observability services.
- [ ] Observability profile starts only with valid collector/alert configuration.
- [ ] Containers run as non-root where supported and have appropriate filesystem permissions.
- [ ] CPU, memory, file descriptor, connection, timeout, and concurrency limits are bounded.
- [ ] Graceful shutdown drains active requests/jobs and closes connections.
- [ ] Horizontal scaling does not rely on local process memory for durable state.

## 9. Automated validation

- [ ] Backend lint, format, type checks, import checks, and focused tests pass.
- [ ] Route registration, CORS precedence, startup validation, health semantics, auth, isolation, and security hardening tests pass.
- [ ] Contract/config/Compose validators pass in CI and fail on deterministic drift.
- [ ] Coverage changes are reviewed; skipped or xfailed tests have owners and reasons.
- [ ] Dependency and container vulnerability scans pass or have approved exceptions.
- [ ] Staging smoke tests cover health, auth, core API, streaming, storage, database, cache, MCP, and provider failure.

## 10. Manual production gates

- [ ] Exact release image/config is deployed to a controlled environment.
- [ ] Live liveness, readiness, CORS/preflight, auth, API, WebSocket/SSE, uploads, and callbacks pass.
- [ ] Production secrets, domains, certificates, provider accounts, and permissions are verified.
- [ ] Database/cache/MCP/provider operations are verified with non-destructive test data.
- [ ] Backup/restore and rollback drills produce evidence.
- [ ] Security, privacy, retention, and operational owners sign off.
- [ ] No unresolved P0/P1 backend or infrastructure defect remains.

**Decision:** GO / NO-GO
**Evidence links:**
**Known non-blocking issues:**
**Release owner:

> Passing this checklist means backend readiness evidence is complete. It does not by itself certify the whole product as production-ready until frontend, infrastructure, security, privacy, and operational gates also pass.

---

## Evidence record

| Check/ID | Result | Evidence | Owner | Follow-up |
|---|---|---|---|---|
| | | | | |
| | | | | |
| | | | | |
