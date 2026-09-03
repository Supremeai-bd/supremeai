# 03 — Getting Started

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.11+ | Backend runtime (`python_version = 3.11` in backend `pyproject.toml`) |
| Poetry | 2.4.1 | Pinned in CI (`poetry.lock` is authoritative) |
| Node.js | 24+ | `engines: node >=24.0.0`, `.nvmrc` = `24` |
| pnpm | 10.15.0+ | `packageManager: pnpm@10.15.0` (Corepack recommended) |
| PostgreSQL | 15/16 | Only if running a local DB instead of Supabase (`pgvector/pgvector:pg15` image in prod compose) |
| Redis | 7 | Optional locally — backend degrades gracefully (`QUEUE_BACKEND_PRIORITY=asyncio,redis,celery,pubsub`) |
| Docker | — | Optional, for the compose-based setup |

## 1. Clone and Install

```bash
git clone https://github.com/SaifulHaqueNiloy/supremeai.git
cd supremeai

# JavaScript workspace (frontend, packages, vscode extension)
corepack enable
pnpm install

# Python backend
cd backend
poetry install --with dev          # add --with browser for Playwright tooling
                                   # add --with ml for torch/sentence-transformers
```

## 2. Configure Environment

Copy the template and fill in what you need (see [04-Configuration](04-configuration.md) for the full reference):

```bash
cp .env.example .env
```

Minimum for a functioning local backend:

```bash
# One LLM provider key is enough — the model router picks whichever is present
GEMINI_API_KEY=...                 # free tier friendly (default model gemini/gemini-2.0-flash)

# Database — either Supabase or local Postgres
DATABASE_URL=postgresql://postgres:supremeai@localhost:5432/supremeai
# SUPABASE_URL=... SUPABASE_KEY=... (enables Supabase client + schema bootstrap)

# Auth secrets (dev; production enforces strength and fail-fast)
JWT_SECRET=dev-secret-change-me-0123456789abcdef
ENCRYPTION_KEY=...                 # generate: python scripts/setup_kms.sh
SUPREMEAI_ADMIN_PASSWORD_HASH=...  # bcrypt hash for the admin login

ENV=local
PORT=8080
```

The settings object (`backend/core/config.py`) reads `.env` from `../.env`, `.env`, `/etc/secrets/.env`, and `/etc/secrets/render.env` (the latter two are Render secret-file mounts). Config validation runs at startup and **exits with code 1** on missing production-critical values — in `ENV=local` you get warnings instead.

## 3. Run the Backend

```bash
# From repo root (turbo script):
pnpm backend:dev
# equivalent to: cd backend && poetry run uvicorn core.app:app --reload

# or from backend/:
poetry run python main.py          # reload enabled only when ENV=local
```

- Base URL: `http://localhost:8080`
- Swagger UI: `http://localhost:8080/docs` · ReDoc: `http://localhost:8080/redoc`
- OpenAPI JSON: `http://localhost:8080/api/v1/openapi.json`
- Liveness: `http://localhost:8080/api/v1/health/live`
- Production hard-enforces **1 uvicorn worker** (512 MB Render constraint) — do not raise `UVICORN_WORKERS` in production.

Optional role-based runs (same image, filtered routers):

```bash
SUPREMEAI_SERVICE_ROLE=scraper poetry run uvicorn services.scraper.main:app --port 8082
SUPREMEAI_SERVICE_ROLE=worker  poetry run python worker_service.py     # Celery supervisor
```

## 4. Run the Frontend

```bash
cd frontend
pnpm dev                           # Vite dev server on http://localhost:5173
```

Dev proxy (from `frontend/vite.config.ts`): `/api`, `/admin-api` and `/auth` are proxied to the resolved backend URL — precedence `VITE_API_URL || VITE_BACKEND_URL || VITE_USER_BACKEND || RENDER_SERVICE_URL`. Missing backend URL **fails the production build** (`process.exit(1)`); for local dev the proxy simply points at `http://localhost:8080` if unset.

Frontend quality loop:

```bash
pnpm test        # vitest run
pnpm typecheck   # tsc --noEmit (strict)
pnpm lint        # eslint
pnpm quality     # all three, strict mode
```

## 5. Run Everything with Docker Compose

`docker-compose.yml` is profile-based:

```bash
# Core API + frontend only (default profile)
docker compose up

# With local Postgres + Redis
docker compose --profile local up

# Scraper microservice
docker compose --profile scraper up

# Everything: core, worker, scraper, mcp control plane, frontend, db, redis
docker compose --profile full up
```

| Service | Port | Notes |
|---------|------|-------|
| `core` | 8080 | Builds `backend/Dockerfile` (multi-stage python:3.11-slim, non-root user, `CMD ["python","main.py"]`) |
| `frontend` | 3000 | nginx serving the Vite build; proxies `/api/`, `/admin-api/`, `/ws` to `http://backend:8080` |
| `db` | 5432 | postgres:16-alpine (`POSTGRES_DB=supremeai`) |
| `redis` | 6379 | redis:7-alpine |
| `worker` | 8081 | `worker_service.py` (profiles `workers`/`full`) |
| `scraper` | 8082 | Playwright/Chromium isolated from the core image |
| `mcp` | 3771 | MCP Control Tower (`infrastructure/mcp-control-plane/Dockerfile`) |

The production compose file (`docker-compose.production.yml`) additionally brings up Prometheus, Grafana, Alertmanager and an OpenTelemetry collector with resource limits and healthchecks.

## 6. Verify the Install

```bash
python scripts/verify_capabilities.py    # capability matrix smoke test (exit 0 = pass)
bash scripts/check_app_boots.sh          # boot smoke check
curl localhost:8080/api/v1/health/live   # {"status":"ok",...}
```

The startup log should show the lifespan sequence: config validation → reliability controller → service init → orchestrator mounted → Supabase bootstrap (if configured) → background agents started.

## 7. Optional Components

- **MCP Control Tower** (`infrastructure/mcp-control-plane/`): TypeScript MCP server exposing render/firebase/supabase/redis/infisical/cloudflare/github adapters. Local dev: see `mcp_config.local.json`; deployed as `supremeai-mcp-tower` via its own `render.yaml`.
- **Backend MCP servers** (`backend/tools/mcp/`): stdio servers — e.g. `python tools/mcp/mcp_server.py` ("supremeai-knowledge-graph", requires Neo4j creds) — for connecting Claude/other MCP clients to SupremeAI capability data.
- **VS Code extension**: open `tools/vscode-extension/`, `pnpm install`, `pnpm compile`, press **F5** to launch an Extension Development Host (details in [11-VS Code Extension](11-vscode-extension.md)).
- **Docs site**: `cd apps/docs && pnpm install && pnpm start` (Docusaurus on :3000).
- **Keep-alive**: `node scripts/keepalive.js` pings `BACKEND_URL/api/v1/health` every 5 minutes if you run the backend on a sleeping free tier.

## Troubleshooting First Steps

| Symptom | Check |
|---------|-------|
| Backend exits immediately at boot | Config validation output — usually missing `JWT_SECRET` / `ENCRYPTION_KEY` / `SUPREMEAI_ADMIN_PASSWORD_HASH` in prod mode |
| `poetry install` fails on lock | Run `poetry check --lock`; CI pins Poetry 2.4.1 and fails on drift |
| Frontend build fails with missing backend URL | Set `VITE_API_URL` — production builds fail fast by design |
| LLM calls fail with `OLLAMA_URL` error | Ollama is fail-fast (no localhost fallback) — unset it or point it at a live server |
| Redis connection errors | Expected on free tier — queue priority falls back to asyncio; set `REDIS_REQUIRED_FOR_PRODUCTION=false` for dev |
| WS dashboard won't connect | Check `VITE_WS_BASE_URL` / scheme swap (https→wss) in `frontend/src/utils/api.ts` |
