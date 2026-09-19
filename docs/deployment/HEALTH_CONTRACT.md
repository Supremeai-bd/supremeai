# Canonical Health Endpoint Contract (P0)

> Status: **Active contract** — enforced by `backend/tests/core/test_health_contract.py`
> Owner sign-off requirement: one operational source of truth for health across
> Docker, Render, monitoring, CI smoke tests and docs.

## The contract

| Path                 | Meaning                        | Response (healthy)                          | Used by                                        |
| -------------------- | ------------------------------ | ------------------------------------------- | ---------------------------------------------- |
| `GET /health`        | Aggregate health summary       | `200 {"status": "ok\|healthy\|degraded"}`   | compose scraper probe, humans, root metadata   |
| `GET /health/live`   | Liveness (process is up)       | `200 {"status": "alive", "alive": true}`    | `backend/Dockerfile` HEALTHCHECK, compose core |
| `GET /health/ready`  | Readiness (can serve traffic)  | `200` ready/degraded or `503` not ready     | compose worker, Render dashboard, monitoring   |
| `GET /health/full`   | Detailed per-check breakdown   | `200` with per-check results                | debugging, monitoring detail view              |

## Legacy alias policy

`/api/v1/health`, `/api/v1/health/live`, `/api/v1/health/ready`,
`/api/v1/health/full` remain mounted as a **documented legacy alias** and must
stay byte-equivalent with the canonical responses. New integrations MUST use
the canonical `/health/*` paths. The alias exists so historical Render configs
and older docs/links do not break; it is not the operational source of truth.

## Where each consumer points

| Consumer                        | Path used today        | Contract status |
| ------------------------------- | ---------------------- | --------------- |
| `backend/Dockerfile` HEALTHCHECK| `/health/live`         | canonical ✔     |
| `docker-compose.yml` core       | `/health/live`         | canonical ✔     |
| `docker-compose.yml` worker     | `/health/ready`        | canonical ✔     |
| `docker-compose.yml` scraper    | `/health`              | canonical ✔     |
| `docker-compose.yml` browser    | `/health` (node http)  | canonical ✔     |
| Render dashboard (per service)  | set to `/health/ready` | verify in dashboard |
| Monitoring / alerting           | `/health/ready`        | canonical ✔     |
| Docs / runbooks                 | `/health/*`            | canonical ✔     |

## Change rules

1. Never rename or repurpose `/health`, `/health/live` or `/health/ready` —
   the contract test will fail and probes will mark healthy containers
   unhealthy (Render may roll back the deployment).
2. If a new consumer needs a different health shape, add a new endpoint;
   do not overload the canonical ones.
3. Keep the legacy alias equivalence test green while the alias exists.
4. Liveness must not depend on external services (DB/Redis); readiness may.

## Live verification (2026-09-14)

Probed from this session via agent-browser against
`https://<render-primary-url>`:

```
/health/ready          → {"status":"ready", ...}
/health/live           → {"status":"alive","alive":true, ...}
/api/v1/health/ready   → {"status":"ready", ...}   (legacy alias)
```

## DB degradation policy (P1 — role-aware readiness)

Source of truth: `backend/core/health_policy.py` (`db_failure_readiness`,
`is_critical_db_check`). Both readiness endpoints consume it:

* `GET /health/ready` (canonical) — the `database` check registers
  **critical** for core/monolith roles and **non-critical** for
  worker/scraper/mcp (`core/app_builder.py`), so only the critical subset
  gates readiness.
* `GET /api/v1/ready` (`api/routes/health.py`) — consults
  `db_failure_readiness(role, env, degradation_requested)` when the DB is
  unavailable, producing the same decision from the same module.

### Decision matrix (DB failure)

| Role (SUPREMEAI_SERVICE_ROLE) | ENV             | Readiness on DB failure                                             |
| ----------------------------- | --------------- | -------------------------------------------------------------------- |
| `core` / `monolith` / unset   | production/staging | **503 not ready** — `SUPABASE_ALLOW_DB_DEGRADATION` is IGNORED (fail-closed) |
| `core` / `monolith` / unset   | dev/local/test  | 200 degraded if `SUPABASE_ALLOW_DB_DEGRADATION=true` (dev convenience) |
| `worker` / `scraper` / `mcp`  | any             | 200 **degraded** — role-specific degradation allowed (queue/poll/tool work continues) |

Pre-existing escape hatch unchanged: a production service that booted with
`SUPABASE_ALLOW_DB_DEGRADATION=true` and no pooler URL runs the engine in
degraded REST-only mode (`core/degraded_mode.db_degraded()`) and reports
`persistence_mode: degraded` (200) — that operator choice predates and is
distinct from the role policy above.

### Response fields (additive)

`GET /health/ready` now returns:

```json
{
  "status": "ready | degraded | not_ready",
  "timestamp": "...",
  "role": "core | worker | scraper | mcp",
  "degraded": ["database"]
}
```

* `degraded` lists unhealthy NON-critical checks (e.g. the database check for
  a worker) so a ready-but-degraded service is observable instead of silently
  green. The HTTP code semantics are unchanged: 200 while all critical checks
  are healthy, 503 otherwise.
* `status: degraded` implements the `200 ready/degraded` shape this contract
  already documented.

`GET /api/v1/ready` additionally returns a `readiness_policy` block
(`{"decision": "role-tolerated", "reason": "..."}`) whenever it stays READY
during a DB failure, and `role` in every response. Enforced by
`backend/tests/core/test_db_degradation_readiness.py`.
