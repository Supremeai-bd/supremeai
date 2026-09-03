# 05 — Backend

The backend (`backend/`) is a Poetry project named `supremeai-backend` v2.0.0 — "SupremeAI 2.0 Backend - Autonomous AI Agent Platform". It is a modular FastAPI monolith that can split into role-scoped services via `SUPREMEAI_SERVICE_ROLE`.

## Entry Point & Boot

`backend/main.py` does the environment bootstrap **before any heavy import** (detects `RENDER` → forces `ENV=production`), installs the intelligent silent catcher, registers SIGTERM/SIGINT handlers that defer to uvicorn teardown, and calls `run_server()` → `uvicorn.run("core.app:app", ...)`. Reload is enabled only when `settings.env == "local"`; production **exits if `UVICORN_WORKERS > 1`** (512 MB constraint). Sentry receives boot failures when `SENTRY_DSN` is set. The `app` object is re-exported lazily via module-level `__getattr__` to avoid building the app twice at import time.

## Module Map (verified file counts)

| Module | Files | Purpose |
|--------|-------|---------|
| `core/` | 352 | The heart: config, middleware, security, orchestration, LLM gateway, agents, cache, queue, messaging, resilience, self-evolution, observability, plugins, skills, RAG, telemetry, storage, automation |
| `tests/` | 376 | Pytest suite (api, core, agents, brain, e2e, integration, security, load, llm, rag, orchestration, p2p…) |
| `api/` | 139 | ~115 route modules under `api/routes/`, central registry `api/routers.py`, `api/deps.py`, `api/middleware.py` |
| `tools/` | 123 | Agent tool library: `code/`, `media/`, `mcp/`, `browser/`, `devops/`, `knowledge/`, `learning/`, `social/`, `security_tools/`, `localization/`, `billing/`, `analytics/`, `creative/`, `ai_agents/` |
| `services/` | 62 | Domain services + microservices `scraper/`, `browser/`, `worker/` (each with own Dockerfile) + `dynamic_ai/`, `llm/`, `hitl/`, `ide_trio/`, `storage/`, `email/`, `billing/`, `ingestion/` |
| `agents/` | 47 | `SentinelAgent`, `InsightMage`, `VulnerabilityProphet`, `PerformanceGuardian`, `SkillLibrarian`, `MorphicAdapter`, `autonomous_agent.py`, `base_pydantic_agent.py` + subpackages (domain, devops, governance, ide, monitoring, infrastructure, evolution_agents, syncguard) |
| `core/tests` + `pyerrorfix/` | 37 | Standalone Python error-detection / auto-fix engine (CI + library) |
| `models/` | 35 | SQLAlchemy 2.0 async ORM models |
| `alembic_migrations/` | 22 | Alembic env + versions |
| `brain/` | 22 | `model_router.py`, `model_registry.py`, `cognitive_router.py`, `expert_router.py`, `reasoning_orchestrator.py`, `task_execution_engine.py`, `supreme_learning_engine.py`, `user_digital_twin.py` |
| `adaptive_engine/` | 18 | Self-improving platform adaptation: registry, learning loop, approval workflow, Supabase vector backend |
| `ecosystem/` | 17 | Phase 2–14 orchestration on a shared SQLite store: `task_engine`, `capability_registry`, `governance`, `mcp_skeleton`, `learning_loop`, `approval_workflow` |
| `engine/` | 16 | Reasoning engines: `smart_router.py`, `tree_of_thought.py`, `debate_engine.py`, `self_reflection.py`, `vector_db.py`, `worker_node.py`, `compression/token_juice.py` |
| `memory/` | 16 | `unified_db_manager.py`, `episodic_memory.py`, `long_term_memory.py`, `chromadb_store.py`, `supabase_store.py`, `rag_pipeline.py`, `sliding_window.py`, own `mcp_server.py` |
| `database/` | 23 | `session.py` (async engine), `supabase_client.py` (`db` singleton), `pgbouncer_pool.py`, `multi_db_router.py`, `tenant_db.py`, 14 raw-SQL migrations |
| `evolution/` | 12 | Re-exports `core.self_evolution` + `advanced_evolution_engine.py`, `canary_manager.py`, `fitness_evaluator.py`, `benchmark_runner.py` |
| `learning/` | 8 | Continual learning: `experience.py`, `pattern_recognizer.py`, `hypothesis_engine.py`, `outcome_analyzer.py`, `evolution_bridge.py` |
| `middleware/` | 8 | `rate_limiter.py`, `idempotency_middleware.py`, `chaos_injector.py`, `anti_hacking.py`, `cors_policy.py`, `tenant_rate_limiter.py` |
| `monitoring/` | 8 | `init_observability`, `metrics.py`, `causal_debugger.py`, `behavioral_guard.py`, `log_batcher.py` |
| `integrations/` | 7 | Flag-guarded adapters: mem0, Graphiti, browser-use, E2B, OpenHands |
| `browser/` | 5 | `AutonomousBrowserAgent`, `SwarmBrowser`, `SemanticDOM`, `VisionGrounding`, `BrowsingMemory` |
| Others | 1–29 each | `skills/`, `config/` (JSON policies), `sandbox/`, `pipelines/`, `scout/`, `byoc/`, `p2p/`, `ws/` (`command_center.py`), `workers/` (Celery), `admin/`, `adapters/`, `runtime/`, `verification/`, `scaling/`, `storage/`, `scripts/` |

## Router Registry & Role Filtering

`api/routers.py` holds a declarative `ALL_ROUTERS` list (~90 entries with `{path, prefix, is_admin, is_critical}`). Registration is **role-filtered**: `monolith` loads everything; `core` skips scraper/browser routes; `scraper` loads only scraper/browser + health; `worker` loads only health. Admin routers automatically get `Depends(get_current_user_token)`. The BYOC router only registers when `ENCRYPTION_KEY` is present. Tier-S routes (`api/routes/tier_s_routes.py`) register 12 additional routers (share, reasoning, artifacts, chat-upload, slash-commands, chat-search, chat-export, global-memory, prompt-templates, branch-conversations, scheduled-tasks, deep-research).

Full endpoint inventory: see [07 — API Reference](07-api-reference.md).

## Key Subsystems

### LLM Gateway (`core/llm/llm_gateway.py`)
Lazy-imports **litellm** (deferred to protect boot memory). Per-call API keys (never injected into `os.environ`), semantic cache, fallback chain, `CostGuard`, shared circuit-breaker manager, Langfuse tracing, and routing from `config/routing_policy.json`. `TASK_MODEL_MAP` defaults: coding → `groq/llama-3.3-70b-versatile`; reasoning → `openrouter/meta-llama/llama-3.3-70b-instruct`; vision/chat/general → `gemini/gemini-2.0-flash`. Provider classes in `services/llm/providers.py` are `BaseOpenAICompatibleProvider` subclasses with SSE parsing, `@circuit_breaker` and `@timed` metrics.

### Orchestration (`core/orchestration/orchestrator.py`)
A periodic `tick()` (via `asyncio.TaskGroup`) runs fitness scoring, the `SelfEvolutionAgent` tick, and the **budget guardian subprocess** (`scripts/orchestrator/auto_budget_guardian.py`) — a guardian failure halts the orchestrator (fail-closed on cost). Intent decomposition (`decompose_intent()`) + `execute_skill_chain()` operate over the `EvolutionSkillGraph` with edge-weight feedback and compensation fallbacks. Siblings: `agent_orchestrator.py`, `master_cognitive_orchestrator.py`, `swarm_orchestrator.py`, `trio_pipeline.py`, `crew_departments.py`, `cloud_sandbox_orchestrator.py`. Exposes `/orchestrator/status` and `POST /orchestrator/tick` (Cloud Scheduler webhook target).

### Agent Framework
- `agents/base_pydantic_agent.py` wraps **pydantic-ai `Agent`** (default model `openai:gpt-4o`) wired to the LLM gateway and `MCPRegistryClient` with dynamic MCP tool registration.
- `core/agents/framework/`: `SupremeOrchestrator` (LangGraph-style), `SupremeCrew` (CrewAI pattern), `AgentDepartment` with `CodingAgent`/`ReviewAgent`/`QAAgent`.
- `core/agent_registry.json`: declarative agent specs (system prompt, tools, permissions, temperature, resource constraints like `max_tokens_per_task`, `max_api_calls_per_hour`).
- `core/agent_factory.py` + `core/agent_supervisor.py` handle creation and supervision.

### Background Work & Queues
Celery app lives in `core/queue/task_queue_enhanced.py` (re-exported by `workers/celery_app.py`). On Render free tier, `worker_service.py` is a FastAPI HTTP wrapper on `$PORT` that supervises a Celery subprocess best-effort and reports **degraded** status when Celery/Redis are absent — honesty over green checks. Queue backend priority: `asyncio → redis → celery → pubsub`; messaging adapters exist for GCP Pub/Sub, Upstash Redis and NATS (`core/messaging/`).

### Microservices (`services/`)
| Service | Entry | Role |
|---------|-------|------|
| `services/scraper/` | FastAPI `main.py` (:8082) | `GET /health`, `POST /scrape|/browse|/recipe` — Playwright/Chromium isolated from the core image |
| `services/browser/` | aiohttp app | Browser automation microservice |
| `services/worker/` | Redis-queue consumer | Needs `CORE_API_URL` in production |

Each has its own `Dockerfile` and `requirements.txt`; CI publishes scraper/worker images separately (worker image = core image digest re-tagged).

### Sandbox & BYOC
`backend/sandbox/` (`docker_sandbox.py`, `file_isolation_gate.py`) plus gVisor/Firecracker hooks via env paths; `backend/byoc/` ("Bring Your Own Cloud": `cloud_connector`, `resource_manager`, `container_orchestrator`) exposes `/api/byoc/credentials|deploy|status/{job_id}` gated on `ENCRYPTION_KEY`, with limits in `config/byoc_limits.json`.

## Dependencies (verified from `pyproject.toml`)

Core stack: `fastapi ^0.136.0`, `uvicorn[standard] ^0.51.0`, `pydantic ^2.10.0`, `pydantic-settings ^2.14.2`, `sqlalchemy ^2.0.36`, `alembic ^1.14.0`, `asyncpg ^0.30.0`, `psycopg2-binary ^2.9.9`, `aiosqlite ^0.20.0`, `redis[hiredis] ^5.2.0`, `httpx ^0.28.1`. AI: `openai >=1.54.0`, `anthropic ^0.120.0`, `litellm >=1.84.0,<2.0.0`, `pydantic-ai ^2.31.0`, `mcp ^1.28.1`. Data/vector: `supabase ^2.11.0`, `qdrant-client ^1.12.1`, `neo4j ^6.2.0`. Platform: `stripe ^15.3.1`, `firebase-admin ^6.5.0`, `pyjwt[crypto] ^2.10.1`, `docker ^7.1.0`, `infisical-python 2.3.5`, `pybreaker ^1.4.1`. Observability: `prometheus-client ^0.26.0`, `opentelemetry-sdk ^1.44.0`, `langfuse ^4.14.4`, `posthog ^7.29.0`, `loguru ^0.7.3`, `sse-starlette ^2.1.3`. Optional groups: `browser` (playwright ^1.62.0), `ml` (torch ^2.5.0, sentence-transformers ^3.3.0, pandas, plotly, scipy).

## Observability

- **Sentry** initialized in `app_builder._init_sentry` (boot failures + runtime errors).
- **OpenTelemetry**: `FastAPIInstrumentor.instrument_app(app)` with OTLP gRPC exporter.
- **Prometheus**: `GET /metrics` registered when `MONITORING_DETAILED`; scrape config in `infrastructure/monitoring/prometheus/`.
- **Langfuse** on every LLM call through the gateway; **PostHog** product analytics.
- **Health checks**: `database` (async `SELECT 1`) and `memory` (psutil < 90%) registered at startup; global exception handler includes open circuit-breaker states.
- **Auto-healer**: `services.auto_healer.get_healer().start_monitoring()` when `AUTO_HEALING_ENABLED`.
