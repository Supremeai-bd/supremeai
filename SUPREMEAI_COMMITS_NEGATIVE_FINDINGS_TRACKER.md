# SupremeAI Commit Improvement Tracker
## Last 2 Commits — Negative Findings / Follow-up Work

**Purpose:**  
This file tracks the weaknesses, risks, and follow-up improvements identified from the last two commits. It is **not** a final-production verdict. The goal is to preserve every negative finding so the next commits can systematically fix them.

**Reviewed commits:**
1. `9d1ddc1` — `fix(platform): free-tier viability + mcp Dockerfile + HTTP worker service`
2. `ad4cf07` — `ops(db): daily evolution_logs retention prune via Management API (bounds 87% DB growth)`

---

## 1. Commit `9d1ddc1` — Follow-up Problems

### 1.1 Worker process starts at module import time
**Finding:** `worker_service.py` calls `_spawn_celery()` during module import.

**Why this is a problem:**
- Startup side effects happen before FastAPI lifecycle startup.
- Makes testing/importing the module less predictable.
- Can conflict with Uvicorn/process lifecycle management.
- A failed/partial environment can trigger subprocess behavior too early.

**Target fix:**
- Move Celery startup into FastAPI `lifespan` / startup.
- Move cleanup into the corresponding shutdown path.
- Avoid custom signal handling unless there is a concrete need.

**Priority:** HIGH

---

### 1.2 Celery worker is not actually supervised
**Finding:** The wrapper starts a Celery subprocess and reports whether it is alive, but does not continuously restart a crashed worker.

**Why this is a problem:**
- HTTP service may remain healthy while the queue consumer has died.
- Render may consider the service healthy even though async task processing is broken.

**Target fix:**
- Add a bounded supervisor loop.
- Detect worker exit.
- Restart with bounded exponential backoff.
- Add a restart counter and circuit-breaker/disable threshold.
- Expose worker readiness separately from HTTP liveness.

**Priority:** HIGH

---

### 1.3 Celery concurrency `-c 2` may be too expensive on 512 MB
**Finding:** The worker launches Celery with concurrency 2.

**Why this is a problem:**
- Free-tier memory is constrained.
- Two workers can materially increase RSS depending on imported code/tasks.
- SupremeAI is explicitly trying to remain lightweight.

**Target fix:**
- Start with `-c 1`.
- Measure actual RSS under representative workloads.
- Increase only with evidence.

**Priority:** HIGH

---

### 1.4 Worker operational endpoints lack visible authentication
**Finding:** `/tasks/drain` and `/worker/status` are exposed by the HTTP wrapper without authentication in the reviewed code.

**Why this is a problem:**
- Unnecessary attack surface.
- `/worker/status` can expose operational details.
- `/tasks/drain` should not be a publicly callable control endpoint.

**Target fix:**
- Make control endpoints internal-only, or require authenticated admin/service credentials.
- Keep public `/health/live` minimal.
- Avoid exposing process IDs and internal implementation details publicly.

**Priority:** CRITICAL

---

### 1.5 Liveness and readiness are conflated
**Finding:** Health endpoints can report success even when Celery/Redis is degraded.

**Why this is a problem:**
- A platform can see HTTP 200 while the actual queue-processing capability is unavailable.
- Monitoring cannot distinguish “process alive” from “worker ready”.

**Target fix:**
Implement separate states:

```text
/health/live  -> process is alive
/health/ready -> required worker dependencies are ready
/worker/status -> authenticated/internal diagnostics
```

Use readiness for routing/operational decisions, while liveness should not fail merely because Redis is temporarily unavailable.

**Priority:** HIGH

---

### 1.6 `/tasks/drain` does not prove real Celery end-to-end execution
**Finding:** The current task/drain mechanism uses the queue abstraction and can report an asyncio-style queue path; this does not by itself prove:

```text
producer -> Redis/broker -> Celery consumer -> task -> result backend -> result
```

**Why this is a problem:**
- The service could appear operational while Celery is not consuming tasks.

**Target fix:**
Create a real smoke test that:
1. submits a known idempotent Celery task,
2. verifies broker delivery,
3. verifies Celery worker consumption,
4. verifies result/acknowledgement,
5. verifies timeout/failure behavior.

**Priority:** CRITICAL

---

### 1.7 Free-tier keepalive contains hardcoded service URLs
**Finding:** Keepalive configuration contains Render URLs directly in workflow/code.

**Why this is a problem:**
- Environment changes require code changes.
- Conflicts with the project's dynamic infrastructure/configuration philosophy.
- Makes multi-environment operation harder.

**Target fix:**
- Store service URLs in GitHub Variables or the central configuration/secret system.
- Resolve services through resource/config registry where appropriate.
- Never hardcode environment-specific deployment topology in application logic.

**Priority:** MEDIUM/HIGH

---

### 1.8 Historical Render API keys require rotation/revocation
**Finding:** The commit removed hardcoded Render API keys from current scripts, which is good, but previously committed secrets remain in Git history if they were ever committed.

**Why this is a problem:**
- Removing a secret from the current tree does not invalidate a leaked credential.
- Git history may remain accessible.

**Target fix:**
- Rotate/revoke all exposed historical Render API keys.
- Verify no active credential remains usable.
- Search current tree and history for secret patterns.
- Consider history rewriting only if appropriate; rotation is the essential control.

**Priority:** CRITICAL

---

### 1.9 Large schema-consolidation migration needs dedicated validation
**Finding:** The new consolidated database migration is very large.

**Why this is a problem:**
- Large migrations have larger rollback and deployment blast radius.
- Schema/RLS/index/vector changes can interact unexpectedly.
- Harder to review and diagnose.

**Target fix:**
- Test upgrade on a clean DB.
- Test upgrade from current production-equivalent schema.
- Test rollback where feasible.
- Verify RLS policies and indexes independently.
- Add migration safety checks to CI.
- Keep Alembic as the single schema authority.

**Priority:** HIGH

---

### 1.10 Repository hygiene: temporary/audit artifacts are entering the repo
**Finding:** New temporary/audit-related files such as patch helpers and manual patch notes appeared in the repository.

**Why this is a problem:**
- Increases repository noise.
- Makes ownership unclear.
- Can confuse agents about authoritative implementation files.

**Target fix:**
Use clear separation:

```text
src/runtime code
docs/
docs/audits/
.audit/              # local/generated audit artifacts where appropriate
CI artifacts         # GitHub artifacts, not committed
```

Delete temporary patch scripts/files after use unless they are intentionally maintained tooling.

**Priority:** MEDIUM

---

# 2. Commit `ad4cf07` — Follow-up Problems

### 2.1 `retention_days` is not explicitly validated
**Finding:** Manual workflow input is inserted into the SQL string and cast to integer.

**Why this is a problem:**
- Invalid values rely on PostgreSQL to reject them.
- There is no explicit policy range.
- Negative/zero/very-large values are not prevented at workflow level.

**Target fix:**
Validate before building the request, for example:
- integer only
- explicit minimum
- explicit maximum

Then also enforce a safe minimum inside the database function for defense in depth.

**Priority:** HIGH

---

### 2.2 Supabase project reference is hardcoded
**Finding:**
`PROJECT_REF: xtvkltzmberxekoamala`

**Why this is a problem:**
- Environment-specific infrastructure identity is committed to source.
- Makes staging/production reuse harder.
- Conflicts with the dynamic infrastructure philosophy.

**Target fix:**
Use a repository/environment variable such as:

```text
SUPABASE_PROJECT_REF
```

or resolve it from the central infrastructure configuration.

**Priority:** MEDIUM

---

### 2.3 HTTP error handling is too weak
**Finding:** `curl -s` is used and success is inferred by searching the response for `"deleted"`.

**Why this is a problem:**
- HTTP failures are not handled as explicitly as they should be.
- API error bodies and transport errors can be ambiguous.
- A successful-looking payload check is weaker than proper HTTP-status validation.

**Target fix:**
Use robust HTTP handling:
- fail on non-2xx responses
- show useful error details
- enforce timeout
- distinguish transport/API/SQL/function errors
- fail the workflow when the operation did not succeed

**Priority:** HIGH

---

### 2.4 Entire API response is logged
**Finding:**
`echo "prune result: ${resp}"`

**Why this is a problem:**
- Logs more data than necessary.
- Future API response changes could accidentally expose sensitive operational information.
- Makes logs noisier.

**Target fix:**
Parse and log only safe fields, especially:

```text
deleted_count
duration
status
```

Never print credentials or full API response bodies unless sanitized for a controlled debugging path.

**Priority:** MEDIUM

---

### 2.5 No explicit preflight check that the retention function exists
**Finding:** Workflow assumes `public.prune_evolution_logs(integer)` exists because a migration is expected to have created it.

**Why this is a problem:**
- Schema drift can cause runtime failure.
- The dependency between migration and operational workflow is implicit.

**Target fix:**
Add a schema/function preflight check in CI or the workflow:

```sql
SELECT to_regprocedure(
  'public.prune_evolution_logs(integer)'
);
```

Fail clearly if the function is missing.

**Priority:** MEDIUM/HIGH

---

### 2.6 Retention policy itself needs data-classification confirmation
**Finding:** The workflow assumes 30 days is appropriate for `evolution_logs`.

**Why this is a problem:**
If `evolution_logs` contains important:
- learning history,
- governance decisions,
- audit evidence,
- experiment lineage,
- safety/evolution records,

then blindly deleting everything older than 30 days could remove information SupremeAI needs.

**Target fix:**
Define retention by data purpose:

```text
Operational logs      -> short retention
Debug telemetry      -> short retention
Evolution telemetry   -> medium retention
Security/audit data   -> long retention
Governance decisions  -> long retention
Core learned knowledge -> do not prune as ordinary logs
```

Confirm the actual contents of `evolution_logs` before locking the policy.

**Priority:** CRITICAL

---

### 2.7 Database function should enforce safe bounds too
**Finding:** Workflow-level validation is the only obvious policy boundary.

**Why this is a problem:**
Another caller could invoke the SQL function directly with an unsafe value.

**Target fix:**
Make the database function enforce its own safe range, e.g.:

```text
minimum_retention_days <= requested_days <= maximum_retention_days
```

The exact values should come from the approved retention policy.

**Priority:** HIGH

---

### 2.8 Consider batch deletion for large tables
**Finding:** The commit calls a single pruning function, but the reviewed workflow does not establish whether the function deletes in bounded batches.

**Why this is a problem:**
A large one-shot DELETE can:
- create large transactions,
- generate WAL,
- hold locks longer,
- increase CPU/I/O,
- temporarily worsen a constrained free-tier database.

**Target fix:**
Verify the function implementation. If necessary, delete in bounded batches and measure:
- rows deleted/run
- execution time
- lock impact
- DB size before/after
- WAL/IO impact where available.

**Priority:** HIGH

---

## 3. Cross-Commit System-Level Follow-ups

These are more important than fixing individual syntax/details because they affect the overall SupremeAI operating model.

### 3.1 Establish a single configuration source of truth
Current findings repeatedly show environment-specific values appearing in workflows/code.

**Target architecture:**

```text
SupremeAI Config / Resource Registry
              |
      +-------+-------+
      |               |
   GitHub CI       Runtime services
      |               |
   Variables/       Infisical
   Secrets
```

Do not duplicate service URLs, project IDs, service IDs, credentials, or deployment topology across scripts.

**Priority:** CRITICAL

---

### 3.2 Establish explicit liveness vs readiness semantics
Apply consistently to Core, Worker, Scraper, MCP and future services.

```text
Liveness  = process can serve health check
Readiness = capability/dependencies are usable
Degraded  = process alive, capability partially unavailable
```

**Priority:** HIGH

---

### 3.3 Every autonomous subsystem needs an actual end-to-end proof
Do not consider a component “working” because:
- process started,
- HTTP returned 200,
- a stub/async fallback responded.

Require real path verification.

```text
input
 -> broker/resource
 -> worker/agent
 -> execution
 -> result
 -> persistence
 -> verification
```

**Priority:** CRITICAL

---

### 3.4 Free-tier optimization must be measurement-driven
Avoid assuming that a process layout is safe because it is theoretically lightweight.

Track:
- RSS
- CPU
- startup time
- queue latency
- task success rate
- restart count
- Redis availability
- DB size
- DB growth rate

**Priority:** HIGH

---

### 3.5 Operational automation must fail safely
For destructive or state-changing automation:

```text
validate
 -> authorize
 -> execute
 -> verify
 -> record
 -> alert
```

This applies to:
- DB pruning
- deployments
- secret rotation
- auto-remediation
- autonomous code changes.

**Priority:** CRITICAL

---

# 4. Suggested Work Order

## P0 — Security / destructive-action safety
- [ ] Protect `/tasks/drain`
- [ ] Protect `/worker/status`
- [ ] Rotate/revoke historical Render API keys
- [ ] Confirm `evolution_logs` data classification
- [ ] Enforce retention bounds inside DB function

## P1 — Reliability
- [ ] Move Celery startup to FastAPI lifespan
- [ ] Add bounded worker supervision/restart
- [ ] Implement liveness/readiness separation
- [ ] Build real Celery end-to-end smoke test
- [ ] Harden DB retention HTTP error handling
- [ ] Validate `retention_days`
- [ ] Verify retention function exists
- [ ] Verify/bound batch deletion

## P2 — Architecture / maintainability
- [ ] Remove hardcoded service URLs
- [ ] Remove hardcoded Supabase project ref
- [ ] Establish central configuration/resource registry usage
- [ ] Clean temporary audit/patch artifacts
- [ ] Review large schema migration

## P3 — Optimization / observability
- [ ] Start worker concurrency at 1
- [ ] Measure memory before increasing concurrency
- [ ] Add retention metrics
- [ ] Add worker restart/queue metrics
- [ ] Add DB growth monitoring and alert threshold

---

# 5. Tracking Rule for Future Commits

For every future SupremeAI commit/push:

### A. Record
- commit SHA
- commit message
- what changed

### B. Classify
- 🟢 improvement
- 🟡 mixed
- 🔴 regression

### C. Preserve negative findings
Do **not** delete previous unresolved findings merely because a later commit improves another area.

### D. Mark resolution only when verified
Use:

```text
OPEN
PARTIALLY FIXED
FIXED — CODE VERIFIED
FIXED — RUNTIME VERIFIED
WONTFIX — JUSTIFIED
```

### E. Never confuse “CI green” with “system healthy”
A green workflow means the defined checks passed; it does not automatically prove production behavior.

---

## Current Tracker Status

| Area | Status |
|---|---|
| Free-tier worker architecture | 🟡 Improved, follow-up required |
| Celery lifecycle | 🔴 Open |
| Worker supervision | 🔴 Open |
| Worker endpoint security | 🔴 Open |
| Celery E2E verification | 🔴 Open |
| Historical secret rotation | 🔴 Open |
| DB retention automation | 🟢 Good improvement |
| Retention input validation | 🔴 Open |
| Retention API error handling | 🟡 Needs hardening |
| Retention data policy | 🔴 Open |
| DB function safety bounds | 🔴 Open |
| Hardcoded infrastructure config | 🟡 Open |
| Repository hygiene | 🟡 Open |
| Measurement/observability | 🟡 Open |

---

## Guiding Principle

**প্রতিটি commit-এর লক্ষ্য শুধু “আজকের সমস্যা fix” করা নয়।**

SupremeAI-এর জন্য আমরা track করব:

> **Improvement = নতুন capability/robustness যোগ হয়েছে + নতুন risk তৈরি হয়নি + আগের negative findings হারিয়ে যায়নি।**

পরবর্তী commit-গুলো এই tracker-এর OPEN/PARTIALLY FIXED items-এর বিরুদ্ধে যাচাই করা হবে।
