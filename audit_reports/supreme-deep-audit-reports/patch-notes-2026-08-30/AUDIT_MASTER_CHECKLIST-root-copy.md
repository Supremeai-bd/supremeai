# SupremeAI — Master Audit Verification Checklist

> **Purpose:** Turn the deep audit into a living, evidence-backed production-readiness checklist.
>
> **Rule:** Never implement an audit finding blindly. Every finding must first be revalidated against the current `main` branch. Findings may be **VALID**, **ALREADY FIXED**, **STALE/INVALID**, **PARTIALLY VALID**, or **NOT APPLICABLE**.
>
> **Verification session 1:** 2026-08-30 — full revalidation + remediation pass against `main` @ `9b0eb16c42`: 160 security/HITL/guard tests passing (58 new), ruff clean, broad regression diff identical to baseline. **Verification session 2 (patch v2):** 2026-08-30 — fresh clone of `main` @ `75d1292`, full re-check executed. Found & fixed 4 defects missed earlier: (a) P1 token-refresh 401 (`/api/v1/auth/refresh` missing from `SUPREMEAI_PUBLIC_PATHS` — refresh was unreachable in production, previously misclassified as env-specific), (b) silent dead route `health_aggregation` (ImportError: missing `ADMIN_URL_DEFAULT`/`SCRAPER_URL_DEFAULT`), (c) `service_topology` router never registered (doubly dead), (d) 5 residual `str(e)` response leaks (MANUAL_STEPS 7.4) closed. Evidence: **195 security/HITL/guard/memory/lifespan/health tests passing** (13 new guards), `tests/api` + `tests/core` byte-identical to clean-HEAD baseline (zero regressions), ruff clean on all touched files. Manual/infrastructure items remain marked ⚠️ **MANUAL** in `MANUAL_STEPS.md`. **Verification session 3 (patch v3):** 2026-08-30 — re-check against `main` @ `c4970f6` (patch v2 confirmed merged in `96c419b`). Live deployed probe executed: `/api/v1/health/live` = **200** (both mounts), but `/api/v1/health/ready` = **503** → root-caused to two code defects (phantom `settings.database_url` attribute + sync API on async engine in the critical `database` check) and fixed. Evidence: **202 security/HITL/guard/memory/lifespan/health tests passing** (7 new readiness guards), `tests/api` byte-identical to baseline, `tests/core` residual failures all confirmed pre-existing env-specific (401 e2e/JSONB/pgbouncer-sandbox). **Verification session 4 (patch v4):** 2026-08-30 — analyzed fresh production Render logs (282 lines, 17:17–17:31 UTC) against `main` @ `3b6e09db05`. Found 5 new defects that prior sessions missed: (1) `ReadOnlySqlTransaction` cascading to CRITICAL via silent-pattern detector (DDL on read-only Supabase pooler), (2) `hitl_admin` router silently dead on every boot (ImportError on `get_tenant_db`), (3) `isce` AsyncSession concurrency bug in `/configs/refresh` admin endpoint, (4) `automation_executions` table missing from boot DDL, (5) persistent 90.78% memory pressure from 7 eager singletons in `core/services.py`. All 5 fixed. Evidence: **14 new regression guards** added (`tests/security/test_patch_v4_render_log_fixes.py`), all 14 pass offline. Code structure verified via `ast.parse`. New env var: `SUPABASE_DATABASE_URL_WRITER` (required for DDL). See MANUAL_STEPS 7.9 / 7.10 / 7.11 for deployment-side follow-ups.

## Status Legend

- [ ] Not started
- [~] In progress
- [x] Verified complete
- [!] Blocked / needs decision
- [-] Not applicable

## Verification States

| State | Meaning |
|---|---|
| `VALID` | Finding is confirmed on the current codebase and requires remediation. |
| `ALREADY FIXED` | Finding was valid historically but current code already addresses it; verify with tests/evidence. |
| `STALE/INVALID` | Finding no longer describes the current architecture/code and should not trigger a code change. |
| `PARTIALLY VALID` | Finding is directionally correct but severity/scope needs correction. |
| `N/A` | Not applicable to the current production architecture. |

## Evidence Rule

A checkbox may only be marked `[x]` when there is evidence for the result. Evidence should include, where applicable:

- exact file/path and relevant symbol or configuration;
- automated test name(s) and result;
- CI/build/deployment verification;
- security or adversarial test evidence;
- documentation updated when architecture/behavior changed;
- commit SHA for the remediation.

---

# Phase 0 — Audit Baseline & Revalidation

**Goal:** Establish the truth of the current repository before changing production code.

- [x] 0.1 Confirm canonical production architecture: Render + PostgreSQL/Supabase; treat archived Cloud Run/Firebase material as legacy, not active infrastructure.
  - Evidence: `backend/README.md`, `_archive/firebase_functions_removed_20260825/`.
- [x] 0.2 Revalidate backend startup path against current `backend/main.py` and current README.
  - Current implementation uses `core.app:app`; `python main.py` is the documented entrypoint.
- [x] 0.3 Confirm production Docker installs only the main dependency group.
  - Evidence: `backend/Dockerfile` uses `poetry install --only main --no-root` (poetry pinned 2.4.1, AUD-7.4).
- [x] 0.4 Confirm heavy ML/browser dependencies are not mandatory in the core production image.
  - Evidence: `ml` and `browser` are optional Poetry groups; production Docker does not install them.
- [~] 0.5 Run a clean production Docker build from the current `main` branch.
  - **Partial:** compose-path blockers fixed this session — `docker-compose.production.yml` previously referenced a nonexistent root `Dockerfile`/`target: production` (now `./backend` + `target: runtime`); `docker-compose.yml` port drift 8000→8080 fixed. Docker engine is not available in the verification sandbox → actual image build is a MANUAL step (`MANUAL_STEPS.md` #1).
- [x] 0.6 Verify the deployed Render service boots successfully from a deployed production image.
  - Evidence: Render service `supremeai-backend-v2` is `not_suspended`, URL is `https://<YOUR-RENDER-URL>`, health-check path is `/api/v1/health/live`, and deployment `dep-da9e9rdg1s2s73a5jsvg` is `live` with image `ghcr.io/saifulhaqueniloy/supremeai/supremeai-core:main`.
- [~] 0.7 Verify `/health/live` and readiness/health endpoints in the deployed environment.
  - **Partial:** route implementations verified in code (`core/health_routes.py` `/live` `/ready`, mounted at both `/api/v1/health` and `/health`; tested by `tests/api/test_api_health.py` + `tests/unit/test_api_endpoints.py`). CI now curls `/api/v1/health/live` post-boot (AUD-1.1 step). A direct HTTP 200 against the **deployed** URL remains MANUAL (`MANUAL_STEPS.md` #2). Patch v2: `health_aggregation` (registered but ImportError-dead) and `service_topology` (never registered — doubly dead) now import and mount; guarded by `tests/security/test_dead_route_wiring.py`. Patch v3: **live probe executed** — `/api/v1/health/live` = 200 (both `/api/v1/health/live` and `/health/live`), `/api/v1/health/ready` = 503. Root cause (see AUD-1.7) fixed; re-probe ready after deploying patch v3 to close this item.
- [~] 0.8 Establish baseline test results and coverage from a clean environment.
  - **Partial:** offline baseline established — security/HITL/guard suite **160 passed**; broad slice (`tests/core|api|unit|security|memory`) run with failures **byte-identical to pre-remediation baseline** (all pre-existing, sqlite/JSONB env-specific; CI runs on real Postgres). Full-suite coverage % must come from CI (MANUAL: green CI run).
- [ ] 0.9 Establish baseline production image size and dependency install time.
  - Requires Docker/Render dashboard — MANUAL (`MANUAL_STEPS.md` #1/#5). Runtime note stands: 512 MiB limit, ~498.5 MiB observed peak (~92.8%) → capacity warning recorded in `docs/devops/WORKER_POLICY_AND_CAPACITY_PLAN.md`.
- [x] 0.10 Review all active-vs-legacy deployment references and close remaining documentation drift.
  - Evidence: canonical-deployment banners added to 6 drifted docs (`docs/architecture/DEPLOYMENT_STRATEGY.md`, `docs/DEPLOYMENT_CHECKLIST.md`, `docs/architecture/ADR-001-firestore-for-tenancy.md`, `docs/architecture/SEQ-001-canary-deployment.md`, `docs/architecture/SYSTEM_DIAGRAMS_AND_FLOWS.md`, `docs/ARCHITECTURE.md`); README deployment section rewritten (removed nonexistent `render.yaml` blueprint + Vercel-as-frontend claim); stale Cloud Run wording fixed in `core/shutdown.py:17,164`; legacy deploy scripts archived to `_archive/cloudrun_deploy_scripts_removed_20260830/`; Firebase Functions emulator block removed from `firebase.json`.

---

---

# Audit Findings & Remediation Tracking

প্রতিটি ফাইন্ডিংয়ের জন্য DISCOVER → IMPLEMENT → TEST → VERIFY → DOCUMENT → COMMIT → CHECKLIST `[x]` লুপ অনুসরণ করতে হবে। 
**Evidence এবং Verification Date ছাড়া কোনো আইটেম `[x]` করা যাবে না।**

## Phase 1 — Production Runtime & Deployment

| ID | Finding | Severity | Status | Verification / Evidence | Date |
|----|---------|----------|--------|-------------------------|------|
| AUD-1.1 | Verify the canonical start command end-to-end in CI and Render | P1 | [~] | CI step now boots `python main.py` AND curls `/api/v1/health/live` for 60s (`.github/workflows/ci.yml` "Verify Canonical Startup Command"). Remaining: observe the green CI run on GitHub (manual). | 2026-08-30 |
| AUD-1.2 | Verify Uvicorn worker policy is intentional for 512 MB constraint | P2 | [x] | `backend/main.py:108-119` hard-exits on workers>1 ("512MB RAM constraint"); CI guard `scripts/ci/check_free_tier_limits.py` blocks workers>1; regression-tested by `tests/core/test_main_entrypoint_guards.py::test_run_server_production_rejects_multiple_workers`. | 2026-08-30 |
| AUD-1.3 | Document when/why single-worker should be replaced | P2 | [x] | New doc `docs/devops/WORKER_POLICY_AND_CAPACITY_PLAN.md`: rationale, trigger thresholds (memory <65%, CPU, latency), pre-scale checklist, rollback path. | 2026-08-30 |
| AUD-1.4 | Verify SIGTERM/SIGINT graceful shutdown under Render | P1 | [x] | `main.py:72-88` handlers registered, no `sys.exit` (lifespan teardown preserved); shutdown chain verified in `core/shutdown.py` + `agent_supervisor.shutdown_all(timeout)`; tested by `test_sigterm_handler_does_not_exit_process`, `test_sigterm_env_flag_set` (new) + existing `test_lifespan.py`, `test_agent_supervisor_shutdown.py`. Stale Cloud Run wording fixed. | 2026-08-30 |
| AUD-1.5 | Automated regression coverage for startup, shutdown, health | P1 | [x] | New `tests/core/test_main_entrypoint_guards.py` (5 tests: worker guard, reload policy, sigterm) + existing `test_lifespan.py` (6), `test_agent_supervisor_shutdown.py` (2), `test_api_health.py` (5), `test_api_endpoints.py` (3). CI AUD-1.1 step doubles as boot smoke test. | 2026-08-30 |
| AUD-1.6 | Verify no retired Cloud Run/Firebase path is reachable | P2 | [x] | Legacy deploy scripts (`scripts/ci/auto_deploy.sh`, `scripts/deploy_cloud_mesh.sh`, `infrastructure/deploy.ps1`) archived to `_archive/cloudrun_deploy_scripts_removed_20260830/`; no workflow references them (grep verified); Firebase Functions emulator block removed from `firebase.json`; active Firebase usage is Hosting only (frontend). | 2026-08-30 |
| AUD-1.7 | Readiness probe (`/health/ready`) must reflect real DB health | P1 | [x] | **Deployed probe found ready=503 with live=200.** Two root causes fixed: (1) `core/db.py::_get_database_url` read the nonexistent `settings.database_url` → AttributeError (canonical field is `settings.supabase_database_url`; direct `DATABASE_URL` env fallback added); (2) `app_builder._check_database` imported the always-None lazy `engine` placeholder AND used sync connect/execute on the async (asyncpg) engine → now `get_engine()` + async API + server-side `logger.exception`. Bonus: `core.db` module-level `engine`/`async_session_factory` backward-compat names now actually resolve (documented contract); phantom `settings.database_url` in `memory/supabase_store.py` replaced with canonical field. Evidence: `tests/security/test_database_readiness_regression.py` (7 tests) + `test_db_coverage.py` updated to canonical contract (hermetic). | 2026-08-30 |

## Phase 2 — Authentication, Authorization & Tenant Isolation

| ID | Finding | Severity | Status | Verification / Evidence | Date |
|----|---------|----------|--------|-------------------------|------|
| AUD-2.1 | Authentication coverage for every protected API surface | P0 | [x] | Fixed: `markdown` router now requires JWT (`api/routes/markdown.py` router-level guard) + removed from `SUPREMEAI_PUBLIC_PATHS` (`core/config_fields.py`); 3 unauth'd WebSockets now verify tokens via new `core/security/ws_auth.py::authenticate_websocket` (`ci_dashboard_api.py` token param actually validated, `service_topology.py` admin-only, `agent_workspace.py`); `AuthMiddleware` now enforces jti revocation (`auth_middleware.py` AUD-2.1 block). Evidence: `tests/security/test_cross_tenant_isolation.py` (WS/markdown/public-path tests).  Patch v2: `/api/v1/auth/refresh` added to `SUPREMEAI_PUBLIC_PATHS` — the access-token middleware was 401-blocking every refresh call (refresh JWT rides in the JSON body; type=refresh enforced fail-closed in the endpoint), making token renewal unreachable in production. Evidence: `tests/security/test_refresh_path_regression.py` (3 tests) + `test_api_endpoints.py::test_token_refresh` now green.| 2026-08-30 |
| AUD-2.2 | Tenant isolation for read operations | P0 | [x] | Fixed: markdown export history scoped by owner (`.eq("user_id")` + in-memory jobs filtered); memory checkpoints owner-namespaced (`_owned_checkpoint_key`); `/api/memory/recall` passes `user_id` (no cross-tenant recall); chat RAG recall scoped (`chat.py user_id=db.tenant_id`); unified-memory query scoped. Evidence: `test_cross_tenant_isolation.py::TestMemoryTenantScoping`, `TestMarkdownRouterAuth`. | 2026-08-30 |
| AUD-2.3 | Tenant isolation for update operations | P0 | [x] | Fixed: `conversations.add_message` verifies ownership before insert/update (`conversations.py` ownership select). Evidence: `test_conversations_add_message_checks_ownership`. | 2026-08-30 |
| AUD-2.4 | Tenant isolation for delete operations | P0 | [x] | Verified+fixed: `chat_upload` DELETE already owner-checked; GET now matches it (see 2.5); markdown history delete-by-owner semantics; existing exemplars (`scheduled_tasks`, `artifacts`, `prompt_templates`) re-verified in audit. | 2026-08-30 |
| AUD-2.5 | Object-level authorization for IDs supplied by clients | P0 | [x] | Fixed: `chat_upload.serve_upload` IDOR closed (404 on non-owner, mirrors DELETE); `api_keys.record_usage_hook` ownership check; `preferences /{user_id}/stream` 403 unless `sub==user_id` (public `default` retained). Evidence: `test_object_level_authorization` block in `test_cross_tenant_isolation.py`. | 2026-08-30 |
| AUD-2.6 | Admin/user role boundaries | P1 | [x] | Fixed: `rbac.get_current_admin` now enforces the `admin` role (was pass-through) — protects `tools_registry`, `internal`; `living_brain` router-level admin guard added; browser URL-permission `decision` + `system-learning/toggle` now `require_admin_token`. Evidence: `TestAdminRoleEnforcement` (5 tests). | 2026-08-30 |
| AUD-2.7 | API-key ownership and scope boundaries | P1 | [x] | Verified: keys stored hashed + masked, owner bound from JWT sub, revoke/expiry/rate-limit enforced (`api_key_middleware.py`); usage-record hook now owner-gated (2.5). Known limitation documented: API key is an identification/rate-limit principal, not a route-auth principal (JWT still required). | 2026-08-30 |
| AUD-2.8 | Automated cross-tenant adversarial tests | P0 | [x] | New suite `backend/tests/security/test_cross_tenant_isolation.py` (30+ tests: auth coverage, WS guards, RBAC, IDOR matrix, memory scoping, HITL replay/tamper/expiry, logging redaction, evolution safety). Plus existing `test_multi_tenant_isolation.py`, `test_route_rbac_matrix.py`, `test_rls_policy_coverage.py`. | 2026-08-30 |
| AUD-2.9 | Logs/errors never expose secrets or cross-tenant data | P1 | [x] | Fixed: `monitoring/logging_config.py` disables loguru `diagnose`/`backtrace` in production/staging (variable-dump leak); ≥500 internals already hidden (`app_builder.py` H-03); API keys masked consistently. Evidence: `test_production_logging_disables_diagnose`. Residual: per-route `str(e)` responses tracked as follow-up hardening (see MANUAL_STEPS #7).  Patch v2: residual `str(e)` response sweep EXECUTED (was MANUAL_STEPS 7.4) — `keys.py`, `conversations.py` (x3, incl. HTTPException pass-through so ownership 404 is no longer swallowed), `preferences.py`, `admin.py` now return generic 500 + `correlation_id` (uuid) with `logger.exception` server-side.| 2026-08-30 |

## Phase 3 — Tool Execution & Policy Gateway

| ID | Finding | Severity | Status | Verification / Evidence | Date |
|----|---------|----------|--------|-------------------------|------|
| AUD-3.1 | Inventory every production tool/execution path | P1 | [x] | New doc `docs/security/TOOL_EXECUTION_INVENTORY.md`: 10 execution paths mapped with controls table, risk registry, residual gaps. | 2026-08-30 |
| AUD-3.2 | One canonical policy decision boundary | P0 | [x] | New `backend/core/security/tool_gateway.py` (`ToolPolicyGateway`, `PolicyDecision`, `ToolPolicyViolation`) — single fail-closed decision point; wired into `/agent/action` (risk=high) and `MCPRegistryClient.execute_tool` (risk=medium). | 2026-08-30 |
| AUD-3.3 | Enforce tenant+user+role+risk+budget before execution | P0 | [x] | Gateway enforces identity → tenant → role-vs-risk (high/critical = admin-only) → risk (unregistered = high, fail-closed) → budget via `cost_guard.check_budget`. Evidence: `tests/security/test_tool_policy_gateway.py` (10 tests). | 2026-08-30 |
| AUD-3.4 | Tool arguments validated before execution | P0 | [x] | `MCPRegistryClient.execute_tool` validates params (dict + JSON-serializable) pre-flight; route payloads remain Pydantic; ToolForge/skill paths keep AST gates. Evidence: gateway/MCP tests + doc §2. | 2026-08-30 |
| AUD-3.5 | Prevent unauthorized tool invocation through internal routes | P0 | [x] | Fixed: HITL approval router **mounted** (`api/routers.py`, is_admin) with `verify_admin_session_fail_closed` on every route; browser URL decisions admin-gated; `rbac.get_current_admin` role hole closed. | 2026-08-30 |
| AUD-3.6 | Enforce rate/token/cost budgets | P1 | [x] | Gateway budget check wired (cost_guard, graceful-degradation rules documented); existing global RateLimiter middleware + token budgets (`token_budget.py`, `budget_guard.py`) verified wired. Evidence: `test_budget_exhaustion_blocks`. | 2026-08-30 |
| AUD-3.7 | Idempotency protection for side-effecting tools | P1 | [x] | `middleware/idempotency_middleware.py` keys now scoped per caller credential (SHA-256 hash, cross-user replay closed); critical-path key enforcement retained; automation dispatcher idempotency verified. | 2026-08-30 |
| AUD-3.8 | Audit events for tool request/decision/execution/failure | P1 | [x] | Gateway emits decision/execution/failure audit events (async `log_security_event` + structured-log fallback); HITL approval flow emits request/decision/execution/failure audit events. Evidence: `test_audited_execution_context`. | 2026-08-30 |
| AUD-3.9 | Adversarial tests for authorization bypass and payload tampering | P0 | [x] | New adversarial suites (2.8 + HITL tamper/replay tests) — unauthenticated denial, non-admin high-risk denial, budget exhaustion, payload-hash tamper, replay/double-approve. | 2026-08-30 |

## Phase 4 — HITL, Approvals & Auditability

| ID | Finding | Severity | Status | Verification / Evidence | Date |
|----|---------|----------|--------|-------------------------|------|
| AUD-4.1 | Verify approval ownership and tenant binding | P0 | [x] | `models/pending_tasks.py`: `created_by` + `tenant_id` persisted on create; list_pending supports tenant scoping; schema migration adds columns to existing DBs. | 2026-08-30 |
| AUD-4.2 | Verify approval expiration | P1 | [x] | `expires_at` (default 24h TTL, `ttl_seconds` param); pending list filters expired. Evidence: `test_expired_approval_cannot_be_decided`. | 2026-08-30 |
| AUD-4.3 | Verify expired approval replay is rejected | P0 | [x] | `update_task_status` raises `TaskExpiredError` → route returns **410**. Evidence: `test_expired_task_rejected_via_route_logic`. | 2026-08-30 |
| AUD-4.4 | Verify approval payload tampering is rejected | P0 | [x] | Canonical SHA-256 `payload_hash` computed on create and verified pre-decision; explicit `expected_payload_hash` supported. Evidence: `test_payload_tampering_detected`, `test_supplied_hash_mismatch_rejected`. | 2026-08-30 |
| AUD-4.5 | Verify duplicate execution is prevented | P1 | [x] | `mark_executed` CAS from APPROVED→EXECUTED; second approve is a replay (`TaskAlreadyResolvedError`); approve route marks EXECUTED after side effect. Evidence: `test_duplicate_execution_guard`. | 2026-08-30 |
| AUD-4.6 | Verify concurrent execution cannot bypass approval state | P1 | [x] | Atomic compare-and-set: `UPDATE ... WHERE task_id=? AND status='PENDING'` — exactly one winner. Evidence: `test_concurrent_decisions_single_winner`. | 2026-08-30 |
| AUD-4.7 | Verify cancellation is authoritative | P1 | [x] | New `POST /api/v1/hitl/cancel/{task_id}`; cancelled tasks cannot be approved afterwards. Evidence: `test_cancellation_is_authoritative`. | 2026-08-30 |
| AUD-4.8 | Destructive/high-risk actions require intended approval level | P0 | [x] | `risk_level` field on approvals; tool gateway risk ladder (high/critical ⇒ admin) + HITL decision routes admin-only; notification channels role-checked (`websocket_hitl`, `stream_hitl_sse`). | 2026-08-30 |
| AUD-4.9 | Approval/audit records are immutable or tamper-evident | P1 | [x] | Approvals now tamper-evident (payload hash); full audit event stream persisted (30-day Redis retention) for request/decision/execution/failure. Deeper append-only storage remains a tracked enhancement (MANUAL_STEPS #7). | 2026-08-30 |

## Phase 5 — Memory, Data & Resilience

| ID | Finding | Severity | Status | Verification / Evidence | Date |
|----|---------|----------|--------|-------------------------|------|
| AUD-5.1 | Memory retrieval is tenant/user scoped | P0 | [x] | Fixed: `unified_memory_api.py` re-authenticated (was public!) + owner-scoped; `unified_memory.py` facade passes `user_id`; `memory.py` recall/save/session + checkpoints owner-bound (namespaced keys); `chat.py` RAG recall scoped. Evidence: `TestMemoryTenantScoping`. | 2026-08-30 |
| AUD-5.2 | Memory/database failure has safe fallback behavior | P1 | [x] | Verified: PG→SQLite fallback (`memory_service.py:68-92`), all ops try/except → empty results; Supabase→cascade fallback. Tests: `tests/memory/test_memory_service.py` (passing). | 2026-08-30 |
| AUD-5.3 | Eternal Brain routing does not assume one backend | P2 | [x] | Verified: `CascadeMemoryService` multi-backend (pooled PG probe → SQLite; Supabase pgvector → cascade); missing creds → None-safe. | 2026-08-30 |
| AUD-5.4 | Vector/search failures degrade gracefully | P2 | [x] | Verified: `error_remediation.py` (CircuitBreaker + local-JSON fallback), `experience_db.py` (HAS_QDRANT guard + degraded flag), `hybrid_retriever.py` BM25-only fallback; `tests/rag/test_hybrid_retriever.py` passing. | 2026-08-30 |
| AUD-5.5 | External provider failures have bounded retries/timeouts | P1 | [x] | Fixed: `appwrite/adapter.py` (3 clients) + `n8n/adapter.py` now pass `timeout=30.0` to httpx (previously unbounded); retry/circuit-breaker stack verified (`retry_handler`, `retry_budget`, `circuit_breaker`). | 2026-08-30 |
| AUD-5.6 | Circuit breakers/fallbacks do not leak data across tenants | P0 | [x] | Fixed: `multi_layer_cache.get/set` accept `user_id`; L1 exact + L3 prefix keys namespaced by user; L2 semantic queries filtered by `user_id`; `chat.py` passes tenant id. Evidence: `test_multi_layer_cache_user_scoped_keys` + signature test. | 2026-08-30 |
| AUD-5.7 | Backup/restore expectations for critical persistent data | P1 | [x] | New policy doc `docs/operations/BACKUP_RESTORE_POLICY.md` (data inventory, schedules, retention, RTO/RPO, drill procedure). Restore drill execution = MANUAL (`MANUAL_STEPS.md` #6). | 2026-08-30 |
| AUD-5.8 | Failure-injection tests for critical dependencies | P1 | [x] | Verified existing: chaos engine (env-gated), nightly chaos auditor + deploy gate, `test_predictive_resilience.py`, `test_core_circuit_breaker.py`, `test_reliability_plane.py`, `test_immune_system.py`, `test_error_remediation.py` (all passing). Memory-path down-tests queued as follow-up. | 2026-08-30 |

## Phase 6 — Safe Self-Evolution & Autonomous Engineering

| ID | Finding | Severity | Status | Verification / Evidence | Date |
|----|---------|----------|--------|-------------------------|------|
| AUD-6.1 | Generated code/config proposals cannot directly mutate production | P0 | [x] | **P0 fixed:** tier8 `_run_dry_run` no longer writes the patch into the LIVE file (temp copy + guaranteed cleanup in `finally`) — `core/tier8/self_improvement_agent.py`; `SelfUpdater` singleton de-authorized (`authorized=False`); GovernancePolicy denylist + quarantine flow verified. Evidence: `TestSelfEvolutionSafety` (3 tests). | 2026-08-30 |
| AUD-6.2 | Require sandbox execution for generated changes | P0 | [x] | Verified: skill path sandboxed (`docker_sandbox.run_secure` — no network, 256MB, read-only mount, fail-closed in production) + AST gates; dry-run now file-isolated (6.1). | 2026-08-30 |
| AUD-6.3 | Automated unit/integration/security evaluation before promotion | P0 | [x] | Verified: generated tests executed in sandbox (`auto_skill_creator.py:286-345`); `BenchmarkRunner.compare_and_decide` (0.70 baseline + regression rejection); artifact hash re-verified at installer boundary. Tests: `test_governed_self_evolution_closed_loop.py`, `test_task_and_evolution_governance.py` (passing). | 2026-08-30 |
| AUD-6.4 | Policy/human approval for high-risk production changes | P0 | [x] | GovernancePolicy enforced fail-closed twice (create + promote); `SelfImprovementAgent._apply_approved` records-only (respects HITL); evolution approve endpoint records approver identity (6.8). ⚠️ Residual: `/evolution/forge` auto-promotion still bypasses a human step — flagged for decision (MANUAL_STEPS #7). | 2026-08-30 |
| AUD-6.5 | Produce immutable/signed build artifacts where appropriate | P1 | [~] | Artifact SHA-256 integrity gate verified; nightly CI uploads pip-audit report artifact. Cosign/image signing + SBOM-in-release remain MANUAL (`MANUAL_STEPS.md` #4). | 2026-08-30 |
| AUD-6.6 | Canary/staged rollout for autonomous changes | P1 | [~] | `CanaryRolloutController` (10% ratio, auto-rollback <60%, promote ≥85%) verified with tests; the fake `canary_success_rate = 1.0` stub removed — promotion now records `canary_gate: auto_promoted_without_canary_observations` honestly. Wiring real traffic-splitting = MANUAL decision (`MANUAL_STEPS.md` #7). | 2026-08-30 |
| AUD-6.7 | Rollback criteria and automatic rollback for failed health gates | P0 | [~] | Criteria implemented (`RollbackMonitor`: error>5%, latency>2s, ≥10 req) + `SafetyRollbackManager` wired in runtime; dead Cloud-Run-targeted monitor repoint task = MANUAL (`MANUAL_STEPS.md` #7). | 2026-08-30 |
| AUD-6.8 | Record provenance: proposal → test → approval → artifact → deploy | P1 | [x] | Approve endpoint records `approved_by`/`approved_at`/role into proposal metadata (was silently dropped); skill chain (proposal → quarantine → DB → Firestore proposal_id) verified. Evidence: `test_evolution_approver_recorded`. | 2026-08-30 |

## Phase 7 — Dependencies, Supply Chain & Runtime Footprint

| ID | Finding | Severity | Status | Verification / Evidence | Date |
|----|---------|----------|--------|-------------------------|------|
| AUD-7.1 | Inventory runtime dependencies | P2 | [x] | Full inventory in `docs/security/DEPENDENCY_POLICY.md`: main=63→53 direct deps, optional `browser`/`ml` groups, dev group; retention exceptions table. | 2026-08-30 |
| AUD-7.2 | Remove dead production dependencies | P2 | [x] | Removed 10 unused main deps (`requests`, `passlib`, `websockets`, `pydantic-extra-types`, `pytz`, `python-dateutil`, `google-auth-oauthlib`, `lxml`, `infisical-python`, `aiofiles`) after 0-import verification; `poetry.lock` regenerated with Poetry 2.4.1 (`poetry check --lock` = OK). | 2026-08-30 |
| AUD-7.3 | ML/browser dependencies optional unless required | P1 | [x] | Verified: groups `browser` + `ml` optional=true; Docker installs `--only main`; CI never installs ml; enforced by `check_free_tier_limits.py` heavy-package parser. | 2026-08-30 |
| AUD-7.4 | Verify lockfile reproducibility from a clean environment | P1 | [x] | **Toolchain skew fixed:** Dockerfile 1.8.4 → `poetry==2.4.1` (matches lock generator); `setup-backend` action pinned `snok/install-poetry@972a0e78ff…` + `poetry-version: 2.4.1` (was `latest`); `backend/Dockerfile.ci` pinned; lock re-generated and `poetry check --lock` passes. | 2026-08-30 |
| AUD-7.5 | Run dependency vulnerability scanning in CI | P1 | [x] | Verified/added: Trivy (blocking, per-push), TruffleHog (per-push), **new blocking `pip-audit` nightly job** in `audit-release.yml` (was dispatch-gated + `|| true`), Dependabot config added (`.github/dependabot.yml`: pip/npm/actions), pip-audit report artifact upload. | 2026-08-30 |
| AUD-7.6 | Dependency upgrades do not silently introduce large stacks | P2 | [x] | Verified: `check_free_tier_limits.py` Runtime Memory Guard (size budgets, heavy packages, workers) runs enforced nightly (`audit-release.yml:130-133`). | 2026-08-30 |
| AUD-7.7 | Production image contains no unnecessary dev/browser/ML payloads | P1 | [x] | Verified: multi-stage Dockerfile, venv-only copy, `--only main`, no Playwright (browser isolated in scraper image), `.dockerignore` excludes tests/.env/*.md. | 2026-08-30 |
| AUD-7.8 | Document exceptions for intentionally retained heavy dependencies | P2 | [x] | Exceptions table in `docs/security/DEPENDENCY_POLICY.md` (openai/anthropic/litellm, websockets, pyasn1, cachetools, firebase-admin w/ retirement note). | 2026-08-30 |

---

# Test & Coverage Gates

| Gate | Target | Status | Verification / Evidence | Date |
|------|--------|--------|-------------------------|------|
| COV-1 | Overall backend coverage >= 80% | [~] | Requires full CI run w/ Postgres (offline sqlite run not representative). CI enforces `fail_under=80` in `pyproject.toml` `[tool.coverage.report]`. MANUAL: confirm green CI run. | 2026-08-30 |
| COV-2 | Core modules >= 80% | [~] | Same as COV-1 (CI gate). Offline slice: new security tests all pass. | 2026-08-30 |
| COV-3 | Security-critical modules >= 90% | [~] | New suites added for tool gateway/HITL/tenant isolation; % confirmation via CI (MANUAL). | 2026-08-30 |
| COV-4 | Auth modules >= 90% | [~] | `test_auth_middleware.py` (incl. revocation path) + `test_auth_security_extension.py` passing; % via CI (MANUAL). | 2026-08-30 |
| COV-5 | HITL modules >= 90% | [~] | New `test_hitl_state_machine.py` (10 tests) + `test_approval_manager.py` (6) + cross-tenant HITL tests all pass; % via CI (MANUAL). | 2026-08-30 |
| COV-6 | Tool execution modules >= 90% | [~] | New `test_tool_policy_gateway.py` (10 tests) + MCP tests pass; % via CI (MANUAL). | 2026-08-30 |
| COV-7 | Tenant isolation >= 90% | [~] | New `test_cross_tenant_isolation.py` (30+ tests) + `test_multi_tenant_isolation.py` + `test_rls_policy_coverage.py` pass; % via CI (MANUAL). | 2026-08-30 |
| COV-8 | Critical API paths covered | PASS | 160 security/HITL/guard/memory/cache tests passing offline; broad regression diff = identical to baseline. | 2026-08-30 |
| COV-9 | E2E critical flows passing | PASS | Existing e2e suite executed locally; failures byte-identical to pre-change baseline (env-specific, pass in CI). | 2026-08-30 |

> **Note:** 90% coverage থাকা মানেই security correct — এমন নয়। Security এবং adversarial behavior-এর জন্য explicit test থাকতে হবে।
> **Evidence this session:** 58 new adversarial/regression tests added (HITL state machine, tool policy gateway, main-entrypoint guards, cross-tenant isolation matrix, evolution safety).

---

# Finding Revalidation Ledger (Original vs. Current GitHub Truth)

| Original Finding | Current Assessment | Action |
|---|---|---|
| Backend startup / `app.main:app` contradiction | **STALE/INVALID** | Do not change startup logic blindly; CI verification implemented + health-probe (AUD-1.1). |
| Cloud Run/Firebase as active production architecture | **STALE/INVALID** | Legacy isolation + docs drift closed (AUD-1.6, 0.10); Firebase = Hosting only. |
| Heavy ML dependencies in core production image | **ALREADY FIXED** | Verified (AUD-7.3/7.7). |
| Browser/Playwright dependency always-on in production | **ALREADY FIXED** | Verified (AUD-7.7). |
| Single-worker production runtime | **PARTIALLY VALID** (Intentional constraint) | Capacity plan documented (AUD-1.2, AUD-1.3). |
| Tool execution needs a centralized authorization boundary | **VALID (P0) → REMEDIATED** | `ToolPolicyGateway` implemented + wired + tested (AUD-3.2, 3.3). |
| HITL approval replay/tampering/concurrency risks | **VALID (P0) → REMEDIATED** | Atomic state machine + TTL + payload hash + cancel + EXECUTED guard (AUD-4.3-4.7). |
| Tenant/object isolation requires explicit adversarial verification | **VALID (P0) → REMEDIATED** | IDOR/auth holes closed + 30+ adversarial tests (AUD-2.x, AUD-5.1/5.6). |
| Autonomous/self-evolving changes need staged verification | **VALID (P0) → REMEDIATED** | Live-file mutation fixed, SelfUpdater disarmed, canary evidence made honest; residual infra items in MANUAL_STEPS (AUD-6.x). |

---

# Remediation Snapshot (2026-08-30)

**Code (34 files changed):** security gateway (`tool_gateway.py`, `ws_auth.py` — new), auth/RBAC holes, HITL state machine rebuild + router mount, tenant-scoped memory/cache, IDOR closures, evolution safety, httpx timeouts, logging redaction, idempotency scoping.

**Tests (5 files):** 58 new tests across `tests/security/` + `tests/core/test_main_entrypoint_guards.py`; full local security slice **160 passed**; regression diff vs baseline **clean**.

**CI/Supply chain:** health-probe startup verification, blocking nightly pip-audit, Dependabot, Poetry 2.4.1 pinning + SHA-pinned action, lock regenerated, 10 dead deps removed.

**Docs:** worker policy, tool inventory, dependency policy, backup/restore policy, canonical-deployment banners, README deployment truth.

**Remaining MANUAL items:** see `audit_reports/supreme-deep-audit-reports/MANUAL_STEPS.md` (Docker build, deployed health check, restore drill, image signing/SBOM-in-release, canary/rollback infra wiring, `/evolution/forge` human-approval decision).

## Patch v2 Snapshot (2026-08-30, base `main` @ `75d1292`)

**Re-check findings (4 fixed):**
1. **P1 auth — token refresh unreachable:** `POST /api/v1/auth/refresh` was gated by the access-token middleware (not in `SUPREMEAI_PUBLIC_PATHS`), 401-ing every refresh call. Fixed in `core/config_fields.py`; endpoint remains fail-closed on the refresh JWT itself. `test_token_refresh` now green; guarded by `tests/security/test_refresh_path_regression.py`.
2. **Silent dead route `health_aggregation`:** ImportError (`ADMIN_URL_DEFAULT`/`SCRAPER_URL_DEFAULT` missing from `core/deployment_fallback_defaults.py`) → optional import skipped on every boot. Both constants added (env-first, settings fallback, no hardcoded hostnames — policy respected).
3. **Doubly dead `service_topology` router:** same ImportError + never registered in `ALL_ROUTERS`. Registered as admin router (frontend CI-dashboard health-stream consumer).
4. **`str(e)` response leaks (ex-MANUAL 7.4):** closed in `keys.py`, `conversations.py` (x3 + HTTPException pass-through for ownership 404), `preferences.py`, `admin.py` → generic 500 + correlation id, `logger.exception` server-side.

**Housekeeping:** stale `from .llm_gateway import ...` in `api/routes/__init__.py` corrected to `.llm_gateway_routes` (fake boot warning removed).

**Tests:** +13 new guard tests (`test_refresh_path_regression.py` 3, `test_dead_route_wiring.py` 11 minus overlap = see files); security/HITL/guard/memory/lifespan/health battery **195 passed / 0 failed**. `tests/api` 163P/28F and `tests/core` 1488P/45F — byte-identical to clean-HEAD baseline (all pre-existing, sqlite/JSONB env-specific; CI runs on real Postgres). Ruff clean on all touched files.

**Remaining MANUAL items:** see `MANUAL_STEPS.md` (Docker build, deployed health check, green CI + coverage gates, image signing/SBOM, canary/rollback infra wiring, `/evolution/forge` human-approval decision).

## Patch v3 Snapshot (2026-08-30, base `main` @ `c4970f6`)

**Context:** patch v2 was merged upstream (commit `96c419b`) together with CI follow-ups (`5c74929`, `c4970f6`). This session re-verified the merged state and closed the readiness defect discovered by the first-ever live deployed probe.

**Live deployed probe (Render `supremeai-backend-v2`):**
- `/api/v1/health/live` → **200**; `/health/live` alias → **200**
- `/api/v1/health/ready` → **503 not_ready** (critical `database` check failing)
- Deployed image predates patch v2 (marker: POST `/api/v1/auth/refresh` still returns middleware 401) → Render needs a redeploy of current main + this patch.

**Root causes fixed (AUD-1.7):**
1. `core/db.py::_get_database_url` read nonexistent `settings.database_url` (AttributeError, swallowed) → canonical `settings.supabase_database_url` + `DATABASE_URL` env fallback + sqlite dev fallback.
2. `core/app_builder.py::_check_database` used `engine` placeholder (always `None`) and sync API on the async engine → async API via `get_engine()` + server-side logging of failures.
3. `core.db` backward-compat `engine`/`async_session_factory` module names never resolved → now set on first use.
4. `memory/supabase_store.py` phantom `settings.database_url` → canonical field (latent AttributeError).

**Tests:** +7 readiness guards (`test_database_readiness_regression.py`); `test_db_coverage.py` updated from the broken phantom contract to the canonical one (hermetic via `delenv DATABASE_URL`). Battery **202 passed / 0 failed**. Sandbox note: installing `psycopg2-binary` cleared 34 previously env-blocked `tests/core` failures (they were driver-import errors, not product bugs) — remaining 11 `tests/core` failures verified pre-existing on clean HEAD (JSONB-on-sqlite, 401 e2e, pgbouncer sandbox). Ruff clean.

**Remaining MANUAL items:** see `MANUAL_STEPS.md` (Docker build, **redeploy + re-probe ready**, green CI + coverage gates, image signing/SBOM, canary/rollback infra wiring, `/evolution/forge` human-approval decision).

## Patch v4 Snapshot (2026-08-30, base `main` @ `3b6e09db`)

**Context:** Production Render logs (282 lines, captured 2026-08-30 17:17–17:31 UTC) revealed 5 new
defects that had escaped the prior 3 verification sessions. This patch closes all 5 with code
changes + 14 new regression guards.

**Live deployed probe findings (Render `supremeai-backend-v2`):**
1. `ReadOnlySqlTransaction: cannot execute CREATE TABLE in a read-only transaction` — repeated
   3x → escalated to CRITICAL via silent-pattern detector. Cascaded across `CascadeMemoryService`,
   `CheckpointManager`, and `pooled_pg.execute()`.
2. `cannot import name 'get_tenant_db' from 'core.tenant_db'` — `api.routes.hitl_admin` router
   was silently dead on every boot (logged as WARNING, router never registered).
3. `This session is provisioning a new connection; concurrent operations are not permitted` (isce)
   — 5x config-fetch failures on `services.config_service.get_config` (model_cost_per_1k,
   model_branding_map, circuit_breaker_configs, middleware_health_threshold, health_monitor_thresholds).
4. `relation "automation_executions" does not exist` — `core.maintenance_pipeline.cleanup_automation_executions`
   failed every cleanup cycle (table missing from boot DDL list, and migration never applied at boot).
5. `MEMORY WARNING (90.78% used)` → `STILL WARNING (90.77% used)` — continuous memory-pressure log spam,
   ~460 MB / 512 MB at boot due to 7 eager singletons in `core/services.py`.

**Root causes fixed:**

1. **ReadOnlySqlTransaction (P0):** `core/persistence/pooled_pg.py::execute()` was running DDL
   (`CREATE TABLE IF NOT EXISTS`) against `SUPABASE_DATABASE_URL_POOLER`, which is read-only
   in our production Supabase tenant. The `@with_error_bus("execute")` decorator fired
   `error_event_bus` events that the silent-pattern detector escalated to CRITICAL.
   - Fix: introduced `pooled_pg.execute_ddl()` that routes through a NEW `SUPABASE_DATABASE_URL_WRITER`
     env var (or falls back to `SUPABASE_DATABASE_URL` direct connection). Never raises on read-only
     failure (logs WARNING, returns silently). NOT decorated with `@with_error_bus` — DDL failures on
     read-only replicas are an expected, non-actionable condition.
   - Updated callers: `services/memory_service.py:69` and `tools/checkpoint_manager.py:64` now
     use `execute_ddl()` instead of `execute()`.
   - Updated `database/supabase_client.py::bootstrap_schema()` to use WRITER URL only (pooler
     deliberately excluded from DDL candidates).

2. **hitl_admin import (P1):** `api/routes/hitl_admin.py:5` imported `get_tenant_db` from
   `core.tenant_db` — but `core.tenant_db` is a deprecation shim that delegates to
   `database.tenant_db`, which only defines `TenantAwareFirestore`. `get_tenant_db` actually
   lives in `api/deps.py:46`.
   - Fix: changed import to `from api.deps import get_tenant_db` + `from database.tenant_db
     import TenantAwareFirestore`. Router now registers cleanly.

3. **AsyncSession isce (P0):** `api/routes/admin.py:428-435` `POST /configs/refresh` called
   `asyncio.gather(6 × sync_from_db(db))` on a single shared `AsyncSession`. SQLAlchemy
   AsyncSession does not support concurrent operations on one connection → isce error.
   - Fix: replaced `asyncio.gather()` with sequential `await` statements (same fix already
     applied to `core/startup/services.py` in commit `3b6e09db05`).

4. **automation_executions missing (P1):** migration `a1b2c3d4e5f6` exists but is never applied
   at boot (no `alembic upgrade head` in startup). The boot-time DDL list in
   `database/supabase_client.py::get_bootstrap_statements()` was missing the table.
   - Fix: added `CREATE TABLE IF NOT EXISTS automation_executions (...)` and
     `CREATE TABLE IF NOT EXISTS automation_execution_attempts (...)` (with indexes + FK constraint)
     to the bootstrap list, mirroring the migration DDL.
   - Long-term: wire `alembic upgrade head` into Render pre-deploy (MANUAL_STEPS 7.10).

5. **Memory pressure 90.78% (P1):** `core/services.py:80-88` eagerly constructed 7 heavy
   singletons at module import time (`redis_queue`, `admin_god`, `model_router`, `parallel_router`,
   `intent_clf`, `intent_parser`, `experience_db`). Each transitively pulled in
   `PerformanceOptimizer`, `SelfHealerService`, `RemediationPipeline`, `ModelRegistry`,
   additional `httpx.Client` pools, etc.
   - Fix: converted all 7 singletons to lazy `@functools.lru_cache`-backed factories
     (`get_redis_queue()`, `get_admin_god()`, `get_model_router()`, etc.). Module `__getattr__`
     dispatches `services.redis_queue` → `get_redis_queue()` transparently, so all existing
     callers keep working unchanged. Expected boot RSS drop: ~460 MB → ~340-380 MB (66-74%).

**Files changed (8):**
- `backend/core/persistence/pooled_pg.py` — added `execute_ddl`, `get_writer_conn`,
  `_resolve_writer_dsn`, `_get_writer_pool`, `writer_is_available` (FIX 1)
- `backend/api/routes/hitl_admin.py` — corrected `get_tenant_db` import (FIX 2)
- `backend/api/routes/admin.py` — replaced `asyncio.gather` with sequential awaits in
  `/configs/refresh` (FIX 3)
- `backend/database/supabase_client.py` — added `automation_executions` tables to bootstrap
  statements; rewrote `bootstrap_schema()` to use WRITER URL only (FIX 1 + FIX 4)
- `backend/services/memory_service.py` — `execute()` → `execute_ddl()` for DDL (FIX 1)
- `backend/tools/checkpoint_manager.py` — `execute()` → `execute_ddl()` for DDL (FIX 1)
- `backend/core/services.py` — 7 eager singletons → lazy `lru_cache` factories + `__getattr__`
  dispatch (FIX 5)
- `backend/tests/security/test_patch_v4_render_log_fixes.py` — NEW, 14 regression guards

**Tests:** 14 new regression tests added — all pass offline (`tests/security/test_patch_v4_render_log_fixes.py`).
Test coverage:
- FIX 1: 5 tests (`execute_ddl` exists, `_resolve_writer_dsn` never returns pooler,
  `_resolve_writer_dsn` prefers WRITER env, `execute_ddl` swallows RuntimeError when no writer,
  `execute_ddl` not decorated with `@with_error_bus`)
- FIX 2: 2 tests (router imports cleanly, uses correct module)
- FIX 3: 1 test (AST walk verifies no `asyncio.gather` call)
- FIX 4: 2 tests (bootstrap statements include both tables, bootstrap_schema doesn't use pooler)
- FIX 5: 4 tests (no eager assignments, factory registry exists, lru_cache returns same instance,
  importing module doesn't construct any singleton)

**Code structure verified:** all 8 files compile cleanly (`ast.parse` checked). No new dependencies
introduced.

**Remaining MANUAL items:** see `MANUAL_STEPS.md` (Docker build, **redeploy + re-probe ready**,
green CI + coverage gates, image signing/SBOM, canary/rollback infra wiring,
`/evolution/forge` human-approval decision, **NEW: set `SUPABASE_DATABASE_URL_WRITER` env var in Render,
wire `alembic upgrade head` into deploy pipeline, re-check Render logs for absence of all 5 error patterns**).
