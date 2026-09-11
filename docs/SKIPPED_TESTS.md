# Skipped Test and Contract Register

**Reviewed:** 2026-09-11
**Scope:** Repository test annotations and migration-dependent contracts
**Decision:** No integrations, environment variables, database migrations, or operational scripts are applied by this work item.

## Purpose

This file is the reviewable register for tests that are intentionally skipped or conditionally unavailable. A skipped test is not treated as evidence that a capability is healthy. Each entry must have an owner, a reason, and a next decision: restore, replace, or formally retire.

## Findings

The repository test suite was directly inventoried via `poetry run pytest tests/unit/test_api_endpoints.py -v`.
Following the resolution of the Prometheus metrics endpoint contract (`/api/admin/metrics` tested with admin headers), the test module contains 15 passed and 25 skipped tests. There are also environment-dependent skips, including the Celery availability check.

## Current classifications

| Category | Evidence | Owner | Decision / acceptance evidence |
|---|---|---|---|
| Resolved canonical routes | `backend/tests/unit/test_api_endpoints.py::TestHealthEndpoints::test_metrics_endpoint` was updated to test canonical `/api/admin/metrics` with admin headers | Backend maintainers | RESOLVED & PASSING; keep the canonical route test green |
| Removed or relocated API routes | `backend/tests/unit/test_api_endpoints.py` skips agent (9), conversation (5), and pagination (3) endpoints because legacy `/api/v1/agents` CRUD routes were superseded by specialized routers (`agent_tasks.py`, `agents.py`, `agent.py`) | API maintainers | Deferred until the canonical router contract is approved. Acceptance: replace legacy tests with tests for the live routes, or record a retirement decision naming the replacement |
| External-auth delegated behavior | `backend/tests/unit/test_api_endpoints.py` skips duplicate-email, weak-password, and wrong-password cases because validation is delegated to Supabase | Auth maintainer | Keep as integration-contract coverage. Acceptance: deterministic local boundary tests plus a credentialed integration run in the auth test tier |
| Optional worker dependency | `backend/tests/workers/test_celery_app.py` skips when Celery is unavailable | Worker maintainer | Conditional skip is allowed. Acceptance: the worker dependency is installed in the worker CI tier and the job publishes its result; absence must remain visible |
| Historical administrative routes | `backend/tests/unit/test_api_endpoints.py` skips `/api/v1/admin/stats`, `/api/v1/admin/users`, `/api/v1/admin/audit-logs` (admin dashboard uses dedicated `/admin-api` prefix) | Admin/API maintainers | Deferred until route ownership is confirmed. Acceptance: test the canonical `/admin-api` routes or formally retire the legacy expectations |
| Previously reported strategic skips | Historical reports mention cognitive routing, generated gRPC protos, and task budget/rate limiting | Capability owners | Reconciled individually in the decision records below; no historical skip is treated as coverage |

### Skip governance

New permanent skips require all four fields in the test reason and this register: owning area, why the test cannot run, the replacement contract, and the evidence required to remove or retire it. CI must publish the skipped count for full backend runs so a rising skip count is visible even when the test job is green. This register is reviewed whenever a skipped test is added, removed, or converted to an integration test.

## Acceptance rules

1. Every permanent skip must state why the behavior is unavailable and what replaces it.
2. A removed route must not retain tests for its old contract unless the tests are explicitly marked historical.
3. External-service behavior must have a deterministic boundary test that does not require credentials, plus an integration test in the appropriate environment when the behavior is production-critical.
4. Conditional dependency skips must be visible in CI summaries and must not silently reduce required coverage.
5. Strategic capabilities require an explicit owner and a decision record before implementation or retirement.

## Deferred actions

These actions are intentionally deferred because this session does not apply integrations, environment variables, database changes, or scripts:

- Run the complete skip inventory with the repository's canonical test command.
- Verify whether Supabase-backed auth and `ai_memory` prerequisites are available.
- Decide whether removed agent/conversation APIs should be restored, replaced, or retired.
- Implement or formally retire the generated-proto contract after current-tree verification.
- Verify production wiring for the existing tenant quota contract; deterministic repository-only coverage now exists in `backend/tests/tools/test_tenant_rate_limiter_contract.py`.

### Tenant quota decision record (2026-09-11)

The repository already contains a centralized `TenantRateLimiter` with tiered RPM/RPD enforcement and fail-closed Redis error handling. New deterministic tests cover under-limit allowance, RPM exhaustion, admin override, Redis failure, and invalid tiers. This does not claim that the limiter is wired into the central task execution boundary or that runtime Redis behavior has been verified; those remain manual acceptance steps.

### Cognitive-router decision record (2026-09-11)

The full v2.0 decomposition API remains deferred because the current implementation intentionally exposes only `CognitiveRouter.route()`. Rather than allowing the legacy v2.0 suite to stand as a false quality signal, deterministic tests now cover the supported direct, decomposed, budget-aware, and factory contracts in `backend/tests/test_strategic_patches/test_cognitive_router_contract.py`. The legacy v2.0 suite remains skipped until its missing public types and execution engine are implemented or formally retired.

Until the remaining actions are completed, skipped tests remain an explicit verification gap rather than a passing quality signal.

## Manual implementation handoff

The following items could not be safely implemented in this environment and are tracked with owners, blockers, manual steps, and acceptance conditions in `docs/MANUAL_IMPLEMENTATION_TASKS.md`:

- generated gRPC artifact restoration and worker-contract verification;
- task-budget/rate-limit contract discovery and implementation;
- complete current-tree skipped-test inventory.

This handoff is not a completion claim. Each item requires runtime evidence or a reviewed implementation diff before it is removed from the deferred register.

## Related records

- `CHECKPOINT.md`
- `docs/architecture/PROJECT_STATUS_RECONCILIATION_2026-09-11.md`
- `backend/database/migrations/README.md`
- `v0_plans/efficient-process.md`
