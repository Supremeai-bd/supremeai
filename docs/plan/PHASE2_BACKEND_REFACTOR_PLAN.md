# Phase 2 — Backend Modularization Plan (Swarm backend: `backend/core/` -> domain dirs)

> **Status:** PLAN ONLY - **not yet executed.** Awaiting user approval.
>
> **Goal:** relocate loose leaf modules from `backend/core/` into domain sub-packages (`services/`, `database/`, `monitoring/`, `middleware/`, `core/errors/`) **without breaking any running code**, using **shim re-exports** so every existing `from core.llm_router import ...` keeps working.
>
> **Why a NEW plan (not the original `kilo_implementation_plan.md`):** ground-truth inventory showed that plan was written against an *assumed* clean tree. Reality already has **partial, duplicated moves** (see §1). A naive mass-move would silently break 2/3 of the codebase (`error_bus` has **66 importers**). This plan is **shim-first, dedup-aware, gate-checked**.

## 0. Executive summary
1. **Do NOT delete** any `core/*.py`. First **copy impl -> new home**, then add a **shim** at the old path that re-exports from the new home.
2. Run the **import-gate + smoke test** after each batch.
3. **Gate command (always, offline):** `python -c 'import backend.core.<module>'` (no ruff needed - see §6).
4. Batch order: A (low-touch, <=2 importers) -> B (medium) -> C (high) -> D (dedup) -> E (`llm_router` shim).

## 1. Ground-truth inventory (what actually exists)
`backend/core/` is a *package* with subdirs. Target leaf modules still sit at `backend/core/` top-level, and several are **already duplicated** in subdirs:

| Module (`core/`) | Already moved? | Existing new home (DO NOT recreate) | Importers |
|---|---|---|---|
| `llm_router.py` | partially | `backend/services/llm/llm_router.py` exists | 4 |
| `error_bus.py` | duplicated | `backend/core/errors/error_bus.py` exists | **66** |
| `error_handler.py` | duplicated | `backend/core/errors/error_handler.py` exists | 1 |
| `metrics.py` | no | `backend/core/observability/` OR `backend/monitoring/` | 4 |
| `logging.py` | no | `backend/core/observability/` OR `backend/monitoring/` | 6 |
| `cors_policy.py` | no | `backend/core/middleware/cors_policy.py` (new) | 2 |
| `rate_limiter.py` | no | `backend/core/middleware/rate_limiter.py` (new) | 9 |
| `pgbouncer_pool.py` | no | `backend/core/database/pgbouncer_pool.py` (new) | 14 |
| `db_repository.py` | no | `backend/core/database/db_repository.py` (new) | 2 |
| `tenant_db.py` | no | `backend/core/database/tenant_db.py` (new) | 10 |
| `cloud_storage.py` | no | `backend/services/storage/cloud_storage.py` (new) | 1 |
| `gcp_firestore.py` | no | `backend/services/storage/gcp_firestore.py` (new) | 11 |
| `email_service.py` | no | `backend/services/email/email_service.py` (new) | 1 |
| `billing_plans.py` | no | `backend/services/billing/billing_plans.py` (new) | 4 |
| `auth_middleware.py` | **DOES NOT EXIST** | - (original plan assumption WRONG) | - |

**Existing dirs (do NOT recreate):** `core/errors/`, `core/database/` (has `connection_manager.py`), `core/llm/` (has `llm_gateway.py`, `distributed_budget.py`), `core/middleware/` (has `circuit_breaker_middleware.py`), `core/observability/` (has `telemetry.py`, `audit_logger.py`), `backend/services/llm/` (has `llm_router.py`, `providers.py`).

## 2. Refined move list (reality-based)
- **2a `services/`** (app services): `email_service` -> `backend/services/email/`, `billing_plans` -> `backend/services/billing/`, `cloud_storage` + `gcp_firestore` -> `backend/services/storage/`. `llm_router` already in `backend/services/llm/` -> **shim only**.
- **2b `database/`** -> `backend/core/database/`: `db_repository`, `pgbouncer_pool`, `tenant_db`.
- **2c `monitoring/`** -> **reuse `backend/core/observability/`** (avoids over-fragmentation): `metrics`, `logging`.
- **2d `middleware/`** -> `backend/core/middleware/`: `cors_policy`, `rate_limiter`.
- **2e `errors/`** -> `backend/core/errors/`: `error_bus`, `error_handler` (ALREADY there = dedup + shim, not a move).

## 3. Shim strategy (critical, non-negotiable)
For **every** moved module, leave a re-export shim at the OLD path so all importers keep working with zero edits:

```python
# backend/core/error_bus.py   (SHIM - keeps 66 importers working)
from backend.core.errors.error_bus import *  # noqa: F401,F403
# re-export the specific names actually used by importers
from backend.core.errors.error_bus import emit_event, ErrorBus  # noqa: F401
```

**Order (zero breakage window):**
1. **Copy** the real impl to the new home. (old path still the single source of truth)
2. **Add the shim** at the old path, importing from the new home.
3. Run **import-gate + smoke** (§6).
4. **Only if green** -> optionally reconcile duplicates. **Default: KEEP both copies; do NOT delete.**

## 4. Step-by-step execution sequence (batchable)
- **Batch A** (low-touch, <=2 importers): `email_service` (1), `cloud_storage` (1), `db_repository` (2), `error_handler` (1): copy + shim + gate.
- **Batch B** (medium): `cors_policy` (2), `billing_plans` (4), `metrics` (4).
- **Batch C** (high): `rate_limiter` (9), `tenant_db` (10), `gcp_firestore` (11), `pgbouncer_pool` (14), `logging` (6), `error_bus` (66, **LAST**, one impl path only).
- **Batch D** (dedup): `diff core/error_bus.py core/errors/error_bus.py`; pick canonical; shim the other. Same for `error_handler`.
- **Batch E**: `llm_router` already moved -> add shim at `core/llm_router.py` -> `backend/services/llm/llm_router.py`; verify `agents/churn_prophet.py`, `agents/insight_mage.py`, `scripts/migrate_llm_routers.py` still import.

After each batch: `python -c 'import backend.core.<each affected module>'` + `python tests/test_ide_trio_smoke.py` + `python -m compileall backend -q`.
## 5. Risks & rollback
- **`error_bus` (66 importers):** moving it wrong = app won't start. Mitigation: shim-first, gate, keep duplicates. **Do not mass-delete.**
- **Circular imports:** `metrics`/`logging` are foundational (imported by `services/llm/llm_router.py`, `core/llm/distributed_budget.py`). Move them LAST; ensure their new-home shim imports nothing heavy.
- **`gcp_firestore` -> `database/tenant_db.py` cross-imports:** `database/tenant_db.py` already imports `gcp_firestore`; moving `gcp_firestore` to `services/storage/` must not create a `database -> services` cycle. Keep `gcp_firestore` importable from BOTH paths via the shim.
- **`logging.py` name clash:** `core/logging.py` + `core/logging_config.py` + `core/observability/`. Ensure the new home doesn't shadow stdlib `logging` via bare `import logging`. Use explicit absolute paths in shims.
- **Rollback:** every move is copy+shim, never delete. To roll back: `git checkout -- backend/core/<module>.py` (restores original) + delete the new file.

## 6. Verification gates
| Gate | Command | Why |
|------|---------|-----|
| **Import gate (mandatory)** | `python -c 'import backend.core.llm_router'` (each module) | Catches shim breakage; works offline; no ruff. |
| **Smoke** | `python tests/test_ide_trio_smoke.py` | Swarm/Trio pipeline backend still works. |
| **Compile all** | `python -m compileall backend -q` | Catches syntax errors across the tree. |
| **ruff (optional)** | `pip install ruff` then `ruff check backend` | **ruff is NOT installed** in this env. Not a blocker. |
| **Circular-import** | `python -c 'import backend.core; import backend.api.main'` | Package-level import still resolves. |
> **Do not ship Phase 2 without green on import-gate + smoke after every batch.**

## 7. What NOT to do (Objective Pushback)
- Do **not** mass-`mv` all 13 modules at once (the 66 `error_bus` importers break synchronously).
- Do **not** delete `auth_middleware.py` (it does not exist) - drop it from the plan.
- Do **not** create a new `backend/monitoring/` dir; reuse `core/observability/` (avoid over-fragmentation - AGENTS.md rule).
- Do **not** touch the verified Trio/Swarm backend files (`trio_adapters.py`, `trio_pipeline.py`, `ide_trio.py`, `mcp_ide_trio.py`) - out of scope.

## 8. Next actions (awaiting approval)
1. User approves this plan (or requests tweaks).
2. Execute Batch A -> import-gate -> smoke; iterate B-E.
3. Update `docs/IDE_SWAARM_PIPELINE.md` with the final architecture diagram.
4. Commit message: `refactor(core): modularize backend with shims (Phase 2, gate-checked)`.

*This plan lives at `docs/PHASE2_BACKEND_REFACTOR_PLAN.md`; it is updated per batch as execution proceeds.*
