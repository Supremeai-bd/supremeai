# SupremeAI Audit Patch v3 — 2026-08-30

**Base:** `main` @ `c4970f6` — patch v2 was ALREADY MERGED upstream in `96c419b` (verified), with CI follow-ups `5c74929` and `c4970f6` (both verified harmless), plus Dependabot bumps.

## Re-verification of merged patch v2 (all green)

- All v2 fixes intact after the bot's simplification of `deployment_fallback_defaults.py` (env-driven defaults functionally verified).
- Battery: **195 passed / 0 failed** on clean `c4970f6` before this patch.
- `tests/api` / `tests/core` byte-identical to established baseline.

## NEW: first-ever LIVE deployed-environment probe (Render)

| Endpoint | Result |
|---|---|
| `GET /api/v1/health/live` | **200** ✅ |
| `GET /health/live` (alias) | **200** ✅ |
| `GET /api/v1/health/ready` | **503 not_ready** ❌ — critical `database` check failing |

Checklist item **0.7 is now half-closed with real production evidence**; the ready failure was root-caused to CODE defects (below), not a database outage.

## Fixes (code) — AUD-1.7: readiness probe never worked

| # | Defect | Fix | File |
|---|--------|-----|------|
| 1 | `core/db.py::_get_database_url` read the **nonexistent** `settings.database_url` attribute → AttributeError on every call, silently swallowed → the critical `database` readiness check failed in **every** environment (matches observed prod 503). Canonical field everywhere else is `settings.supabase_database_url` (`SUPABASE_DATABASE_URL_POOLER`). | Canonical field first, direct `DATABASE_URL` env fallback (Render convention), sqlite dev fallback last; scheme upgrade `postgres:// → postgresql+asyncpg://` preserved | `backend/core/db.py` |
| 2 | `app_builder._check_database` imported the module-level `engine` placeholder — **always `None`** (lazy resolution never happened) → `None.connect()`; AND used the **sync** `connect()/execute()` API against the **async (asyncpg) engine**; AND swallowed all exceptions silently | `get_engine()` + `async with engine.connect()` + `await conn.execute(...)` + server-side `logger.exception` (diagnosability) | `backend/core/app_builder.py` |
| 3 | `core.db` documented `engine` / `async_session_factory` module names as "resolved on first use" but never assigned them (backward-compat lie) | Now actually resolved in `get_session_factory()` | `backend/core/db.py` |
| 4 | `memory/supabase_store.py` ended its DSN fallback chain with the same phantom `settings.database_url` (latent AttributeError when env unset) | Canonical `getattr(settings, "supabase_database_url", "")` | `backend/memory/supabase_store.py` |

## Tests

- **+7** readiness guards: `backend/tests/security/test_database_readiness_regression.py`
  (URL resolution: env/env-fallback/sqlite-fallback/canonica-first; lazy engine resolution contract; async-API source guards)
- `backend/tests/core/test_db_coverage.py` — updated from the broken phantom contract to the canonical one, made hermetic (`delenv DATABASE_URL`)
- Battery: **202 passed / 0 failed**
- Sandbox note: installing `psycopg2-binary` cleared 34 previously env-blocked `tests/core` failures (driver-import errors, not product bugs); the remaining 11 were verified pre-existing on clean HEAD (JSONB-on-sqlite, 401 e2e flows, pgbouncer mock-target issue).
- `tests/api`: byte-identical to baseline (28F/163P/24S, all pre-existing).
- ruff clean on all touched files.

## Docs updated (in this same patch)

- `AUDIT_MASTER_CHECKLIST.md` — session-3 header, live probe results in Phase 0.7, **new tracked finding AUD-1.7**, Patch v3 Snapshot
- `MANUAL_STEPS.md` — item #2 updated with probe evidence + post-deploy re-probe instructions

## How to apply

```bash
git apply --check  supremeai-audit-patch-v3-20260830.patch   # dry-run
git apply          supremeai-audit-patch-v3-20260830.patch
# 3-way if the tree moved:
git apply -3       supremeai-audit-patch-v3-20260830.patch
```

## After merge — the 2 actions that close the loop

1. **Redeploy Render** (the currently deployed image predates even patch v2 — verify via `POST /api/v1/auth/refresh` with `{}`: patch-v2+ returns 422, pre-v2 returns "Missing authentication token").
2. **Re-probe**: `live` → 200 (already proven) and `ready` → expect **200** with this patch; if still 503, the check now logs the concrete DB failure server-side (check Render logs / `SUPABASE_DATABASE_URL_POOLER` env). Then mark checklist 0.7 → `[x]`.
