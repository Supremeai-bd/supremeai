# 13 — Deployment

## Deployment Topology

| Component | Platform | Identity |
|-----------|----------|----------|
| Backend core | **Render** free tier | `supremeai-primary-node.onrender.com` |
| Worker | Render free tier | `supremeai-worker-node` (`worker_service.py`) |
| Scraper | Render free tier | `supremeai-scraper-node` (Playwright isolated) |
| MCP Control Tower | Render (Blueprint) | `supremeai-mcp-tower` — only service with a `render.yaml` (`infrastructure/mcp-control-plane/render.yaml`) |
| Frontend | **Firebase Hosting** | `https://supremeai-a.web.app` (project `supremeai-a`; `.firebaserc` targets `user`→`supremeai-a`, `admin`→`supremeai-admin`) |
| Keep-alive pinger | **Cloudflare Workers** | `supremeai-worker` (cron `*/8 * * * *`, `infrastructure/wrangler.toml`) |
| Database | **Supabase** | project `xtvkltzmberxekoamala` (Management API used by retention workflow) |
| Secrets | **Infisical** | env slugs `staging`/`prod`, imported at deploy time |

> **Vercel**: no `vercel.json` and no deploy automation exists. Vercel appears only as residual env names, `.env.example` example URLs and a bundle-size limit entry in `check_free_tier_limits.py`. Deploy the frontend via Firebase Hosting, not Vercel.

## CI/CD Pipelines (.github/workflows/)

### `ci.yml` — "CI Pipeline" (main pipeline, 1208 lines)
Triggers: push to `main, develop, feature/*, fix/*`; PRs to `main, develop`; manual dispatch with force flags. Concurrency cancel-in-progress; least-privilege top-level permissions. Env: `NODE_VERSION=24`, `PYTHON_VERSION=3.11`.

**PR jobs:** `changes` (path filter) → `security` (Trivy + secret-in-code) → `registry` (canonical config registry validation) → `build-mcp` (npm ci, build, Trufflehog) → `advanced-checks` (`check_required_secrets.py pre_check` for Infisical/Firebase/GCP/Render/Cloudflare secrets, then ~14 audit scripts from `scripts/advanced_analysis/` + `ci-full-audit.sh` + pip-audit + bandit + trufflehog + gitleaks + actionlint) → `backend-tests` (postgres+redis services; composite action `./.github/actions/setup-backend` — Python 3.11, Poetry 2.4.1 SHA-pinned, lockfile check; ruff; tiered pytest; OpenAPI schema validation; coverage gate; Infisical staging import; canonical startup-command verification) → `integration-test` → `frontend-tests` (`check_single_frontend.py` gate, `tsc --noEmit --strict`, eslint, `vitest run --coverage`, knip) → `build`.

**`main` jobs:** `deploy-frontend` (environment `production`; `generate_firebase_config.py` renders `firebase.template.json` → `firebase.json` with `BACKEND_URL`; `w9jds/firebase-action deploy --only hosting` with `GCP_SA_KEY`) · `publish-core-image` (GHCR `ghcr.io/<repo>/supremeai-core` from `backend/Dockerfile`, **Cosign keyless signing**, Anchore SBOM) · `publish-scraper-image` · `publish-worker-alias` (worker image = core digest re-tagged via `docker buildx imagetools create`) · `deploy-core` / `deploy-worker` / `deploy-scraper` / `deploy-mcp` (Infisical prod import → `scripts/ci/render_trigger_deploy.py` with `RENDER_API_KEY`(+`_2/3/4/_BACKUP`) × service IDs) · `db-schema-check` (live prod DB vs `backend/database/contracts/schema_contract.yaml`) · `deploy-cloudflare-worker` (wrangler) · `notify-failure` (Slack) · `smart-summary`.

### `audit-release.yml` — "Audit & Official Release Center"
Daily deep audit (cron 03:00) · nightly blocking `pip-audit` · weekly self-audit + silent-error scan (Mondays) · scraper CI + health checks (dispatch) · `build-artifacts` matrix on `v*` tags · `create-release` on tags.

### `maintenance.yml` — "Manual Maintenance & Auto-Fix"
Daily cron 02:00 + dispatch with ~15 toggles: 24 h-gap gatekeeper, health check, read-only prod DB schema check, auto-lint-fix, dependency vulnerability scan, codebase docs generation, Cloudflare worker test, performance E2E, CI failure smart summary, outdated-dependency report, auto dependency upgrade, changelog generator, **Upstash FLUSHDB cache purge**, API health check, cost-guard DEFCON, AI DB optimizer, MLOps nightly eval, vulnerability scan, churn analysis, encrypted Telegram backup (`teldrive_backup`).

### `keepalive.yml` — "Free-tier Keep-Alive"
Cron `*/10 * * * *` pinging the four Render services (`/api/v1/health/live` for core & scraper, `/health` for worker & MCP) to defeat Render's ~15-minute idle spin-down. Belt-and-braces: `infrastructure/wrangler.toml` runs a Cloudflare cron `*/8` and notes the "3 separate Render accounts × 750 h free" strategy; `scripts/keepalive.js` is a standalone 5-minute pinger.

### `db-retention.yml` — "DB Retention Prune"
Daily 03:30 — Supabase Management API RPCs `prune_evolution_logs(N)` / `prune_learning_data(N)` (30-day default) to bound free-tier DB growth.

## Docker Images

**`backend/Dockerfile`** (canonical): multi-stage `python:3.11-slim`; builder installs Poetry 2.4.1 and runs `poetry install --only main` (browser/ml groups excluded); runtime creates non-root user `supremeai`, `EXPOSE 8080`, `HEALTHCHECK` → `http://localhost:8080/api/v1/health/live`, `CMD ["python", "main.py"]`.

Other images: `backend/Dockerfile.ci` (torch + whisper for CI), `backend/services/{browser,worker,scraper}/Dockerfile`, `infrastructure/mcp-control-plane/Dockerfile` (node), `frontend/Dockerfile` (node:20-alpine + corepack pnpm builder → `nginx:alpine` with SPA fallback + `/api`, `/admin-api`, `/ws` proxy).

**`docker-compose.yml`** (dev, profile-based): `core` (:8080), `frontend` (:3000), `db` (postgres:16-alpine, profile `local`), `redis` (7-alpine, profile `local`), `worker` (:8081, profile `workers`), `scraper` (:8082, profile `scraper`), `mcp` (:3771, profile `mcp`), everything via `--profile full`.

**`docker-compose.production.yml`**: backend (target `runtime`, healthcheck `/health/live`, limits 2 CPU / 2 GB, Prometheus labels) + `pgvector/pgvector:pg15` (localhost-only, tuned) + redis (password, AOF) + **Prometheus v2.48 + Grafana 10.2.3 + OTel Collector 0.88 + Alertmanager v0.26** with configs from `infrastructure/monitoring/`.

## Deploy Runbook (backend)

```bash
# 1. Pre-deploy gate (9 steps: compile, router imports, boot test, no-requests check,
#    frontend secret scan, migration safety, required secrets, free-tier limits, optional pytest)
bash scripts/pre_deploy_check.sh            # add --quick to skip tests

# 2. Trigger Render deploy for a service
python scripts/deploy/trigger_render_deploy.py    # or scripts/ci/render_trigger_deploy.py (CI path)

# 3. Watch it
python scripts/deploy/check_render.py
python poll_render.py

# 4. Advanced patterns (optional)
python scripts/deploy/blue_green_deploy.py  # blue/green
python scripts/deploy/canary_deploy.py      # canary
python scripts/deploy/disaster_recovery_test.py
python scripts/deploy/infrastructure_as_code_validator.py
```

Frontend deploy: `pnpm deploy:frontend` (= `generate_firebase_config.py && firebase deploy --only hosting`) or push to `main` (auto). Secrets sync: `python scripts/sync_render_secrets.py`, `python scripts/deploy/update_infisical_render.py`.

## Free-Tier Engineering (the defining constraint)

- **Render free instance**: ~512 MB RAM, ~15-min idle sleep. Countermeasures: single-worker enforcement, `LOW_MEMORY_MODE`, `MemoryAwareMiddleware`, four keep-alive mechanisms (above), `worker_service.py` HTTP wrapper so the worker always answers health checks.
- **`scripts/ci/check_free_tier_limits.py`** (pre-commit + nightly): Render ~500 MB deploy context, GitHub Actions 8 GB cache, Vercel 100 MB, Firebase 1 GB, repo 200 MB — auto-fix tiers at 80 % (warn/cleanup) and 95 % (aggressive `git gc`).
- **`scripts/free-tier-health-check.sh`**: exit 0 < 70 % usage, 1 = 70–89 %, 2 ≥ 90 %.
- **`scripts/monitoring/capacity_planner.py`**: "Zero-Cost HA Strategy" — usage estimation, sleep/wake optimization, Telegram alerts, GitHub Step Summary.
- **`scripts/runner/zero_cost_optimizer.sh`**: health-gated docker/pycache prune.
- **Upstash/Redis**: `keepalive` maintenance job can FLUSHDB; `db-retention.yml` bounds Supabase growth.

## Known Stale References (do not follow)

- Root `package.json` `deploy:gcp` → `infrastructure/terraform` (**does not exist**).
- Root `package.json` `docker:build`/`docker:up` → `infrastructure/docker/docker-compose.yml` (**does not exist**; use root compose files).
- Healthcheck path differs: Dockerfile uses `/api/v1/health/live`, production compose overrides to `/health/live`, keep-alive pings both variants — all endpoints exist.
- `supabase-ca.crt` sits at repo root with no code references; the live mechanism is `SUPABASE_DB_CA_CERT`.
- `scripts/security/code-quality.yml` and `dependency-health-check.yml` are workflow-shaped YAML stored outside `.github/workflows/` — not active.
