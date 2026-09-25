# SupremeAI — Complete Codebase Guide

> **Purpose:** Every module, trick, and technique in the codebase — documented in 5-10 lines each. Each entry explains: **what it is**, **why it was created**, **key files**, and **how to check if it's working**.
>
> **Repo:** `SaifulHaqueNiloy/supremeai` | **Version:** 2.0.0 | **Date:** 2026-09-20
> **Total entries:** ~193 modules + ~60 tricks across Backend, Frontend, Packages, Apps, Infrastructure, Scripts, CI/CD, and Root Configs.

---

## Table of Contents

1. [Backend — Core](#backend--core)
2. [Backend — API & Services](#backend--api--services)
3. [Backend — Agents, Brain & Engine](#backend--agents-brain--engine)
4. [Backend — Context, Learning & Evolution](#backend--context-learning--evolution)
5. [Backend — Runtime, Pipelines, Scaling & Sandbox](#backend--runtime-pipelines-scaling--sandbox)
6. [Backend — Adapters, Integrations, Ecosystem & BYOC](#backend--adapters-integrations-ecosystem--byoc)
7. [Backend — Security, Middleware & Observability](#backend--security-middleware--observability)
8. [Backend — Data, Models, Schemas & Workers](#backend--data-models-schemas--workers)
9. [Backend — Other Modules](#backend--other-modules)
10. [Frontend](#frontend)
11. [Packages](#packages)
12. [Apps (Docs & Mission Control)]#apps-docs--mission-control)
13. [VSCode Extension](#vscode-extension)
14. [Infrastructure](#infrastructure)
15. [Scripts](#scripts)
16. [CI/CD Workflows](#cicd-workflows)
17. [Root Configs](#root-configs)
18. [Tricks & Patterns Index](#tricks--patterns-index)

---

## Backend — Core

### `backend/core/config.py` + `config_cache.py` + `config_validator.py`
**Purpose:** Fail-fast Pydantic settings + TTL-cached DB-driven config + schema-based env validation.
**Created for:** Zero hardcoded secrets; missing required var → `sys.exit(1)`; runtime-tunable thresholds without redeploy.
**Key files:** `core/config.py`, `core/config_cache.py`, `core/config_validator.py`, `core/config_fields.py`, `core/config_secrets.py`
**Check if working:** Boot with missing `SUPABASE_DATABASE_URL_POOLER` → startup crashes with explicit message.

### `backend/core/lifespan.py` + `core/startup/services.py`
**Purpose:** FastAPI lifespan orchestrator — initializes DB pool, Redis, OTel tracing, orchestrator, runs Alembic auto-migration.
**Created for:** Defensive boot ordering; degraded mode if non-critical subsystems fail; graceful shutdown.
**Key files:** `core/lifespan.py`, `core/startup/services.py`, `core/shutdown.py`
**Check if working:** Startup logs `🔄 Running automatic Alembic migrations...` then `✅ ...completed.`

### `backend/core/error_handler.py` / `error_bus.py`
**Purpose:** Observable anti-suppression error pipeline — every error emits a structured `ErrorEvent`, never silently swallowed.
**Created for:** Bounded DLQ (maxsize=1000); CancelledError always re-raised; listener failures never silent-dropped.
**Key files:** `core/errors/error_handler.py`, `core/errors/error_bus.py`, `core/error_bus.py` (`@with_error_bus` decorator)
**Check if working:** Raise inside `@with_error_bus("test")` → `error_event_bus.emit` called, exception re-raised.

### `backend/core/orchestration/`
**Purpose:** Pipeline/cron orchestration — periodic task scheduler, swarm/multi-agent orchestrators, master cognitive dispatcher.
**Created for:** Coordinate fitness scoring, self-evolution, skill graph on 5-minute cycles with OTel spans.
**Key files:** `orchestration/periodic_task_scheduler.py`, `orchestration/swarm_orchestrator.py`, `orchestration/master_cognitive_orchestrator.py`
**Check if working:** `GET /api/v1/orchestrator/status` returns `running: True` + last-run timestamps.

### `backend/core/agents/`
**Purpose:** Agent framework — CodingAgent, ReviewAgent, task-runner, autonomous orchestrator, langgraph/crewai adapters.
**Created for:** R-A-C-E role/action/context/expectation prompt assembly; department-style multi-agent coordination.
**Key files:** `agents/framework/agent_department.py`, `agents/framework/autonomous_task_orchestrator.py`, `agents/live/browser_agent.py`
**Check if working:** `from core.agents.framework.agent_department import CodingAgent; CodingAgent(model_router).execute("hello")` returns dict.

### `backend/core/circles/`
**Purpose:** Federated Capability Circle (FCC) architecture — Governance/Execution/Evolution/Infrastructure circles.
**Created for:** Provider-neutral control plane; single wire format (`ExecutionEnvelope`/`ResultEnvelope`).
**Key files:** `circles/contracts.py`, `circles/envelopes.py`, `circles/governance_core.py`, `circles/registry.py`
**Check if working:** `from core.circles import get_governance_core; gc = get_governance_core()` returns non-None.

### `backend/core/kernel/dispatcher.py`
**Purpose:** Single-door entry facade — authenticates actor, resolves target circle, applies policy + circuit breakers.
**Created for:** Migrate callers from flat registry to FCC federation with safe legacy fallback.
**Key files:** `core/kernel/dispatcher.py`, `core/kernel/interface.py`
**Check if working:** `KernelRequest` submission returns `KernelResponse` with `ExecutionStatus` enum.

### `backend/core/intelligence/`
**Purpose:** Deterministic, provider-independent routing + swarm consensus + verification engine.
**Created for:** Safety ceilings (IRREVERSIBLE/SENSITIVE/CODING/RESEARCH classification); no LLM calls for routing.
**Key files:** `intelligence/router.py`, `intelligence/swarm_consensus.py`, `intelligence/verification.py`
**Check if working:** `IntelligenceRouter().classify("delete prod database")` returns `TaskClassification.IRREVERSIBLE`.

### `backend/core/learning/`
**Purpose:** Persistent learning store — buffered durable telemetry + bounded token-ratio calibration.
**Created for:** Evidence-before-adaptation (≥3 identical errors for proposal); HITL only (never auto-applies).
**Key files:** `learning/store.py`, `learning/loop.py`, `learning/calibration.py`, `learning/provider_scorer.py`
**Check if working:** `get_learning_store().start()` then `record_llm_event({...})` → row queued for Postgres flush.

### `backend/core/cache/`
**Purpose:** Five-tier caching — Redis exact/prefix, semantic vector cache, in-memory LRU, auto-cache proxy.
**Created for:** Cut LLM API cost via semantic similarity; bounded in-memory fallback when Redis down.
**Key files:** `cache/redis_manager.py`, `cache/multi_layer_cache.py`, `cache/semantic_cache.py`, `cache/rate_limit_atomic.py`
**Check if working:** `await redis_manager.get_client_async()` returns Redis client; `from core.cache import get_cache` works.

### `backend/core/database/connection_manager.py`
**Purpose:** Unified facade over three pools (SQLAlchemy async ORM, asyncpg raw SQL, psycopg2 sync legacy).
**Created for:** New code uses `orm_session()` / `raw_pool()` / `sync_connection()` without knowing pool internals.
**Key files:** `core/database/connection_manager.py`
**Check if working:** `await connection_manager.health_check()` returns `{"orm_engine": bool, "raw_pool": bool, "sync_pool": bool}`.

### `backend/core/persistence/`
**Purpose:** Sync psycopg2 threaded pool + write-behind batcher for high-frequency writes.
**Created for:** Replaces per-call `sqlite3.connect()` (state wiped on Render restart); bounded pool.
**Key files:** `persistence/pooled_pg.py`, `persistence/write_behind.py`
**Check if working:** `WriteBehindBatcher("audit").flush_all()` invoked at shutdown flushes pending writes.

### `backend/core/pgbouncer_pool.py`
**Purpose:** asyncpg connection pool with retry + health check at startup.
**Created for:** `init_db_pool(url)` + `get_db_pool_with_retry(max_retries=3)` for API key lookup, audit logger.
**Key files:** `core/pgbouncer_pool.py`
**Check if working:** Boot log: `✅ Database connection pool health check passed.`

### `backend/core/db_schema_gate.py`
**Purpose:** Fail-fast schema gate — probes required tables via PostgREST read-only.
**Created for:** Issue #478 — production never silently runs with missing tables; readiness returns 503.
**Key files:** `core/db_schema_gate.py`
**Check if working:** `production_schema_incompatible()` returns None when OK; returns reason string when table missing.

### `backend/core/health/`
**Purpose:** Multi-tier health system — probes, monitor (Prometheus), self-healer, proactive healer, uptime tracker.
**Created for:** K8s-style `/health/live` vs `/health/ready` split; role-aware readiness.
**Key files:** `health/health_probes.py`, `health/health_monitor.py`, `health/self_healer.py`, `health/proactive_healer.py`
**Check if working:** `GET /api/v1/health/ready` returns 200 with `schema.checked=True`; `GET /api/v1/health/live` always 200.

### `backend/core/llm/llm_gateway/`
**Purpose:** Multi-provider LLM gateway — Routing/LitellmSetup/Resilience/Completion/Streaming mixins.
**Created for:** Per-call API key passing (no `os.environ` mutation); litellm lazy-loaded (saves ~240MB on cold boot).
**Key files:** `llm_gateway/gateway.py`, `llm_gateway/registry.py`, `llm_gateway/routing.py`, `llm_gateway/resilience.py`
**Check if working:** `await LLMGateway().async_generate(prompt="hi", model="groq/llama-3.1-8b-instant")` returns dict.

### `backend/core/llm/token_budget.py` + `distributed_budget.py`
**Purpose:** Token budget management + per-provider RPM/TPM/RPD tracking + Redis-backed multi-worker daily budget.
**Created for:** Conservative buffers (5% below official limits); auto-pause provider when near-exhausted.
**Key files:** `llm/token_budget.py`, `llm/distributed_budget.py`, `llm/free_tier_tracker.py`
**Check if working:** `get_tracker().get_best_available_provider()` returns provider ranked by remaining quota.

### `backend/core/memory/`
**Purpose:** Auto-RAG memory injection — retrieves top-K relevant past memories and prepends to prompt.
**Created for:** Persistent cross-session memory; silent graceful degradation if recall fails.
**Key files:** `memory/auto_rag_injector.py`
**Check if working:** `auto_rag_injector.inject(prompt, user_id="u1")` returns prompt with `--- 🧠 Past Context ---` block.

### `backend/core/ai_memory/`
**Purpose:** Free-tier-optimized pgvector vector store (`ai_memory` table, 384-dim embeddings).
**Created for:** 512MB-memory-constrained deployment — batch ops, streaming results, small pool (size=2).
**Key files:** `ai_memory/vector_store.py`
**Check if working:** `await FreeTierOptimizedVectorStore(url, key).search([0.1]*384, top_k=5)` returns up to 5 rows.

### `backend/core/messaging/`
**Purpose:** Multi-provider messaging — PubSub, Upstash Redis REST, NATS JetStream, GCP PubSub.
**Created for:** Pluggable transport with explicit `MockMessagingAdapter` (refuses to fabricate delivery).
**Key files:** `messaging/pubsub.py`, `messaging/upstash_redis_queue.py`, `messaging/nats_messaging.py`, `messaging/service.py`
**Check if working:** `await global_pubsub.publish("chan", {"x":1})` delivers to subscribers within 2s.

### `backend/core/resilience/`
**Purpose:** Circuit breaker + predictive breaker + auto-remediation + chaos engine + safety rollback.
**Created for:** Prevent cascading failures across LLM provider calls; canonical `CircuitBreakerState` enum.
**Key files:** `resilience/circuit_breaker.py`, `resilience/predictive_circuit_breaker.py`, `resilience/auto_remediation.py`
**Check if working:** `CircuitBreaker("test", failure_threshold=3).call(fn)` opens after 3 failures.

### `backend/core/i18n/`
**Purpose:** Bengali-first text utilities + preferred-language → system-directive loop closure.
**Created for:** M19 P-D — user's saved language preference reaches the model (was a closed loop).
**Key files:** `i18n/language_directive.py`, `i18n/bengali_text.py`, `localization/bhasha_bot.py`
**Check if working:** `await resolve_preferred_language(user_id)` returns "bn" or "en".

### `backend/core/plugins/`
**Purpose:** Plugin manifest registry + permission manager + capability resolver + lifecycle manager.
**Created for:** Idempotent seeding of official plugin manifests (Slack/Telegram/Gmail/Notion/Drive/GitHub).
**Key files:** `plugins/manifest_registry.py`, `plugins/permission_manager.py`, `plugins/capability_resolver.py`
**Check if working:** `await PluginManifestRegistry.seed_official_plugins(session)` is idempotent across boots.

### `backend/core/integrations/registry.py`
**Purpose:** Central registry of all optional integrations (n8n, Appwrite, Ollama, OTel, Langfuse, Sentry, Mem0, etc.).
**Created for:** Single place to report enabled/disabled/misconfigured/not-adopted status.
**Key files:** `core/integrations/registry.py`
**Check if working:** `IntegrationRegistry().snapshot()` returns dict with `IntegrationStatus` enum per integration.

### `backend/core/observability/`
**Purpose:** Neutral metrics registry (Prometheus) + OTel tracing + Langfuse adapter + audit logger + log batcher.
**Created for:** Issue #683 — fix forbidden `core → api` import; 5% Redis traffic sampling to bound cardinality.
**Key files:** `observability/metrics_registry.py`, `observability/telemetry.py`, `observability/audit_logger.py`, `observability/log_batcher.py`
**Check if working:** `record_request(method="GET", path="/x")` increments Prometheus counter; `GET /metrics` exposes `supremeai_*`.

### `backend/core/observability/audit_logger.py`
**Purpose:** Tamper-evident audit trail for autonomous decisions, written via write-behind batcher.
**Created for:** High-frequency audit writes batched (max 200/2s); env-gated SQLite fallback.
**Key files:** `observability/audit_logger.py`
**Check if working:** `AuditLogger().log("decision", {"k":"v"}, "reasoning")` appears in `audit_logs` table within 2s.

---

## Backend — API & Services

### `backend/api/server.py` + `api/middleware.py`
**Purpose:** FastAPI app definition + API-level middleware (correlation ID, request ID, tenant extraction, response standardization).
**Created for:** `X-Correlation-ID`/`X-Request-ID` chain; standard error envelope on all non-JSON responses.
**Key files:** `api/server.py`, `api/middleware.py`, `api/errors.py`, `api/dependencies.py`
**Check if working:** Every response has `X-Correlation-ID` header; unhandled exception → `ErrorResponse` envelope.

### `backend/api/routes/` (180+ route files)
**Purpose:** All HTTP endpoints — health, auth, admin_dashboard (modular), browser (modular), chat (SSE), agents, billing, etc.
**Created for:** Per-domain route files; commandcenter sub-package (observe/operate/build/money/secure/system).
**Key files:** `api/routes/health.py`, `api/routes/auth.py`, `api/routes/chat.py`, `api/routes/admin_dashboard/`, `api/routes/zero_cost.py`
**Check if working:** `GET /api/v1/zero-cost/health` returns `redis_connected` + queue metrics.

### `backend/services/` (top-level)
**Purpose:** Domain services — auto_healer, dynamic_planner, escrow, integration_discovery, sandbox, vision, voice.
**Created for:** Higher-level orchestration above `core/` modules; wrapped by API routes.
**Key files:** `services/auto_healer.py`, `services/dynamic_planner.py`, `services/config_service.py`, `services/memory_service.py`
**Check if working:** `from services import global_http_client` returns real client post-lifespan.

### `backend/services/dynamic_ai/`
**Purpose:** Dynamic AI orchestrator + provider registry + learning engine + local fallback + circuit breaker.
**Created for:** "NEVER crashes due to external API issues" — task classification routes to best provider with fallback.
**Key files:** `dynamic_ai/orchestrator.py`, `dynamic_ai/provider_registry.py`, `dynamic_ai/learning_engine.py`, `dynamic_ai/local_fallback.py`
**Check if working:** `DynamicAIOrchestrator().route(TaskType.CODE_GENERATION, "write fn")` returns response even if primary 5xxs.

### `backend/services/hitl/`
**Purpose:** Human-In-The-Loop approval engine — canonical approval state machine + audit ledger + dispatch.
**Created for:** Pending → approved/rejected/expired transitions; 24h default TTL; idempotency key prefix `hitl:`.
**Key files:** `hitl/engine.py`, `hitl/hitl_ledger.py`, `hitl/dispatch.py`
**Check if working:** `HITLEngine().create_approval(...)` writes to `pending_approvals`; transition out of `approved` raises error.

### `backend/services/ide_trio/`
**Purpose:** Three-stage IDE pipeline — GeminiWriter (write) → KiloReviewer (review) → ClineChecker (check).
**Created for:** Multi-agent code generation with role separation; each stage optional (ImportError-safe).
**Key files:** `services/ide_trio/gemini_writer.py`, `services/ide_trio/kilo_reviewer.py`, `services/ide_trio/cline_checker.py`
**Check if working:** `from services.ide_trio import GeminiWriter, KiloReviewer, ClineChecker` returns 3 classes.

### `backend/services/storage/`, `services/email/`, `services/billing/`, `services/worker/`, `services/scraper/`
**Purpose:** Storage adapter (Appwrite/local), transactional email (Resend), billing plans, background worker, headless scraper.
**Created for:** Each independently deployable (own Dockerfile); storage singleton picks adapter from settings.
**Key files:** `storage/cloud_storage.py`, `email/email_service.py`, `billing/billing_plans.py`, `worker/main.py`, `scraper/web_scraper.py`
**Check if working:** `StorageDispatcher().put(bucket, key, file)` routes to Appwrite if enabled else local.

### `backend/middleware/` (top-level)
**Purpose:** Cross-cutting middleware — anti-hacking context, CORS policy, idempotency, tenant rate limiter, chaos injector.
**Created for:** Alert-only anti-hacking (default); tenant rate limit fail-mode config (`open`/`fallback`/`closed`).
**Key files:** `middleware/anti_hacking.py`, `middleware/cors_policy.py`, `middleware/idempotency_middleware.py`, `middleware/tenant_rate_limiter.py`
**Check if working:** Tenant rate limit exceeded in `closed` mode → 429; in `open` mode → 200 + loud log.

### `backend/monitoring/`
**Purpose:** Real-time zero-cost observability — Sentry init (free tier, 20% tracing), PerformanceTimer, behavioral guard.
**Created for:** Zero silent failures; sentry integrations loaded only if `SENTRY_DSN` set; agent anomaly thresholds (30 tool calls/min).
**Key files:** `monitoring/__init__.py`, `monitoring/metrics.py`, `monitoring/logging_config.py`, `monitoring/behavioral_guard.py`
**Check if working:** `init_observability()` logs `📡 Sentry Real-Time Error Tracking Initialized.` when SENTRY_DSN set.

---

## Backend — Agents, Brain & Engine

### `backend/agents/`
**Purpose:** SupremeAI 2.0 agent package — registry of all specialized domain/devops/monitoring/governance/evolution/IDE agents.
**Created for:** Central place to register new agent classes; many legacy files are backward-compat facades re-exporting from `core.agents.*`.
**Key files:** `agents/__init__.py`, `agents/ephemeral_executor.py`, `agents/base_pydantic_agent.py`, subpkgs `devops/`, `domain/`, `governance/`, `evolution_agents/`, `monitoring/`, `ide/`
**Check if working:** `python -c "import agents; print(agents.HeadlessTerminalAgent)"` from `backend/` — no ImportError.

### `backend/agents/ephemeral_executor.py`
**Purpose:** Use-and-throw sandboxed skill execution engine.
**Created for:** Run each skill in isolated Docker container with `--network none`, read-only mounts, 256m/0.5-CPU cap, 30s timeout, AST pre-flight.
**Key files:** `agents/ephemeral_executor.py` (`EphemeralExecutor`, `ExecutionResult`, `SecurityScanner`)
**Check if working:** `pytest tests/agents/test_ephemeral_executor.py -q`.

### `backend/brain/`
**Purpose:** Higher-level reasoning / model-routing / orchestration layer.
**Created for:** Phase-1 duplicate consolidation — `autonomous_agent.py`, `agent_departments.py` are now facades to `core/agents/framework/*`.
**Key files:** `brain/model_router.py`, `brain/reasoning_orchestrator.py`, `brain/cognitive_router.py`, `brain/user_digital_twin.py`, `brain/economic_optimizer.py`, `brain/causal/root_cause.py`
**Check if working:** `python -c "from brain.model_router import ModelRouter; print(ModelRouter.__name__)"`.

### `backend/brain/reasoning_orchestrator.py`
**Purpose:** Coordinates long-term + episodic memory with a Chain-of-Thought reasoner to plan multi-step tasks.
**Created for:** Glue LLM + memory + CoT; `cot_reasoner` bounded by `max_iterations=2` so agent loop cannot run away.
**Key files:** `brain/reasoning_orchestrator.py`
**Check if working:** `pytest tests/brain/ -q`.

### `backend/engine/`
**Purpose:** Core reasoning/routing/tool/vector/sandbox engine modules — worker_node, tool_forge, smart_router, tree_of_thought, debate_engine, cost_optimizer, embedding, forge_compiler, compression.
**Created for:** Swap-friendly building blocks; `forge_compiler.py` linearizes React-Flow DAG into topologically-sorted execution sequence.
**Key files:** `engine/forge_compiler.py`, `engine/tool_forge.py`, `engine/smart_router.py`, `engine/tree_of_thought.py`, `engine/worker_node.py`, `engine/compression/token_juice.py`
**Check if working:** `pytest tests/engine/ -q`.

### `backend/engine/vector_db.py`
**Purpose:** Free-tier vector memory adapter — no Pinecone dependency; delegates to shared `experience_db` singleton.
**Created for:** All agents share ONE memory pool — Pinecone-shaped interface preserved so no caller breaks.
**Key files:** `engine/vector_db.py`
**Check if working:** `pytest tests/engine/test_vector_db.py -q`.

---

## Backend — Context, Learning & Evolution

### `backend/context/`
**Purpose:** Canonical Context Engine (M2) — smallest-sufficient-context assembly over EXISTING Files/Memory/RAG surfaces.
**Created for:** Doctrine: NO new context database — pure stdlib, offline-testable. Scope chain `GLOBAL → USER → WORKSPACE → PROJECT → CHAT → RUN → STEP`.
**Key files:** `context/engine.py` (`ContextEngine`, `ContextBundle`, `RawCandidate`), `context/budget.py`, `context/items.py`, `context/scopes.py`, `context/sources.py`
**Check if working:** `pytest tests/context/ -q`.

### `backend/context_engine/`
**Purpose:** Companion deterministic budgeted prompt-assembler — section-capped, priority best-fit greedy fill.
**Created for:** Earlier prompt assembly did `f"{memory}{prompt}"` with no budget — caused context bloat + TPM breakage on free-tier.
**Key files:** `context_engine/engine.py` (`AssembledContext`, `ContextBlock`, `ContextEngine`), `context_engine/budget.py`
**Check if working:** `pytest tests/context_engine/ -q`.

### `backend/learning/`
**Purpose:** Continual-learning subsystem — experience ledger, outcome analyzer, pattern detector, hypothesis engine.
**Created for:** Persist outcome-classified `ExperienceRecord`s, mine patterns, generate improvement hypotheses, validate statistically.
**Key files:** `learning/experience.py`, `learning/outcome_analyzer.py`, `learning/pattern_detector.py`, `learning/hypothesis_engine.py`, `learning/evolution_bridge.py`
**Check if working:** `pytest tests/learning/ -q`.

### `backend/evolution/`
**Purpose:** Phase-3 self-evolution layer — 6-state cycle, fitness evaluator, canary rollout, auto-tuner, strategy optimizer.
**Created for:** Proposal → Static/Security Scan → Sandbox Benchmark → Canary Gate → Auto-Rollback pipeline.
**Key files:** `evolution/auto_evolution_controller.py`, `evolution/change_proposal.py`, `evolution/fitness_evaluator.py`, `evolution/canary_manager.py`, `evolution/benchmark_runner.py`
**Check if working:** `pytest tests/test_evolution/ tests/test_evolution_gate.py -q`.

---

## Backend — Runtime, Pipelines, Scaling & Sandbox

### `backend/runtime/`
**Purpose:** Canonical Task Runtime — authoritative control plane (`TaskContract → StateMachine → Planner → BudgetGuard → TaskExecutor → VerifierEngine → Memory → TaskResult`).
**Created for:** Single execution contract; `budget_guard.py` raises `BudgetExceededError` on any compute/cost/token breach.
**Key files:** `runtime/task_runtime.py`, `runtime/planner.py`, `runtime/task_executor.py`, `runtime/budget_guard.py`, `runtime/task_context.py`
**Check if working:** `pytest tests/runtime/ -q`.

### `backend/pipelines/`
**Purpose:** Async background pipelines — code-to-DB outbox sync + synthetic-data export.
**Created for:** `code_to_db_sync.py` does incremental code indexing + idempotency-key-matched outbox flushing; `synthetic_data_pipeline.py` exports Prompt/Response pairs for HuggingFace fine-tuning.
**Key files:** `pipelines/code_to_db_sync.py`, `pipelines/synthetic_data_pipeline.py`
**Check if working:** `python -c "from pipelines.code_to_db_sync import *; print('ok')"`.

### `backend/scaling/`
**Purpose:** Distributed Scaling Manager — multi-node cluster, horizontal auto-scale, priority-based task distribution, failover.
**Created for:** Phase-3 production hardening of the swarm; `DistributedScalingManager` operates over `NodeInfo`/`NodeState`.
**Key files:** `scaling/distributed_manager.py` (`DistributedScalingManager`, `NodeInfo`, `NodeState`, `ScalingDecision`)
**Check if working:** `python -c "from scaling import DistributedScalingManager; print('ok')"`.

### `backend/sandbox/`
**Purpose:** Docker-based isolated code-execution sandbox + AST pre-flight security gate.
**Created for:** `docker_sandbox.py` runs untrusted code in `python:3.11-slim` with 256m/0.5-CPU/10s limits; `file_isolation_gate.py` uses AST scanner to block `eval`/`__import__`/`os.system`.
**Key files:** `sandbox/docker_sandbox.py` (`DockerSandbox`), `sandbox/file_isolation_gate.py`
**Check if working:** `docker info && python -c "from sandbox.docker_sandbox import DockerSandbox"`.

---

## Backend — Adapters, Integrations, Ecosystem & BYOC

### `backend/adapters/`
**Purpose:** Domain adapters — abstract `BaseAdapter` + `AdaptationResult` contract used by Business, Dev, UX, RedTeam adapters.
**Created for:** Phase-2 intelligence layer; each adapter implements its own heuristics (12+ languages, WCAG auditing, OWASP A01–A06).
**Key files:** `adapters/base_adapter.py`, `adapters/business_adapter.py`, `adapters/dev_adapter.py`, `adapters/ux_adapter.py`, `adapters/red_team_adapter.py`
**Check if working:** `pytest tests/adapters/ -q`.

### `backend/integrations/`
**Purpose:** Open-source integration bridges — BrowserUse, E2B, Graphiti, Mem0, OpenHands adapters.
**Created for:** Each adapter is feature-flag guarded + optional-dependency (env flag + `importlib.find_spec`) so system runs at zero cost without the dep.
**Key files:** `integrations/_flags.py` (`flag`, `import_available`), `integrations/browser_use_adapter.py`, `integrations/e2b_adapter.py`, `integrations/mem0_adapter.py`, `integrations/graphiti_adapter.py`
**Check if working:** `python -c "from integrations import E2BAdapter, Mem0MemoryAdapter; print('ok')"`.

### `backend/ecosystem/`
**Purpose:** SupremeAI orchestration modules (ROADMAP Phases 2–14); each module self-contained, idempotent, persistence via shared SQLite.
**Created for:** Capability registry, approval workflow, citizen manifests, learning loop, evolution gate, federation bridge, standalone 47-endpoint FastAPI app.
**Key files:** `ecosystem/standalone_app.py`, `ecosystem/capability_registry.py`, `ecosystem/evolution_gate.py` (`evaluate_promotion`), `ecosystem/federation_bridge.py`
**Check if working:** `cd backend && python -m ecosystem.standalone_app` (boots 47 endpoints).

### `backend/byoc/`
**Purpose:** Bring-Your-Own-Cloud — GCP service-account encryption, Terraform-driven Cloud Run orchestration, per-user resource manager.
**Created for:** `cloud_connector.py` uses Fernet to encrypt GCP SA JSON; `container_orchestrator.py` runs real `terraform init && terraform apply`.
**Key files:** `byoc/cloud_connector.py`, `byoc/container_orchestrator.py` (`ContainerOrchestrator`), `byoc/resource_manager.py`
**Check if working:** `pytest tests/byoc/ -q`.

---

## Backend — Security, Middleware & Observability

### `backend/core/security/__init__.py` (token + API key primitives)
**Purpose:** JWT create/verify, API key generate/hash/verify (HMAC-SHA256, constant-time), token revocation via Redis blacklist.
**Created for:** Admin tokens fail-closed in production (Redis down → reject); dev/test fail-open with loud log.
**Key files:** `core/security/__init__.py`
**Check if working:** `verify_token(jwt)` raises HTTPException(401) on revoked/expired.

### `backend/core/security/authentication/auth_middleware.py`
**Purpose:** Raw-ASGI JWT auth middleware — bearer token from header, query-string token only for SSE paths.
**Created for:** OPTIONS preflight never blocked; SSE/EventSource gets token via `?token=` query; admin-bypass only in test env.
**Key files:** `core/security/authentication/auth_middleware.py`, `core/security/authentication/rbac.py`
**Check if working:** `curl -H "Authorization: Bearer <jwt>" /api/v1/whoami` returns 200; missing token → raw ASGI 401.

### `backend/core/security/api_key_middleware.py`
**Purpose:** `x-api-key` header validation — Redis-cached key lookup, rate limiting, expiry check, DB circuit breaker.
**Created for:** Trusted-proxy-aware client IP extraction (XFF spoofing prevention); 30s recovery breaker on DB lookups.
**Key files:** `core/security/api_key_middleware.py`, `core/security/api_key_limiter.py`
**Check if working:** Request with valid `x-api-key` → `record_api_key_usage()` called.

### `backend/core/security/origin_validator.py` (TrustedOriginMiddleware)
**Purpose:** CSRF/origin enforcement — empty-default frozensets, host-header tampering block, security headers.
**Created for:** Wildcard CORS bypass prevention; denylist filtering; OPTIONS handled with proper preflight headers.
**Key files:** `core/security/origin_validator.py`, `middleware/cors_policy.py`
**Check if working:** Request from origin not in allowed list → 403 `Cross-Origin Request Blocked`.

### `backend/core/security/autonoguard_middleware.py`
**Purpose:** JIT OTP injection + AST scan of code bodies + IP-churn detection on sensitive endpoints.
**Created for:** Lazy-init on first request; mock-safe; stateless distributed enforcement via Redis.
**Key files:** `core/security/autonoguard_middleware.py`, `core/autonoguard_engine.py`
**Check if working:** POST `/api/sensitive/...` without `X-JIT-OTP` header on a sensitive path → blocked.

### `backend/core/security/secret_vault.py`
**Purpose:** Enterprise Infisical/Doppler secret vault with TTL-based in-memory cache, fail-closed behavior.
**Created for:** Removes monolithic GCP Secret Manager; 5-min cache TTL; strict 10s timeout on Infisical init.
**Key files:** `core/security/secret_vault.py`
**Check if working:** `vault.get_secret("SUPABASE_URL")` returns cached value within TTL.

### `backend/core/security/scanning/`
**Purpose:** Secret scanner (gitleaks patterns + AI-enhanced) + AST sandbox scanner (blocks `eval`, `__import__`, `os.system`).
**Created for:** Pre-execution code validation in sandbox; novel-pattern detection via LLM.
**Key files:** `scanning/secret_scanner.py`, `scanning/ast_scanner.py`, `scanning/enhanced_ast_scanner.py`
**Check if working:** `ASTSandboxScanner().scan("import os; os.system('rm -rf /')")` returns `is_safe=False`.

### `backend/core/security/protection/`
**Purpose:** Honeypot (attack signature detection + IP block), SSRF protection (DNS-cached, metadata-aware), prompt firewall.
**Created for:** Two-tier signature matching; pre-auth RAM guard (1MB inspect limit).
**Key files:** `protection/honeypot.py`, `protection/ssrf_protection.py`, `protection/prompt_firewall.py`
**Check if working:** Honeypot blocks `' OR 1=1--` on any path with 418; `is_safe_url("http://169.254.169.254/")` returns False.

### `backend/core/middleware/origin_shield.py`
**Purpose:** Cloudflare Origin Shield pre-shared secret validation (`X-Origin-Verify-Key` header).
**Created for:** Issue #781 — Render free-tier `ipAllowList=0.0.0.0/0` requirement; direct `.onrender.com` hits blocked.
**Key files:** `core/middleware/origin_shield.py`
**Check if working:** In production with `ORIGIN_VERIFY_KEY` set, `curl` direct hit to `.onrender.com` → 403; via Cloudflare Worker → 200.

### `backend/core/middleware/health_aware_middleware.py`
**Purpose:** Injects `request.state.system_degraded=True` when system health is degraded; adds `X-SupremeAI-Health-Warning` header.
**Created for:** 5-second cached health status; critical endpoints get extra logging in degraded state.
**Key files:** `core/middleware/health_aware_middleware.py`
**Check if working:** When `db_degraded()`, response header `X-SupremeAI-Health-Warning` set on non-critical endpoints.

### `backend/core/middleware/security.py`
**Purpose:** SecurityHeadersMiddleware + SQL injection / XSS / path-traversal pattern detection (including double-encoded variants).
**Created for:** Strict CSP (`unsafe-inline` removed from script-src); double-encoded `%252e%252e%252f` traversal bypass closed.
**Key files:** `core/middleware/security.py`, `core/middleware/docs_auth.py`, `core/middleware/query_timing.py`
**Check if working:** Response headers include `Content-Security-Policy` + `X-Frame-Options: DENY`.

### `backend/core/middleware/docs_auth.py`
**Purpose:** Production gate on `/docs`, `/redoc`, `/openapi.json` — 404 when docs disabled, HTTP Basic when enabled.
**Created for:** Sign-off blocker prevention — endpoint existence must not leak; constant-time Basic auth comparison.
**Key files:** `core/middleware/docs_auth.py`
**Check if working:** In production with `SUPREMEAI_DOCS_ENABLED=false`, `curl /docs` → 404.

---

## Backend — Data, Models, Schemas & Workers

### `backend/data/`
**Purpose:** Bundled knowledge cargo for cold-start.
**Created for:** `supremeai_long_term_knowledge_v1.json` — manifest v1.0.0, 132 entries with `knowledge_key`, `title`, `domain`, `content`, `confidence`, `risk_level`.
**Key files:** `data/supremeai_long_term_knowledge_v1.json`
**Check if working:** `python -c "import json; d=json.load(open('backend/data/supremeai_long_term_knowledge_v1.json')); print(len(d['records']))"`.

### `backend/models/`
**Purpose:** SQLAlchemy ORM models on shared `models.base.Base` DeclarativeBase + common mixins (timestamps, soft-delete).
**Created for:** Single source of truth for DB schema across `agents_sessions`, `evolution`, `integration`, `api_key`, `wallet`, etc.
**Key files:** `models/__init__.py`, `models/base.py`, `models/agent_session.py`, `models/evolution.py`, `models/api_key.py`, `models/wallet.py`
**Check if working:** `python -c "from models import Base; print(sorted(Base.metadata.tables))"`.

### `backend/schemas/`
**Purpose:** Pydantic schemas + the SkillIndexManager (atomic `.index.json` read/write).
**Created for:** `skill_manifest.py` defines `SkillManifest` + `SkillStatus` StrEnum; `skill_index.py` derives absolute path from `__file__` so CWD changes can't break it.
**Key files:** `schemas/skill_manifest.py`, `schemas/skill_index.py`
**Check if working:** `python -c "from schemas.skill_index import SkillIndexManager; print('ok')"`.

### `backend/workers/`
**Purpose:** Background workers — Celery entrypoint, chaos auditor, precognitive watcher, synaptic dream (memory consolidation).
**Created for:** `celery_app.py` re-exports `core.queue.task_queue_enhanced.celery_app`; `synaptic_dream.py` prunes transient low-importance `ai_memory` rows past retention horizon.
**Key files:** `workers/celery_app.py`, `workers/chaos_worker.py`, `workers/precognitive_watcher.py`, `workers/synaptic_dream.py`
**Check if working:** `celery -A workers.celery_app inspect ping` (requires Redis broker).

### `backend/verification/`
**Purpose:** Deterministic Verification Engine — no task is `COMPLETED` without objective, verifiable evidence.
**Created for:** Separates model self-confidence from external factual verification; consumes criterion specs, returns `CriterionResult`/`VerificationSummary`.
**Key files:** `verification/verifier.py` (`VerifierEngine`, `get_verifier()`)
**Check if working:** `python -c "from verification import get_verifier; print(get_verifier())"`.

### `backend/utils/`
**Purpose:** Shared utility helpers — timestamps, http client, client IP, environment, branding, platform detect.
**Created for:** DRY helpers; `client_ip.py` is proxy-aware: takes the **last** XFF entry (Render appends real client IP at end) to defeat rate-limit bucket-rotation.
**Key files:** `utils/timestamps.py`, `utils/client_ip.py`, `utils/environment.py`, `utils/http_client.py`, `utils/branding.py`
**Check if working:** `python -c "from utils.client_ip import *; from utils.timestamps import utc_now_iso; print(utc_now_iso())"`.

### `backend/alembic_migrations/`
**Purpose:** Canonical DB migration system — Alembic env.py prefers `SUPABASE_DATABASE_URL_WRITER` (direct writer, not PgBouncer pool).
**Created for:** Replace raw SQL with one linear Alembic history; 25+ revisions; P0 fix prioritizes writer endpoint because PgBouncer rejects DDL.
**Key files:** `alembic_migrations/env.py`, `alembic_migrations/versions/`, `alembic.ini`
**Check if working:** `cd backend && alembic upgrade head` succeeds; `alembic check` exits 0.

---

## Backend — Other Modules

### `backend/p2p/`
**Purpose:** Peer-to-peer primitives — credit ledger + secure tunnel (stubs for future federated execution).
**Created for:** Foundation for a future peer-to-peer credit economy + authenticated peer tunnels.
**Key files:** `p2p/credit_system.py` (`CreditLedger.earn`), `p2p/secure_tunnel.py` (`SecureTunnel.create`/`terminate`)
**Check if working:** `python -c "import asyncio; from p2p.credit_system import CreditLedger; print(asyncio.run(CreditLedger().earn('u1', 1.0, 'test')))"`.

### `backend/ws/`
**Purpose:** WebSocket command-center router (currently a health-check stub).
**Created for:** Single FastAPI `APIRouter` mounted at `/ws/command-center` with a `/health` GET. Real WS auth lives in `core/security/ws_auth.py`.
**Key files:** `ws/command_center.py`
**Check if working:** `curl http://localhost:8000/ws/command-center/health` returns `{"status":"ok"}`.

### `backend/skills/`
**Purpose:** Backward-compat facade unifying dynamic skill provisioning with `core.skills.*`.
**Created for:** `provisioner.py` auto-installs background system + Python deps for a skill manifest; `skill_registry.py` loads manifests from `skills/manifests/`.
**Key files:** `skills/provisioner.py`, `skills/skill_registry.py`, `skills/installer.py`, `skills/manifests/`
**Check if working:** `python -c "from skills import SkillProvisioner; print(SkillProvisioner)"`.

### `backend/missions/`
**Purpose:** Mission Orchestration core (Task 7-c) — link GOAL → STRATEGY → ordered PHASES through strict state machine.
**Created for:** Immutable `MissionTraceEvent` audit trail; bounded repair loop (`MAX_REPAIRS=3`); persistence is SQLAlchemy on Supabase Postgres.
**Key files:** `missions/models.py` (`Mission`, `MissionTraceEvent`), `missions/state_machine.py`, `missions/service.py` (`MissionService`)
**Check if working:** `pytest tests/missions/ -q`.

### `backend/scout/`
**Purpose:** Policy-driven web crawler + dedup + extractive summarization (zero LLM tokens).
**Created for:** `APPROVED_DOMAINS` allowlist; `PolicyEngine` enforces SSRF safety; `ContentDeduplicator` uses SHA-256 + Jaccard ≥ 0.80; `ExtractiveSummarizer` ranks sentences by salience (no LLM).
**Key files:** `scout/crawler.py`, `scout/policy.py`, `scout/dedup.py`, `scout/extractor.py`, `scout/web_crawler_agent.py`
**Check if working:** `pytest tests/scout_tests/ -q`.

### `backend/admin/`
**Purpose:** Admin package — `AdminGodLayer` (constitutional enforcement), `GodModeAuditLog`, `GodModeContext`.
**Created for:** God-mode session + RBAC + constitutional enforcement + audit logging. Falls back to SQLite for tests.
**Key files:** `admin/__init__.py` (`AdminGodLayer`, `GodModeAuditLog`, `GodModeContext`), `admin/god.py`
**Check if working:** `pytest admin/test_god.py -q`.

### `backend/adaptive_engine/`
**Purpose:** SupremeAI 2.0 Adaptive Engine — auto-learning, platform adaptation, capability registry, experience DB, learning loop, governance.
**Created for:** Enforces `REUSE > ADAPT > EXTEND > CREATE` (capability-explosion guard) with full lifecycle FSM and Hot/Warm/Cold runtime tiers. Experience DB falls back to Supabase pgvector on Render cold-start.
**Key files:** `adaptive_engine/capability_registry.py`, `adaptive_engine/experience_db.py`, `adaptive_engine/learning_loop.py`, `adaptive_engine/governance.py`
**Check if working:** `pytest tests/adaptive_engine/ -q`.

### `backend/pyerrorfix/`
**Purpose:** Reusable Python error-detection + auto-fix engine — stdlib-only (`ast`, `tokenize`, `re`).
**Created for:** Runs in GitHub Actions and as a library. CLI: `python -m pyerrorfix analyze backend/ --format json --fix`.
**Key files:** `pyerrorfix/cli.py`, `pyerrorfix/core/scanner.py`, `pyerrorfix/core/issue.py` (`Issue`, `Severity`, `Category`), `pyerrorfix/detectors/`, `pyerrorfix/fixers/`
**Check if working:** `python -m pyerrorfix catalog --format json | head`.

### `backend/runs/`
**Purpose:** Canonical Run fabric (M1) — every Mission/Agent/Tool/MCP/Browser/Code execution is observable as a Run.
**Created for:** Lifecycle, retry classification, budgets, artifacts, ordered audit event stream. State machine: `REQUESTED → POLICY_CHECKED → PLANNED → RUNNING → terminal → FINALIZED`.
**Key files:** `runs/state_machine.py`, `runs/retry.py` (`RetryClass`, `is_retryable`), `runs/budgets.py`, `runs/models.py` (`Run`, `RunEvent`), `runs/service.py`
**Check if working:** `pytest tests/runs/ -q` and `SELECT count(*) FROM runs;`.

### `backend/storage/`
**Purpose:** Object-storage asset managers — Firebase + Cloudflare R2.
**Created for:** `r2_storage_client.py` (audit B-01) — **fail-closed**: previously returned mock presigned URLs when creds missing; now raises `StorageNotConfiguredError`.
**Key files:** `storage/asset_manager.py`, `storage/r2_storage_client.py`
**Check if working:** `python -c "from storage.r2_storage_client import StorageNotConfiguredError; print('ok')"`.

---

## Frontend

### `frontend/` (root config)
**Purpose:** Vite + React 19 + Tailwind 4 SPA, single unified build serving both User and Admin contexts.
**Created for:** `package.json` is `supremeai-studio-client@2.0.0`, depends on `@supremeai/{core-infrastructure,design-tokens,shared-services,shared-types,ui-components}`.
**Key files:** `package.json`, `vite.config.ts`, `nginx.conf`, `index.html`, `Dockerfile`
**Check if working:** `pnpm --filter supremeai-studio-client build` emits `frontend/dist/`; `pnpm test` passes.

### `frontend/src/main.tsx` + `App.tsx`
**Purpose:** Bootstrap React root, install providers, mount one-route-graph.
**Created for:** `main.tsx` eagerly inits Firebase + heartbeat + global fetch interceptor + SW registration (PROD only). `App.tsx` lazy-loads 30+ pages.
**Key files:** `src/main.tsx`, `src/App.tsx`
**Check if working:** `pnpm dev` boots; `/` shows GuestChatPage; `/workspace` triggers ProtectedRoute.

### `frontend/src/auth/`
**Purpose:** Canonical identity helpers — never client-computes privilege; reads backend role from `authStore` or server-signed admin JWT.
**Created for:** Single-frontend migration Phase 2/4 — replace old "role in localStorage" anti-pattern.
**Key files:** `auth/identity.ts`, `auth/routePolicies.ts`
**Check if working:** `getCanonicalRole()` returns `'admin'` only when `authStore.role === 'admin'` OR admin JWT is unexpired.

### `frontend/src/commandcenter/`
**Purpose:** AETHEL Command Center sub-app — separate shell with LeftRail/BottomDeck/CommandPalette, fed by WebSocket + SSE.
**Created for:** Replacing old admin "canvas" with focused operator cockpit mounted at `/commandcenter`.
**Key files:** `shell/CommandCenterApp.tsx`, `state/useCommandCenterStore.ts`, `realtime/websocketManager.ts`, `realtime/CommandCenterRealtimeProvider.tsx`
**Check if working:** Load `/commandcenter` — `useMetrics` + `useHealthMap` resolve; WS status transitions to `open`.

### `frontend/src/components/`
**Purpose:** All presentational React components, grouped by surface (chat, dashboard, customer, admin, editor, layout, ui, swarm, etc.).
**Created for:** Component library backing every page; `components/ui/*` exports primitives (Button, Card, Badge, Input, Skeleton, etc.).
**Key files:** `core/AuthGuards.tsx`, `core/guards/RoleGuard.tsx`, `chat/ChatInterface.tsx`, `dashboard/LivingDashboardShell.tsx`, `admin/AdminConsole.tsx`
**Check if working:** `pnpm test` runs 50+ component tests; `pnpm storybook` mounts stories.

### `frontend/src/config/`
**Purpose:** Single source-of-truth registries for roles/permissions, navigation, commands, defaults.
**Created for:** Phase 2/6 of single-frontend migration — kill duplicate nav/command definitions across User + Admin.
**Key files:** `config/permissions.ts` (`ROLES`, `PERMISSIONS`, `isRole`, `hasPermission`), `config/navigationRegistry.ts`, `config/commandRegistry.ts`
**Check if working:** `getImplementedRoutePaths()` matches every path declared in `App.tsx`.

### `frontend/src/hooks/`
**Purpose:** Reusable React hooks (auth, chat, websocket, translation, admin queries, event bus, dynamic dock, server stream).
**Created for:** Decoupling data-access logic from components; each hook wraps a TanStack Query or a realtime subscription.
**Key files:** `hooks/index.ts` (barrel), `hooks/useAuth.ts`, `hooks/useChat.ts`, `hooks/useWebSocket.ts`, `hooks/useTranslation.ts`
**Check if working:** `import { useAuth } from '@/hooks'` resolves; `pnpm test` runs hook tests.

### `frontend/src/i18n/`
**Purpose:** Lightweight i18n (en/bn) without external lib.
**Created for:** Bangla + English locale support; persists locale via `localStorage['supreme_lang']` and syncs to `/api/preferences.preferred_language`.
**Key files:** `i18n/I18nProvider.tsx`, `i18n/useI18n.ts`, `i18n/useTranslation.ts`, `i18n/translations.ts`
**Check if working:** `useTranslation()` returns `t('common.login')` = `Login`/`লগইন` per locale.

### `frontend/src/services/`
**Purpose:** Frontend service layer — HTTP client, auth, agent/run/chat/cost/skills/MCP/file/project/admin/CI/realtime services.
**Created for:** One canonical apiClient with idempotency keys, JIT-OTP injection, CSRF + device fingerprint, X-Request-ID correlation, p-queue concurrency, 60s Render-cold-start timeout.
**Key files:** `services/apiClient.ts`, `services/tokenStorage.ts`, `services/authService.ts`, `services/agentService.ts`, `services/realtime/WebSocketManager.ts`
**Check if working:** `apiClient.get('/api/v1/health/live')` returns JSON; `getAuthHeaders()` includes `Authorization`, `X-Device-Fingerprint`.

### `frontend/src/store/`
**Purpose:** Zustand stores — authStore (canonical session), adminStore (admin step-up), useStore (system config + chat + deploy gate), plus slices.
**Created for:** Single-frontend migration — authStore owns role/permissions from backend only; adminStore owns Firebase→OTP→TOTP step-up state.
**Key files:** `store/authStore.ts`, `store/adminStore.ts`, `store/useStore.ts`, `store/slices/`
**Check if working:** `useAuthStore.getState().status` starts `UNINITIALIZED`; `initialize()` flips to `LOGGED_IN`/`LOGGED_OUT`.

### `frontend/src/utils/`
**Purpose:** Pure utility helpers — backend URL resolution, fetch interceptor, class names, device fingerprint, secure WS.
**Created for:** One API base policy (runtime context-aware), global fetch interceptor (cookie scoping + structured error normalization), zero-cost device fingerprint.
**Key files:** `utils/api.ts` (`getApiBaseUrl`, `getBackendUrl`, `fetchWithRetry`), `utils/apiInterceptor.ts`, `utils/cn.ts`, `utils/secureWebSocket.ts`
**Check if working:** `import { apiClient } from '@/services/apiClient'` uses `getApiBaseUrl(path)` correctly.

### `frontend/src/workers/`
**Purpose:** Web Workers offloading main-thread log parsing.
**Created for:** `LiveLogs` filter/search on huge log arrays without blocking the UI thread.
**Key files:** `workers/logParser.worker.ts` (actions: PARSE_LOGS, SEARCH_LOGS, FILTER_LOGS)
**Check if working:** `useLogParserWorker()` hook posts FILTER_LOGS → returns filtered array without dropping frames.

### `frontend/src/firebase.ts`
**Purpose:** Lazy Firebase initialization with `/__/firebase/init.json` fallback.
**Created for:** Firebase Hosting deployments use init.json; non-Firebase hosts use `VITE_FIREBASE_*` env vars; eager init prevents "No Firebase App" race.
**Key files:** `src/firebase.ts`
**Check if working:** `initFirebase()` resolves; `getFirebaseAuth()` returns initialized `Auth` instance.

---

## Packages

### `packages/core-infrastructure/`
**Purpose:** Edge-safe shared infrastructure primitives (single-sourced).
**Created for:** DRY Phase 1-B3 — five divergent `timingSafeEqualStr` copies consolidated; `CircuitBreaker` replaces private stub.
**Key files:** `src/index.ts`, `src/circuit-breaker.ts`, `src/timing-safe.ts`
**Check if working:** `import { CircuitBreaker, timingSafeEqualStr } from '@supremeai/core-infrastructure'` resolves.

### `packages/design-tokens/`
**Purpose:** Single source of truth for SupremeAI 2.0 design tokens; style-dictionary build pipeline emits CSS variables, JSON, Flutter Dart, VS Code theme.
**Created for:** DRY across web + Flutter + VS Code + Bengali translations.
**Key files:** `build.js`, `design-tokens.json`, `tokens/primitives.json`, `tokens/semantic.json`, `src/admin.json`, `src/admin.bn.json`
**Check if working:** `pnpm --filter @supremeai/design-tokens build` regenerates all `outputs/*`.

### `packages/shared-services/`
**Purpose:** Platform-agnostic SupremeAI core services shared by VS Code extension + Electron + Web.
**Created for:** DRY Phase 1 — single `SupremeAIService`, `BaseWebSocketManager`, `createHttpClient`, `SelfHealingService`, `SecurityScanner`.
**Key files:** `src/http/canonical-http.ts`, `src/platform.ts`, `src/realtime/BaseWebSocketManager.ts`, `src/services/SupremeAIService.ts`
**Check if working:** `import { createHttpClient, BaseWebSocketManager } from '@supremeai/shared-services'` resolves.

### `packages/shared-types/`
**Purpose:** Zod-validated TS types shared by backend + frontend + extension (single contract).
**Created for:** DRY Phase 1-B1 — frontend had 6 chat roles vs shared-types 3 (drift); now `CHAT_ROLES` is the canonical superset.
**Key files:** `src/index.ts`, `src/message.ts` (`MessageSchema`, `CHAT_ROLES`), `src/conversation.ts`, `src/chat.ts`, `src/auth.types.ts`
**Check if working:** `import { MessageSchema } from '@supremeai/shared-types'` works in both frontend and backend.

### `packages/ui-components/`
**Purpose:** Cross-app React providers (currently the single shared TanStack Query client).
**Created for:** Single QueryClient (with smart retry: no retries on 401/403/429) shared by studio + future desktop apps.
**Key files:** `src/index.ts`, `src/contexts/SharedProviders.tsx`
**Check if working:** `import { SharedProviders } from '@supremeai/ui-components'` resolves; `useQueryClient()` returns singleton.

### `packages/scripts/`
**Purpose:** Internal Python readiness orchestrator + pre-commit secret guard.
**Created for:** Pre-boot env validation (OPENAI_API_KEY, JWT_SECRET ≥ 64 bytes, DB URL, Redis), LLM gateway ping, Redis ping; secret-scanner blocks commits.
**Key files:** `master_validator.py`, `security_guard.py`
**Check if working:** `python3 packages/scripts/master_validator.py` exits 0 with `ALL SYSTEMS GO!`.

---

## Apps (Docs & Mission Control)

### `apps/docs/` (Docusaurus)
**Purpose:** Public documentation site at `https://docs.supremeai.dev`.
**Created for:** English + Bengali (i18n locales `['en','bn']`) docs + OpenAPI docs (via `docusaurus-plugin-openapi-docs`).
**Key files:** `docusaurus.config.ts`, `sidebars.ts`, `docs/intro.md`, `docs/api-reference.md`
**Check if working:** `pnpm --filter supremeai-docs build` produces `apps/docs/build/`.

### `apps/mission-control/` (Next.js 16 operator console)
**Purpose:** Standalone governed autonomy console — live tower telemetry, 106-tool MCP explorer, PR↔main conflict watching, brain & memory, watchdog alerting.
**Created for:** Zero-cost operator UI separated from the studio SPA; runs on Render free tier, SQLite via Prisma, MCP Streamable HTTP.
**Key files:** `package.json`, `next.config.ts` (`output:'standalone'`, `reactStrictMode:true`, `ignoreBuildErrors:false`), `prisma/schema.prisma`, `src/middleware.ts`, `src/app/page.tsx`
**Check if working:** `pnpm --filter @supremeai/mission-control build` produces `.next/standalone/`; `pnpm db:push` initializes SQLite.

### `apps/mission-control/src/lib/tower-client.ts`
**Purpose:** MCP Streamable HTTP (JSON-RPC over POST `/mcp`) client with admin-key auth, session caching, auto-wake.
**Created for:** Zero-cost philosophy — Render free tier sleeps after 15 min; tower client pings `/health` then retries; tower URL/key resolve from DB → env.
**Key files:** `src/lib/tower-client.ts` (`wakeTower`, `towerHealth`, `listTowerTools`, `callTowerTool`)
**Check if working:** `towerHealth()` returns `{status:'live'|'sleeping'|'unreachable', latencyMs, version}`.

### `apps/mission-control/src/lib/api-auth.ts`
**Purpose:** Edge-runtime-safe auth helpers (WebCrypto only — no `node:crypto`).
**Created for:** FE-10 (Issue #503) — every `/api/*` route previously had no auth; now HMAC-signed `mc_unlock` cookie (12h TTL).
**Key files:** `src/lib/api-auth.ts` (re-exports `timingSafeEqualStr` from `@supremeai/core-infrastructure`)
**Check if working:** `signUnlockCookie(token, now)` → `verifyUnlockCookie(value, token)` round-trips.

### `apps/mission-control/src/middleware.ts`
**Purpose:** Edge middleware gating every `/api/*` request.
**Created for:** Defense-in-depth — bearer/X-Admin-Key header OR HMAC-signed cookie passes; production with no token fails closed.
**Key files:** `src/middleware.ts`
**Check if working:** `curl /api/dashboard` without cookie returns 401; after `POST /api/auth/unlock` the cookie authenticates.

### `apps/mission-control/src/app/api/tower/*`
**Purpose:** Tower proxy endpoints — `/wake` (POST), `/tools` (GET), `/call` (POST).
**Created for:** Browser-side tower-gateway.ts calls these REST wrappers; `/call` enforces allowlist of tool prefixes.
**Key files:** `tower/wake/route.ts`, `tower/tools/route.ts`, `tower/call/route.ts`
**Check if working:** `POST /api/tower/wake` returns `{woke, attempts, latencyMs}`.

---

## VSCode Extension

### `tools/vscode-extension/`
**Purpose:** VS Code extension `supremeai-vscode@6.0.0` — real-time code learning, AI chat, CodeFlow analysis, swarm pipeline, security scan, performance monitor.
**Created for:** Bringing SupremeAI backend to the IDE; activates on `*` (every workspace), contributes 32 commands, 8 webviews, 1 theme.
**Key files:** `package.json`, `src/extension.ts`, `src/services/SupremeAIService.ts`, `src/services/SwarmPipelineProvider.ts`, `src/providers/SupremeAISidebarProvider.ts`
**Check if working:** `pnpm --filter supremeai-vscode compile` passes; F1 → `SupremeAI: Run Swarm Pipeline` prompts for task.

### `tools/vscode-extension/src/services/SwarmPipelineProvider.ts`
**Purpose:** Trio/Swarm pipeline command — detects Gemini/Kilo/Cline IDEs, calls backend `agent_review_workflow/execute`.
**Created for:** Multi-agent swarm orchestration; never silently defaults to `http://localhost:8080` (FE-11/Issue #526).
**Key files:** `src/services/SwarmPipelineProvider.ts`
**Check if working:** With `supremeai.swarmBackendUrl` unset, command shows error toast with `Open Settings` button.

---

## Infrastructure

### `infrastructure/mcp-control-plane/`
**Purpose:** TypeScript MCP "Control Tower" — Streamable-HTTP server exposing ~24 tool domains (render, github, supabase, infisical, cloudflare, ai, redis, firebase, memory, etc.).
**Created for:** Centralize multi-cloud control behind one MCP server so VS Code/Claude/Cursor can drive the platform.
**Key files:** `src/index.ts`, `src/tools/index.ts`, `src/lib/env.ts`, `package.json`, `render.yaml`, `Dockerfile`
**Check if working:** `cd infrastructure/mcp-control-plane && npm ci && npm run build && node dist/index.js` — `curl http://localhost:3771/health` returns 200.

### `infrastructure/mcp-control-plane/src/adapters/`
**Purpose:** 13 provider adapters (firebase, infisical, render, ai, supabase, firecrawl, github, memory, redis, qdrant, notify, misc, cloudflare).
**Created for:** Decouple provider logic from tool definitions; each implements `ProviderAdapter` from `base.ts`.
**Key files:** `src/adapters/base.ts`, `src/adapters/render/index.ts`, `src/adapters/infisical/index.ts`, `src/adapters/cloudflare/index.ts`
**Check if working:** `npx tsx test_adapters.ts` runs all adapter smoke tests.

### `infrastructure/mcp-control-plane/src/tools/`
**Purpose:** 24 MCP tool modules registered via `registerAllTools()` — system, render, github, supabase, redis, cloudflare, infisical, firebase, ai, notify, memory, federation, guardian, etc.
**Created for:** Map every platform capability to MCP tools with Zod-validated schemas.
**Key files:** `src/tools/index.ts`, `src/tools/render.tools.ts`, `src/tools/infisical.tools.ts`, `src/tools/guardian.tools.ts`
**Check if working:** `mcp inspector http://localhost:3771/mcp` lists all tools.

### `infrastructure/mcp-control-plane/src/policy/` + `src/guardian/` + `src/remediation/`
**Purpose:** Access control (HITL approvals, risk engine) + autonomous guardian (GitHub policy enforcement) + remediation engine (killswitch, rules).
**Created for:** Multi-tenant agent governance — `policy.engine.ts` + `risk.engine.ts` decide which tools need human approval; `remediation/killswitch.ts` halts runaway loops.
**Key files:** `src/policy/policy.engine.ts`, `src/guardian/engine.ts`, `src/remediation/engine.ts`, `src/remediation/killswitch.ts`
**Check if working:** `npx tsx test_policy.ts && npx tsx test_guardian.ts && npx tsx test_remediation.ts` all exit 0.

### `infrastructure/cloudflare_worker.js`
**Purpose:** Cloudflare Worker edge proxy — weighted load-balancer across 4 Render backends, edge rate limiting (120 req/min/IP via KV), circuit breaker, public-API cache, Origin Shield header injection.
**Created for:** Edge-level failover + protection in front of Render free-tier; Worker injects `X-Origin-Verify-Key` to block direct `.onrender.com` hits (#781 fix).
**Key files:** `cloudflare_worker.js`, `wrangler.toml`
**Check if working:** `curl -I https://supremeai-worker.paykaribazaronline.workers.dev/api/v1/health` returns 200.

### `infrastructure/wrangler.toml`
**Purpose:** Worker config — KV namespace binding (`SUPREMEAI_KV`), 4 backend role URLs as `[vars]`, NO cron triggers (ToS-compliant).
**Created for:** INF-10 fix (#533) — previously declared ZERO KV bindings, so rate limiting silently no-op'd.
**Key files:** `wrangler.toml`, `cloudflare_worker.js`
**Check if working:** `CLOUDFLARE_ACCOUNT_ID=<id> npx wrangler deploy --dry-run` validates.

### `infrastructure/deploy.ps1`
**Purpose:** PowerShell orchestrator for GCP Cloud Run deploys — builds backend image, pushes to Artifact Registry, deploys with `--no-allow-unauthenticated`.
**Created for:** INF-06 fix (#529) — bare `docker build <root>` failed because repo root has no Dockerfile.
**Key files:** `infrastructure/deploy.ps1`, `backend/Dockerfile`
**Check if working:** `pwsh infrastructure/deploy.ps1 -Target gcp` succeeds.

### `infrastructure/check_deploy_gate.py`
**Purpose:** Firestore-backed autonomous deploy gatekeeper — fail-closed (LOCKED on missing doc/field/connection error).
**Created for:** Defense against accidental deploys during audits/outages.
**Key files:** `infrastructure/check_deploy_gate.py`
**Check if working:** `python infrastructure/check_deploy_gate.py` exits 0 only when Firestore doc is UNLOCKED.

### `infrastructure/monitoring/prometheus/`
**Purpose:** Prometheus scrape config + alert rules — backend scrape hits `/api/admin/metrics` with bearer token.
**Created for:** Old config scraped `/metrics` (non-existent); invalid `metric_relabel_configs` crashed prometheus.
**Key files:** `prometheus.yml`, `alert_rules.yml`, `secrets/backend_metrics_token.example`
**Check if working:** `promtool check config prometheus.yml` exits 0; `:9090/targets` shows all targets UP.

### `infrastructure/monitoring/grafana/`
**Purpose:** Grafana provisioning (datasource + dashboard provider) and the `supremeai-overview.json` dashboard.
**Created for:** INF-15 fix (#561) — Grafana shipped with ZERO datasources and ZERO provisioning providers.
**Key files:** `provisioning/datasources/prometheus.yml`, `provisioning/dashboards/provider.yaml`, `dashboards/supremeai-overview.json`
**Check if working:** `docker compose --profile observability up grafana` → http://127.0.0.1:3300 → dashboard auto-loads.

### `infrastructure/monitoring/opentelemetry/otel-collector-config.yaml`
**Purpose:** OTel Collector — OTLP receivers (gRPC 4317, HTTP 4318), PII-redaction, exports traces to Jaeger + metrics to Prometheus.
**Created for:** INF-11 fix (#534) — `otlp/jaeger` exporter targeted unresolvable `jaeger:4317` while no jaeger service existed.
**Key files:** `otel-collector-config.yaml`
**Check if working:** `:13133` health endpoint returns 200; Jaeger UI at `:16686` shows ingested traces.

### `backend/Dockerfile`
**Purpose:** Backend FastAPI runtime image — 2-stage: builder (poetry install) → runtime (python:3.11-slim, non-root `supremeai` user, `/health/live` probe on 8080).
**Created for:** Single canonical backend image for core, worker, scraper (override command); `target: runtime` is what prod runs.
**Key files:** `backend/Dockerfile`, `backend/pyproject.toml`
**Check if working:** `docker build -t supremeai/core -f backend/Dockerfile backend/` succeeds; `docker run -p 8080:8080 supremeai/core` — `/health/live` returns 200.

### `backend/services/scraper/Dockerfile`
**Purpose:** Browser-ready Playwright image — same 2-stage as backend + `poetry install --only main,browser` + `playwright install --with-deps chromium`.
**Created for:** INF-07 fix (#530) — base `backend/Dockerfile` installs no Playwright/Chromium, so scraper crashed.
**Key files:** `backend/services/scraper/Dockerfile`, `backend/services/scraper/main.py`
**Check if working:** `docker build -t supremeai/scraper -f backend/services/scraper/Dockerfile backend/` succeeds.

### `docker-compose.yml` (dev)
**Purpose:** Local dev orchestration — core + worker + scraper + mcp + frontend + redis + db (pgvector/pgvector:pg16).
**Created for:** R-03: pgvector everywhere; R-06: redis + db default-on; R-05: backend/ baked into mcp image.
**Key files:** `docker-compose.yml`, `backend/Dockerfile`, `infrastructure/mcp-control-plane/Dockerfile`
**Check if working:** `VERSION=dev docker compose up` boots core + frontend + redis + db healthy.

### `docker-compose.production.yml`
**Purpose:** Prod stack — backend (loopback-only 8080), postgres (pgvector, tuned), redis (auth + AOF + LRU), observability profile.
**Created for:** All observability ports bound `127.0.0.1` only; `VERSION:?` required (fail-fast); `backend` network alias (FE-02 fix).
**Key files:** `docker-compose.production.yml`, `.env.production`
**Check if working:** `VERSION=v2.0.0 docker compose -f docker-compose.production.yml --profile observability up -d` — every service healthy.

---

## Scripts

### `scripts/ci/` (80+ CI gate scripts)
**Purpose:** Pre-merge gate library — render/vercel preflight, action pinning, route registry, config contract, RLS/RBAC auditor, migration safety diff, coverage quality gate, security headers.
**Created for:** Single source of CI checks so `ci.yml` and `pre-commit-config.yaml` invoke the same Python entry-points.
**Key files:** `render_deploy_preflight.py`, `check_actions_pinning.py`, `security_gate.py`, `circle_architecture_gate.py`, `migration_safety_diff.py`
**Check if working:** `python scripts/ci/<script>.py --help` exits 0; CI workflow `ci.yml` green on PRs.

### `scripts/db/`
**Purpose:** Database lifecycle — `auto_migrate.py`, `auto_seed.py`, `verify_pgvector.py`, `validate_retrieval.py`.
**Created for:** Idempotent DB bootstrap from fresh clone — verify pgvector extension, FTS index, knowledge seed loaded.
**Key files:** `scripts/db/auto_migrate.py`, `scripts/db/verify_pgvector.py`, `scripts/db/auto_seed.py`
**Check if working:** `python scripts/db/auto_migrate.py` exits 0; `python scripts/db/verify_pgvector.py` prints `✅ pgvector installed`.

### `scripts/security/`
**Purpose:** Security automation — `auto_vulnerability_scanner.py` (pip-audit + Bandit + GitLeaks + SBOM), `auto_secret_rotate.py`, `repair_and_federate_cloudflare.py`, `delete_vault_stale_keys.py`.
**Created for:** Continuous secret hygiene + SCA/SAST in CI; vault cleanup; Cloudflare KV vault auto-repair across 5-account federation.
**Key files:** `scripts/security/auto_vulnerability_scanner.py`, `scripts/security/secrets_rotation_manager.py`, `scripts/security/check_internal_topology.sh`
**Check if working:** `python scripts/security/auto_vulnerability_scanner.py --full-scan` produces SARIF + JSON.

### `scripts/devops/`
**Purpose:** DevOps automation — `run_local_audit.py` (LLM audit of modular audit markdowns), `refactor_wiz.py`, `todo_manager.py`, `devops_security_scan.py`.
**Created for:** Self-audit + automated patch authoring loop; `run_local_audit.py` is the local LLM audit entry-point (offline Ollama preferred).
**Key files:** `scripts/devops/run_local_audit.py`, `scripts/devops/devops_security_scan.py`
**Check if working:** `python scripts/devops/run_local_audit.py --help` exits 0.

### `scripts/deploy/`
**Purpose:** Render deploy orchestration — `render_deploy_preflight.py`, `trigger_render_deploy.py`, `blue_green_deploy.py`, `disaster_recovery_test.py`, `generate_firebase_config.py`.
**Created for:** Multi-account Render deploys (4 accounts, 750h free each); DRY Phase 2-C3 migrated all scripts onto `scripts/lib/render_client.py` (SSOT).
**Key files:** `scripts/deploy/render_deploy_preflight.py`, `scripts/deploy/blue_green_deploy.py`, `scripts/lib/render_client.py`
**Check if working:** `python scripts/deploy/check_render.py` lists services; `python scripts/deploy/disaster_recovery_test.py --dry-run` exits 0.

### `scripts/advanced_analysis/` (25+ deep-analysis scripts)
**Purpose:** Heavy nightly audits — `bola_idor_detector.py`, `circular_import_mapper.py`, `dead_code_verified_finder.py`, `duplicate_logic_detector.py`, `hardcode_config_scanner.py`, `blocking_call_detector.py`.
**Created for:** Run by `scheduled-deep-audit.yml` nightly — these were the original "20+ steps per push" extracted out of `ci.yml`.
**Key files:** `scripts/advanced_analysis/bola_idor_detector.py`, `scripts/advanced_analysis/circular_import_mapper.py`, `scripts/advanced_analysis/dead_code_verified_finder.py`
**Check if working:** `python scripts/advanced_analysis/bola_idor_detector.py backend/` produces findings.

### `scripts/audit/`
**Purpose:** Repo-wide audit scanners — `system_deep_scan_2026_09_15.py`, `system_defect_scan_2026_09_16.py`, `generate_route_consumer_inventory.py`.
**Created for:** Date-stamped evidence generators (per audit round) — output to `docs/audits/evidence/<today>/`.
**Key files:** `scripts/audit/system_defect_scan_2026_09_16.py`, `scripts/audit/system_deep_scan_2026_09_15.py`
**Check if working:** `python scripts/audit/system_defect_scan_2026_09_16.py` writes `defect_scan_report.json`.

### `scripts/health/`
**Purpose:** System health diagnostics — `superai_health_check.py` (CPU/mem/disk, Python env, required env vars, DB, Redis, LLM, FastAPI).
**Created for:** Single `--deep` flag for full diagnostics; `--fix` auto-fixes common issues; `--json` for CI.
**Key files:** `scripts/health/superai_health_check.py`
**Check if working:** `python scripts/health/superai_health_check.py --quick` exits 0 with green checkmarks.

### `scripts/backup/`
**Purpose:** Backup/restore manager — `superai_backup_manager.py` (db, env, code, Redis, configs, logs), `auto_cross_cloud_replicate.py`.
**Created for:** Scheduled rotation; one-click restore with integrity verification; cross-cloud replication for DR.
**Key files:** `scripts/backup/superai_backup_manager.py`
**Check if working:** `python scripts/backup/superai_backup_manager.py create --components db,env` exits 0.

### `scripts/benchmark/` + `scripts/k6/`
**Purpose:** Load & performance benchmarking — `superai_load_tester.py` (LLM endpoint concurrency/throughput/percentiles), `k6/load_test.js`.
**Created for:** Before/after patch CPU impact measurement; `--compare` flag for baseline-vs-patched runs.
**Key files:** `scripts/benchmark/superai_load_tester.py`, `scripts/k6/load_test.js`
**Check if working:** `python scripts/benchmark/superai_load_tester.py --url http://localhost:8000/api/chat --concurrent 10 --requests 100`.

### `scripts/billing/`
**Purpose:** Multi-tenant quota enforcement — `quota_enforcer.py` (hard limits, auto-suspend, Slack/Discord alerts), `usage_reporter.py`, `fraud_detector.py`.
**Created for:** Free-tier abuse prevention + paid-tier compliance; `--enforce-all --dry-run` for safe audits.
**Key files:** `scripts/billing/quota_enforcer.py`, `scripts/billing/usage_reporter.py`
**Check if working:** `python scripts/billing/quota_enforcer.py --enforce-all --dry-run` lists tenants near/over quota.

### `scripts/monitoring/`
**Purpose:** Observability scripts — `sla_tracker.py` (SLO compliance), `cost_analyzer.py`, `capacity_planner.py`, `fetch_logs.py`, `superai_log_analyzer.py`.
**Created for:** SLA/SLO tracking across API + AI providers + DB + WebSocket + CI/CD; cost analysis; capacity planning for free-tier ceilings.
**Key files:** `scripts/monitoring/sla_tracker.py`, `scripts/monitoring/cost_analyzer.py`
**Check if working:** `python scripts/monitoring/sla_tracker.py --check` prints SLO compliance.

### `scripts/i18n/`
**Purpose:** Internationalization — `banglish_converter.py` (Banglish↔Bangla), `bangla_translator.py`, `rtl_support_checker.py`.
**Created for:** SupremeAI is bilingual (English + Bangla); Banglish support for code-mixed user input.
**Key files:** `scripts/i18n/banglish_converter.py`, `scripts/i18n/bangla_translator.py`
**Check if working:** `python scripts/i18n/banglish_converter.py --text "ami bhalo achi"` outputs Bangla script.

### `scripts/testing/`
**Purpose:** Test infrastructure — `mutation_testing.py` (mutation engine with parallel execution), `auto_test_generator.py`, `api_contract_validator.py`, `log_anomaly_detector.py`.
**Created for:** Mutation testing for test-suite quality; auto-test generation for new endpoints; log anomaly detection in CI runs.
**Key files:** `scripts/testing/mutation_testing.py`, `scripts/testing/api_contract_validator.py`
**Check if working:** `python scripts/testing/mutation_testing.py --target backend/core/config.py --threshold 80` produces report.

### `scripts/quality/`
**Purpose:** Continuous code quality — `auto_dead_code_remover.py` (vulture + radon), `auto_refactor_suggester.py`, `docs_drift_check.py`.
**Created for:** Auto-PR generation for dead code removal, refactors, coverage bumps; `CREATE_PR=true` opens a GitHub PR.
**Key files:** `scripts/quality/auto_dead_code_remover.py`, `scripts/quality/docs_drift_check.py`
**Check if working:** `python scripts/quality/auto_dead_code_remover.py` writes `dead_code_report.md`.

### `scripts/governance/`
**Purpose:** Architecture & plan governance — `architecture_check.py` (AST import-graph + Tarjan SCC cycle detection + boundary violations from `architecture-rules.yml`).
**Created for:** Detect silent circular imports / boundary violations; ratchet down violations baseline.
**Key files:** `scripts/governance/architecture_check.py`, `scripts/architecture_baseline.json`, `architecture-rules.yml`
**Check if working:** `python scripts/governance/architecture_check.py` exits 0 when violations ≤ baseline.

### `scripts/lib/render_client.py`
**Purpose:** SSOT Render API client (DRY Phase 2-C1, stdlib-only urllib) — `list_services`, `list_deploys`, `trigger_deploy`.
**Created for:** Eliminate 15 hand-rolled Render API clients; uniform retry policy.
**Key files:** `scripts/lib/render_client.py`
**Check if working:** `python -c "import sys; sys.path.insert(0,'scripts/lib'); from render_client import RenderClient"` returns JSON.

---

## CI/CD Workflows

### `.github/workflows/ci.yml` (CI Pipeline)
**Purpose:** Main CI — push/PR/dispatch triggers; SHA-pinned actions; coverage gates (`MIN_BACKEND_COVERAGE=30`, `MIN_FRONTEND_COVERAGE=16`); Node 24, Python 3.11.
**Created for:** Modularised v5.0 — heavy jobs extracted to reusable workflows; `find_stub_data.py` (stub-blocker) wired into CI.
**Key files:** `.github/workflows/ci.yml`, `scripts/find_stub_data.py`
**Check if working:** `gh run list --workflow=ci.yml --limit 5` shows green checkmarks.

### `.github/workflows/ci-deploy-production.yml`
**Purpose:** Reusable production deploy workflow — Render (4 accounts), Cloudflare Worker, live Alembic migration gate.
**Created for:** Called by `ci.yml` after Docker images published; `SUPABASE_DATABASE_URL_WRITER` declared `required: false` but gate ENFORCES by default.
**Key files:** `ci-deploy-production.yml`, `scripts/ci/render_trigger_deploy.py`
**Check if working:** Deploy logs show "🟢 DEPLOYMENT APPROVED" from `check_deploy_gate.py`.

### `.github/workflows/ci-docker.yml`
**Purpose:** Reusable Docker build/sign/publish + budget guard — builds core/scraper, pushes to GHCR, signs with Cosign, generates SBOM.
**Created for:** Supply-chain integrity — only runs if Render preflight passes; outputs `core-digest` + `core-tags`.
**Key files:** `ci-docker.yml`, `.github/actions/build-sign-image/action.yml`
**Check if working:** `gh run list --workflow=ci-docker.yml` green; `cosign verify ghcr.io/<repo>/supremeai-core` returns signature.

### `.github/workflows/ci-mcp-build.yml`
**Purpose:** Reusable MCP Control Tower build — `npm ci`, `npm run typecheck`, `npm run build`, lockfile reproducibility check.
**Created for:** INF-16 fix (#562) — pin Node 24 in BOTH CI and Dockerfile so Node 22+/24-only APIs don't pass CI but break at runtime.
**Key files:** `ci-mcp-build.yml`, `infrastructure/mcp-control-plane/package.json`
**Check if working:** `gh run list --workflow=ci-mcp-build.yml` green.

### `.github/workflows/ci-doctor.yml`
**Purpose:** Self-healing CI — opens/updates tracking issue on red main runs; auto-commits regenerated `docs/generated/` evidence; auto-closes issues when green.
**Created for:** "Silent red" gap — scheduled workflow failures were invisible before.
**Key files:** `ci-doctor.yml`, `.github/scripts/ci_smart_summary.py`
**Check if working:** Trigger a red run → CI Doctor opens an issue; fix the failure → CI Doctor auto-closes.

### `.github/workflows/maintenance.yml`
**Purpose:** Daily 02:00 + Mon 02:30 hygiene — smart CI failure summary, health check, DB schema check, auto-lint-fix PR, auto-dependency-upgrade PR.
**Created for:** Task 14-b honesty fix — `cancel-in-progress: false` (was true, so weekly cancelled nightly).
**Key files:** `maintenance.yml`, `.github/scripts/ci_smart_summary.py`
**Check if working:** `gh run list --workflow=maintenance.yml` shows daily runs.

### `.github/workflows/scheduled-deep-audit.yml`
**Purpose:** Daily 03:00 UTC heavy audit — dependency+SBOM scan, mutation testing, performance benchmark, duplicate-logic detector, `ci-full-audit.sh` (actionlint + trufflehog + gitleaks).
**Created for:** Extracted from `ci.yml`'s 20+ step pre-merge job — now nightly + manual only.
**Key files:** `scheduled-deep-audit.yml`, `scripts/ci-full-audit.sh`
**Check if working:** `gh run list --workflow=scheduled-deep-audit.yml` green.

### `.github/workflows/qa-live-smoke.yml`
**Purpose:** Daily 03:15 UTC live production smoke — two-layer probe: Layer A (customer chain: SPA + direct CORS call), Layer B (direct API health).
**Created for:** 2026-09-18 incident — Firebase Hosting doesn't support rewrite proxies, so SPA's same-origin probe was a ghost path.
**Key files:** `qa-live-smoke.yml`, `scripts/ci/production_smoke_test.py`
**Check if working:** `gh run list --workflow=qa-live-smoke.yml` green.

### `.github/workflows/e2e-suites.yml`
**Purpose:** Playwright E2E suites in one matrix workflow (issue #1261 merged the former `05-e2e-guest.yml` / `06-e2e-customer.yml` / `07-e2e-admin.yml` wrappers) — guest (PR + dispatch), customer (nightly 01:30 UTC + dispatch), admin (manual only).
**Created for:** Auth-credential dependency — customer suite needs `QA_CUSTOMER_*` secrets; admin needs `QA_ADMIN_*` + TOTP.
**Key files:** `e2e-suites.yml`, `reusable-e2e-runner.yml`
**Check if working:** `gh workflow run e2e-suites.yml` green; artifacts include Playwright HTML reports (`qa-guest-results`, `qa-customer-results`, `qa-admin-results`).

### `.github/workflows/08-production-preflight.yml` + `09-post-deploy-smoke.yml`
**Purpose:** Deploy gates — 08 (preflight: frontend build/typecheck/lint, `@smoke` Playwright, backend health contract); 09 (post-deploy canary).
**Created for:** P0/P1 fails block deploy; canary turns red on selector mismatch.
**Key files:** `08-production-preflight.yml`, `09-post-deploy-smoke.yml`
**Check if working:** Deploy pipeline calls both; canary verifies production URL.

### ~~`.github/workflows/deploy-firebase-hosting.yml`~~ (removed)
**Status:** Workflow removed in the Wave 3.5 consolidation (issue #1261) — it was dispatch-only and had no callers (never invoked by any workflow or script), so it was dead weight in the Actions tab. History preserved in git; runbook kept at `docs/deployment/FIREBASE_HOSTING_CI.md`.
**Key files:** `scripts/deploy/generate_firebase_config.py` (still used by other build scripts)

### `.github/workflows/db-retention.yml`
**Purpose:** Daily 03:30 prune `evolution_logs` older than 30d via `prune_evolution_logs()` SQL.
**Created for:** Prevent table bloat on free-tier Postgres (500MB cap).
**Key files:** `db-retention.yml`
**Check if working:** `gh run list --workflow=db-retention.yml` green; logs show `Deleted N rows from evolution_logs`.

### `.github/workflows/dast-zap.yml`
**Purpose:** Weekly Mon 05:30 OWASP ZAP scan against `STAGING_BASE_URL`.
**Created for:** Issue #707 — DAST moved from Mon 04:00 to 05:30 to avoid collision with audit-release.
**Key files:** `dast-zap.yml`
**Check if working:** `gh run list --workflow=dast-zap.yml` shows weekly green; uploads SARIF artifact.

### `.github/workflows/constitution-governance.yml`
**Purpose:** Weekly Mon 06:17 + PR path-triggered; validates `exceptions.yml` expiry + runs constitution rule tests (7 deterministic rules).
**Created for:** Constitution rules (ARCH-001, REL-001, REL-002, SEC-001, SEC-002, SEC-003, CFG-001) must be deterministic + tested.
**Key files:** `constitution-governance.yml`, `.github/scripts/constitution/engine.py`, `.github/constitution/rules.yml`
**Check if working:** `PYTHONPATH=.github/scripts python -m unittest discover -s .github/scripts/constitution/tests -v` exits 0.

### `.github/workflows/keepalive.yml`
**Purpose:** Manual-only (`workflow_dispatch: {}`) free-tier pinger — pings 4 Render health endpoints.
**Created for:** Originally scheduled, deliberately downgraded to manual — "scheduled pings must not be used to bypass free-tier sleeping limits."
**Key files:** `keepalive.yml`
**Check if working:** `gh workflow run keepalive.yml` — run log shows `PING <url>: HTTP 200` for each of 4 services.

### `.github/actions/build-sign-image/` (composite action)
**Purpose:** Reusable Docker build pipeline — Docker Buildx + GHCR login + metadata-action + build-push-action + Cosign signing + SBOM.
**Created for:** Used by `ci-docker.yml` for both core and scraper images; outputs `digest` and `tags`.
**Key files:** `.github/actions/build-sign-image/action.yml`
**Check if working:** Workflow calling this action shows `digest` output; `cosign verify` succeeds.

### `.github/actions/setup-frontend/` + `setup-backend/` + `setup-playwright/`
**Purpose:** Reusable environment setup — Node 24 + PNPM 10.15.0 / Python 3.11 + Poetry 2.4.1 / browser cache + Playwright.
**Created for:** PERF (#470 Layer-2) — probe apt packages with `dpkg -s` before `apt-get update` (saves ~18-20s per matrix job).
**Key files:** `.github/actions/setup-frontend/action.yml`, `.github/actions/setup-backend/action.yml`, `.github/actions/setup-playwright/action.yml`
**Check if working:** Workflows show "✅ Poetry/Pip cache HIT" in step summary.

### `.github/scripts/constitution/` (engine + tests + rules)
**Purpose:** 7 deterministic Constitution rules — ARCH-001 (no local-machine in prod code), REL-001 (no silent failure), SEC-002 (no secret hardcoding), etc.
**Created for:** Per-PR diff audit (only changed files scanned); reporters for console + GitHub step summary.
**Key files:** `.github/scripts/constitution/engine.py`, `.github/scripts/constitution/rules/*.py`, `.github/constitution/rules.yml`
**Check if working:** `PYTHONPATH=.github/scripts python -m unittest discover -s .github/scripts/constitution/tests -v` exits 0.

### `.github/scripts/service_preflight_check.py`
**Purpose:** CI startup gate — validates external service credentials (Render Primary + Backup, Vercel, Firebase) BEFORE expensive jobs run.
**Created for:** Repo-aware gating — `GITHUB_REPOSITORY` detects production main repo; only there does Render/Vercel fail block. Forks warn-only.
**Key files:** `.github/scripts/service_preflight_check.py`
**Check if working:** CI log shows `[PREFLIGHT] Render Primary: ✅ Vercel: ✅ Firebase: ⚠️` on main repo.

### `.github/dependabot.yml`
**Purpose:** Dependabot opens weekly PRs for pip (backend), npm (root), monthly for github-actions.
**Created for:** AUD-7.5 — Dependabot was entirely absent; added with reviewers + `dependencies`/`security` labels.
**Key files:** `.github/dependabot.yml`
**Check if working:** `gh pr list --label dependencies` shows recent Dependabot PRs.

---

## Root Configs

### `vercel.json`
**Purpose:** Vercel deployment config — Vite framework, custom build command, output `frontend/dist`.
**Created for:** SPA fallback (`rewrites: /(.*) → /index.html`) + strict CSP + asset immutability (`Cache-Control: max-age=31536000, immutable` on `/assets/*`).
**Key files:** `vercel.json`, `scripts/ci/verify_frontend_build_contract.py`
**Check if working:** `vercel build` succeeds; deployed URL returns correct CSP headers.

### `turbo.json`
**Purpose:** Turborepo task pipeline — `build`, `test`, `lint`, `typecheck`, `dev`, plus per-package overrides.
**Created for:** Monorepo build ordering — frontend build waits for shared-types, shared-services, design-tokens, ui-components, core-infrastructure.
**Key files:** `turbo.json`, `pnpm-workspace.yaml`
**Check if working:** `pnpm turbo run build --filter=frontend...` succeeds with cache hits.

### `pnpm-workspace.yaml`
**Purpose:** PNPM workspace declaration — `packages/*`, `frontend`, `apps/mission-control`, `tools/vscode-extension`.
**Created for:** 2026-09-17 cleanup — `apps/mission-control` joined workspace; `apps/docs` intentionally kept outside.
**Key files:** `pnpm-workspace.yaml`, `pnpm-lock.yaml`
**Check if working:** `pnpm install --frozen-lockfile` succeeds; `pnpm -r ls --depth -1` lists all packages.

### `architecture-rules.yml`
**Purpose:** Data-file holding cross-circle forbidden imports — `backend/memory` ↔ `backend/brain`, both blocked from `backend/core/browser_session_manager.py`.
**Created for:** M11 Phase-1 zero-hardcode — rules previously lived as in-code dict; rule change no longer requires code change.
**Key files:** `architecture-rules.yml`, `scripts/governance/architecture_check.py`
**Check if working:** `python scripts/governance/architecture_check.py` exits 0 when no violations.

### `secrets_registry.yaml`
**Purpose:** Catalog of every secret — name, criticality per environment (github-actions, infisical-vault, render-admin, render-backend), note.
**Created for:** Single source of truth for "which secret goes where" — 1194 lines covering all secrets.
**Key files:** `secrets_registry.yaml`, `scripts/security/secrets_rotation_manager.py`
**Check if working:** `python -c "import yaml; print(len(yaml.safe_load(open('secrets_registry.yaml'))['keys']))"` returns count.

### `firebase.template.json`
**Purpose:** Firebase config template — Firestore rules + indexes, Hosting targets (`user` + `admin` both serving `frontend/dist`), SPA rewrites, cache headers, CSP.
**Created for:** Idempotent Firebase Hosting deploys via `scripts/deploy/generate_firebase_config.py`.
**Key files:** `firebase.template.json`, `scripts/deploy/generate_firebase_config.py`, `config/firestore.rules`
**Check if working:** `firebase deploy --only hosting --dry-run` validates; deployed URL returns CSP + cache headers.

### `mkdocs.yml`
**Purpose:** MkDocs Material site config — site_name, dark/light palette, plugins (search, swagger-ui-tag, gen-files, literate-nav).
**Created for:** Auto-generated API docs from OpenAPI spec + Mermaid diagram support.
**Key files:** `mkdocs.yml`, `scripts/generate_api_docs.py`
**Check if working:** `mkdocs serve` boots; `/api/v1/` page renders Swagger UI.

### `.pre-commit-config.yaml`
**Purpose:** Local pre-commit Iron Curtain — pre-commit-hooks (YAML/JSON/TOML/debug-statement/private-key), gitleaks v8.30.1, local hooks (secret-hunter, API-contract-check, ruff, mypy, ESLint, blindspot-scan, stub-data-blocker, actions-pin-checker, env-mode-guard, critical-invariant-guard on pre-push).
**Created for:** Forensic V8 fix — previous `gitleaks` hook was wrongly listed under `pre-commit/pre-commit-hooks` repo, so pre-commit env init failed silently.
**Key files:** `.pre-commit-config.yaml`, `packages/scripts/security_guard.py`
**Check if working:** `pre-commit run --all-files` exits 0 after fixes.

### `.gitleaks.toml`
**Purpose:** Custom gitleaks rules — `render-api-key` (`rnd_[a-zA-Z0-9]{16,}`) + `supremeai-key` (`sk-sup(?:reme)?-[a-zA-Z0-9]{20,}`) at HIGH severity.
**Created for:** Built-in detectors auto-enable; this file adds Render + SupremeAI key formats + minimizes false positives.
**Key files:** `.gitleaks.toml`
**Check if working:** `gitleaks detect --config .gitleaks.toml --source . --no-banner` exits 0 on clean tree.

### `.actionlint.json`
**Purpose:** Actionlint config — bash shell `[bash, --noprofile, --norc, -eo, pipefail, {0}]`, required permissions (`contents: read`).
**Created for:** Enforce least-privilege permissions across all workflows; fail CI if a workflow requests more than `contents: read`.
**Key files:** `.actionlint.json`
**Check if working:** `actionlint` exits 0.

### `.env.example`
**Purpose:** Environment variable template — core (ENV, PORT, SERVICE_ROLE), CORS origins, JWT/encryption secrets, backend URLs, all provider keys.
**Created for:** Mandatory AI Agent Directive header — agents MUST fetch `.agents/rules/supremeai_universal_guardian.md` before any operation.
**Key files:** `.env.example`, `.agents/rules/supremeai_universal_guardian.md`
**Check if working:** `cp .env.example .env && python scripts/bootstrap_env.py` populates missing keys.

---

## Tricks & Patterns Index

### Trick: Redis Federation Pool
**What:** Multiple sibling free-tier Upstash accounts (`REDIS_SECONDARY_URL` … `REDIS_QUINARY_URL`) form a federation pool; on quota exhaustion, failover rotates to next pool.
**Why:** 5 accounts × 10k cmd/day = 50k/day at $0; consumers never degrade to in-memory fallback unless ALL pools exhausted.
**File:** `backend/core/cache/redis_manager.py:69-77` (env keys), `:191-230` (`_try_failover`)
**Check:** Set `REDIS_SECONDARY_URL` to 2nd account, exhaust primary quota → log shows `Redis federation pool 1/N QUOTA EXHAUSTED — failed over to pool 2/N`.

### Trick: Secret Vault Caching (`_get_cached_secret`)
**What:** Settings layer exposes `_get_cached_secret(key)` — checks `os.getenv`, then Infisical vault's bulk-loaded in-memory cache (5-min TTL); zero network calls post-warmup.
**Why:** Redis federation pool, health probes, and LLM gateway all need sibling-account URLs that live ONLY in Infisical; bulk cache avoids per-request API quota burn.
**File:** `backend/core/cache/redis_manager.py:103-118`; vault cache at `backend/core/security/secret_vault.py:99-110`
**Check:** `settings._get_cached_secret("REDIS_SECONDARY_URL")` returns value < 1ms after first call (cache hit).

### Trick: Circuit Breaker Pattern (canonical)
**What:** Centralized `CircuitBreaker` with three-state enum (`CLOSED`/`OPEN`/`HALF_OPEN`) and `normalize_circuit_state()` for cross-implementation vocabulary unification.
**Why:** Codebase has 5+ breaker implementations with different state spellings; normalization keeps Redis-persisted state comparable.
**File:** `backend/core/resilience/circuit_breaker.py:24-62` (enum + normalizer), `core/resilience/circuit_breaker_manager.py` (shared singleton)
**Check:** `CircuitBreaker("x", failure_threshold=3).call(failing_fn)` raises `CircuitBreakerOpenError` after 3 failures.

### Trick: Origin Shield Middleware (#781)
**What:** Cloudflare Worker adds `X-Origin-Verify-Key: <secret>` header; backend middleware timing-safe-compares; direct `.onrender.com` hits lack header → 403.
**Why:** Render free-tier forces `ipAllowList=0.0.0.0/0`; without Origin Shield, anyone hitting the raw URL bypasses Cloudflare WAF/edge.
**File:** `backend/core/middleware/origin_shield.py:77-122`; Worker at `infrastructure/cloudflare_worker.js`
**Check:** In prod, `curl https://<app>.onrender.com/api/v1/anything` → 403; via Cloudflare Worker → 200.

### Trick: Test-Auth-Bypass Guard
**What:** `AuthMiddleware` allows bypassing JWT auth ONLY when `is_test_environment() AND settings.is_bypass_allowed` both true; production always returns False.
**Why:** Test suite needs to hit endpoints without JWTs, but bypass must never be reachable in prod even if env misconfigured.
**File:** `backend/core/security/authentication/auth_middleware.py:219-243`
**Check:** With `ENV=production`, even setting `SUPREMEAI_BYPASS_ALLOWED=true` → middleware still rejects.

### Trick: Zero-Cost Mode
**What:** In-process async queue + Upstash Redis free tier + self-healing adaptive circuit breaker + performance learning engine; total infra cost $0/month.
**Why:** Render free tier (512MB, 1 instance) + Upstash free tier (10k req/day) → must avoid Celery/RQ workers, paid Redis, synchronous blocking.
**File:** `backend/core/zero_cost_architecture/zero_cost_patch_phase1_4.py`, `api/routes/zero_cost.py`
**Check:** `GET /api/v1/zero-cost/health` returns `redis_connected: true` + queue metrics.

### Trick: Auto-Migration (Alembic at Boot)
**What:** At FastAPI lifespan startup, `scripts.db.auto_migrate.run_migrations` runs synchronously in a thread before serving requests; gated by `AUTO_MIGRATE=true` (default).
**Why:** Live schema never drifts from application code; production migration failure crashes boot (fail-closed).
**File:** `backend/core/startup/services.py:76-89`
**Check:** Boot log: `🔄 Running automatic Alembic migrations...` then `✅ ...completed.`

### Trick: LLM Provider Key Pool
**What:** `_ProviderKeyPool` splits comma-joined multi-key env strings (`GEMINI_API_KEY=k1,k2,k3`) into individual keys, rotates round-robin, puts key on cooldown after 401/403/429.
**Why:** Previously the raw `"k1,k2,k3"` string was sent as one API key → every provider call 401 → fallback chain was dead.
**File:** `backend/core/llm/llm_gateway/registry.py:57-100`
**Check:** `await gateway._get_api_key_for_model("groq/llama-3.1-8b-instant")` returns one key; after 401, key on cooldown 5min.

### Trick: Health Endpoint Design (`/health` vs `/live` vs `/ready`)
**What:** Three-tier split — `/health` (deep, 503 if degraded), `/ready` (readiness, role-aware, schema-gated), `/live` (cheap liveness, always 200).
**Why:** K8s/Render probes need different signals: liveness must be cheap; readiness can fail-closed on schema drift; deep health surfaces subsystem latency.
**File:** `backend/api/routes/health.py:43-114` (`/health`), `:117-197` (`/ready`), `:200-203` (`/live`)
**Check:** `curl /live` → 200 `{"alive": true}` with no DB call; `curl /ready` → 200 with `schema.checked=true`.

### Trick: Atomic Single-Op Rate Limiting (Upstash Quota Burn Fix)
**What:** 4-command Redis pipeline (INCR + EXPIRE + TTL check + conditional EXPIRE) collapsed into ONE `EVAL` Lua script — 1 billable op instead of 4 (75% saving).
**Why:** Upstash bills every pipeline command; old stack burned ~12 ops/request → 3k bot requests/day exhausted quota in ~14 days.
**File:** `backend/core/cache/rate_limit_atomic.py:28-50` (`ATOMIC_WINDOW_LUA` + `atomic_window_incr`)
**Check:** `await atomic_window_incr(client, "rl:k1", 60)` returns window count in 1 Redis op.

### Trick: Anti-Suppression Error Pipeline (`@with_error_bus`)
**What:** `@with_error_bus("component")` decorator wraps sync/async functions — on exception, emits structured `ErrorEvent` to `error_event_bus` then re-raises.
**Why:** Codebase audit found bare `except Exception: pass` blocks silently dropping failures; decorator enforces observable failure.
**File:** `backend/core/error_bus.py:18-50` (decorator), `backend/core/messaging/event_bus.py:29-60`
**Check:** Decorate a function that raises `ValueError("x")` → `error_event_bus` subscriber receives `ErrorEvent`.

### Trick: Cloudflare Worker KV Binding (edge rate limiting)
**What:** `[[kv_namespaces]]` binding `SUPREMEAI_KV` in `wrangler.toml` — required by `cloudflare_worker.js` `getKV()` for `ratelimit:<ip>` counters (120 req/min/IP).
**Why:** INF-10 fix — previously declared ZERO KV bindings, so `getKV()` always returned null and rate limiting silently no-op'd.
**File:** `infrastructure/wrangler.toml`, `infrastructure/cloudflare_worker.js:16-21`
**Check:** `wrangler kv namespace list` shows the namespace; worker `/health` returns 200.

### Trick: Multi-account Render Federation (4 workspaces, 750h each)
**What:** `wrangler.toml` `[vars]` declares 4 backend role URLs (PRIMARY/WORKER/SCRAPER/MCP), each on separate Render free-tier account (750h/month each).
**Why:** Render free tier caps one service at 750h/month (~31 days), insufficient for 24/7 multi-service. Federation pools 4×750h = 3000h/month.
**File:** `infrastructure/wrangler.toml`, `infrastructure/mcp-control-plane/src/lib/env.ts`
**Check:** `env.render.primary.apiKey`, `env.render.worker.apiKey` all return non-empty; `getBackends()` returns 4 entries.

### Trick: Migration-Gate (Alembic offline mode + writer endpoint)
**What:** `backend/alembic_migrations/env.py` prefers `SUPABASE_DATABASE_URL_WRITER` (direct Postgres, not PgBouncer) for DDL; `ci-deploy-production.yml` enforces by default.
**Why:** Issue #517 — PgBouncer transaction-mode rejects `ALTER TABLE` and migration locking statements.
**File:** `backend/alembic_migrations/env.py`, `.github/workflows/ci-deploy-production.yml`
**Check:** `cd backend && SUPABASE_DATABASE_URL_WRITER=... alembic upgrade head` succeeds; CI deploy `migration-gate` step shows "✅ passed".

### Trick: SHA-Pinned Actions
**What:** Every `uses:` in `.github/workflows/*.yml` pinned to full 40-char commit SHA — `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`.
**Why:** Trap #95 — unpinned `@v3` tags can be re-pointed by a compromised maintainer; SHA pinning makes supply-chain attacks detectable.
**File:** `.github/workflows/*.yml`, `scripts/ci/check_actions_pinning.py`
**Check:** `python scripts/ci/check_actions_pinning.py .github/workflows/*.yml` exits 0.

### Trick: Vite sourcemap hidden strategy
**What:** Production builds set `sourcemap: false` (not `'hidden'`).
**Why:** `'hidden'` only strips the `//# sourceMappingURL=` comment — `.map` files were still emitted and uploaded by Vercel, leaking original TS/TSX source.
**File:** `frontend/vite.config.ts:197`
**Check:** `ls frontend/dist/assets/*.map` returns nothing after `pnpm build`.

### Trick: Service Worker cache strategy
**What:** SW (`public/sw.js`) only caches same-origin fingerprinted assets (8+ hex hash); never caches HTML, `/api/*`, `/admin-api/*`, or third-party domains.
**Why:** Stale index.html across deployments would point to old bundles; API responses cached cause CORS/staleness.
**File:** `frontend/public/sw.js:1-87`
**Check:** DevTools → Application → Service Workers shows `supremeai-pwa-cache-v4`.

### Trick: Token storage (sessionStorage + in-memory, legacy migration)
**What:** User token and admin JWT stored in `sessionStorage` + in-memory cache; legacy `localStorage` entries swept on read and removed.
**Why:** Issue #521 (FE-04) — XSS exposure window for `localStorage` is unlimited; `sessionStorage` cleared on tab close.
**File:** `frontend/src/services/tokenStorage.ts:47-91`
**Check:** After login, `sessionStorage.getItem('supremeai_auth_token')` returns JWT; `localStorage.getItem(...)` returns null.

### Trick: API base resolution (relative path logic)
**What:** `getApiBaseUrl(path)` returns `''` (relative) when `VITE_USE_RELATIVE_PATH==='true'`, otherwise resolves runtime-context-aware backend.
**Why:** Firebase Hosting has no external rewrite proxy — must use direct backend URL (CORS allow); Vercel/Docker use relative paths + reverse proxy.
**File:** `frontend/src/utils/api.ts:178-195`
**Check:** With `VITE_USE_RELATIVE_PATH=true`, `apiClient.get('/api/v1/health/live')` hits same-origin path.

### Trick: Firebase init.json fetch fallback
**What:** `initFirebase()` first tries `fetch('/__/firebase/init.json')` (served by Firebase Hosting); if missing, falls back to `VITE_FIREBASE_*` env vars.
**Why:** Firebase Hosting deployments auto-serve init.json; non-Firebase hosts must inject via env; eager init prevents "No Firebase App" race.
**File:** `frontend/src/firebase.ts:7-39`
**Check:** On localhost, `initFirebase()` throws if env vars missing; in production with env set, resolves cleanly.

### Trick: Auth frame on WebSocket (first-message auth)
**What:** WS connections open without credentials in URL; first `onopen` sends `{"type":"auth","token":"<bearer>"}`; backend closes with code 4001 if missing.
**Why:** Security audit S-2 — token in URL query is recorded in browser history, server access logs, and proxy logs.
**File:** `frontend/src/utils/secureWebSocket.ts:44-67`, `frontend/src/commandcenter/realtime/websocketManager.ts:55-63`
**Check:** Open `/workspace` and watch WS frame inspector — first frame after upgrade is `{"type":"auth","token":"…"}`; URL has no `?token=`.

### Trick: React Query shared singleton via SharedProviders
**What:** `@supremeai/ui-components`' `SharedProviders` instantiates ONE `QueryClient` with smart retry (no retry on 401/403/429, max 2 retries, exponential backoff + jitter).
**Why:** FINAL-TEST FIX — duplicate `<QueryClientProvider>` in `App.tsx` and `SharedProviders` created nested duplicate caches.
**File:** `packages/ui-components/src/contexts/SharedProviders.tsx:7-46`
**Check:** `useQueryClient()` returns same instance; 401 response triggers zero retries.

### Trick: JIT OTP injection via X-JIT-OTP header
**What:** `apiClient.performSensitiveAction(path, body, otpCode)` injects `X-JIT-OTP: <code>` header; backend response 202 Accepted means OTP required.
**Why:** Phase 2 Hybrid Fingerprint Login — JIT OTP challenge happens in-line on sensitive operations without full re-auth.
**File:** `frontend/src/services/apiClient.ts:470-481`
**Check:** POSTing sensitive action without OTP returns `{success:false, requiresOTP:true}`.

### Trick: X-Request-ID correlation ID
**What:** Every apiClient call injects `X-Request-ID: <uuid>`; backend echoes it back in response header and structured logs.
**Why:** Issue #685 — user-reported failures can be matched to backend structured logs / LLM telemetry with one id end-to-end.
**File:** `frontend/src/services/apiClient.ts:160-161, 344-352`
**Check:** `curl -v /api/v1/auth/me` response has `X-Request-ID` header.

### Trick: Anti-sleep heartbeat (Render cold-start prevention)
**What:** In PROD, `main.tsx` calls `startAntiSleepHeartbeat()` — pings `/api/v1/live` 10s after load, then every 10 minutes.
**Why:** Render free tier sleeps after 15 min idle; `/api/v1/live` is process-liveness only (no Redis/DB touch).
**File:** `frontend/src/services/heartbeat.ts:6-40`
**Check:** Console logs `[Heartbeat] ✅ Live: …/api/v1/live` every 10 min.

### Trick: manualChunks vendor splitting
**What:** `build.rollupOptions.output.manualChunks(id)` buckets react|react-dom → `vendor-react`, framer-motion|lucide → `vendor-ui`, @xyflow → `vendor-flow`, @tanstack/react-query → `vendor-query`.
**Why:** Circular import bug — react-dom previously landed in `vendor-flow` causing `Cannot set properties of undefined (setting 'Activity')` boot crash.
**File:** `frontend/vite.config.ts:171-189`
**Check:** `ls frontend/dist/assets/vendor-react-*.js` exists; react chunk < 200KB and loads first.

### Trick: Multi-account rotator
**What:** `MultiAccountRotator` rotates API keys/accounts across whitelisted providers (`groq`, `deepseek`, `google_ai_studio`, `openai`, `anthropic`, `cohere`) with per-account cooldown/rate-limit tracking.
**Why:** Distributes free-tier quotas across many keys so a single account's TPM/RPM ceiling doesn't throttle the system.
**File:** `backend/tools/security_tools/multi_account_rotator.py:18`
**Check:** `python -c "from tools.security_tools.multi_account_rotator import ALLOWED_PROVIDERS; print(sorted(ALLOWED_PROVIDERS))"`.

### Trick: Agent loop limiter
**What:** Hard ceiling on agent iteration count + per-run token count, enforced by a `BudgetGuard`-style lock.
**Why:** Prevents runaway agentic loops (infinite tool-call / re-plan cycles) from burning free-tier quota.
**File:** `backend/core/orchestration/agent_orchestrator.py:13-14` (`MAX_AGENT_TOKENS`, `MAX_AGENT_ITERATIONS`), `backend/core/config_fields.py:490` (default `max_agent_iterations=5`)
**Check:** `python -c "from core.config import settings; print(settings.max_agent_iterations)"` prints `5`.

### Trick: Sandbox code execution (E2B-inspired)
**What:** Isolated code-execution sandbox with optional E2B bridge plus local subprocess-isolation fallback; 256 KB output cap, 30s timeout.
**Why:** AI-generated code must not touch host filesystem or external network — fail-closed isolation regardless of `e2b` dep installed.
**File:** `backend/integrations/e2b_adapter.py`
**Check:** `SUPREMEAI_E2B_ENABLED=false python -c "from integrations import E2BAdapter; E2BAdapter().run('print(1)')"` returns from local fallback.

### Trick: BYOC (Bring Your Own Cloud)
**What:** Per-tenant GCP service-account encryption (Fernet) + Terraform-driven Cloud Run container orchestration.
**Why:** Tenants bring their own GCP credentials so their skills run in their own billing/quota boundary; creds encrypted at rest.
**File:** `backend/byoc/cloud_connector.py` (Fernet from `ENCRYPTION_KEY`), `backend/byoc/container_orchestrator.py` (real `terraform init && terraform apply`)
**Check:** `pytest tests/byoc/ -q`.

### Trick: WebSocket auth (first-message handshake)
**What:** Fail-closed WS auth helper supporting both `ws://host/path?token=<jwt>` and `{"type":"auth","token":"<jwt>"}` first-message handshake.
**Why:** FastAPI `AuthMiddleware` only guards `http` scopes — every WS endpoint historically drifted and several accepted unauthenticated connections.
**File:** `backend/core/security/ws_auth.py:35-57` (`authenticate_websocket`)
**Check:** `rg -n "authenticate_websocket" backend/` shows every WS endpoint calling the helper.

### Trick: Evolution forge / self-learning
**What:** `ForgeCompiler.compile_and_sort` linearizes a React-Flow DAG into a topologically-sorted execution sequence; `evaluate_promotion` is the evidence-backed gate.
**Why:** Self-evolution needs (a) deterministic plan compilation and (b) an evidence gate that blocks promotion until sandbox benchmark + canary + integrity all pass.
**File:** `backend/engine/forge_compiler.py:7-9`, `backend/ecosystem/evolution_gate.py:31`
**Check:** `python -c "from engine.forge_compiler import ForgeCompiler; print(ForgeCompiler.compile_and_sort([], []))"`.

### Trick: Scout pattern (zero-token crawler)
**What:** Zero-token policy-driven crawler — `APPROVED_DOMAINS` allowlist → `PolicyEngine` SSRF check → `ContentDeduplicator` (SHA-256 + Jaccard ≥ 0.80) → `ExtractiveSummarizer` (sentence-salience, no LLM).
**Why:** Web ingestion must be safe (SSRF guard), cheap (no LLM calls), and idempotent (dedup).
**File:** `backend/scout/policy.py`, `backend/scout/dedup.py`, `backend/scout/extractor.py`
**Check:** `pytest tests/scout_tests/ -q`.

### Trick: Adaptive engine (capability registry)
**What:** Capability registry with full lifecycle FSM (`IDEA → DISCOVERED → PROPOSED → APPROVED → BUILDING → VALIDATING → ACTIVE → MEASURED → PROMOTE/ARCHIVE`) and Hot/Warm/Cold tiers.
**Why:** Prevents capability explosion by forcing `REUSE > ADAPT > EXTEND > CREATE` lookups before any new capability is approved.
**File:** `backend/adaptive_engine/capability_registry.py`, `backend/adaptive_engine/governance.py`
**Check:** `python -c "from adaptive_engine.capability_registry import CapabilityLifecycleState; print(list(CapabilityLifecycleState))"`.

### Trick: Knowledge graph (Neo4j) fail-closed
**What:** `GraphService` over Neo4j Aura free-tier async driver; **fail-closed dry-run mode** when `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD` missing or mock-prefixed.
**Why:** Earlier code assumed `localhost`/`neo4j` defaults — silently connecting to non-existent DB; BE-14 made it fail-closed.
**File:** `backend/tools/graph_service.py:7-38`
**Check:** `NEO4J_URI= python -c "from tools.graph_service import GraphService; print(GraphService().dry_run)"` prints `True`.

### Trick: Triple vector backend (Qdrant/ChromaDB/pgvector)
**What:** `ExperienceDatabase` probes for `chromadb`, `qdrant_client`, `sentence_transformers` at boot; on Render free-tier (no persistent disk), falls back to Supabase pgvector.
**Why:** Render free-tier sleeps and loses local ChromaDB/Qdrant state on every cold-start; pgvector in already-provisioned Supabase DB preserves learned experiences across restarts.
**File:** `backend/adaptive_engine/experience_db.py`, `backend/adaptive_engine/supabase_vector_backend.py`
**Check:** `LOW_MEMORY_MODE=true python -c "from adaptive_engine.experience_db import ExperienceDatabase; print(ExperienceDatabase().vector_backend_degraded)"` prints `True`.

### Trick: COOP/COEP cross-origin isolation for WebContainer
**What:** Vite dev/preview and nginx both set `Cross-Origin-Opener-Policy: same-origin` + `Cross-Origin-Embedder-Policy: require-corp`; values env-overridable.
**Why:** ERR-A04 — `@webcontainer/api` requires `window.crossOriginIsolated === true`; without it the sandbox prints "Sandbox unavailable in this preview".
**File:** `frontend/vite.config.ts:140-156`, `frontend/nginx.conf:35-36`
**Check:** DevTools → Console → `self.crossOriginIsolated` returns `true`.

### Trick: Build-contract fail-fast for missing backend URL
**What:** `vite.config.ts` throws on production build if `UNIFIED_BACKEND` is empty AND `VITE_USE_RELATIVE_PATH!=='true'`; also throws if URL is loopback.
**Why:** FE-07 — bare `console.warn` shipped a Vercel bundle with `USER_BACKEND_URL=''`; every apiClient call hit catch-all rewrite and white-screened.
**File:** `frontend/vite.config.ts:42-84`
**Check:** `NODE_ENV=production vite build` without env vars exits non-zero.

### Trick: Concurrency groups + `cancel-in-progress: false`
**What:** Every scheduled workflow has `concurrency: { group: <name>-<ref>, cancel-in-progress: false }`.
**Why:** Task 14-b — `maintenance.yml` originally had `cancel-in-progress: true`, so Monday 02:30 weekly cron cancelled the 02:00 nightly. `false` makes the second run queue.
**File:** `.github/workflows/maintenance.yml`, `scheduled-deep-audit.yml`, `qa-live-smoke.yml`, etc.
**Check:** `gh run list --workflow=maintenance.yml` shows both 02:00 and 02:30 runs as completed.

### Trick: `additional_contexts` for backend-in-mcp-image
**What:** `docker-compose.yml` service `mcp` declares `build: { context: ./infrastructure/mcp-control-plane, additional_contexts: { backend: ./backend } }`. Dockerfile `COPY --from=backend . ./backend/`.
**Why:** R-05 fix — backend/ was previously bind-mounted at runtime (empty on hostless deploys). Baking backend/ into the image means MemorySubAdapter always finds `mcp_server.py`.
**File:** `docker-compose.yml` (service `mcp`), `infrastructure/mcp-control-plane/Dockerfile`
**Check:** `docker run --rm supremeai/mcp ls /app/backend/memory/mcp_server.py` returns the file.

### Trick: Free-tier size guard (Render/GitHub/Vercel/Firebase)
**What:** `.pre-commit-config.yaml` `free-tier-size-guard` hook runs `scripts/ci/check_free_tier_limits.py` per commit — checks Render (500MB), GitHub Actions (8GB), Vercel (100MB), Firebase (1GB). 80% → warning, 95% → commit block.
**Why:** Free-tier overage causes silent deploy failures; pre-commit catches bloat before CI/CD.
**File:** `.pre-commit-config.yaml`, `scripts/ci/check_free_tier_limits.py`
**Check:** `python scripts/ci/check_free_tier_limits.py` exits 0 with green per-service percentages.

### Trick: `ENV=production` local blocker + critical-invariant pre-push guard
**What:** `.pre-commit-config.yaml` runs `env_mode_guard.py` on pre-commit (blocks `ENV=production` in local `.env`) and `check_critical_invariants.py` on pre-push.
**Why:** Prevents accidental local prod-mode runs (which could hit prod secrets) and silent regression of critical security modules when rebasing.
**File:** `.pre-commit-config.yaml` (env_mode_guard + critical-invariant-guard hooks)
**Check:** `echo "ENV=production" >> .env && git commit -m test` is blocked by `env-mode-guard`.

---

*Document generated 2026-09-20. Total: ~193 module entries + ~60 tricks across the entire SupremeAI codebase. Every entry has a concrete "Check if working" step for future verification.*
