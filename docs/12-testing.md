# 12 — Testing

SupremeAI runs a four-layer test estate: backend pytest (376 files), frontend Vitest (72 files), Playwright E2E, and k6 load tests — all wired into CI with tiered coverage gates.

## Backend (pytest)

**Config** (`backend/pyproject.toml [tool.pytest.ini_options]`):

- `testpaths=["tests"]`, `asyncio_mode="auto"`, per-test `timeout=30` (thread method)
- `addopts = -ra -v --tb=short --strict-markers --strict-config --import-mode=importlib --cov=core --cov-report=term-missing/html/xml`
- `filterwarnings = ["error", ...]` — warnings are failures
- Coverage source: `core, api, tools, ws, workers`; **`fail_under = 80`** in `[tool.coverage.report]` (local runs; CI applies its own tiered gates)

**Markers**: `critical` ("fast, merge-blocking"), `important`, `overall`, `hitl`, `integration`, `unit`, `chaos`, `requires_network`, `requires_redis`, `e2e`, `security`, `performance`.

**Fixtures**:

- Repo-root `conftest.py` — puts `backend/` on `sys.path`, sets `RATE_LIMIT_ENABLED=false` before collection, autouse test-env setup (TESTING/ENV=test/sqlite/redis-mock with restore), `mock_redis`, `mock_async_redis`, autouse `mock_external_apis`.
- `backend/tests/conftest.py` — forces `TESTING=true`, `ENV=test`, auth/origin bypasses, deletes cached `core.config*` modules to force reload; provides `app` fixture via httpx `ASGITransport`/`AsyncClient`, async SQLite engine/session fixtures, and CI tier classification (`_CRITICAL_TEST_PARTS`).

**Run commands** (match CI exactly):

```bash
cd backend
# PR gate
poetry run pytest tests/ -m "(critical or important) and not requires_network and not e2e and not chaos" --timeout=30
# main branch gate
poetry run pytest tests/ -m "not requires_network and not e2e and not chaos" --timeout=30
```

Test tree (~30 topic dirs): `api/`, `core/`, `agents/`, `brain/`, `e2e/`, `integration/`, `security/`, `load/`, `llm/`, `rag/`, `orchestration/`, `memory/`, `middleware/`, `database/`, `monitoring/`, `hitl/`, `byoc/`, `p2p_tests/`, …

## Coverage Policy Tiers

`scripts/ci/coverage_policy.yaml` + `scripts/ci/coverage_quality_gate.py` implement multi-tier gates (CI env sets `MIN_BACKEND_COVERAGE=35`, `MIN_FRONTEND_COVERAGE=9` as floors):

| Tier | Threshold | Scope |
|------|-----------|-------|
| `overall pr` | 25 % | Whole repo on PRs |
| `critical pr` | 80 % | `backend/core/llm/**`, `backend/core/orchestration/**`, `backend/core/security/**`, `backend/api/auth/**`, agent/api_keys/billing routes, usage/memory services, queue, checkpoint_manager, parallel_agent_executor, microvm_sandbox |
| `important pr` | 60 % | services/tools/routes |
| `changed` | critical 80 / standard 60 | Changed files |
| `release_changed` | 90 / 75 | Release-bound changes |
| `critical_paths pr` | 95 % | Highest-risk paths |

`scripts/testing/test_runners.py`, `scripts/quality/auto_improve_coverage.py`, `scripts/advanced_analysis/test_coverage_gap_mapper.py` and the plans (`backend/COVERAGE_90_PLAN.md`, `backend/TEST_COVERAGE_PLAN.md`) support raising coverage over time.

## Frontend (Vitest)

`frontend/vitest.config.ts`: jsdom, `globals: true`, setup `src/test/setup.ts`, include `src/**/*.{test,spec}.*`; React/React-DOM aliased to local node_modules (React 19 pin vs monorepo override). Coverage via v8 — reporters text/json/html/lcov, thresholds lines/functions/branches/statements **10 %**, covering components, commandcenter, hooks, store, services, providers, core, i18n.

```bash
cd frontend
pnpm test            # vitest run
pnpm test:watch      # watch mode
pnpm quality         # typecheck:strict + lint:strict + test
```

CI `frontend-tests` job additionally runs `tsc --noEmit --strict`, ESLint, `vitest run --coverage` (thresholds) and **knip** (dead-code detection, config `knip.json`). 72 test files are colocated under `frontend/src/` (stores, services, hooks, commandcenter kit, App).

## E2E (Playwright)

- Root `playwright.config.ts`: `testDir: ./tests/e2e` (dir does not currently exist), `fullyParallel`, CI retries 2 / workers 2, trace+screenshot+video on failure, chromium (+firefox/webkit/mobile via `FULL_E2E`), webServer `pnpm dev` at `http://localhost:3000`, base URL from `E2E_BASE_URL`.
- `playwright-ct.config.ts`: component tests, pattern `**/*.ct.spec.tsx` (none currently present).
- Specs actually present: `frontend/e2e/commandcenter.spec.ts` (AETHEL smoke: KPI tiles, module navigation, OTP modal, WS-degraded state) and `frontend/e2e/multiworkspace.spec.ts` (fleet canvas badges).
- **Known gap**: no `playwright.config.*` inside `frontend/` and no npm `e2e` script; specs default to port 4173 while the root config targets 3000; `multiworkspace.spec.ts` uses `/#/workspace` (hash) though the app uses BrowserRouter. Run them ad-hoc: `npx playwright test frontend/e2e/commandcenter.spec.ts`.

## Load Testing (k6)

`scripts/k6/load_test.js`: stages 20→50→0 VUs (30 s / 1 m / 30 s); thresholds `p(95) < 500 ms` and failure rate < 5 % (relaxed when `CI` env set); targets `SUPREMEAI_URL` hitting `/health`, `/actuator/health`, `POST /task/execute`. Complementary Python tooling: `scripts/benchmark/perf_benchmark.py`, `superai_load_tester.py`, `scripts/testing/performance_benchmark.py`, and the checked-in `supremeai_performance_benchmark.json` baseline.

## Specialized Testing Tools

| Tool | Purpose |
|------|---------|
| `scripts/testing/mutation_testing.py` | Mutation testing |
| `scripts/testing/api_contract_validator.py` + `scripts/ci/verify_api_contract.py` (pre-commit) | API contract drift |
| `scripts/ai/prompt_injection_tester.py` | Prompt-injection red teaming |
| `scripts/testing/log_anomaly_detector.py` | Log anomaly detection |
| `scripts/testing/auto_test_generator.py` + `tools/autonomy/tools/test_synthesizer.py` | Regression-test generation from traces |
| `scripts/security/test_security.py`, `packages/scripts/security_guard.py` (pre-commit `secret-hunter`) | Security tests |
| `scripts/quality/regression_scanner.py`, `check_ollama_test_coverage.py` | Regression & local-LLM coverage |
| `scripts/testenv/setup_test_env.sh` | Reproducible test environment |

## CI Test Flow (recap)

PR: security → registry → advanced checks → `backend-tests` (postgres+redis services, ruff, tiered pytest, OpenAPI validation, coverage gate) → `integration-test` → `frontend-tests` (single-frontend gate, tsc, eslint, vitest+coverage, knip) → build artifact. `main`: adds deploy jobs and post-deploy `db-schema-check`. The `audit-release.yml` workflow adds nightly pip-audit, weekly self-audit + silent-error scan, scraper CI and health checks, and tag-driven release artifacts.
