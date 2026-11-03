# SUPREMEAI — PRE-PRODUCTION & GO-LIVE MASTER TODO
## Production Readiness Final Verification Checklist

**Repository:** `SaifulHaqueNiloy/supremeai`  
**Purpose:** Production-এর ঠিক আগে SupremeAI-এর code, backend, database, security, third-party services, infrastructure, frontend, observability, reliability, billing, backup/restore এবং operational readiness শেষবার যাচাই করার master checklist।

---

# 0. GO-LIVE RULE

Production deploy করা যাবে **শুধু তখনই**, যখন:

```text
CRITICAL = 100% PASS
HIGH     = 100% PASS
MEDIUM   = known + accepted + documented
```

কোনো unresolved:

- data-loss risk
- tenant-isolation risk
- authentication bypass
- secret exposure
- billing correctness issue
- backup/restore failure
- destructive production-action bug
- catastrophic dependency failure

থাকলে **GO-LIVE BLOCK**।

---

# 1. FINAL RELEASE FREEZE

- [ ] Release branch/tag নির্ধারণ করা হয়েছে।
- [ ] Production candidate commit SHA লিখে রাখা হয়েছে।
- [ ] `main` এবং production candidate একই expected commit-এ আছে।
- [ ] Uncommitted local changes নেই।
- [ ] Temporary debug code নেই।
- [ ] `print()`/debug logging cleanup হয়েছে।
- [ ] Development-only endpoints disabled।
- [ ] Development-only credentials removed।
- [ ] Test/mock providers production configuration থেকে বাদ।
- [ ] Feature flags-এর production values reviewed।
- [ ] Deprecated code paths identified।
- [ ] Dead dependencies reviewed।
- [ ] Release changelog তৈরি হয়েছে।
- [ ] Known limitations document করা হয়েছে।
- [ ] Rollback commit/tag প্রস্তুত।
- [ ] Database migration set reviewed।

---

# 2. REPOSITORY / CODE QUALITY

## General

- [ ] Full backend test suite pass।
- [ ] Full frontend test suite pass।
- [ ] Type checking pass।
- [ ] Linting pass।
- [ ] Formatting pass।
- [ ] Import errors absent।
- [ ] Circular import review pass।
- [ ] Static analysis pass।
- [ ] Security scan pass।
- [ ] Dependency vulnerability scan pass।
- [ ] Secret scanning pass।
- [ ] Build succeeds from a clean environment।
- [ ] Production Docker/build artifact reproducible।

## Python / Backend

- [ ] `pytest` pass।
- [ ] Async tests pass।
- [ ] No leaked event loops।
- [ ] No un-awaited coroutine warnings।
- [ ] No blocking CPU-heavy work in request handlers unless intentional।
- [ ] DB sessions properly closed।
- [ ] HTTP clients properly closed।
- [ ] Redis connections properly handled।
- [ ] Background tasks properly supervised।
- [ ] Exception handling verified।

## Frontend

- [ ] Production build passes।
- [ ] TypeScript build passes।
- [ ] No console errors।
- [ ] No failed network requests under normal usage।
- [ ] Error boundaries verified।
- [ ] Loading states verified।
- [ ] Empty states verified।
- [ ] Retry states verified।
- [ ] Mobile/responsive layouts checked।
- [ ] Accessibility sanity check completed।

---

# 3. ENVIRONMENT & CONFIGURATION

Create a production configuration matrix.

For every variable:

```text
Name
Purpose
Required?
Secret?
Source
Production value present?
Fallback acceptable?
```

- [ ] All required environment variables are present.
- [ ] No development defaults accidentally active.
- [ ] No local-only URLs active.
- [ ] No `localhost` dependency in backend production configuration.
- [ ] No hard-coded production domains in code.
- [ ] CORS production origins verified.
- [ ] Allowed hosts verified.
- [ ] API base URLs verified.
- [ ] Frontend API URL verified.
- [ ] Admin API URL verified.
- [ ] Cookie/security settings verified.
- [ ] TLS verification enabled.
- [ ] Production logging level reviewed.
- [ ] Timezone/UTC behavior verified.
- [ ] Feature flags reviewed individually.

---

# 4. SECRET MANAGEMENT

Current project uses secret-management/configuration infrastructure; verify the actual production setup rather than assuming configuration exists.

- [ ] All production secrets stored in approved secret manager / environment store.
- [ ] No secret committed to Git.
- [ ] No secret embedded in frontend bundle.
- [ ] No API keys in logs.
- [ ] No credentials in exceptions.
- [ ] No secrets in URLs/query strings.
- [ ] No credentials in OpenAPI examples.
- [ ] Secret scanning run on current release.
- [ ] Historical leaked credentials rotated where applicable.
- [ ] Production secrets are different from development secrets.
- [ ] Secret rotation procedure documented.
- [ ] Emergency credential revocation procedure documented.

---

# 5. AUTHENTICATION

- [ ] User registration tested.
- [ ] User login tested.
- [ ] Admin login tested.
- [ ] Token issuance tested.
- [ ] Token validation tested.
- [ ] Token expiration tested.
- [ ] Refresh flow tested if applicable.
- [ ] Logout/revocation tested.
- [ ] Invalid token rejected.
- [ ] Expired token rejected.
- [ ] Tampered token rejected.
- [ ] Wrong audience/issuer rejected where configured.
- [ ] Password policy tested.
- [ ] Password hashing verified.
- [ ] Account disable flow tested.
- [ ] Suspended account cannot authenticate.
- [ ] Brute-force/rate limiting tested.
- [ ] OTP/JIT admin verification tested.
- [ ] OTP cooldown tested.
- [ ] OTP replay tested.
- [ ] OTP brute-force behavior tested.
- [ ] Session invalidation tested.
- [ ] Admin/user authentication separation verified.

---

# 6. AUTHORIZATION / RBAC / TENANT ISOLATION

This is a **GO-LIVE BLOCKER** category.

- [ ] Every protected endpoint requires authentication.
- [ ] Every admin endpoint requires admin authorization.
- [ ] User cannot call admin operations.
- [ ] Guest cannot access authenticated resources.
- [ ] Role permissions tested.
- [ ] Resource ownership checks tested.
- [ ] Cross-user access attempts rejected.
- [ ] Cross-tenant access attempts rejected.
- [ ] Tenant ID never trusted blindly from client payload.
- [ ] Tenant context derives from authenticated identity where appropriate.
- [ ] Object-level authorization tested.
- [ ] IDOR/BOLA test performed.
- [ ] Shared-resource permissions tested.
- [ ] HITL approval permissions tested.
- [ ] Automation admin permissions tested.
- [ ] File/storage ownership tested.
- [ ] Memory ownership tested.
- [ ] Agent ownership tested.
- [ ] Usage/billing ownership tested.

### Required adversarial tests

```text
User A → User B resource
Tenant A → Tenant B resource
Normal user → admin endpoint
Guest → write endpoint
Expired account → resource
Deleted user → previous resource
Forged tenant_id → resource
Forged user_id → resource
```

All must fail safely.

---

# 7. MULTI-CUSTOMER / MULTI-REQUEST READINESS

- [ ] Multiple users can operate simultaneously.
- [ ] Concurrent requests do not leak context.
- [ ] User A's memory cannot appear for User B.
- [ ] User A's agents cannot appear for User B.
- [ ] User A's files cannot appear for User B.
- [ ] User A's usage cannot affect User B accounting.
- [ ] User A's automation events do not route into User B context.
- [ ] Tenant-scoped cache keys verified.
- [ ] Tenant-scoped Redis keys verified.
- [ ] Tenant-scoped DB queries verified.
- [ ] Tenant-scoped vector retrieval verified.
- [ ] Tenant-scoped telemetry verified where required.
- [ ] Per-user concurrency limits tested.
- [ ] Per-tenant rate limits tested.
- [ ] Per-tenant cost limits tested.

---

# 8. API SECURITY

- [ ] HTTPS enforced.
- [ ] HTTP redirects/blocks checked.
- [ ] CORS allowlist verified.
- [ ] Host validation verified.
- [ ] Request body limits verified.
- [ ] Upload size limits verified.
- [ ] Query parameter validation verified.
- [ ] Path parameter validation verified.
- [ ] JSON schema validation verified.
- [ ] Unknown fields handled safely.
- [ ] SSRF protections tested.
- [ ] Open redirect checks performed.
- [ ] Path traversal tests performed.
- [ ] Command injection tests performed.
- [ ] SQL injection tests performed.
- [ ] Template injection tests performed where relevant.
- [ ] Header injection tests performed.
- [ ] CSRF protection reviewed where relevant.
- [ ] Rate limiting tested.
- [ ] Abuse throttling tested.
- [ ] Error responses do not reveal internal stack traces.

---

# 9. DATABASE — POSTGRESQL

## Connectivity

- [ ] Production DB connection verified.
- [ ] TLS/SSL verified.
- [ ] Connection pooling configured.
- [ ] Pool maximum reviewed.
- [ ] Pool minimum reviewed.
- [ ] Idle timeout reviewed.
- [ ] Connection timeout reviewed.
- [ ] Query timeout reviewed.
- [ ] DB failover behavior documented.

## Schema

- [ ] All migrations applied cleanly in staging.
- [ ] Migration order verified.
- [ ] Current DB revision verified.
- [ ] No pending migration.
- [ ] No accidental destructive migration.
- [ ] New indexes verified.
- [ ] Foreign keys verified.
- [ ] Unique constraints verified.
- [ ] Check constraints verified.
- [ ] Nullable fields reviewed.
- [ ] Default values reviewed.

## Data integrity

- [ ] Referential integrity tested.
- [ ] Duplicate record scenarios tested.
- [ ] Concurrent write scenarios tested.
- [ ] Transaction boundaries tested.
- [ ] Rollback behavior tested.
- [ ] Partial failure behavior tested.
- [ ] Long-running query detection enabled/reviewed.
- [ ] N+1 query hotspots reviewed.
- [ ] Unbounded query endpoints reviewed.

---

# 10. PGVECTOR / VECTOR MEMORY

If pgvector is used in production:

- [ ] Embedding dimension consistency verified.
- [ ] Model/embedding version recorded.
- [ ] Vector indexes verified.
- [ ] Similarity metric verified.
- [ ] Tenant filtering applied before/with retrieval.
- [ ] User filtering verified.
- [ ] Deleted-user vectors removed/isolated.
- [ ] Re-embedding/migration procedure documented.
- [ ] Large vector search performance tested.
- [ ] Empty-index behavior tested.
- [ ] Wrong-dimension input rejected.

---

# 11. DATABASE BACKUP & RESTORE

This is a **GO-LIVE BLOCKER**.

- [ ] Automated production backup exists.
- [ ] Backup frequency documented.
- [ ] Backup retention documented.
- [ ] Backup encryption verified.
- [ ] Backup storage location separate from primary DB.
- [ ] Backup access restricted.
- [ ] Backup integrity checked.
- [ ] Restore performed on a clean environment.
- [ ] Restore actually boots the application.
- [ ] Restore point objective (RPO) documented.
- [ ] Recovery time objective (RTO) documented.
- [ ] Disaster recovery runbook written.
- [ ] Emergency DB restore owner identified.

### Required practical test

```text
Take real production-like backup
        ↓
Restore to isolated environment
        ↓
Run migrations if required
        ↓
Start backend
        ↓
Run smoke tests
        ↓
Verify users/files/agents/memory/billing
```

---

# 12. DATABASE BACKUP ENDPOINT SAFETY

The admin code contains a database backup action.

Before production:

- [ ] Backup action restricted to highest-trust admin.
- [ ] Backup files are not publicly served.
- [ ] Backup directory is outside public static paths.
- [ ] Backup file permissions verified.
- [ ] Backup files do not contain credentials that could be redistributed accidentally.
- [ ] Backup cleanup policy implemented.
- [ ] Backup does not block request workers for a dangerously long time.
- [ ] Large database backup strategy is suitable for real scale.

---

# 13. REDIS / CACHE

- [ ] Production Redis connectivity verified.
- [ ] TLS/auth verified where required.
- [ ] Connection lifecycle verified.
- [ ] TTLs verified.
- [ ] Session keys verified.
- [ ] OTP keys verified.
- [ ] Cache namespaces verified.
- [ ] Tenant/user prefixes verified.
- [ ] Cache poisoning tests performed.
- [ ] Cache stampede behavior reviewed.
- [ ] Redis outage behavior tested.
- [ ] Redis restart behavior tested.
- [ ] Redis memory policy reviewed.
- [ ] Sensitive data not stored longer than necessary.

---

# 14. DISTRIBUTED IDEMPOTENCY

Current automation idempotency includes an in-memory layer; final production verification must ensure correctness across multiple workers/instances.

- [ ] Distributed idempotency store implemented if multi-instance production is used.
- [ ] Redis-backed idempotency tested.
- [ ] `event_id` semantics verified.
- [ ] `idempotency_key` semantics verified.
- [ ] Critical workflows use deterministic idempotency keys.
- [ ] Database uniqueness enforced where required.
- [ ] Race-condition test performed.
- [ ] Duplicate concurrent request test performed.
- [ ] Restart does not incorrectly allow duplicate critical actions.

---

# 15. AUTOMATION / n8n

- [ ] n8n deployment exists only if production automation requires it.
- [ ] n8n version pinned/documented.
- [ ] n8n instance health verified.
- [ ] n8n HTTPS verified.
- [ ] Webhook authentication enabled.
- [ ] `N8N_WEBHOOK_SECRET` present.
- [ ] Missing secret fails closed.
- [ ] Arbitrary webhook forwarding unavailable.
- [ ] Workflow allowlist verified.
- [ ] Workflow registry matches actual n8n workflows.
- [ ] Workflow versions documented.
- [ ] Timeout policies tested.
- [ ] Retry policies tested.
- [ ] 429 behavior tested.
- [ ] 5xx behavior tested.
- [ ] Permanent 4xx behavior tested.
- [ ] Replay protection verified.
- [ ] Signature verification verified.
- [ ] Duplicate event handling verified.
- [ ] n8n outage does not break core AI.
- [ ] Execution IDs recorded.
- [ ] Automation execution history visible to admin.
- [ ] Sensitive automation payloads minimized.
- [ ] n8n credentials never reach frontend.
- [ ] n8n workflow backups/export policy documented.
- [ ] n8n restore procedure tested.

---

# 16. MESSAGING — TELEGRAM / EMAIL / OPTIONAL PROVIDERS

- [ ] Telegram bot token valid.
- [ ] Telegram chat routing verified.
- [ ] Unauthorized recipient rejected.
- [ ] Telegram rate-limit behavior tested.
- [ ] Telegram failure fallback tested.
- [ ] Email provider/API key valid.
- [ ] Email sender/domain verified.
- [ ] Email deliverability tested.
- [ ] Bounce/failure behavior handled.
- [ ] Messaging dispatcher provider selection verified.
- [ ] Mock messaging cannot accidentally be active in production.
- [ ] Sensitive notifications do not leak private data.
- [ ] Notification retries are bounded.
- [ ] Duplicate notification behavior tested.

---

# 17. BILLING / PAYMENT

If Stripe / SSLCommerz or any payment provider is active:

- [ ] Production credentials verified.
- [ ] Test mode disabled.
- [ ] Webhook endpoints use HTTPS.
- [ ] Webhook signatures verified.
- [ ] Duplicate webhook handling tested.
- [ ] Payment idempotency tested.
- [ ] Successful payment tested.
- [ ] Failed payment tested.
- [ ] Cancelled payment tested.
- [ ] Refunded payment tested if supported.
- [ ] Partial/refund edge cases tested if supported.
- [ ] Subscription lifecycle tested if applicable.
- [ ] User entitlement updates verified.
- [ ] Usage/balance updates are transactional.
- [ ] Payment cannot grant duplicate credits.
- [ ] Payment failure cannot revoke unrelated user data.
- [ ] Billing audit logs exist.
- [ ] Finance reconciliation procedure documented.

---

# 18. FIREBASE

For Firebase Auth/hosting or other active Firebase services:

- [ ] Production project verified.
- [ ] Correct project ID verified.
- [ ] Admin SDK credentials verified.
- [ ] Web app configuration verified.
- [ ] Authentication providers verified.
- [ ] Authorized domains verified.
- [ ] Admin/user separation verified.
- [ ] Firestore rules reviewed if Firestore is active.
- [ ] Firestore indexes verified if needed.
- [ ] Hosting deployment target verified.
- [ ] Preview/staging domain cannot accidentally write production data.
- [ ] Firebase quotas reviewed.
- [ ] Emergency project access documented.

---

# 19. STORAGE — R2 / MINIO / CLOUD / APPWRITE OPTIONAL

- [ ] Canonical storage provider selected for production.
- [ ] Storage credentials valid.
- [ ] Bucket names verified.
- [ ] Bucket public/private policy verified.
- [ ] Private files cannot be fetched anonymously.
- [ ] Signed URL expiry verified.
- [ ] File upload limit verified.
- [ ] MIME validation verified.
- [ ] Filename/path sanitization verified.
- [ ] Tenant/user path isolation verified.
- [ ] Delete behavior verified.
- [ ] Large file behavior tested.
- [ ] Storage outage behavior tested.
- [ ] Storage backup/retention policy documented.
- [ ] Logical storage key remains provider-independent.
- [ ] Appwrite is not accidentally the only source of truth unless intentionally selected.
- [ ] R2/MinIO/Appwrite provider switching tested if abstraction promises this.

---

# 20. LOCAL OLLAMA / USER-SIDE AI

This section must enforce the project rule:

```text
Ollama = optional user-local capability
Ollama != backend infrastructure
```

- [ ] Backend works with `OLLAMA_URL` absent.
- [ ] User without Ollama gets normal cloud experience.
- [ ] Local mode tested.
- [ ] Cloud mode tested.
- [ ] Auto mode tested.
- [ ] Local unavailable → safe cloud fallback.
- [ ] Local companion/bridge cannot grant cloud permissions.
- [ ] Local endpoint is not blindly accepted from arbitrary remote requests.
- [ ] User explicitly opts into local execution.
- [ ] Private local prompts stay local by default.
- [ ] Remote telemetry content is disabled/metadata-only for private local tasks.
- [ ] Local model timeout tested.
- [ ] Missing model tested.
- [ ] Ollama restart tested.

---

# 21. AI PROVIDERS

For every active LLM provider:

```text
Provider
API key
model
rate limit
timeout
fallback
cost
health
```

- [ ] Credentials valid.
- [ ] Model name valid.
- [ ] Provider limits verified.
- [ ] Rate limiter tested.
- [ ] Circuit breaker tested.
- [ ] Timeout tested.
- [ ] 429 tested.
- [ ] 5xx tested.
- [ ] Invalid API key tested.
- [ ] Provider outage tested.
- [ ] Provider fallback tested.
- [ ] Account rotation tested where active.
- [ ] Free-tier accounting verified where active.
- [ ] Cost estimation verified.
- [ ] Maximum task cost enforced.
- [ ] Maximum token limits enforced.
- [ ] Provider recovery tested.

---

# 22. LiteLLM

If LiteLLM is enabled:

- [ ] Actual runtime integration verified.
- [ ] It is behind `ModelProvider`.
- [ ] Existing SupremeAI routing policy remains authoritative.
- [ ] Account rotation is not duplicated incorrectly.
- [ ] Rate limits are not double-counted.
- [ ] Costs are not double-counted.
- [ ] Fallback behavior tested.
- [ ] LiteLLM outage does not make all AI unavailable if direct fallback is intended.
- [ ] LiteLLM version pinned.
- [ ] LiteLLM configuration documented.
- [ ] Removing LiteLLM leaves a working provider path.

If LiteLLM is not intentionally used:

- [ ] Remove unused dependency/configuration.

---

# 23. LANGFUSE / AI OBSERVABILITY

If Langfuse is enabled:

- [ ] Actual runtime integration verified.
- [ ] Trace creation verified.
- [ ] Agent traces verified.
- [ ] Tool traces verified.
- [ ] Retrieval traces verified.
- [ ] Generation traces verified.
- [ ] Token/cost metadata verified.
- [ ] Prompt versions verified where used.
- [ ] Failure to Langfuse does not break AI.
- [ ] Sensitive payload policy verified.
- [ ] Metadata-only mode tested.
- [ ] Full-content mode only enabled intentionally.
- [ ] Self-host/cloud choice documented.
- [ ] Retention policy documented.

---

# 24. OPENTELEMETRY

- [ ] Backend request spans work.
- [ ] Agent execution spans work.
- [ ] LLM spans work.
- [ ] Tool spans work.
- [ ] DB spans work where useful.
- [ ] Redis spans work where useful.
- [ ] Automation spans work.
- [ ] `trace_id` propagates correctly.
- [ ] `event_id` correlation works.
- [ ] automation execution ID correlation works.
- [ ] No sensitive values appear in spans.
- [ ] Sampling policy reviewed.
- [ ] Telemetry exporter failure does not break application.
- [ ] Collector health verified if self-hosted.

---

# 25. SENTRY

If Sentry is enabled:

- [ ] Backend errors captured.
- [ ] Frontend errors captured.
- [ ] Production environment tagged correctly.
- [ ] Release version tagged.
- [ ] PII scrubbing verified.
- [ ] Secrets removed from captured requests.
- [ ] Sampling verified.
- [ ] Sentry outage does not affect core app.
- [ ] Retention/usage policy reviewed.

---

# 26. MEMORY — NATIVE / MEM0 / GRAPHITI

## Native memory

- [ ] User isolation verified.
- [ ] Tenant isolation verified.
- [ ] Delete flow verified.
- [ ] Memory search relevance tested.
- [ ] Memory size limits verified.

## Mem0

- [ ] Actual upstream integration verified.
- [ ] Optional flag behavior verified.
- [ ] Fallback is durable.
- [ ] Fallback is not process-memory-only for production.
- [ ] Privacy controls verified.
- [ ] Tenant/user isolation verified.

## Graphiti

- [ ] Actual upstream dependency verified.
- [ ] Async API is natively async.
- [ ] No nested event-loop behavior.
- [ ] Data store healthy.
- [ ] Temporal query behavior tested.
- [ ] Tenant isolation verified.
- [ ] Disable/fallback mode tested.

---

# 27. BROWSER AUTOMATION

For existing Playwright/browser-use stack:

- [ ] Browser version pinned.
- [ ] Browser binaries available in production image.
- [ ] Headless mode verified.
- [ ] Sandbox/security verified.
- [ ] SSRF protection verified.
- [ ] URL allowlist reviewed.
- [ ] Credential isolation verified.
- [ ] Browser session cleanup verified.
- [ ] Memory/resource usage load-tested.
- [ ] Browser crash recovery tested.
- [ ] Timeout policy tested.
- [ ] Playwright vs browser-use architecture decision documented.
- [ ] Duplicate browser stacks avoided unless justified.

---

# 28. SANDBOX / E2B / CODE EXECUTION

- [ ] Sandbox isolation verified.
- [ ] Network policy verified.
- [ ] Filesystem isolation verified.
- [ ] CPU limits verified.
- [ ] Memory limits verified.
- [ ] Execution timeout verified.
- [ ] Process count limits verified.
- [ ] Secret access blocked.
- [ ] Host filesystem inaccessible.
- [ ] Container escape/security review performed.
- [ ] Malicious code test performed.
- [ ] Sandbox cleanup verified.
- [ ] Existing Firecracker/gVisor/E2B provider selection documented.
- [ ] Optional E2B failure does not break core agent operations.

---

# 29. AI AGENT RUNTIME

- [ ] Agent loop terminates correctly.
- [ ] Maximum iteration limit enforced.
- [ ] Maximum token limit enforced.
- [ ] Maximum tool-call limit enforced where appropriate.
- [ ] Infinite-loop protection tested.
- [ ] Tool timeout tested.
- [ ] Tool failure handling tested.
- [ ] Tool permission checks tested.
- [ ] Agent cannot bypass security policy.
- [ ] HITL triggers correctly.
- [ ] HITL approval resumes correct execution.
- [ ] HITL rejection stops execution.
- [ ] HITL expiry handled.
- [ ] Agent cancellation works.
- [ ] Concurrent agent runs isolated.
- [ ] Agent retry does not duplicate destructive actions.

---

# 30. TOOLS / MCP / EXTERNAL ACTIONS

For every tool:

- [ ] Input schema validated.
- [ ] Authorization checked.
- [ ] Tenant/user context propagated.
- [ ] Tool timeout defined.
- [ ] Tool result bounded.
- [ ] Sensitive output redacted where necessary.
- [ ] External API failures handled.
- [ ] Tool cannot access unauthorized resources.
- [ ] Destructive tool requires appropriate HITL.
- [ ] Tool execution audited.
- [ ] MCP server permissions reviewed if MCP is active.

---

# 31. HITL / SECURITY GATES

- [ ] High-risk action classification works.
- [ ] Medium-risk behavior verified.
- [ ] Low-risk behavior verified.
- [ ] Approval request created.
- [ ] Approval visible to correct admin.
- [ ] Wrong user cannot approve.
- [ ] Duplicate approvals handled safely.
- [ ] Expired approval rejected.
- [ ] Rejected action cannot continue.
- [ ] Approved action continues exactly once.
- [ ] Approval action audited.
- [ ] Sensitive payload minimized.
- [ ] Notification path verified.

---

# 32. SECURITY AUDIT

- [ ] Full dependency vulnerability scan.
- [ ] Secret scan.
- [ ] SAST.
- [ ] Authentication review.
- [ ] Authorization review.
- [ ] SSRF review.
- [ ] File upload review.
- [ ] Sandbox review.
- [ ] Prompt injection review.
- [ ] Tool injection review.
- [ ] Model-context manipulation review.
- [ ] Data exfiltration review.
- [ ] Cross-tenant isolation review.
- [ ] Admin privilege escalation review.
- [ ] Billing privilege escalation review.

---

# 33. PROMPT / AI SECURITY

- [ ] System prompt protection reviewed.
- [ ] Prompt injection tests performed.
- [ ] Malicious document tests performed.
- [ ] Tool poisoning tests performed.
- [ ] User-controlled content never becomes trusted system instruction.
- [ ] External webpage content treated as untrusted.
- [ ] Model output validated before dangerous tool calls.
- [ ] Sensitive data filtering verified.
- [ ] Secret exfiltration tests performed.
- [ ] Agent cannot reveal internal credentials/configuration.
- [ ] HITL required for dangerous operations.

---

# 34. API CONTRACT / OPENAPI

- [ ] Production OpenAPI generated.
- [ ] Schema committed/available as intended.
- [ ] Schema validation passes.
- [ ] Breaking-change detection passes.
- [ ] Security schemes accurate.
- [ ] Error schemas accurate.
- [ ] New admin integration endpoints documented.
- [ ] Automation execution endpoints documented.
- [ ] Client/frontend contract matches backend.
- [ ] OpenAPI generation does not require production secrets.
- [ ] OpenAPI generation mode is explicit.

---

# 35. LOAD TESTING

At least three load profiles:

```text
Normal
Peak
Stress
```

Test:

- [ ] Concurrent login.
- [ ] Concurrent chat requests.
- [ ] Concurrent agent executions.
- [ ] Concurrent file uploads.
- [ ] Concurrent retrieval.
- [ ] Concurrent automation events.
- [ ] Concurrent admin requests.
- [ ] Concurrent DB writes.
- [ ] Concurrent Redis usage.
- [ ] Provider rate limits.
- [ ] Queue/workers under load.
- [ ] Browser execution under load if enabled.

Measure:

```text
P50
P95
P99
error rate
CPU
RAM
DB connections
Redis memory
provider latency
```

---

# 36. STRESS / CHAOS TESTING

Simulate:

- [ ] PostgreSQL unavailable.
- [ ] Redis unavailable.
- [ ] n8n unavailable.
- [ ] LLM provider unavailable.
- [ ] LLM provider returns 429.
- [ ] Storage unavailable.
- [ ] Telegram unavailable.
- [ ] Email provider unavailable.
- [ ] Langfuse unavailable.
- [ ] Sentry unavailable.
- [ ] Ollama unavailable.
- [ ] Browser crashes.
- [ ] Worker restart during task.
- [ ] Backend restart during request.
- [ ] Backend restart during automation.
- [ ] Network latency spike.
- [ ] Duplicate events.
- [ ] Partial database outage.

Required principle:

```text
Optional integration failure
        ↓
Graceful degradation

Core service failure
        ↓
Known recovery path
```

---

# 37. FRONTEND / USER EXPERIENCE

## Authentication

- [ ] Login flow.
- [ ] Register flow.
- [ ] Logout.
- [ ] Session expiry.
- [ ] Unauthorized redirects.
- [ ] Admin access control.

## Core AI

- [ ] New chat.
- [ ] Streaming.
- [ ] Stop/cancel.
- [ ] Retry.
- [ ] Error recovery.
- [ ] Tool execution indication.
- [ ] HITL approval UI.
- [ ] Long responses.
- [ ] Markdown/code rendering.

## Files

- [ ] Upload.
- [ ] Download.
- [ ] Preview.
- [ ] Delete.
- [ ] Large file handling.
- [ ] Unsupported format handling.

## Admin

- [ ] User management.
- [ ] Agent management.
- [ ] Security.
- [ ] HITL.
- [ ] Provider status.
- [ ] Automation status.
- [ ] Execution history.
- [ ] Integration health.
- [ ] Failure states.
- [ ] Loading/empty/error states.

---

# 38. ACCESSIBILITY

- [ ] Keyboard navigation.
- [ ] Focus states.
- [ ] Proper labels.
- [ ] Contrast.
- [ ] Screen-reader basics.
- [ ] Error messages accessible.
- [ ] Modal focus handling.
- [ ] Mobile usability.

---

# 39. PERFORMANCE

- [ ] Frontend bundle analyzed.
- [ ] Large dependencies reviewed.
- [ ] Initial load optimized.
- [ ] API response sizes reviewed.
- [ ] Streaming used where appropriate.
- [ ] Database indexes verified.
- [ ] Slow endpoints identified.
- [ ] Memory leaks checked.
- [ ] Browser automation resource use reviewed.
- [ ] AI provider calls do not block unrelated users.

---

# 40. CACHING

- [ ] Cache keys documented.
- [ ] User/tenant isolation verified.
- [ ] TTLs appropriate.
- [ ] Sensitive values have short TTLs.
- [ ] Cache invalidation tested.
- [ ] Cache clear admin operation safe.
- [ ] Cache outage fallback tested.
- [ ] No stale security state retained.

---

# 41. BACKGROUND WORKERS / TASKS

- [ ] Worker process health checked.
- [ ] Worker concurrency configured.
- [ ] Retry policy bounded.
- [ ] Dead-letter path verified.
- [ ] Long tasks do not block API workers.
- [ ] Task cancellation tested.
- [ ] Worker restart recovery tested.
- [ ] Duplicate task prevention tested.
- [ ] Task state persistence verified.
- [ ] Graceful shutdown verified.

---

# 42. LOGGING

- [ ] Structured logs enabled.
- [ ] Request IDs present.
- [ ] Trace IDs present where appropriate.
- [ ] User/tenant IDs logged only where safe.
- [ ] Secrets redacted.
- [ ] Tokens redacted.
- [ ] Payment secrets redacted.
- [ ] Local file contents not logged.
- [ ] Error stack traces controlled.
- [ ] Log retention configured.
- [ ] Log volume reviewed.

---

# 43. MONITORING / ALERTING

Create alerts for:

- [ ] Backend down.
- [ ] High 5xx rate.
- [ ] High latency.
- [ ] DB connection exhaustion.
- [ ] Redis unavailable.
- [ ] High provider failure rate.
- [ ] Provider rate limiting.
- [ ] Automation failure spike.
- [ ] Security alerts.
- [ ] Billing webhook failures.
- [ ] Storage failures.
- [ ] High memory.
- [ ] High CPU.
- [ ] Disk/storage pressure.
- [ ] Worker failures.

Every alert must have:

```text
severity
owner
action
runbook
```

---

# 44. HEALTH / READINESS / LIVENESS

Verify:

```text
/health
/ready
/live
```

or equivalent endpoints.

- [ ] Liveness does not depend on unnecessary external services.
- [ ] Readiness reflects required dependencies.
- [ ] Optional integrations do not make readiness falsely fail.
- [ ] DB readiness checked.
- [ ] Redis readiness checked if required.
- [ ] Startup failure is understandable.
- [ ] Health responses do not leak secrets.

---

# 45. DEPLOYMENT / INFRASTRUCTURE

- [ ] Production backend deployment reproducible.
- [ ] Production frontend deployment reproducible.
- [ ] Correct region selected.
- [ ] CPU allocation reviewed.
- [ ] RAM allocation reviewed.
- [ ] Autoscaling strategy documented.
- [ ] Worker scaling documented.
- [ ] Timeouts configured.
- [ ] Reverse proxy configured.
- [ ] TLS certificate valid.
- [ ] Domain verified.
- [ ] DNS verified.
- [ ] Firewall rules reviewed.
- [ ] Internal services not unnecessarily public.
- [ ] n8n not unintentionally exposed.
- [ ] Admin endpoints protected.

---

# 46. RENDER / HOSTING SPECIFIC CHECKS

If Render remains the backend host:

- [ ] Correct service selected.
- [ ] Start command verified.
- [ ] Build command verified.
- [ ] Environment variables verified.
- [ ] Persistent disk strategy reviewed if used.
- [ ] Health check path verified.
- [ ] Restart behavior understood.
- [ ] Instance count verified.
- [ ] Background worker/service separation verified.
- [ ] Free-tier/paid-tier limits reviewed.
- [ ] Memory constraints tested.
- [ ] Deploy rollback tested.

---

# 47. FIREBASE HOSTING CHECKS

If Firebase hosts frontend/admin:

- [ ] Correct hosting site selected.
- [ ] Production build deployed.
- [ ] Rewrite rules verified.
- [ ] SPA fallback verified.
- [ ] Cache headers reviewed.
- [ ] Preview channels not mixed with production.
- [ ] Environment-specific frontend config verified.
- [ ] Rollback deployment available.

---

# 48. THIRD-PARTY QUOTA / POLICY AUDIT

For every external provider:

```text
Provider
Plan
Current limits
Current pricing
Current terms
Current API version
Rate limits
Data policy
Account owner
Emergency fallback
```

Check:

- [ ] OpenAI/other active LLM provider limits.
- [ ] Gemini limits.
- [ ] Groq limits.
- [ ] OpenRouter limits.
- [ ] Hugging Face limits.
- [ ] Cloudflare limits.
- [ ] NVIDIA limits.
- [ ] Payment provider limits.
- [ ] Firebase quotas.
- [ ] storage quotas.
- [ ] email quota.
- [ ] Telegram limits.
- [ ] Render limits.
- [ ] n8n license/use-case compatibility if deployed.
- [ ] Appwrite license/deployment/use-case compatibility if deployed.
- [ ] Any client-facing embedding restrictions reviewed.

**Important:** Do not assume today's free tier, pricing or license terms will remain unchanged.

---

# 49. VENDOR-EXIT TEST

For each optional third-party component ask:

```text
Can we disable it?
Can core still work?
Can we replace it?
Where is the adapter?
Where is the configuration?
Where is the data?
How do we migrate?
```

Verify:

- [ ] n8n removable.
- [ ] LiteLLM removable.
- [ ] Langfuse removable.
- [ ] Appwrite removable.
- [ ] Ollama optional.
- [ ] Mem0 removable.
- [ ] Graphiti removable.
- [ ] E2B removable.
- [ ] OpenHands removable.
- [ ] browser-use removable.
- [ ] Sentry removable.

---

# 50. DATA RETENTION & PRIVACY

- [ ] User data retention policy defined.
- [ ] Chat retention defined.
- [ ] File retention defined.
- [ ] Memory retention defined.
- [ ] Automation execution retention defined.
- [ ] Logs retention defined.
- [ ] Telemetry retention defined.
- [ ] Billing data retention defined.
- [ ] Deleted user data cleanup tested.
- [ ] Export/delete workflows tested.
- [ ] Third-party data-sharing documented.
- [ ] Sensitive AI content sharing minimized.

---

# 51. GDPR/PRIVACY-LIKE OPERATIONAL CONTROLS

Even if not legally required for every deployment, verify:

- [ ] Data inventory exists.
- [ ] Sensitive fields identified.
- [ ] Data processors/vendors identified.
- [ ] User deletion flow exists.
- [ ] Data export flow exists where required.
- [ ] Retention limits documented.
- [ ] Third-party telemetry data minimized.
- [ ] Local Ollama data does not leave device without explicit policy.

---

# 52. AUDIT LOGGING

Audit events for:

- [ ] Login.
- [ ] Logout.
- [ ] Admin login.
- [ ] Role changes.
- [ ] User disable.
- [ ] Agent creation/deletion.
- [ ] Tool execution.
- [ ] HITL approval.
- [ ] HITL rejection.
- [ ] Security alerts.
- [ ] Automation execution.
- [ ] Workflow enable/disable.
- [ ] Integration configuration changes.
- [ ] Billing events.
- [ ] Data deletion.
- [ ] Backup actions.
- [ ] Rollback actions.

Audit entries should have:

```text
who
what
when
where/context
target
result
trace/event ID
```

---

# 53. ADMIN DANGEROUS ACTIONS

Review all admin actions that can:

```text
clear cache
backup
rollback DB
change rules
apply fixes
approve HITL
change providers
change automation
```

For each:

- [ ] Proper permission.
- [ ] Confirmation.
- [ ] Audit log.
- [ ] Safe failure.
- [ ] Idempotency.
- [ ] Rollback if applicable.
- [ ] No accidental broad destructive behavior.

---

# 54. DATABASE ROLLBACK SAFETY

Before production:

- [ ] Never rely on automatic blind rollback for every migration.
- [ ] Forward migration tested.
- [ ] Backward compatibility tested where needed.
- [ ] Data migration tested.
- [ ] Large-table migration runtime estimated.
- [ ] Locking impact evaluated.
- [ ] Rollback instructions documented.
- [ ] Backup taken before destructive migration.

---

# 55. CI/CD

- [ ] Unit tests required.
- [ ] Integration tests required.
- [ ] Security scan required.
- [ ] Secret scan required.
- [ ] Type/lint checks required.
- [ ] Build required.
- [ ] OpenAPI validation required.
- [ ] Migration check required.
- [ ] Coverage threshold sensible and stable.
- [ ] Production deploy requires green pipeline.
- [ ] Deployment artifact immutable/tagged.
- [ ] Rollback workflow tested.

---

# 56. TEST ENVIRONMENT PARITY

Staging should resemble production in:

```text
Python version
Node version
database version
Redis version
environment variables
proxy behavior
TLS
worker configuration
storage configuration
AI provider adapters
```

- [ ] Staging is not using hidden dev-only behavior.
- [ ] Production-specific bugs are not masked by localhost fallbacks.
- [ ] Realistic data volume tested.
- [ ] Realistic concurrency tested.

---

# 57. SMOKE TEST — IMMEDIATELY AFTER DEPLOY

Within the first post-deploy verification:

- [ ] Homepage loads.
- [ ] User login works.
- [ ] Admin login works.
- [ ] User can create request/chat.
- [ ] AI response works.
- [ ] Streaming works.
- [ ] Memory works.
- [ ] File upload works.
- [ ] Agent creation works.
- [ ] Tool call works.
- [ ] HITL flow works.
- [ ] Notification works.
- [ ] Automation event works.
- [ ] Billing test path works in the production-safe manner intended.
- [ ] Admin integrations page works.
- [ ] Health endpoints work.
- [ ] Logs are arriving.
- [ ] Traces are arriving.
- [ ] No critical alerts fired.

---

# 58. POST-DEPLOY MONITORING WINDOW

For the first production window:

- [ ] Watch 5xx rate.
- [ ] Watch P95/P99 latency.
- [ ] Watch DB connections.
- [ ] Watch Redis.
- [ ] Watch AI provider failures.
- [ ] Watch automation failures.
- [ ] Watch billing webhook failures.
- [ ] Watch auth failures.
- [ ] Watch memory/CPU.
- [ ] Watch user reports.
- [ ] Watch error tracking.
- [ ] Watch telemetry.

Document:

```text
time
metric
baseline
observed
action
```

---

# 59. ROLLBACK DRILL

Before declaring release successful:

```text
Release N
   ↓
simulate critical issue
   ↓
rollback to N-1
   ↓
verify DB compatibility
   ↓
verify application
   ↓
verify user login
   ↓
verify AI
```

- [ ] Rollback command documented.
- [ ] Rollback owner identified.
- [ ] Rollback tested in staging.
- [ ] DB rollback/forward strategy understood.
- [ ] Cache invalidation after rollback defined.
- [ ] n8n workflow compatibility checked.
- [ ] Frontend/backend version compatibility checked.

---

# 60. DISASTER RECOVERY DRILL

Perform a tabletop exercise:

```text
Scenario:
Primary backend unavailable
```

Verify:

- [ ] Owner knows what to do.
- [ ] Backup location known.
- [ ] Secrets recovery documented.
- [ ] Database recovery documented.
- [ ] DNS/domain recovery documented.
- [ ] Storage recovery documented.
- [ ] n8n recovery documented if required.
- [ ] Firebase recovery documented.
- [ ] Payment webhook recovery documented.
- [ ] User communications plan exists.

---

# 61. DOCUMENTATION CHECK

Required docs:

- [ ] Deployment guide.
- [ ] Environment variable reference.
- [ ] Architecture overview.
- [ ] API documentation.
- [ ] Security model.
- [ ] Backup/restore runbook.
- [ ] Incident response runbook.
- [ ] Rollback runbook.
- [ ] Third-party integration inventory.
- [ ] Vendor exit plan.
- [ ] Billing operations guide.
- [ ] Admin operations guide.
- [ ] Local Ollama guide.
- [ ] n8n operations guide.
- [ ] OpenAPI generation guide.

---

# 62. SUPPORT / OPERATIONS READINESS

- [ ] Production owner identified.
- [ ] Security owner identified.
- [ ] Database owner identified.
- [ ] Billing owner identified.
- [ ] Incident escalation path documented.
- [ ] Emergency contact list exists.
- [ ] Critical dashboard URLs documented.
- [ ] Important credentials access documented without exposing secrets.
- [ ] Maintenance window policy documented.

---

# 63. USER-FACING FAILURE UX

Every major dependency failure should produce a useful message.

Test:

```text
AI provider unavailable
Storage unavailable
Automation unavailable
Ollama unavailable
File processing failed
Payment failed
Session expired
Rate limit reached
```

Required:

- [ ] User understands what happened.
- [ ] User knows whether retry is safe.
- [ ] Sensitive internal details are hidden.
- [ ] Retry action is available where appropriate.

---

# 64. COST CONTROL

- [ ] LLM per-request budget enforced.
- [ ] Per-user usage tracking works.
- [ ] Per-tenant usage tracking works.
- [ ] Provider free-tier tracking works where active.
- [ ] Cost spikes trigger alerts.
- [ ] Long-running agents have limits.
- [ ] Browser executions have limits.
- [ ] Sandbox executions have limits.
- [ ] n8n workloads have bounded usage.
- [ ] Observability retention cost reviewed.
- [ ] Storage growth monitored.

---

# 65. MAINTENANCE COST REVIEW

For every service:

```text
Can it be disabled?
What does it cost?
What resource does it consume?
What happens if it disappears?
How hard is replacement?
```

Especially review:

```text
n8n
LiteLLM
Langfuse
Sentry
Appwrite
Redis
PostgreSQL
Firebase
Render
LLM providers
Storage providers
```

---

# 66. THIRD-PARTY VERSION PINNING

- [ ] Runtime dependency versions reviewed.
- [ ] Production image dependency set frozen.
- [ ] Major-version upgrades prohibited without testing.
- [ ] n8n version pinned.
- [ ] Appwrite version pinned if self-hosted.
- [ ] LiteLLM version pinned.
- [ ] Langfuse version pinned.
- [ ] Mem0 version pinned.
- [ ] Graphiti version pinned.
- [ ] browser-use version pinned.
- [ ] Playwright/browser version pinned.
- [ ] E2B/OpenHands versions pinned if used.

---

# 67. THIRD-PARTY UPGRADE POLICY

Never blindly update all dependencies.

Required process:

```text
New version
   ↓
Read release notes
   ↓
Check breaking changes
   ↓
Check license/policy changes
   ↓
Run staging tests
   ↓
Security scan
   ↓
Load test
   ↓
Production rollout
```

---

# 68. SECURITY POLICY CHANGE WATCH

Maintain a vendor watch list:

```text
Provider
Current policy/license
Last checked
Next review
Impact if changed
Fallback
```

This is especially important for:

- hosted AI providers
- n8n
- Appwrite
- hosted telemetry
- payment providers
- storage providers

---

# 69. OPEN-SOURCE COMPONENT STATUS

Current desired status:

```text
OpenAPI
    ✅ standard / no runtime vendor dependency

OpenTelemetry
    ✅ standard / core telemetry

n8n
    ✅ optional automation provider
    ✅ removable
    ⚠️ production hardening required

LiteLLM
    ⚠️ adopt only if runtime value is proven

Langfuse
    ⚠️ optional observability

Ollama
    ✅ user-local optional capability

Appwrite
    ⚠️ selective provider only
    ❌ no full backend migration

Mem0
    ⚠️ optional memory enhancement

Graphiti
    ⚠️ optional temporal memory

OpenFGA
    ⏸ defer until required

LiveKit
    ⏸ defer until required
```

---

# 70. FINAL GO / NO-GO GATE

## BLOCKING — must all PASS

- [ ] Tenant isolation.
- [ ] Authentication.
- [ ] Authorization.
- [ ] Secret security.
- [ ] Database integrity.
- [ ] Backup + restore.
- [ ] Billing correctness.
- [ ] Critical HITL/security paths.
- [ ] Core AI availability.
- [ ] Production deploy.
- [ ] Rollback.
- [ ] Load test.
- [ ] Critical third-party health.
- [ ] Monitoring/alerting.
- [ ] No catastrophic known vulnerability.

## HIGH — must all PASS

- [ ] Storage.
- [ ] Redis.
- [ ] n8n.
- [ ] provider fallback.
- [ ] OpenTelemetry.
- [ ] OpenAPI.
- [ ] admin operations.
- [ ] user-facing error recovery.
- [ ] data retention.
- [ ] cost controls.

## MEDIUM

- [ ] Optional integrations.
- [ ] Advanced analytics.
- [ ] Future voice/realtime.
- [ ] advanced enterprise authorization.
- [ ] non-critical UX polish.

---

# 71. RELEASE SIGN-OFF

Fill this before production:

```text
Release:
Commit SHA:
Date:
Environment:

Backend:
Frontend:
Database:
Redis:
Storage:
Authentication:
Billing:
AI Providers:
n8n:
OpenTelemetry:
Langfuse:
Ollama:
Sentry:
Other:

Critical tests:
Passed:
Failed:
Known issues:

Backup tested:
Restore tested:
Rollback tested:
Load tested:
Security tested:

GO / NO-GO:

Approved by:
```

---

# 72. Recommended Final Test Sequence

Run in this order:

```text
1. Clean build
2. Unit tests
3. Integration tests
4. Security tests
5. Authentication/authorization tests
6. Multi-tenant isolation tests
7. Database migration test
8. Backup/restore test
9. Redis/idempotency test
10. AI provider failover test
11. Agent/HITL test
12. Storage test
13. Messaging test
14. n8n test
15. OpenAPI contract test
16. OpenTelemetry test
17. Frontend E2E test
18. Load test
19. Chaos/dependency outage test
20. Staging smoke test
21. Rollback drill
22. Production deployment
23. Production smoke test
24. Post-deploy monitoring
```

---

# 73. Final Principle

Do not ask:

> “Does the application open?”

Ask:

> “Can a malicious user, a broken provider, a failed database connection, a duplicate event, a large traffic spike, a deployment failure, or a policy change cause data loss, cross-customer access, financial loss, security compromise, or complete service failure?”

Production readiness means those scenarios have:

```text
prevention
+
detection
+
containment
+
recovery
```

documented and tested.

---

# 74. SupremeAI Final Go-Live Standard

The final production system should satisfy:

```text
                    SUPREMEAI
                       |
       +---------------+---------------+
       |               |               |
      SAFE            RELIABLE        OBSERVABLE
       |               |               |
    Auth/RBAC       HA/fallback      Logs/traces
    Isolation       Backup           Metrics
    HITL            Restore          Alerts
    Secrets         Rollback         Audit
       |               |               |
       +---------------+---------------+
                       |
                 Vendor Independent
                       |
       +---------------+---------------+
       |               |               |
      n8n           Ollama          AI Providers
   optional        user-local       replaceable
```

> **Final rule: No feature is considered production-ready merely because its code exists. It must be tested in healthy, failure, disabled, concurrent, recovery, and security-sensitive states.**
