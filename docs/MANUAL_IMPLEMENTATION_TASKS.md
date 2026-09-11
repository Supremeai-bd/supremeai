# Manual Implementation Tasks

**Reviewed:** 2026-09-11
**Scope:** Remaining contracts that cannot be completed safely in the current environment

These tasks are intentionally explicit because the current session does not have the repository test tooling, generated gRPC artifacts, integrations, environment variables, or permission to apply operational scripts.

## 1. Verify generated gRPC contract

- **Owner:** Backend/platform maintainers
- **Source:** `backend/tests/core/test_grpc_client.py`
- **Blocked by:** Generated `protos` package and repository test tooling are unavailable in this environment.
- **Manual steps:**
  1. Install backend development dependencies from the canonical project manifest.
  2. Generate or restore the versioned `protos` package from the authoritative `.proto` source.
  3. Run the gRPC client test module.
  4. Confirm request field names and response serialization against the worker service implementation.
  5. Record the command, result, and generated-artifact version in `docs/SKIPPED_TESTS.md`.
- **Done when:** The tests run without module-level skipping and pass against the supported worker contract.

## 2. Resolve task-budget/rate-limit contract

- **Owner:** Backend/platform maintainers
- **Source:** `backend/tools/tenant_rate_limiter.py` and current task-routing implementation.
- **Status:** Repository-only contract coverage added in `backend/tests/tools/test_tenant_rate_limiter_contract.py`. Production wiring at the central task execution boundary remains unverified.
- **Blocked by:** The supported public task-execution integration point and runtime Redis behavior require maintainer verification.
- **Manual steps:**
  1. Identify the canonical budget and rate-limit owner; do not create a parallel limiter.
  2. Define tenant/user scoping, limits, rejection behavior, and audit evidence.
  3. Add deterministic unit tests for allowed, exhausted, reset, and failure paths.
  4. Add integration coverage at the central task execution boundary.
  5. Update `docs/SKIPPED_TESTS.md` with the accepted contract or formal retirement decision.
- **Done when:** A single governed API exists, deterministic tests pass, and rejected work is observable.

## 3. Complete current-tree skipped-test inventory

- **Owner:** Quality/release maintainers
- **Blocked by:** Canonical backend test tooling is unavailable in the current environment.
- **Manual steps:**
  1. Run the repository's canonical backend test command with skip reporting enabled.
  2. Export the complete skip list and classify each item as restore, replace, conditional, or retire.
  3. Assign an owner and acceptance condition to every remaining skip.
  4. Update `docs/SKIPPED_TESTS.md` and `STATUS.md` from the resulting evidence.
- **Done when:** No unexplained skip remains and CI exposes conditional skips in its summary.

## Execution rule

Do not mark any task complete from documentation alone. Each task requires command output or a reviewed implementation diff, plus an updated evidence record.

## Related records

- `docs/SKIPPED_TESTS.md`
- `v0_plans/efficient-process.md`
- `backend/tests/core/test_grpc_client.py`
- `backend/api/routes/task_router.py`

---

_This register is a manual handoff, not a claim that the tasks are complete._
