# SupremeAI Audit Patch v2 — 2026-08-30

**Base:** `main` @ `75d1292` ("Fix CI canonical startup error by using aiosqlite async driver for mock DB")
**Supersedes/complements:** `supremeai-audit-patch-20260830` (commit `ce1356f`, already merged in `main`)

## What this patch contains

Full re-check of `AUDIT_MASTER_CHECKLIST.md` against a fresh clone of `main`, plus 4 defect fixes
that survived the earlier remediation pass, 13 new regression-guard tests, and updated audit docs.

### Fixes (code)

| # | Severity | Defect | Fix | File(s) |
|---|----------|--------|-----|---------|
| 1 | **P1** | `POST /api/v1/auth/refresh` blocked by access-token middleware with 401 (path missing from `SUPREMEAI_PUBLIC_PATHS`) → **token refresh unreachable in production**; previously misclassified as sqlite/JSONB env-specific test failure | Path added to default public paths. Endpoint stays fail-closed: it validates the refresh JWT itself (`type=refresh` enforced, invalid → 401, missing → 422). Only the *access-token* middleware gate is bypassed — by design, since the refresh token rides in the JSON body. | `backend/core/config_fields.py` |
| 2 | P1 | Silent dead route `health_aggregation`: registered in `ALL_ROUTERS` but ImportError at boot (`ADMIN_URL_DEFAULT`/`SCRAPER_URL_DEFAULT` missing from `core/deployment_fallback_defaults.py`) → `optional=True` swallowed it every deploy | Both constants added following the existing `BACKEND_URL_DEFAULT` policy: env var first, settings fallback, `""` last — no hardcoded hostnames (CI checker `check_hardcoded_deployment_config.py` respected) | `backend/core/deployment_fallback_defaults.py` |
| 3 | P1 | `service_topology` router doubly dead: same ImportError **and** never registered in `ALL_ROUTERS` (admin service health checker + CI-dashboard WebSocket health-stream) | Registered as admin router (`is_admin: True` → token dependency applied; router already enforces `get_current_admin` + `authenticate_websocket`) | `backend/api/routers.py` |
| 4 | P2 | 5 residual `str(e)` response leaks (`MANUAL_STEPS` 7.4): `keys.py`, `conversations.py` ×3, `preferences.py`, `admin.py` | Generic 500 + `correlation_id` (12-hex uuid) to clients; full detail server-side via `logger.exception`. Bonus: `conversations.add_message` now re-raises `HTTPException` so the ownership **404 is no longer swallowed into a 500** (AUD-2.5 semantics) | `backend/api/routes/{keys,conversations,preferences,admin}.py` |
| 5 | cosmetic | Stale `from .llm_gateway import ...` in `api/routes/__init__.py` (module doesn't exist; real one is `llm_gateway_routes`) → fake "Router import failed" warning every boot | Corrected module path | `backend/api/routes/__init__.py` |

### New regression guards (tests)

| File | Tests | Locks in |
|---|---|---|
| `backend/tests/security/test_refresh_path_regression.py` | 3 | refresh path in public config; middleware classifies it public; endpoint still fails closed on bad refresh token |
| `backend/tests/security/test_dead_route_wiring.py` | 8 | fallback-default exports; no hardcoded hostnames; `health_aggregation` + `service_topology` import; clean `api.routes` import (no stale warning); both routers registered in `ALL_ROUTERS` |

### Docs updated (in this same patch)

- `audit_reports/supreme-deep-audit-reports/AUDIT_MASTER_CHECKLIST.md` — session-2 header, AUD-2.1/AUD-2.9 evidence, Phase 0.7 note, **Patch v2 Snapshot** section
- `audit_reports/supreme-deep-audit-reports/MANUAL_STEPS.md` — item 7.4 marked ✅ DONE (no longer manual)

## Test evidence (offline sandbox, sqlite)

| Suite | Result |
|---|---|
| security/HITL/guard + memory + lifespan + supervisor-shutdown + api-health + endpoints | **195 passed, 0 failed** (was 150P/1F/21E before patch) |
| `tests/api/` | 163P / 28F / 24S — **byte-identical to clean-HEAD baseline** (all pre-existing, env-specific) |
| `tests/core/` | 1488P / 45F / 56S — **byte-identical to clean-HEAD baseline** |
| ruff on all 10 touched files | **clean** |

Baseline methodology: `git stash -u` → run suite on clean HEAD → compare → `git stash pop`. Failure sets and counts match exactly on both sides.

## How to apply

```bash
git apply --check  supremeai-audit-patch-v2-20260830.patch   # dry-run
git apply          supremeai-audit-patch-v2-20260830.patch
# or with a 3-way merge if the tree moved ahead:
git apply -3       supremeai-audit-patch-v2-20260830.patch
```

Then push a branch and let CI validate (green run closes AUD-1.1 + COV gates — see MANUAL_STEPS #3).

## Manual steps still outstanding

See `audit_reports/supreme-deep-audit-reports/MANUAL_STEPS.md` in the patched tree (also reproduced in `MANUAL_STEPS_REMAINING.md` in this zip). Headlines: Docker image build (0.5/0.9), deployed health probe (0.7), green CI + coverage gates (0.8/COV-1..7), image signing/SBOM (AUD-6.5), canary/rollback infra decisions, `/evolution/forge` HITL decision, frontend token attach (7.7), append-only audit storage (7.5), Firebase-admin retirement plan (7.6), API-key scopes schema (7.8). Item 7.4 is now DONE.
