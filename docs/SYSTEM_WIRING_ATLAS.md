# SupremeAI Master System Wiring & Impact Atlas

**Repository:** `Supremeai-bd/supremeai`  
**SSOT Registry:** [`config/service_registry.yaml`](../config/service_registry.yaml)  
**Canonical Name Map:** [`scripts/ci/canonical_name_registry.json`](../scripts/ci/canonical_name_registry.json)  
**Live Auto-Scanner:** [`scripts/ops/wiring_atlas.py`](../scripts/ops/wiring_atlas.py)

> **Security Invariant:** এই document-এ কোনো secret value বা credential কখনোই থাকবে না। শুধু secret/key name, canonical vs alias mapping, consumer file path, port/health contract এবং change blast-radius থাকবে।
>
> **Quick CLI Lookup:**
> - পুরো সিস্টেমের সামারি দেখতে: `python scripts/ops/wiring_atlas.py --summary`
> - যেকোনো Key বা Service পরিবর্তনের প্রভাব (Blast Radius) দেখতে: `python scripts/ops/wiring_atlas.py --impact STEALTH_WEBHOOK_URL`
> - CI/CD Drift Check চালাতে: `python scripts/ops/wiring_atlas.py --check`

---

## ১. Canonical Architecture & Hop-by-Hop Request Flow

```text
User / Client
    │
    ├── supremeai.live / Cloudflare Edge (0 MB RAM)
    │       └── studio/infrastructure/cloudflare-studio-proxy/src/index.js
    │             ├── Static / UI  ────────► Vercel Studio (https://supremeai-studio.vercel.app)
    │             ├── /v1/* Proxy  ────────► Render API Gateway (https://supremeai-api-ulw0.onrender.com)
    │             └── 10m Cron     ────────► /cf-keepwarm (pings all Render /health endpoints)
    │
    ├── Studio UI (React/Vite)
    │       └── studio/src/components/chat/UnifiedChatPanel.tsx
    │
    └── Direct API / Agent Client
            │
            ▼
      SupremeAI API Gateway (Render 512MB Free Tier · ~65MB RAM)
      Service: supremeai-api · Port: 8787 ($PORT) · Health: /healthz, /readyz
      Entrypoint: gateway.service.app:app (gateway/Dockerfile)
            │
            ├── Priority-1 ($0 Stealth Webhook Relay)
            │       └── POST <STEALTH_WEBHOOK_URL>/v1/chat/completions
            │           Header: X-Stealth-Secret: <STEALTH_WEBHOOK_SECRET>
            │           Target: supremeai-browser / supremeai-scraper-node (~30MB RAM, Pure HTTP)
            │                     ├── Tier 1 ($0): Gemini Cookie Session (SUPREMEAI_GEMINI_COOKIES via Infisical)
            │                     ├── Tier 2 ($0): Duck.ai Fast HTTP SSE Stream (6s cap, zero Playwright)
            │                     └── Tier 3 ($0): Zero-Auth OpenAI HTTP Relay (text.pollinations.ai/openai)
            │
            ├── Provider Squad Pool (when enabled)
            │       └── Gemini / Groq / OpenRouter / Anthropic / OpenAI / DeepSeek / Mistral
            │
            ├── Redis / Cache / Rate-Limit
            │       └── Upstash Redis 5-Account Chain (UPSTASH_REDIS_REST_URL + _SECONDARY.._QUINARY)
            │
            ├── Core Decision & Task Runtime
            │       └── supremeai-primary-node-5xso (core/main.py · Port: 8080 · Health: /health, /health/live)
            │       └── supremeai-worker-node (core/services/worker/main.py · Port: 8080 · Health: /health)
            │
            └── Persistent Data & Secrets
                    ├── Supabase Postgres (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY)
                    ├── Qdrant Vector Store (QDRANT_URL + QDRANT_API_KEY)
                    └── Infisical Secret Vault (INFISICAL_CLIENT_ID + INFISICAL_CLIENT_SECRET + INFISICAL_PROJECT_ID)

Separate Governed Control Plane:
  Agent / CLI ──► supremeai-mcp-tower (Port: 3771 / $PORT · Health: /health · MCP: /mcp)
                    └── Zero-credential proxy to GitHub, Render, Supabase, Redis, Cloudflare, Infisical
```

---

## ২. Canonical Service Identity, Port & 512MB Memory Budget Map

সবগুলো সার্ভিসের কেন্দ্রীয় সংজ্ঞা [`config/service_registry.yaml`](../config/service_registry.yaml)-এ সংরক্ষিত আছে:

| Service ID | Render / Platform Name | Source & Entrypoint | Local / Container Port | Health & Readiness | Canonical Service ID & Key Env | 512MB Free-Tier RAM Budget |
|---|---|---|---|---|---|---|
| `api` | `supremeai-api` | `gateway/Dockerfile` → `gateway.service.app:app` | `8787` / `8787` (`$PORT`) | `/healthz`, `/readyz` | `RENDER_API_SERVICE_ID`<br>`RENDER_API_KEY_5` | **~65 MB / 512 MB** |
| `scraper` | `supremeai-browser` (`supremeai-scraper-node`) | `browser/Dockerfile` → `main:app` (`browser/server.py`) | `8788` / `8080` (`$PORT`) | `/health` | `RENDER_SCRAPER_SERVICE_ID`<br>`RENDER_API_KEY_3` | **~30 MB / 512 MB** *(Pure HTTP, No Chromium)* |
| `mcp` | `supremeai-mcp-tower` | `infrastructure/mcp-control-plane/Dockerfile` → `dist/index.js` | `3771` / `3771` (`$PORT`) | `/health`, `/mcp` | `RENDER_MCP_SERVICE_ID`<br>`RENDER_API_KEY_4` | **~90 MB / 512 MB** |
| `core` | `supremeai-primary` (`-5xso`) | `core/Dockerfile` → `python main.py` | `8000` / `8080` (`$PORT`) | `/health`, `/health/live`, `/health/ready` | `RENDER_CORE_SERVICE_ID`<br>`RENDER_API_KEY` (`_1`) | **~140 MB / 512 MB** |
| `worker` | `supremeai-worker` | `core/services/worker/Dockerfile` → `main.py` | `8080` / `8080` (`$PORT`) | `/health` | `RENDER_WORKER_SERVICE_ID`<br>`RENDER_API_KEY_2` | **~80 MB / 512 MB** |
| `brain` | `supremeai-brain` | `core/services/brain/Dockerfile` → `main.py` | `8080` / `8080` (`$PORT`) | `/health` | `RENDER_BRAIN_SERVICE_ID`<br>`RENDER_API_KEY_6` | **~95 MB / 512 MB** |
| `ci-runner` | `supremeai-ci-runner` | Remote CI verification runner | Managed | `/health` | `RENDER_CI_RUNNER_SERVICE_ID`<br>`RENDER_API_KEY_PAYKARI` (`_7`) | **~110 MB / 512 MB** |
| `cloudflare` | `cloudflare-studio-proxy` | `studio/infrastructure/cloudflare-studio-proxy/src/index.js` | Edge | `/cf-health`, `/cf-keepwarm` | `CLOUDFLARE_WORKER_URL`<br>`CLOUDFLARE_API_TOKEN` | **0 MB** *(Serverless Edge)* |
| `frontend` | `supremeai-studio` | `studio/package.json` (Vite / React) | `5173` / `3000` | Vercel Edge | `VERCEL_PROJECT_ID`<br>`VERCEL_TOKEN` | **0 MB** *(Static CDN)* |

---

## ৩. Secret এবং Environment-এর 3-Way Mapping (Canonical vs. Aliases)

### ৩.১ Source-of-Truth Policy

| Key Family | Canonical Source of Truth | Runtime Injection | CI Usage | Repository Policy |
|---|---|---|---|---|
| **Stealth & Web Relay Keys** | Infisical Vault | `supremeai-api` & `supremeai-browser` | Smoke tests only | শুধু নাম থাকবে, কোনো মান নয় |
| **LLM Provider API Keys** | Infisical Vault | `supremeai-api` & `supremeai-primary` | Audit job only | Numbered pool (`_1.._12`) supported |
| **Render Service IDs** | GitHub Variables + `config/service_registry.yaml` | CI planner (`plan_render_deploys.py`) | Workflow matrix | Canonical `RENDER_*_SERVICE_ID`; `*_SVC_ID` fallback-only |
| **Render API Credentials** | GitHub Environment Secret / Infisical | Deploy job & MCP Tower | Per-service least privilege | `RENDER_API_KEY_1..7` mapped per service |
| **DB / Redis / Vector Keys** | Infisical Vault | Core, Gateway & MCP runtime | Staging/smoke gates | 5-account Upstash Redis chain |
| **Studio Public Config** | Vercel / Cloudflare Project Config | Build-time `VITE_*` | Public non-secret only | `VITE_*`-এ কখনো প্রাইভেট সিক্রেট থাকবে না |

### ৩.২ High-Priority Canonical Names & Legacy Alias Resolution

| Capability | Canonical Name (Use This) | Legacy Aliases (Compatibility Only) | Main Consumers |
|---|---|---|---|
| **Core Service ID** | `RENDER_CORE_SERVICE_ID` | `RENDER_CORE_SVC_ID`, `RENDER_PRIMARY_SVC_ID` | `scripts/ci/plan_render_deploys.py`, `infrastructure/mcp-control-plane/src/lib/env.ts` |
| **API Gateway Service ID** | `RENDER_API_SERVICE_ID` | `RENDER_API_SVC_ID`, `RENDER_SVC_ID` | `scripts/ci/plan_render_deploys.py`, `infrastructure/mcp-control-plane/src/lib/env.ts` |
| **Stealth / Scraper Service ID** | `RENDER_SCRAPER_SERVICE_ID` | `RENDER_SCRAPER_SVC_ID`, `RENDER_BROWSER_SERVICE_ID` | `scripts/ci/plan_render_deploys.py`, `infrastructure/mcp-control-plane/src/lib/env.ts` |
| **MCP Tower Service ID** | `RENDER_MCP_SERVICE_ID` | `RENDER_MCP_SVC_ID` | `scripts/ci/plan_render_deploys.py`, `infrastructure/mcp-control-plane/src/lib/env.ts` |
| **Worker Service ID** | `RENDER_WORKER_SERVICE_ID` | `RENDER_WORKER_SVC_ID` | `scripts/ci/plan_render_deploys.py`, `infrastructure/mcp-control-plane/src/lib/env.ts` |
| **Brain Service ID** | `RENDER_BRAIN_SERVICE_ID` | `RENDER_BRAIN_SVC_ID` | `scripts/ci/plan_render_deploys.py`, `infrastructure/mcp-control-plane/src/lib/env.ts` |
| **CI Runner Service ID** | `RENDER_CI_RUNNER_SERVICE_ID` | `RENDER_CI_RUNNER_SVC_ID` | `scripts/ci/plan_render_deploys.py`, `infrastructure/mcp-control-plane/src/lib/env.ts` |
| **Stealth Webhook URL** | `STEALTH_WEBHOOK_URL` | `UPSTREAM_WEBHOOK_URL`, `SUPREMEAI_WEB_RELAY_URL` | `gateway/service/app.py`, `gateway/service/providers/adapters.py`, `gateway/service/telegram_webhook.py` |
| **Stealth Webhook Secret** | `STEALTH_WEBHOOK_SECRET` | `UPSTREAM_WEBHOOK_SECRET` | `gateway/service/app.py`, `browser/server.py` |
| **Gemini Cookie Bundle** | `SUPREMEAI_GEMINI_COOKIES` | `SUPREMEAI_GEMINI_1PSID`, `SUPREMEAI_GEMINI_3PSID` | `browser/server.py` (`fetch_cookies_from_infisical`) |
| **Supabase Service Role Key** | `SUPABASE_SERVICE_ROLE_KEY` | `SUPABASE_SERVICE_KEY`, `SUPABASE_SECRET_KEY` | `core/config.py`, `infrastructure/mcp-control-plane/src/lib/env.ts` |
| **Supabase Anon Key** | `SUPABASE_ANON_KEY` | `SUPABASE_KEY`, `SUPABASE_PUBLISHABLE_KEY` | `core/api/routes/service_topology.py`, `infrastructure/mcp-control-plane/src/lib/env.ts` |

---

## ৪. Webhook, Auth Header ও CORS Contract

| Caller | Receiver | Endpoint | Required Auth / Header | CORS Policy | Failure Contract |
|---|---|---|---|---|---|
| **Studio UI / Edge** | **API Gateway** | `POST /v1/chat/completions` | `X-SupremeAI-Key` (`guest` or signed key) / `Authorization: Bearer` | Exact production origins (`supremeai.live`, `app.supremeai.live`, `supremeai-studio.vercel.app`) | `401/403` on bad key; `502/503` if relay offline |
| **API Gateway** | **Stealth Webhook Relay** (`browser/server.py`) | `POST /v1/chat/completions`<br>`POST /api/chat` | `X-Stealth-Secret: <STEALTH_WEBHOOK_SECRET>` or `Authorization: Bearer` | Server-to-server + explicit `_ALLOWED_BROWSER_ORIGINS` (no `*`) | `401` on invalid secret; cascades Gemini Cookie ➔ Duck.ai ➔ Zero-Auth HTTP |
| **Telegram Servers** | **API Gateway / Core** | `POST /webhook/telegram` | `X-Telegram-Bot-Api-Secret-Token: <TELEGRAM_WEBHOOK_SECRET>` | Server-to-server | `401/403` fail-closed |
| **GitHub Webhooks** | **Core / MCP Tower** | `POST /api/v1/webhooks/github` | `X-Hub-Signature-256` (`GITHUB_WEBHOOK_SECRET`) | Server-to-server | HMAC SHA-256 fail-closed |
| **MCP Client / Agent** | **MCP Control Tower** | `POST /mcp` | `Authorization: Bearer <MCP_API_KEY \| MCP_ADMIN_KEY>` | Role-separated (`admin` ≠ `agent`) | `401/403` + per-IP mutation rate limit |
| **Cloudflare Cron** | **All Render Nodes** | `GET /health`, `/healthz` | `User-Agent: SupremeAI-KeepWarm/1.0` | Public read-only health check | `12s` abort timeout per node |

---

## ৫. CI/CD Changed-Path ➔ Auto-Deploy Dependency Graph

[`scripts/ci/plan_render_deploys.py`](../scripts/ci/plan_render_deploys.py) এবং [`core/config/service_topology.yaml`](../core/config/service_topology.yaml) অনুযায়ী কোন ফোল্ডারে পরিবর্তন করলে কোন সার্ভিস ডিপ্লয় হবে:

| Changed Path Prefix | Target Service | Canonical Service ID Variable | Deploy API Key Variable | Notes |
|---|---|---|---|---|
| `gateway/**`, `config/routing_policy*` | `api` (`supremeai-api`) | `RENDER_API_SERVICE_ID` | `RENDER_API_KEY_5` | Public API Gateway |
| `browser/**` | `scraper` (`supremeai-browser`) | `RENDER_SCRAPER_SERVICE_ID` | `RENDER_API_KEY_3` | Lightweight Stealth Relay |
| `infrastructure/mcp-control-plane/**`, `mcp.json` | `mcp` (`supremeai-mcp-tower`) | `RENDER_MCP_SERVICE_ID` | `RENDER_API_KEY_4` | Does NOT trigger Cloudflare deploy |
| `core/**`, `requirements*`, `pyproject.toml` | `core` & `worker` | `RENDER_CORE_SERVICE_ID`<br>`RENDER_WORKER_SERVICE_ID` | `RENDER_API_KEY` (`_1`)<br>`RENDER_API_KEY_2` | Core runtime & async worker |
| `core/services/brain/**` | `brain` | `RENDER_BRAIN_SERVICE_ID` | `RENDER_API_KEY_6` | Dedicated model/brain service |
| `scripts/ci/**`, `scripts/ops/**` | `ci-runner` | `RENDER_CI_RUNNER_SERVICE_ID` | `RENDER_API_KEY_PAYKARI` | CI offload runner |
| `studio/**` *(excluding cloudflare-studio-proxy)* | `frontend` | `VERCEL_PROJECT_ID` | `VERCEL_TOKEN` | Vercel Studio UI |
| `studio/infrastructure/cloudflare-studio-proxy/**` | `cloudflare` | `CLOUDFLARE_WORKER_URL` | `CLOUDFLARE_API_TOKEN` | Edge Proxy & Keep-Warm Worker |
| `render.yaml`, `config/service_registry.yaml`, `plan_render_deploys.py` | **ALL Render Services** | All 7 IDs | All keys | Topology change widens verification to all services |

---

## ৬. Blast-Radius Runbook ("If X Changes ➔ Update Y")

ভবিষ্যতে কোনো একটি জিনিস পরিবর্তন করলে ঠিক কোথায় কোথায় হাত দিতে হবে তার চেকলিস্ট:

| যদি এটি পরিবর্তন করেন (Change Scenario) | যে ফাইল ও ভল্ট কী-গুলো অবশ্যই আপডেট করতে হবে (Must Update) | কীভাবে ভেরিফাই করবেন (Verification Command) |
|---|---|---|
| **১. Stealth Webhook URL বা Secret বদল** | ১. Infisical Vault: `STEALTH_WEBHOOK_URL`, `STEALTH_WEBHOOK_SECRET`<br>২. Render Dashboard (`supremeai-api` ও `supremeai-browser`)<br>৩. (Optional direct UI relay): `VITE_STEALTH_WEBHOOK_URL` | `python scripts/ops/wiring_atlas.py --impact STEALTH_WEBHOOK_URL`<br>`pytest gateway/tests/test_stealth_webhook.py browser/tests/test_relay_entrypoint.py` |
| **২. নতুন Gemini Cookie আপডেট করা** | ১. Infisical Vault-এ `SUPREMEAI_GEMINI_COOKIES` (JSON বা gzip+base64) আপডেট করুন।<br>২. `supremeai-browser`-এ `INFISICAL_CLIENT_ID`, `INFISICAL_CLIENT_SECRET`, `INFISICAL_PROJECT_ID` সেট আছে কি না নিশ্চিত করুন। | `curl https://supremeai-scraper-node.onrender.com/health` ➔ `"cookies_loaded": true` |
| **৩. কোনো Render Service-এর URL বা পোর্ট বদল** | ১. `config/service_registry.yaml`<br>২. `studio/infrastructure/cloudflare-studio-proxy/src/index.js` (`RENDER_SERVICES`)<br>৩. `render.yaml` ও সার্ভিসের নিজস্ব `Dockerfile`<br>৪. Infisical Vault-এ সংশ্লিষ্ট `RENDER_*_URL` | `python scripts/ops/wiring_atlas.py --check`<br>`pytest tests/security/test_code_review_remediation_guards.py` |
| **৪. নতুন Render Service যোগ বা Service ID বদল** | ১. `config/service_registry.yaml`<br>২. `scripts/ci/plan_render_deploys.py` (`SERVICE_RULES`)<br>৩. `core/config/service_topology.yaml`<br>৪. `.github/workflows/unified-pipeline.yml` (`deploy-and-verify`)<br>৫. GitHub Actions Variables-এ `RENDER_<NAME>_SERVICE_ID` | `python scripts/ops/wiring_atlas.py --check` |
| **৫. নতুন Frontend ডোমেইন বা CORS Origin যোগ** | ১. Infisical / Env: `CORS_ORIGINS`, `BROWSER_CORS_ORIGINS`, `ECOSYSTEM_CORS_ORIGINS`<br>২. `gateway/service/app.py`, `browser/server.py`, `core/security/origin_validator.py` | `pytest tests/security/test_code_review_remediation_guards.py` |
| **৬. নতুন LLM Provider API Key যোগ** | ১. Infisical Vault-এ `<PROVIDER>_API_KEY` (বা `_1.._N`)<br>২. `gateway/service/providers/adapters.py` ও `gateway/service/pool.py`<br>৩. `scripts/ci/canonical_name_registry.json` | `python scripts/ops/wiring_atlas.py --impact <PROVIDER>_API_KEY` |

