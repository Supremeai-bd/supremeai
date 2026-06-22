# SupremeAI 2.0 — Rerun Checklist
## Verification Steps for CI/CD and Local Development

_Status: ACTIVE_
_Last Updated: 2026-06-22_

---

## 1. Environment Bootstrap
- [ ] `cp .env.example .env` (if `.env` is missing)
- [ ] `python scripts/bootstrap_env.py` (syncs missing keys)
- [ ] `cd backend && poetry install`
- [ ] `pnpm install` (frontend)
- [ ] `.env` contains all required keys: `JWT_SECRET`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `SENTRY_DSN`, `SUPABASE_URL`, `SUPABASE_KEY`

## 2. Database / Supabase
- [ ] `github_repos` table exists with columns: `id, repo_name, owner, description, language, category, priority, status, metadata, added_date, last_updated`
- [ ] `tools_registry` table exists
- [ ] `user_preferences` table exists
- [ ] `feature_flags` table exists
- [ ] `usage_metrics` table exists with `date, total_requests, total_tokens, total_cost, unique_users, avg_latency_ms, error_rate`
- [ ] Indexes created: `idx_repos_category`, `idx_repos_priority`, `idx_repos_status`

## 3. Backend Verification
- [ ] `poetry run uvicorn core.app:app --reload` starts without import errors
- [ ] OpenAPI docs available at `/docs` (when `debug=True` or `docs_auth_enabled=True`)
- [ ] `GET /health` returns 200
- [ ] `GET /api/v1/repos` returns data (or 503 if Supabase not configured)
- [ ] `GET /api/v1/tools` returns data
- [ ] `GET /api/v1/preferences` returns defaults
- [ ] `GET /api/v1/metrics/usage` returns items
- [ ] `POST /api/v1/metrics/usage` persists data

## 4. New Endpoint Smoke Tests
```bash
BASE="http://127.0.0.1:8000"
curl -s "$BASE/health" | jq .
curl -s "$BASE/api/v1/repos" | jq .
curl -s -X POST "$BASE/api/v1/repos" -H "Content-Type: application/json" -d '{"repo_name":"test","owner":"test"}'
curl -s "$BASE/api/v1/tools" | jq .
curl -s "$BASE/api/v1/preferences?user_id=default" | jq .
curl -s "$BASE/api/v1/metrics/usage" | jq .
```

## 5. Lint & Typecheck
- [ ] `poetry run ruff check .` → 0 errors
- [ ] `poetry run mypy core/ brain/ api/ memory/ tools/ storage/` → no errors

## 6. Tests
- [ ] `poetry run pytest backend/tests/` → all pass
- [ ] Coverage >= 90% (`--cov-fail-under=90`)

## 7. Frontend
- [ ] `pnpm turbo run build --filter=supremeai-studio-client` succeeds
- [ ] `pnpm turbo run lint --filter=supremeai-studio-client` succeeds
- [ ] `pnpm turbo run test --filter=supremeai-studio-client` succeeds

## 8. Docker
- [ ] `docker-compose -f infrastructure/docker/docker-compose.yml build` succeeds
- [ ] `docker-compose -f infrastructure/docker/docker-compose.yml up -d` brings up all services
- [ ] `docker ps` shows expected containers

## 9. CI/CD
- [ ] Push to `main` triggers `.github/workflows/monorepo_ci_cd.yml`
- [ ] All jobs pass: `detect-changes`, `backend-test`, `studio-build`, `deploy-backend`, `deploy-frontend`
- [ ] Discord notification sent on success/failure

## 10. Performance (optional)
- [ ] `python scripts/benchmark/perf_benchmark.py --url http://127.0.0.1:8000 --requests 100`
- [ ] P95 latency < 500 ms for `/health`
- [ ] P95 latency < 2s for `/api/v1/repos`

---

_Next Review: 2026-07-22_
