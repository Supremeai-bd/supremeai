# Skipped Test and Contract Register

**Reviewed:** 2026-09-11
**Scope:** Repository test annotations and migration-dependent contracts
**Decision:** No integrations, environment variables, database migrations, or operational scripts are applied by this work item.

## Purpose

This file is the reviewable register for tests that are intentionally skipped or conditionally unavailable. A skipped test is not treated as evidence that a capability is healthy. Each entry must have an owner, a reason, and a next decision: restore, replace, or formally retire.

## Findings

The repository contains more skipped tests than the previously reported summary of six. The largest group is in `backend/tests/unit/test_api_endpoints.py`, where tests reference routes that were removed or moved during cleanup. There are also environment-dependent skips, including the Celery availability check.

The previous summary should therefore be treated as stale until a fresh inventory is generated in an environment with the project test tooling available.

## Current classifications

| Category | Evidence | Decision required |
|---|---|---|
| Removed or relocated API routes | `backend/tests/unit/test_api_endpoints.py` skips agent and conversation endpoints because the referenced routes are no longer present | Confirm replacement route contract, rewrite tests, or retire the obsolete tests |
| External-auth delegated behavior | The same test module skips duplicate-email, weak-password, and wrong-password cases because validation is delegated to Supabase | Keep as integration-contract tests only if the external auth system is available; otherwise document the boundary and add deterministic local contract tests |
| Optional worker dependency | `backend/tests/workers/test_celery_app.py` skips when Celery is unavailable | Keep conditional, but verify the worker test tier in CI where the dependency is installed |
| Previously reported strategic skips | Historical reports mention cognitive routing, generated gRPC protos, and task budget/rate limiting | Reconcile against the current tree before implementation; do not assume these remain the only skipped contracts |

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
- Implement or formally retire the historical cognitive-router, generated-proto, and task-budget contracts after current-tree verification.

Until those actions are completed, skipped tests remain an explicit verification gap rather than a passing quality signal.

## Related records

- `CHECKPOINT.md`
- `docs/architecture/PROJECT_STATUS_RECONCILIATION_2026-09-11.md`
- `backend/database/migrations/README.md`
- `v0_plans/efficient-process.md`

