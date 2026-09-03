# 07 — API Reference

The authoritative machine-readable contract is the checked-in **`backend/openapi.json`** (title *SupremeAI 2.0*): **398 paths** — 198 under `/api`, 96 under `/api/v1`, 54 unprefixed, 38 under `/admin-api`, 7 under `/admin`, 5 under `/health`. Live docs: `/docs` (Swagger) and `/redoc` when the server runs. This page groups the surface by domain with real paths; it is a map, not an exhaustive dump.

## Authentication Model

- **User auth**: JWT bearer tokens from `/api/v1/auth/*` — the React app sends `Authorization: Bearer <token>` plus `X-CSRF-Token` and a device-fingerprint header (`frontend/src/services/apiClient.ts`).
- **Admin auth**: Firebase login (`POST /api/admin/firebase-login`) → OTP/TOTP step-up → admin JWT (`supreme_admin_jwt` client-side); every `/admin-api/*` and `/admin/*` router is registered with `Depends(get_current_user_token)` (`api/routers.py`).
- **API keys**: `APIKeyAuthMiddleware` + `api_key_limiter` for machine clients; WebSocket endpoints authenticate within a strict window (`WS_AUTH_WINDOW_SECONDS`) with attempt caps.
- **Test bypasses** (`ALLOW_TEST_AUTH_BYPASS`, `ALLOW_TEST_ORIGIN_BYPASS`) are hard-disabled in production.

## Health & Meta

| Method & Path | Purpose |
|---|---|
| `GET /` | Welcome payload |
| `GET /health`, `/health/live`, `/health/ready`, `/health/full`, `/health/aggregated` | Liveness/readiness/deep checks (also mounted under `/api/v1/health`) |
| `GET /api/v1/health/live` | **Docker HEALTHCHECK + keep-alive ping target** |
| `GET /metrics` | Prometheus (when `MONITORING_DETAILED`) |
| `GET /api/v1/openapi.json` | OpenAPI schema |
| `GET /health/aggregated` | `health_checker.check_all()` — DB + memory + circuit breakers |
| `GET /admin/free-tier-status` | Free-tier resource posture (from `core/admin_routes.py`) |

## Auth (`api/routes/auth.py`, prefix `/api/v1/auth`)

`POST /login` · `POST /register` · `POST /refresh` · `POST /logout` · `GET /me` · `GET /verify`. Role resolution happens server-side only — the frontend's `authStore` trusts `/api/v1/auth/*` responses, never client-side role guessing.

## Chat, Tasks & Streaming

| Endpoint | Notes |
|---|---|
| `POST /api/chat/completion` | Blocking completion |
| `POST /api/chat/stream` | **Primary chat path** — SSE stream (`data:` chunks, `[DONE]` sentinel); consumed by both `chatService.ts` and `useChat.ts` |
| `WS /ws/chat` | "Neural Engine Stream" websocket with SSE shim `stream_chat_sse` |
| `POST /api/task/execute` · `GET /api/task/stream` | Task execution + SSE task stream |
| `WS /ws/command-center` | Command-center channel (`ws/command_center.py`) |
| `WS /ws/hitl` (+ SSE shim) | Human-in-the-loop approvals |
| `WS /voice` (+ SSE shim) | Voice sessions |
| `WS /agent/terminal-stream` | Agent terminal output |
| `WS /ws/dashboard`, `/ws/session/{id}/takeover`, `/dashboard`, `/health-stream` | Admin/ops realtime |

## Agents & Orchestration

`GET /api/agents/` (list) · `POST /api/agents/research/search|summarize|cite` · `POST /api/v1/agent/execute` · `POST /api/v1/agent/action` · `GET /orchestrator/status` · `POST /orchestrator/tick` (Cloud Scheduler webhook) · swarm/trio pipeline endpoints backing the VS Code extension's `POST {swarmBackendUrl}/api/v1/ide-trio/execute` (Gemini → Kilo → Cline chain).

## Knowledge, Memory & Skills

`POST /api/knowledge/ask|ask-scribe|search|seed` · `POST /api/memory/checkpoint` · `GET /api/memory/conversations` · `POST /unified-memory/long-term/store` · `POST /unified-memory/long-term/query` · `GET /api/skills/catalog`. Backed by pgvector (`ai_memory` table), ChromaDB, and the RAG pipeline (`memory/rag_pipeline.py`).

## Billing & Payments

`GET /api/billing/plans` · `POST /api/billing/checkout` · `GET /api/billing/history` · `POST /api/billing/add-funds` · `POST /api/billing/webhook/stripe` · `POST /api/billing/webhook/sslcommerz` · `POST /payments/checkout|webhook`. Stripe idempotency is enforced (per recent hardening commit); `user_wallets` + `transaction_ledger` tables underpin balances.

## Dev Tooling

`POST /github/connect|discover|implement|push` (GitHub automation) · `/api/ci/*` (+ `CI` webhook receivers) · `POST /tools/image-to-code` · `/api/deep-research/*` · `POST /api/tts/synthesize` · `GET /api/v1/media/generate-upload-url` (R2 pre-signed uploads). Infra webhooks: `n8n_webhooks`, `cdc_webhooks`, `webhooks_ai`.

## BYOC (gated on `ENCRYPTION_KEY`)

`POST /api/byoc/credentials` · `POST /api/byoc/deploy` · `GET /api/byoc/status/{job_id}` — bring-your-own-cloud deploys via `byoc/` (cloud connector, resource manager, container orchestrator), limits in `backend/config/byoc_limits.json`.

## LLM Gateway Admin

`GET /llm-gateway/health` · `GET /llm-gateway/admin/gateway/state` · `POST /llm-gateway/admin/circuit-breaker/reset/{name}` — operational control of the litellm gateway, its cache and breakers.

## Admin API (`/admin-api/*`, 38 paths)

User management (`/users` list/create/delete), backups, costs, feature flags, model router control, swarm control, deploy gate + emergency deploy, health map, audit logs, consent matrix. Consumed by `frontend/src/services/adminService.ts`, `useAdminApi` hooks and the AETHEL Command Center.

Representative panels → endpoints mapping lives in `frontend/src/components/admin/` and `src/commandcenter/data/hooks.ts` (React Query: `useMetrics` 15 s refresh, `useHealthMap` 45 s).

## Tier-S Feature Routes (`api/routes/tier_s_routes.py`)

| Tier | Feature | Router |
|------|---------|--------|
| S1 | Share conversations | `share` |
| S2 | Reasoning steps | `reasoning` |
| S3 | Artifacts | `artifacts` |
| S4 | Chat image upload | `chat-upload` |
| S5 | Slash commands | `slash-commands` |
| S6 | Chat search | `chat-search` |
| S7 | Chat export | `chat-export` |
| S8 | Global memory | `global-memory` |
| S9 | Prompt templates | `prompt-templates` |
| S10 | Branch conversations | `branch-conversations` |
| S11 | Scheduled tasks | `scheduled-tasks` |
| S12 | Deep research | `deep-research` |

## Core Admin Routes (boot-mounted)

From `core/admin_routes.py`: `POST /api/admin/firebase-login`, `GET /admin/free-tier-status`, plus platform ops endpoints. Memory-aware middleware (`core/memory_manager.py`) protects the process under free-tier pressure.

## Cross-Cutting Response & Error Contract

- `ResponseStandardizationMiddleware` normalizes success/error envelopes; the shared `ApiResponse<T>` zod schema in `packages/shared-types/src/conversation.ts` (`{ success, data?, error{code,message,details?}, requestId? }`) mirrors it.
- The global exception handler **includes open circuit-breaker states** in error payloads so clients can see degraded dependencies.
- Idempotency middleware (`IdempotencyMiddleware`) plus the `add_idempotency` migration protect POST replays.
- Rate limiting is Redis-backed with a simplified local fallback (`RATE_LIMIT_USE_SIMPLIFIED` forced off in production).

## Versioning

Routes are grouped under `/api` (current) and `/api/v1` (versioned subset — auth, health, media, telemetry). The registry in `api/routers.py` is the single place a new router is attached; `scripts/ci/validate_router_imports.py` (pre-commit `router-smoke-test`) fails fast on dead imports, and `scripts/advanced_analysis/orphan_route_finder.py` flags routes no client calls.
