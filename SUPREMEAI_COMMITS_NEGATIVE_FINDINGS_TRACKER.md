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
Debug telemetry       -> short retention
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

পরবর্তী commit-গুলো এই tracker-এর OPEN/PARTIALLY FIXED items-এর বিরুদ্ধে যাচাই করা হবে.

---

# 6. 24-Hour Audit — 2026-09-01 16:34 UTC → 2026-09-02 16:34 UTC

**Audit scope:** `main` branch commits in the preceding 24-hour window, with targeted diff review of deployment, CI, service-role, MCP, memory, and database changes. The current `main` head at audit time is `fc1933607b6e6ba261d538da4a9c63d5728461d8`.

## 6.1 Major verified improvements

| Commit | Classification | Verified improvement |
|---|---|---|
| `23805a4` | 🟢 | Split Core / Worker / Scraper deployment jobs instead of one backend deployment path. |
| `99fa830` | 🟢 | Parallelized Core/Worker/Scraper image builds and added GitHub Actions layer caching, reducing sequential build time. |
| `22409bd` | 🟢 | Removed redundant Worker image rebuild and aliases Worker to Core's already-built digest. |
| `056b733` | 🟢 | Added scraper-specific path filtering and SHA-based image tags for traceability. |
| `6eefe03` | 🟢 | Added memory-aware gating for SelfEvolutionAgent and DailyLearner using the existing memory manager. |
| `be193f1` | 🟢 | Added service-role-based router modularization intended to reduce free-tier memory pressure. |
| `c4034f4` | 🟢 | Connected AgentSupervisor failure handling to the MCP Control Tower for an automated health sweep path. |
| `ad4cf07` | 🟢 | Added automated `evolution_logs` retention pruning to control DB growth. |
| `9d1ddc1` | 🟢 | Added MCP Docker packaging, HTTP worker wrapper, keepalive, service-role groundwork, secret scrubbing, and consolidated schema setup. |
| `fc19336` | 🟡 | Added an opt-in production degradation switch intended to prevent a missing DB pooler URL from crash-looping the node. |

## 6.2 New verified regressions / negative findings

### 6.2.1 CRITICAL — `fc19336`: degraded DB boot still creates an in-memory SQLite fallback
**Commit:** `fc1933607b6e6ba261d538da4a9c63d5728461d8`  
**File:** `backend/database/session.py`

**Finding:** When `SUPREMEAI_ALLOW_DB_DEGRADATION` is enabled and the production DB URL is missing or engine creation fails, the code does **not** stop before the fallback block. It proceeds to `create_async_engine(...)`; on failure, the existing exception handler creates `sqlite+aiosqlite:///:memory:` and assigns it to the global engine/session maker.

**Why this is dangerous:**
- The commit description says the degraded mode should boot **without** SQLAlchemy.
- The implementation instead can boot with an empty in-memory SQLite database.
- SQL-dependent routes may then appear available against ephemeral state, creating a data-integrity / false-health risk.
- This weakens the original safety property that production must never silently use SQLite.

**Status:** RESOLVED & REGRESSION-TESTED (Commit in progress)

**Fix implemented:**
- In `backend/database/session.py`, `init_engine()` returns immediately in production when `SUPABASE_ALLOW_DB_DEGRADATION=true`, keeping `_engine_instance` and `_session_maker_instance` strictly `None` (zero SQLite creation).
- In the `except Exception as exc:` block of `init_engine()`, if production and degraded mode are enabled, it logs the failure and immediately returns (no fallthrough to SQLite in-memory).
- `_get_session_maker()` raises explicit `RuntimeError` on access during degraded mode, and `get_db_session_context()` handles it cleanly with `HTTPException(503)`.
- `check_engine_health()` safely checks `if engine is None: return False` without crashing.
- 5 comprehensive regression tests added in `backend/tests/database/test_session_degradation_regression.py` validating all states (production missing DB + degraded=true, production DB error + degraded=true, production degraded=false fail-closed, and dev SQLite allowed).
- Added `("database",)` to `_CRITICAL_TEST_PARTS` in `backend/tests/conftest.py`.

**Priority:** RESOLVED (P0 Closed)

---

### 6.2.2 CRITICAL — `be193f1`: service-role rollout reintroduced hardcoded Render credentials
**Commit:** `be193f164365614d0de6bbec0e9d2431f8a9baec`  
**File:** `set_roles.py`

**Finding:** The service-role patch added a root-level script containing literal Render service IDs and Render API credential values in source code.

**Why this is dangerous:**
- A recent earlier pass intentionally removed hardcoded Render credentials from root scripts.
- This commit reintroduced the exact class of secret-management regression that the previous security cleanup was meant to eliminate.
- Secrets in the current tree must be treated as exposed even if they are later removed.

**Status:** OPEN — CODE VERIFIED

**Target fix:**
- Remove all credential literals from `set_roles.py`.
- Resolve service IDs and credentials from Infisical / GitHub environment secrets / variables.
- Rotate every credential that has been committed.
- Extend CI secret scanning to fail on this class of regression.

**Priority:** CRITICAL

---

### 6.2.3 HIGH — `c4034f4`: MCP health-sweep task errors are not caught by the surrounding `try`
**Commit:** `c4034f43ebb86a7e695cd4b97db582715d12610a`  
**Files:** `backend/core/agent_supervisor.py`, `backend/core/mcp_client.py`

**Finding:** The agent supervisor calls `asyncio.create_task(_trigger_mcp())` inside a `try/except`, but exceptions raised later inside `_trigger_mcp()` are asynchronous task exceptions and are not caught by that surrounding `except` block.

**Additional risk:** The MCP client is a global singleton whose `connect()` replaces `_exit_stack` / `_session`. Concurrent health-sweep tasks can race over this mutable state.

**Why this is a problem:**
- A failed MCP connection/tool call can become an unobserved task exception.
- Concurrent failure handling can corrupt or replace shared MCP session state.
- The error log promises failure handling that the current structure cannot reliably provide.

**Status:** OPEN — CODE VERIFIED

**Target fix:**
- Put the `try/except/finally` inside the background coroutine.
- Always disconnect in `finally` when a connection was established.
- Serialize or pool MCP connections rather than mutating a global session from concurrent tasks.
- Add a test for MCP connect failure and `health.sweep` failure.

**Priority:** HIGH

---

### 6.2.4 MEDIUM — `6eefe03`: memory threshold is documented as env-overridable but is not read from env
**Commit:** `6eefe030b945f9225e28fb370a6413cca4534604`  
**File:** `backend/core/memory_manager.py`

**Finding:** The code comment says `HEAVY_TASK_SAFE_THRESHOLD` is “Overridable via env”, but the implementation hard-codes `65.0` and `is_safe_for_heavy_task()` only accepts an explicit function argument.

**Why this matters:**
- Operational tuning cannot be done through environment configuration as documented.
- This is a configuration-contract mismatch, not merely documentation drift.

**Status:** OPEN — CODE VERIFIED

**Target fix:**
Read a validated environment value once through the canonical settings/config registry and use `65%` only as the default.

**Priority:** MEDIUM

---

### 6.2.5 MEDIUM — `056b733`: manual backend force flag also forces scraper publication
**Commit:** `056b73321cb3e1ef4e5a41c4e5451a19313581d5`  
**File:** `.github/workflows/ci.yml`

**Finding:** The new scraper change flag is defined as:

```text
scraper: steps.filter.outputs.scraper == 'true' || github.event.inputs.force_backend == 'true'
```

So a manual `force_backend` action also forces the scraper image/deploy path.

**Why this matters:**
- It weakens the intended selective-deploy optimization.
- A user asking to force only backend publication can unexpectedly rebuild/deploy the expensive scraper service.

**Status:** OPEN — CODE VERIFIED

**Target fix:**
Introduce a dedicated `force_scraper` input and keep backend and scraper forcing independent.

**Priority:** MEDIUM

---

## 6.3 Existing findings that remain relevant

The 24-hour audit also confirms that the earlier tracker findings remain important. In particular:

- Worker lifecycle/supervision and worker control-endpoint security remain unresolved from `9d1ddc1`.
- Retention validation, destructive-operation safety, data classification, and batch-deletion verification remain unresolved from `ad4cf07`.
- Historical Render credential rotation remains required; the `be193f1` regression increases its urgency.
- The project is moving toward a central dynamic configuration model, but the service-role and MCP changes show that hardcoded infrastructure identity can still reappear during rapid fixes.

---

## 6.4 24-hour audit action order

### P0
- [ ] Fix `fc19336` so degraded production mode never creates SQLite.
- [ ] Remove and rotate the Render credentials reintroduced by `be193f1`.
- [ ] Add a CI guard preventing committed Render credentials.

### P1
- [ ] Harden MCP background-task exception/finally handling.
- [ ] Make MCP connection/session concurrency safe.
- [ ] Add DB-degradation regression tests.
- [ ] Add MCP failure-path tests.

### P2
- [ ] Make the memory threshold truly env/config driven.
- [ ] Add a dedicated `force_scraper` workflow input.
- [ ] Continue migration of service IDs/URLs to the canonical configuration source.

---

## 6.5 Audit conclusion

**Overall:** 🟡 **Mixed improvement**

The last 24 hours contain substantial reliability, CI, deployment, free-tier, MCP, and operational improvements. However, the audit also found two **CRITICAL** security/data-integrity regressions and multiple reliability/configuration weaknesses introduced during the same rapid change sequence.

**Release posture:** **Do not treat the current `main` as fully production-safe solely because the CI/deployment workflow is green.** The new P0 findings must be closed and verified first.
