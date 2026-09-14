# Operational Contracts — Single Source of Truth

> Branch: `final-test/ops-smoke-and-runbooks` (production contract closure follow-up), 2026-09-14.
> This file is the **single source of truth** for the runtime/deployment contracts
> described here, reconciled against the merged P0/P1 hardening on `main`
> (PR #293). If code and this doc disagree, fix the code or update this doc in
> the same PR — never let them drift silently.
>
> Related (canonical on main): `docs/deployment/HEALTH_CONTRACT.md`,
> `docs/deployment/RATE_LIMITING.md`, `docs/deployment/ENV_EVIDENCE_MATRIX.md`,
> `docs/operations/SLO_AND_ALERTS.md`, `docs/operations/BACKUP_RESTORE_AND_ROLLBACK.md`.

---

## 1. Canonical Health Contract

**Rule.** The canonical health surface is:

| Endpoint | Meaning | Response |
|---|---|---|
| `GET /health` (and `/health/full`) | Full health — runs **all** registered checks, per-check latency/errors | `200` healthy / `503` degraded or unhealthy |
| `GET /health/live` | Liveness — is the process alive? (k8s restarts on failure) | `200` alive / `503` dead |
| `GET /health/ready` | Readiness — all **critical** checks pass; safe to receive traffic | `200` ready / `503` not_ready |

`/api/v1/health/*` remains mounted **only as a legacy alias** (same router).
All operational configuration must point at `/health/*`. New tooling must never
use `/api/v1/health/*` — and nothing anywhere may use `/api/v1/admin/health/*`
(that router prefix never existed in the health router; the k8s probes pointed
there and probed a 404 — fixed in this branch).

**Where enforced.**

| Consumer | Path used | Location |
|---|---|---|
| Router mounting (canonical + legacy alias) | — | `backend/core/app_builder.py` (CANONICAL HEALTH CONTRACT block) |
| Probe implementations | — | `backend/core/health_routes.py` (`""`, `/full`, `/ready`, `/live`) |
| Docker HEALTHCHECK | `/health/live` | `backend/Dockerfile` |
| k8s liveness / readiness / startup probes | `/health/live`, `/health/ready`, `/health/ready` | `infrastructure/kubernetes/namespace.yaml` (**fixed in this branch** — previously `/api/v1/admin/health/*` 404s) |
| Keep-alive pinger | `/health/live` | `.github/workflows/keepalive.yml` (**fixed in this branch** — previously legacy `/api/v1/health/live`) |
| Frontend service-health probes | `/api/v1/health/live` (legacy alias, functional) | `frontend/src/utils/api.ts` — migrate to `/health/live` next time frontend touches this file |

**Env vars.** None (contract is path-level). `PORT` selects the listen port (default 8080).

**How to verify.**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://<backend>/health          # 200 or 503 (full)
curl -s -o /dev/null -w "%{http_code}\n" https://<backend>/health/live     # 200
curl -s -o /dev/null -w "%{http_code}\n" https://<backend>/health/ready    # 200
```

A `404` on any of the three means the deployment is running a stale image — redeploy.

---

## 2. API Docs Exposure Policy (P0)

**Rule.** `/docs`, `/redoc` and the OpenAPI schema are **DISABLED by default in
staging/production**. They are:

- enabled by default in local dev only;
- opt-in outside local via `SUPREMEAI_DOCS_ENABLED=true`;
- `SUPREMEAI_DOCS_PASSWORD` must be **non-empty at boot in staging/production
  regardless** of opt-in (boot fails fast otherwise), and must be **≥ 12
  characters** and **not the public dev fallback `dev_password_only`** when
  docs are opted in — no auto-generation path exists anymore (it was removed:
  it silently defeated the fail-fast check);
- when enabled in a non-local env, docs are protected by HTTP Basic auth
  (`SUPREMEAI_DOCS_USERNAME` / `SUPREMEAI_DOCS_PASSWORD`).

**Where enforced.**

- `backend/core/config_fields.py` — real `docs_enabled` (tri-state `None` /
  bool) / `docs_auth_enabled` / `docs_username` / `docs_password` fields +
  `docs_password_ok` / `effective_docs_enabled` properties.
- `backend/core/config_validation.py` — `validate_docs_password` (no
  auto-generate; empty passes through as empty) and `validate_all` (fail-fast
  on missing password in staging/production; fail-fast on weak/dev-fallback
  password when opted in).
- `backend/core/middleware/docs_auth.py` — `DocsAuthMiddleware` issues the
  Basic-auth challenge (401 + `WWW-Authenticate`) for `/docs`, `/redoc`,
  `/openapi.json` (incl. the `/api/v1/openapi.json` mount).
- `backend/core/app_builder.py` — mounts docs only when the policy allows.

**Env vars.**

| Variable | Effect |
|---|---|
| `SUPREMEAI_DOCS_ENABLED` | tri-state: unset → on in local, **off** in staging/production; `true` opts in (still Basic-auth gated + strong password required); `false` off everywhere |
| `SUPREMEAI_DOCS_USERNAME` | Basic-auth user (default `admin`) |
| `SUPREMEAI_DOCS_PASSWORD` | **required** in staging/production boot; ≥ 12 chars and never `dev_password_only` when opted in |

Note: `docs_auth_enabled` is a plain field (default `true`) with **no env
alias** — there is no supported way to disable docs auth via environment.

**How to verify.**

```bash
# Docs disabled (default in prod): expect 404
curl -s -o /dev/null -w "%{http_code}\n" https://<backend>/docs
curl -s -o /dev/null -w "%{http_code}\n" https://<backend>/api/v1/openapi.json

# Docs explicitly enabled: expect 401 without credentials, 200 with
curl -s -o /dev/null -w "%{http_code}\n" -u "$SUPREMEAI_DOCS_USERNAME:$SUPREMEAI_DOCS_PASSWORD" https://<backend>/docs
```

CI/pytest contexts are exempt from the middleware (keeps test suites deterministic).

---

## 3. Admin Secret Contract (`/internal/*`)

> ⚠ **Enforcement status:** the code side of this contract lands with the
> `final-test/admin-secret-failclosed` branch (PR). On `main` today,
> `backend/api/routes/internal.py` still falls back to `docs_password` — and
> since `supremeai_admin_secret` does not exist as a config field there, the
> effective admin secret is the public dev default `dev_password_only`.
> Treat that hole as open until that PR merges.

**Rule.** Automation calling `/internal/*` endpoints (e.g.
`POST /internal/run-daily-evolution`) must authenticate with the **dedicated**
`SUPREMEAI_ADMIN_SECRET` via the `X-Admin-Secret` header. The `docs_password`
fallback is **removed** — the publicly-known `dev_password_only` default can
never again act as an admin key.

Behavior (after the fix lands):

- `SUPREMEAI_ADMIN_SECRET` unset on server → `500` ("Admin secret not
  configured on server.") — fail-closed, even if the caller sends
  `dev_password_only`;
- wrong secret → `403 Forbidden`;
- comparison is constant-time (`secrets.compare_digest`);
- boot in staging/production **fails fast** unless the secret is set,
  ≥ 12 characters, not a public fallback, and not equal to
  `SUPREMEAI_DOCS_PASSWORD` (no secret reuse across gates).

**Where enforced.**

- `backend/api/routes/internal.py` — `_require_admin()` / `_resolve_admin_secret()`.
- `backend/core/config_fields.py` — `supremeai_admin_secret` field + `admin_secret_ok`.
- `backend/core/config_validation.py` — `validate_all` fail-fast for weak/missing secret.

**Env vars.** `SUPREMEAI_ADMIN_SECRET` (long random string; store in Infisical + Render).

**How to verify.**

```bash
# Expect 403 (or 500 if unset server-side — also actionable):
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://<backend>/internal/run-daily-evolution \
  -H "X-Admin-Secret: wrong-value" -H "Content-Type: application/json" -d '{}'
# The old bypass must be dead — expect 500/403, never 200:
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://<backend>/internal/run-daily-evolution \
  -H "X-Admin-Secret: dev_password_only" -H "Content-Type: application/json" -d '{}'
```

---

## 4. DB Degradation Policy (P1)

**Rule.** Database failure policy is **role-based**; the single source of truth
is `backend/core/health_policy.py::db_failure_readiness`:

| Service role (`SUPREMEAI_SERVICE_ROLE`) | DB failure ⇒ readiness |
|---|---|
| `core` / unset | production/staging: **NOT READY — always.** `SUPABASE_ALLOW_DB_DEGRADATION=true` is *ignored* (fail-closed, reason logged). local/dev: degradation **allowed** when the flag is set. |
| `worker` / `scraper` / `mcp` | May be ready without DB (role-specific degradation; the flag is honored — DB check registered non-critical). |

The core API must never serve traffic without its database in
production/staging. The escape hatch exists only for roles whose function is
not DB-backed (and for local dev).

**Where enforced.**

- `backend/core/health_policy.py` — `CORE_ROLES`, `DEGRADED_ROLES`,
  `db_failure_readiness()`, `is_critical_db_check()`.
- `backend/core/app_builder.py` — readiness DB check consumes the policy and
  registers the check's criticality per role.
- `backend/database/session.py` + `backend/core/degraded_mode.py` — engine-level
  degradation and SQLite-fallback gates (`sqlite_fallback_allowed()` is
  fail-closed in production; per-feature CRITICAL warning fires once).

**Env vars.**

| Variable | Effect |
|---|---|
| `SUPREMEAI_SERVICE_ROLE` | `core` (default) or `worker` / `scraper` / `mcp` |
| `SUPABASE_ALLOW_DB_DEGRADATION` | `true` accepts persistence-less operation — **worker/scraper/mcp in any env; core roles in local dev only** |

**How to verify.**

```bash
# On the core node, stop/block the DB (or point DATABASE_URL at a dead host) and redeploy:
curl -s https://<backend>/health/ready     # expect 503 NOT_READY, never 200
curl -s https://<backend>/health           # expect "database" check unhealthy, critical=true
```

Regression tests on main: `backend/tests/core/test_db_degradation_policy.py`
(and the session/degraded-mode regression suites).

---

## 5. Rate Limit Authority (P1)

**Rule.** The **Redis-backed** limiter is the authoritative multi-instance rate
limiter (`backend/core/rate_limit.py`, driven through
`RequestValidationMiddleware` via the centralized redis manager) — tiered
sliding window:

| Tier | Limit |
|---|---|
| Anonymous | 10 req/min |
| Authenticated | 60 req/min |
| Premium | 300 req/min |
| Admin | 1000 req/min |

(+ endpoint overrides in the middleware's `SIMPLE_RATE_LIMITS`.)

The in-memory request log in `RequestValidationMiddleware` is a **per-process
EMERGENCY fallback only** — with 2+ instances the aggregate limit becomes
per-instance and must not be relied upon for cross-instance correctness. When
it engages, a WARNING is logged (visible in Render logs / Loki).

**Known gap (P1-3, open):** the middleware's hard limits remain **hardcoded
class constants** on `main` — `MAX_BODY_SIZE = 10 MB`, `MAX_QUERY_LENGTH =
2048`, `MAX_HEADER_SIZE = 8192`, fallback `RATE_LIMIT = 100`. There are **no**
`SECURITY_MAX_BODY_BYTES` / `SECURITY_MAX_QUERY_LENGTH` /
`SECURITY_MAX_HEADER_SIZE` / `SECURITY_FALLBACK_RATE_LIMIT` /
`SECURITY_FALLBACK_RATE_WINDOW` env vars on `main` (older drafts of this doc
listed them — they belong to an unmerged parallel branch). Moving these to
env/config is the remaining P1-3 item. `RATE_LIMIT_ENABLED=false` is the only
supported env switch today (disables the in-memory fallback limiter; tests).

**Where enforced.**

- `backend/core/rate_limit.py` — `RateLimiter` (Redis sliding window,
  check-then-add so rejected requests never refill the window; bounded
  in-memory fallback cache).
- `backend/core/middleware/security.py` — `RequestValidationMiddleware`
  (Redis-authoritative check, emergency fallback, body/query/header limits).
- `docs/deployment/RATE_LIMITING.md` — deployment-facing write-up.

**How to verify.**

```bash
# Functional check: hammer one endpoint past the applicable limit:
for i in $(seq 1 120); do curl -s -o /dev/null -w "%{http_code} " https://<backend>/api/v1/<endpoint>; done
# Expect 429s once the limit is crossed; X-RateLimit-* headers present.
```

Multi-instance proof: with 2 replicas behind one LB, the Redis limiter's
`X-RateLimit-Limit`/`Remaining` must be consistent across instances (fallback
would show per-instance counters).

---

## 6. Frontend Build Contract (P0)

**Rule.** A production frontend build **must not** ship without real backend
URLs. Vite inlines `VITE_*` at build time; a bundle built with a missing/
localhost backend URL silently ships in "viewer/degraded mode".

`main` enforces this **post-build, on the artifact**:
`scripts/ci/verify_frontend_build_contract.py` runs in CI against the built
`frontend/dist` and **fails the build** when:

1. `dist/build-info.json` is missing (the production build must run the
   vendored plugin that writes it — see `frontend/vite.config.ts`);
2. `userBackendUrl` / `adminBackendUrl` are empty (viewer-mode default
   forbidden; override only with `--viewer-mode-allowed`);
3. a URL is plain `http` (unless `--allow-insecure`);
4. any resolved URL points at a loopback host (`localhost`, `127.0.0.1`,
   `0.0.0.0`, `[::1]`);
5. the bundle leaks the Docker-default dev backend URL string (`http://localhost:8080`)
   or any `http://localhost:<port>` backend URL.

It writes `ci-reports/frontend-build-contract.json` as the evidence artifact —
that report is the "Verified" column of
`docs/deployment/ENV_EVIDENCE_MATRIX.md` for the frontend row.

**Where enforced.**

- `scripts/ci/verify_frontend_build_contract.py` (artifact verifier; exit 1 blocks CI).
- `frontend/vite.config.ts` (writes `build-info.json` at build time).
- `.github/workflows/ci.yml` (runs the verifier after the frontend build).
- Runtime URL resolution mirror: `frontend/src/utils/api.ts` (`getApiBaseUrl()`).

**Env vars (build-time, consumed by Vite).** `VITE_USER_BACKEND`,
`VITE_ADMIN_BACKEND`, `VITE_API_URL`, `VITE_BACKEND_URL`.

**How to verify.**

```bash
# Local: build then verify the artifact exactly like CI does
cd frontend && pnpm run build && cd ..
python3 scripts/ci/verify_frontend_build_contract.py --dist frontend/dist \
  --report ci-reports/frontend-build-contract.json                     # expect exit 0
# Negative control (empty dist):
python3 scripts/ci/verify_frontend_build_contract.py --dist /tmp/empty-dist  # expect exit 1
```

---

## 7. Related session contracts (pointers)

- **Coverage gates (status on `main`)**: the backend gate actually enforced is
  `scripts/ci/coverage_policy.yaml` (`overall.pr` **25**, run by
  `scripts/ci/coverage_quality_gate.py`). `MIN_BACKEND_COVERAGE: 30` is
  declared in `.github/workflows/ci.yml` env but **not yet wired** to any step
  (dead config — wiring is pending). Frontend gate is live via vitest CLI
  thresholds (`MIN_FRONTEND_COVERAGE: 16`). Recommended ladder:
  backend 25 → 30 (wire `MIN_BACKEND_COVERAGE` first) → 40 → 50 → 60;
  frontend 16 → 20 → 25 → 30. Raise one step only after CI stays green for a week.
- **Production smoke test**: `scripts/ci/production_smoke_test.py` (**new in
  this branch**) — health → login → `/auth/me` → chat → logout, with offline
  self-test (`--self-test`) and per-step timing. Env vars: `SMOKE_BASE_URL`,
  `SMOKE_EMAIL`, `SMOKE_PASSWORD`, `SMOKE_SKIP_AUTH`, `SMOKE_TIMEOUT`.
- **Live-env verification**: `docs/deployment/ENV_EVIDENCE_MATRIX.md` (update
  after each deployment change; CI does not enforce it yet).
