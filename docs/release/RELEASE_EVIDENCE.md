# SupremeAI Release Evidence Record

> Canonical single evidence record for the production readiness release gate (AGENTS.md §2: report evidence, not claims).
> Every field is one of: `PASS`, `FAIL`, `BLOCKED`, `NOT VERIFIED` — with evidence and owner.
> Rules: no claim is PASS without a command/output or artifact link produced in the current environment.

**Created:** 2026-09-14
**Baseline correction:** The plan referenced `origin/main @ d7daadc` as baseline. Verified: `d7daadc` is an ancestor of current HEAD; the release baseline is therefore frozen at the SHA below.

## Gate Output Fields

| Field | Value | Status | Evidence |
|---|---|---|---|
| `release_sha` | `422de8e163d3d9fdfbd104350f05afb39123aecd` (`main`, "V0/fix high blockers (#288)") | PASS | `git rev-parse HEAD`; `git merge-base --is-ancestor d7daadc HEAD` → ancestor confirmed |
| `release_branch` | `main` | PASS | `git branch --show-current` |
| `working_tree` | Clean except untracked `docs/audits/` | PASS | `git status --porcelain` |
| `image_digests` | NOT VERIFIED | BLOCKED | Requires clean-checkout image build (Action Item 2) |
| `runtime_versions` | PARTIAL | NOT VERIFIED | Node ≥24 (`.nvmrc`=24, engines pnpm@10.15.0, packageManager pnpm@10.15.0); Python ^3.11 (`backend/pyproject.toml`); actual toolchain versions on build machine NOT VERIFIED |
| `environment/config_version` | `.env.example` present (canonical contract: `specs/001-dynamic-production-configuration/contracts/config-contract.md`); live config NOT VERIFIED | NOT VERIFIED | — |
| `database_schema_version` | NOT VERIFIED | BLOCKED | Alembic head must be read from `backend/alembic_migrations/` + live DB (Action Item 6) |
| `migration_evidence` | NOT VERIFIED | BLOCKED | Action Item 6 |
| `security_scan_results` | NOT VERIFIED | BLOCKED | Gitleaks config present (`.gitleaks.toml`, `.secrets-allowlist.json`); scan run evidence required (Action Items 5, 9) |
| `backend_test_results` | NOT VERIFIED | BLOCKED | STATUS.md marks Ruff/Poetry checks NOT VERIFIED in current env; must run fresh (Validation) |
| `frontend_test_results` | NOT VERIFIED | BLOCKED | STATUS.md claims PASS (420 tests) but must be reproduced locally (Validation) |
| `mission_results` | NOT VERIFIED | BLOCKED | Action Item 10 |
| `load/capacity_results` | NOT VERIFIED | BLOCKED | Action Item 12 (`scripts/k6/load_test.js`) |
| `backup_restore_result` | NOT VERIFIED | BLOCKED | Action Item 6 |
| `rollback_result` | NOT VERIFIED | BLOCKED | Action Item 11 |
| `monitoring/alert_result` | NOT VERIFIED | BLOCKED | Compose has Prometheus/Grafana/OTEL under `observability` profile; alert firing NOT VERIFIED |
| `known_exceptions_with_expiry` | See Known Open Items below | OPEN | Reconciliation register R4, R5, R8 (partial), R9, R11 |
| `release_owner` | UNASSIGNED | BLOCKED | Human governance required |
| `approvers` | UNASSIGNED | BLOCKED | Human governance required |
| `go_no_go` | **NO-GO** (current state) | — | All gate fields above are BLOCKED/NOT VERIFIED |


## Frozen Baseline Inventory (verified from the working tree)

### Service topology (declared in STATUS.md + manifests; live serving status NOT VERIFIED)

| Component | Declared runtime | Deploy surface | Manifest evidence |
|---|---|---|---|
| Backend (FastAPI, Python 3.11) | `backend/main.py` → uvicorn `core.app:app`, 1 worker enforced in production | Render Docker (`supremeai-primary-node`) + compose `supremeai-backend` (target=runtime, port 8080) | `backend/Dockerfile` (CMD `python main.py`, non-root, HEALTHCHECK `/health/live`); `backend/main.py` (workers>1 → sys.exit(1)) |
| Async worker | Celery/HTTP `backend/worker_service.py` | Render Docker (`supremeai-worker-node`) | STATUS.md; **worker & scraper services appear absent from `docker-compose.production.yml` — drift to verify** |
| Scraper | Headless browser service | Render Docker (`supremeai-scraper-node`) | STATUS.md; not in production compose (same drift) |
| MCP control plane | Node.js MCP server | Render (`supremeai-mcp-tower`) + `infrastructure/mcp-control-plane/` | STATUS.md, infrastructure listing |
| Frontend | React 19 + Vite 7, pnpm workspace | Firebase hosting (`supremeai-a.web.app`, `supremeai-admin.web.app`) + Vercel/Netlify origins in CORS | `.env.example` CORS lists, `firebase.template.json`, `vercel.json` |
| Edge router/keepalive | Cloudflare Worker | `infrastructure/cloudflare_worker.js`, `infrastructure/wrangler.toml`, `keepalive.yml` | infrastructure listing |
| Database | PostgreSQL/Supabase + PgBouncer | Supabase (prod) / `pgvector/pgvector:pg15` (compose) | `.env.example`, compose |
| Cache | Redis/Upstash | Upstash (prod) / `redis` service (compose) | `.env.example` (REDIS_REQUIRED_FOR_PRODUCTION=false — **risk to verify**) |
| Observability | Prometheus v2.48.0, Grafana 10.2.3, OTEL collector 0.88.0 | Compose `observability` profile; `infrastructure/monitoring/` | compose lines 165–241 |

### CI/CD surface (14 workflows verified in `.github/workflows/`)

`ci.yml`, `qa-contract.yml`, `dast-zap.yml`, `audit-release.yml`, `staging-deploy.yml`, `ci-deploy-production.yml`, `ci-docker.yml`, `ci-mcp-build.yml`, `ci-advanced-checks.yml`, `constitution-governance.yml`, `db-retention.yml`, `keepalive.yml`, `maintenance.yml`, `scheduled-deep-audit.yml`, `templates/`.
Recent history shows modularization into reusable workflows + composite actions (`b575540`, `f668ab9`, `fb984a5`, `1bd781e`, `15277c99`, `3ce3958`, range #287/#288) — pipeline behavior must be re-validated against the new orchestration (Action Item 9).

### Lockfiles / reproducibility inputs (existence PASS; determinism run NOT VERIFIED)

- `backend/pyproject.toml` + `backend/poetry.lock` (Poetry 2.4.1 pinned in Dockerfile builder; `--only main --no-root` install)
- `pnpm-lock.yaml` + `frontend/package.json` (pnpm@10.15.0, Node 24)
- `docker-compose.production.yml` — backend build fixed to `./backend` `target: runtime` (AUD/0.5 fix comment); requires `.env.production` + `.env.grafana` env_file files at deploy time (NOT VERIFIED)

## Known Open Items (from `PROJECT_STATUS_RECONCILIATION_2026-09-13.md`)

| ID | Item | Status at baseline |
|---|---|---|
| R4 | `docs/SKIPPED_TESTS.md` missing; 125 skip markers across 53 files | OPEN |
| R5 | CI coverage declarations (30%/16%) vs. stale `COVERAGE_90_PLAN.md` | OPEN |
| R8 | Scout crawler persistence + research wiring | PARTIALLY FIXED |
| R9 | `performance_metrics` dead table (no writers/readers) | OPEN |
| R11 | STATUS.md "100% complete" governance claim contradicted by R4–R9 | OPEN |

External action required (R10): rotate any Render/GitHub tokens that may have appeared in the deleted leaked CI-log file.

## Answers to Plan Open Questions (evidence-based, partial)

1. **Authoritative production target:** Evidence points to **Render (Docker) as the primary production surface** (STATUS.md service matrix, `.env.example` Render URLs/ALLOWED_HOSTS, `scripts/render_build_backend.sh`, `fb984a5` render-deploy composite action, R10 Render tokens) with **Firebase Hosting for the frontend**, Cloudflare Worker as edge/keepalive, Supabase Postgres + Upstash Redis as data services. `infrastructure/kubernetes/`, `vercel.json`, and `docker-compose.production.yml` are alternative/self-hosted surfaces — parity/drift among them is an explicit Action Item 1/2 gap. **Final designation requires owner confirmation.**
2. **Backend entrypoint serving users:** `backend/main.py` → uvicorn `core.app:app`, production locked to 1 worker (512MB constraint). Worker/scraper/MCP topology per STATUS.md Render services — live confirmation pending.
3. **SLOs / cost ceiling / compliance:** No SLO definition found in reviewed docs — NOT VERIFIED; requires owner input before Action Item 8 alerting can be finalized.
4. **Which P0/P1s are fixed on main:** R1, R2, R3, R6, R7, R10 marked FIXED; R4/R5/R9/R11 OPEN; R8 partial. Security-audit P0/P1 runtime evidence still required (Action Items 4–5).

## Next Gates (ordered)

1. Action Item 2 — clean-checkout reproducible build + image digests + SBOM/scan.
2. Action Item 3 — startup/config fail-fast gate + tests.
3. Action Items 4–5 — authz/tenant-isolation + secrets/provider/MCP hardening.
4. Action Items 6–7 — migrations/backups + queue/streaming determinism.
5. Action Items 8–9 — observability/SLO + CI release gates.
6. Action Items 10–12 — mission suite + staging validation + capacity.
7. Action Items 13–14 — runbooks + GO/NO-GO.
