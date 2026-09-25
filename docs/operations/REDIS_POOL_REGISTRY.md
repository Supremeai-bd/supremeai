# Redis Pool Registry

**Issue:** #706 (Redis dual-path config drift) · **Created:** 2026-09 · **Owner action required:** credential rotation (see [#696/#697](../security/CREDENTIAL_ROTATION_CHECKLIST.md))

The platform talks to Redis over **two independently-configured access paths with separate
credentials**, plus a **5-deep free-tier federation pool** for quota failover. Because the
credential sets rotate on separate schedules, they drift independently — #706 caught them
mid-drift: the Upstash REST path answered `PING → PONG (14ms)` while the direct TCP path
(`REDIS_URL`) failed authentication. This file is the single source of truth for *which
variable feeds which consumer and what it is for*, so drift like that is diagnosable from
the repo instead of only from a live tower env dump.

> **Never put live credential values in this file.** Names and purposes only.
> Rotation itself is an owner action — start from the repo's credential-rotation
> checklist (`docs/security/CREDENTIAL_ROTATION_CHECKLIST.md`, added by the #696
> repo-side remediation; Upstash ×5 entry), and see #696 (leak) and #697 (history purge).

---

## 1. The two access paths

| Path | Env vars | Client | Who uses it |
|---|---|---|---|
| **Direct TCP** (hot path) | `REDIS_URL` + federation pool (below) | `redis.asyncio` pool via `SecureRedisManager` (`backend/core/cache/redis_manager.py:82`, `:290-297`) | Every hot operation: rate limiting, per-request security state, caching, LLM cache, task queues |
| **Upstash REST** (auxiliary) | `UPSTASH_REDIS_REST_URL` + `UPSTASH_REDIS_REST_TOKEN` | httpx REST client (`backend/core/messaging/upstash_redis_queue.py:18-48`) | Cloud-routing queue, admin auth hit-limiter, MCP-tower `redis.ping`, ops scripts |

### Used-path determination (probe alignment, #706 fix #1)

The backend health probes (`backend/core/health/health_probes.py`) report **both paths
independently** (`redis_direct` / `redis_rest` sub-results) and tie the **overall** redis
status to the **direct TCP path**, because that is the path the app actually uses for hot
operations. Evidence (file:line):

- `backend/core/rate_limit.py:94` — per-request rate limiter → `redis_manager.get_client_async()` (TCP)
- `backend/core/cache_manager.py:50` — `redis.from_url(self.redis_url)` (TCP)
- `backend/core/intelligent_cache.py:146` — `os.environ["REDIS_URL"]` → TCP client
- `backend/core/llm/llm_gateway/litellm_runtime.py:51` — LiteLLM redis cache on `settings.redis_url` (TCP)
- `backend/core/queue/task_queue_enhanced.py:109` — task queue backend (TCP)
- `backend/middleware/anti_hacking.py:55-57` — per-request anti-abuse state via `redis_manager` (TCP)

REST-path consumers (auxiliary, reported informationally — their outage must not flip the
overall redis status):

- `backend/brain/parallel_cloud_router.py:50` — `UpstashRedisQueue()`
- `backend/core/services.py:101-105` — shared `get_redis_queue()` singleton factory (`:213` registry)
- `backend/api/routes/admin_auth.py:91-101` — admin auth hit-counter via REST queue
- `infrastructure/mcp-control-plane/src/adapters/redis/index.ts:14-21` — tower `redis.ping` tool
- Ops scripts: `scripts/monitoring/capacity_planner.py`, `scripts/health/superai_health_check.py`, `scripts/backup/superai_backup_manager.py`

**Demotion rule (#706 fix #2):** if a configured path is *not* used by the app's hot
operations (only probed), it is reported as `unused-configured` / informational instead of
degrading overall health. For the current tree **both paths have real consumers**, so no
demotion fires; the determination is recorded with evidence above and in
`backend/core/health/health_probes.py` (module docstring, `REDIS_HOT_PATH`).

### Tower-side observation (not a backend bug)

The MCP tower's `system_health` row `redis-primary` showed HTTP 401 while the tower's own
`redis_ping` returned PONG. Cause visible in tower code: the `system.health` redis probe
(`infrastructure/mcp-control-plane/src/tools/system.tools.ts:107-121`) extracts the bearer
token from the URL's *embedded userinfo*; when the account registry entry resolves to
`UPSTASH_REDIS_REST_URL` (`account.registry.ts:139` — a bare `https://` host with no
embedded credentials) the probe is sent unauthenticated → 401, even though
`UPSTASH_REDIS_REST_TOKEN` is valid. Tower-side fix is separate from this backend change.

---

## 2. Pool registry

Status legend: **ACTIVE** (consumed by live code) · **ACTIVE (failover)** (consumed lazily
on connect/quota-failover) · **STALE** (declared but no code consumer) ·
**PARTIAL** (consumed, but drifted/duplicated naming).

| Variable | Consuming service(s) | Purpose | Status |
|---|---|---|---|
| `REDIS_URL` | backend API, worker, scraper — all roles, via `SecureRedisManager` (`core/cache/redis_manager.py:82`); plus standalone TCP clients: `core/cache_manager.py:50`, `core/intelligent_cache.py:146`, `core/llm/token_budget.py:205-222`, `core/llm/llm_gateway/litellm_runtime.py:51`, `core/queue/task_queue_enhanced.py:109`, `core/optimization/optimized_redis_client.py:58`, `core/self_evolution/self_evolution_agent.py:133-140`, `core/kaggle_orchestrator.py:322-330`, `backend/tools/agent_tools.py:113` | **Hot path** — cache, rate limiting, task queues, anti-abuse state, LLM cache, provider-switch flag (`active_provider`) | **ACTIVE (hot path)** — creds currently failing auth per #706 → **ROTATION REQUIRED** |
| `REDIS_SECONDARY_URL` | backend only — `SecureRedisManager._FEDERATION_ENV_KEYS` (`core/cache/redis_manager.py:73`) | Quota-exhaustion failover pool #2 (5-account federation, issue #460) — takes over when the primary account exhausts its monthly quota | **ACTIVE (failover)** — live distribution inconsistent (primary exposes 4 pool vars, worker exposes 5) — owner to confirm & normalize |
| `REDIS_TERTIARY_URL` | backend only — `core/cache/redis_manager.py:74` | Failover pool #3 (same mechanism) | **ACTIVE (failover)** — same distribution note |
| `REDIS_QUATERNARY_URL` | backend only — `core/cache/redis_manager.py:75` | Failover pool #4 (same mechanism) | **ACTIVE (failover)** — same distribution note |
| `REDIS_QUINARY_URL` | backend only — `core/cache/redis_manager.py:76` | Failover pool #5 (same mechanism) | **ACTIVE (failover)** — same distribution note |
| `REDIS_FEDERATION_URLS` | backend only — `core/cache/redis_manager.py:136` | Comma-separated bulk form of the failover pool (appended after the named vars, deduped) | **ACTIVE (optional)** |
| `UPSTASH_REDIS_REST_URL` | backend (`core/messaging/upstash_redis_queue.py:18`, consumers in §1); MCP control-plane tower (`infrastructure/mcp-control-plane/render.yaml:23`, `src/lib/env.ts:84`); ops scripts (fallback in `scripts/generate_api_health_report.py:55`, `scripts/health/superai_health_check.py:692`, `scripts/backup/superai_backup_manager.py:560`, `scripts/devops/config/validators.py:464`) | **REST path** — cloud-routing queue, admin auth hit-limiter, tower `redis_ping`, ops health/backup tooling | **ACTIVE** — creds currently VALID per #706 (PONG 14ms) |
| `UPSTASH_REDIS_REST_TOKEN` | same consumers as `UPSTASH_REDIS_REST_URL` | REST bearer auth (`upstash_redis_queue.py:44`) | **ACTIVE** — currently valid per #706 |
| `UPSTASH_REDIS_URL` | backend zero-cost architecture REST client (`core/zero_cost_architecture/zero_cost_patch_phase1_4.py:94,818`); TCP-URL fallback in `backend/tools/agent_tools.py:113`, `core/automation/idempotency.py:102`, `api/routes/session_takeover.py:300` | Zero-cost REST queue/cache client + legacy fallback URL | **PARTIAL** — naming drift vs `UPSTASH_REDIS_REST_*`; purpose undocumented — owner to confirm whether this is the same Upstash account or a separate one |
| `UPSTASH_REDIS_TOKEN` | backend zero-cost REST client auth header (`core/zero_cost_architecture/zero_cost_patch_phase1_4.py:99,818`) | Bearer token for the `UPSTASH_REDIS_URL` REST client | **PARTIAL** — pairs with `UPSTASH_REDIS_URL`; purpose undocumented — owner to confirm |
| `REDIS_PASSWORD` | self-hosted Docker compose stack only (`docker-compose.production.yml:26,135,147,352` — `--requirepass` + `redis_exporter` auth) | Auth for the compose-internal `redis` container (not Upstash — Upstash credentials are embedded in the URLs) | **ACTIVE** (docker-compose deployments only) |
| `REDIS_KEY_PREFIX` | backend zero-cost coordination keys (`core/zero_cost_architecture/zero_cost_patch_phase1_4.py:107`, default `supremeai:zca:`) | Key namespacing for the zero-cost module (other modules hard-code their own prefixes) | **ACTIVE** (zero-cost module only) |
| `REDIS_TOKEN` | none — only inventoried in `backend/core/config_classification.py:1727` | purpose undocumented — owner to confirm (likely legacy; Upstash auth travels in the URL / REST token) | **STALE** — candidate for removal |

### Known drift hazards (documented, intentionally NOT changed here)

- `core/cache_manager.py:253` and `core/intelligent_cache.py:146` fall back to
  `UPSTASH_REDIS_REST_URL` when `REDIS_URL` is unset — but both feed it into a **TCP** redis
  client. An `https://` REST endpoint can never satisfy a TCP client, so this fallback can
  only ever fail. Same pattern: `backend/tools/agent_tools.py:113`,
  `core/automation/idempotency.py:102`, `api/routes/session_takeover.py:300` (with
  `UPSTASH_REDIS_URL`). Left as-is per #706 scope (no client-construction semantics
  changes); flagged for a follow-up cleanup once the owner confirms which accounts exist.
- The frontend once read non-prefixed `UPSTASH_REDIS_REST_URL/TOKEN` client-side
  (documented in `docs/master_docs/FRONTEND-01-DESIGN_SYSTEM_AND_TOKENS.md:172`) — that
  hazard stays banned; these variables are backend/tower/ops-only.

---

## 3. Rotation requirements (owner action — see #696/#697)

All five federation URLs (and the REST credentials) **leaked via the tower** and are on the
rotation checklist (Upstash ×5 entry — `CREDENTIAL_ROTATION_CHECKLIST.md`, #696 remediation).
Notes for whoever rotates:

1. Rotate the **whole pool** — primary *and* `SECONDARY…QUINARY` — not just `REDIS_URL`;
   all five were exposed together.
2. Each Upstash account has **two independent credential forms**: the TCP password embedded
   in `rediss://…` URLs and the **REST token**. The TCP password for the primary account is
   already failing auth (#706) — treat every URL as stale until rotated and verified.
3. After rotation, verify **both paths**: tower `redis_ping` (REST) **and** a backend-boot
   direct-TCP probe (`redis_direct` in the health probes) — the paths authenticate
   separately, so a single green check is not sufficient.
4. While rotating, normalize the per-service env distribution (primary currently exposes 4
   of the 5 pool vars, worker exposes 5) so failover behaves identically on every service.
