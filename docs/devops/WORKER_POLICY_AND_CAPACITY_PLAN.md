# Uvicorn Worker Policy & Capacity Plan (AUD-1.2 / AUD-1.3)

> **Status:** Enforced policy. See `backend/main.py` (production branch hard-fails when
> `UVICORN_WORKERS > 1`) and `scripts/ci/check_free_tier_limits.py` (blocks worker > 1 in
> committed env files).

## 1. Current policy: exactly ONE worker in production

The canonical production runtime is the Render free-tier service
`supremeai-backend-v2` (512 MiB memory limit) running the Docker image built from
`backend/Dockerfile` with the entrypoint `python main.py`.

| Setting | Value | Where enforced |
|---|---|---|
| Workers | `1` (hard cap) | `backend/main.py` — `logger.critical` + `sys.exit(1)` if `UVICORN_WORKERS > 1` |
| Reload | `False` in production | `backend/main.py` |
| Health path | `/api/v1/health/live` | Render dashboard health check |
| Memory limit | 512 MiB (Render free tier) | platform; observed peak ≈ 498.5 MiB (~92.8%) |

### Why single-worker is intentional

1. **Memory ceiling.** Each Uvicorn worker is a full Python process importing the entire
   FastAPI app (SQLAlchemy async engines, Redis pools, Playwright-free core, embedding
   clients, LLM gateway). Measured RSS of one worker ≈ 400–500 MiB under load. Two workers
   do not fit in 512 MiB — guaranteed OOM-kill, which Render manifests as the service
   restarting mid-request.
2. **Async concurrency is sufficient.** The backend is fully async (FastAPI + Async
   SQLAlchemy + async Redis + httpx). A single event loop multiplexes I/O-bound LLM/API
   traffic efficiently; CPU-bound work is offloaded (Docker sandbox exec, background tasks).
3. **Shared in-process state.** Several subsystems (semantic cache warmers, tier-8 agents,
   the AutoHealer lifespan loop) assume a single process. Scaling workers without first
   externalizing that state would introduce split-brain bugs.

## 2. When to move beyond one worker (trigger thresholds)

Increase capacity ONLY after ALL of the following are true:

| Trigger | Threshold | Evidence source |
|---|---|---|
| Sustained memory headroom | RSS < 65% of the limit for 7 consecutive days | Render metrics / `system_memory_usage` gauge |
| CPU saturation | p95 event-loop latency > 300 ms or CPU > 80% for > 15 min windows | `/metrics` Prometheus endpoint |
| Concurrency pressure | Frequent 503/queue-time alerts from RateLimiter or uvicorn backlog | Render logs + alert bot |
| Business need | Traffic pattern requires > 1 node (HA), not just throughput | on-call review |

## 3. Required checklist BEFORE raising workers (upgrade path)

1. **Vertical first:** upgrade the Render plan (e.g. 2 GiB) before adding workers.
2. **Externalize single-process state:** session cache (L4), tier-8 agent loops, and the
   AutoHealer must be Redis-backed (verified multi-instance safe) — not in-process memory.
3. **Postgres pool math:** `pool_size * workers + overflow` must stay below the Supabase/
   PgBouncer connection budget (see `backend/core/pgbouncer_pool.py`).
4. **Set via env:** `UVICORN_WORKERS=<n>` in the Render environment (the code reads it),
   then remove the CI guard exception ONLY in `scripts/ci/check_free_tier_limits.py` for
   that specific deployment plan.
5. **Canary:** deploy during low traffic; watch `/api/v1/health/live`, memory gauge, and
   p95 latency for at least 60 minutes before closing the change.
6. **Rollback:** revert `UVICORN_WORKERS=1` and redeploy the previous image if memory
   exceeds 85% of the new limit or error rate rises.

## 4. Related audit items

- AUD-1.2 — worker policy verified as intentional (this document + `main.py` guard).
- AUD-1.3 — this document is the required "when/why to replace" plan.
- 0.9 — baseline: 512 MiB limit; observed ≈ 498.5 MiB peak (~92.8%) during the sampled
  window → **capacity warning stands; do not increase workload on the current plan.**
