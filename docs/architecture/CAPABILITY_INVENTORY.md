# Capability Inventory — Integrations, Providers & External Dependencies

> **Scope:** This inventory catalogs every **integration adapter, LLM provider, external service dependency, and adoptable external repo** in SupremeAI — classified by **governance tier** (Internal / Governed Provider / Research Source / Rejected).
>
> **Why this exists:** The Ecosystem Intelligence Roadmap v2 (`docs/architecture/ECOSYSTEM_INTELLIGENCE_ROADMAP.md`) requires a single source-of-truth that the Ecosystem Scout (#4055), Capability Evaluation Engine (#4047), and Policy Engine (#4049) can cross-reference. Without it, "do we already have this capability?" cannot be answered mechanically — and Rule 4 (Evidence Before Adoption) collapses to guesswork.
>
> **Relationship to `docs/CAPABILITY_INVENTORY.md` (issue #1101):** That inventory covers **product capability surfaces** (auth, chat, llm-gateway as features). This inventory covers **integration/provider/external-dep governance** — different lens, cross-referenced. Together they form the complete picture.
>
> **Machine-readable companion:** `docs/architecture/inventory.yaml` — the Scout pipeline diffs against this, not the Markdown.
>
> **CI guard:** `scripts/agents/inventory_lint.py` — fails if a new adapter/provider file appears under `backend/integrations/` or `backend/core/llm/providers/` without a matching inventory entry.

---

## Governance Tier Classification

| Tier | Definition | Routing | Health-check | Replaceability |
|---|---|---|---|---|
| 🟢 **Internal** | Native SupremeAI capability — core code, no external service dependency | Direct call | Self (in-process) | N/A — it IS the capability |
| 🔵 **Governed Provider** | External service behind the Capability Router + Policy Engine; health-checked, policy-gated, fallback-documented | Router → Policy → Provider | `service_topology.py` tri-state | Documented replacement path; can swap without code change |
| 🟡 **Research Source** | External repo/concept studied for ideas but NOT integrated; no runtime dependency | N/A (read-only research) | N/A | N/A — not adopted |
| ⛔ **Rejected** | Evaluated and explicitly rejected; rationale recorded to prevent re-audit | N/A | N/A | N/A |
| 🟠 **Orphaned** | Code exists but has zero live callers; awaiting audit (Revive / Retire decision) | N/A until audit completes | N/A | Audit决定 |

---

## 1. Integration Adapters (`backend/integrations/`)

| Adapter | File | Tier | Status | Flag | Health Check | Fallback | Owner Issue |
|---|---|---|---|---|---|---|---|
| Browser Use | `browser_use_adapter.py` | 🟠 Orphaned | Awaiting audit (#4044) | `SUPREMEAI_BROWSER_USE_ENABLED` | None (orphaned) | Jina Reader → Firecrawl → WebScraper (zero-cost chain) | #4044 |
| OpenHands | `openhands_adapter.py` | 🟠 Orphaned | Awaiting audit (#4045) | `SUPREMEAI_OPENHANDS_ENABLED` | None (orphaned) | "skipped + planner" → normal chat route | #4045 |
| mem0 | `mem0_adapter.py` | 🟠 Orphaned | Retire-planned (#4057) | (none — importlib probe) | None | keyword-cosine + consolidation (zero-cost) | #4057 |
| E2B | `e2b_adapter.py` | 🟠 Orphaned | Retire-planned (#4057) | (none) | None | `sandbox/docker_sandbox.py` (native) | #4057 |
| Graphiti | `graphiti_adapter.py` | 🟠 Orphaned | Retire-planned (#4057) | `SUPREMEAI_GRAPHITI_ENABLED` | None | timestamped episode triples + recency/keyword ranking | #4057 |
| Telegram Bot | `telegram_bot.py` | 🟢 Internal | Active (MESH-4, #942) | (env-driven) | `service_topology.py` (if registered) | N/A — native | #942 |
| Telegram Handlers | `telegram_handlers.py` | 🟢 Internal | Active (MESH-4, #942) | (env-driven) | N/A (pure logic layer) | N/A — native | #942 |
| Telegram Config | `telegram_config.py` + `telegram_config.yaml` | 🟢 Internal | Active (MESH-4, #942) | (env-driven) | N/A | N/A — native | #942 |
| GitHub Webhook | `github_webhook.py` | 🟢 Internal | Active (MESH-7, #962) | (env-driven) | HMAC verify; 503 if unsigned | N/A — native | #962 |

### Orphaned Adapter Audit Status (Phase 1.2)
- **Browser Use** (#4044): Audit IN PROGRESS — hypothesis: revive as governed browser provider (escalation: HTTP → Playwright → Browser Use). Decision pending evidence.
- **OpenHands** (#4045): Audit IN PROGRESS — hypothesis: revive as coding execution provider (SupremeAI = orchestrator, OpenHands = executor). Decision pending evidence.
- **mem0 / E2B / Graphiti** (#4057): Retire planned — redundant with native MemoryRepository + pgvector + sandbox + episodic memory. Awaiting #4043 completion to confirm no live caller.

### Shared Integration Helpers
- `backend/integrations/_flags.py` — `flag(name)` + `import_available(module)` helpers (feature-flag + optional-import pattern, matches `services/memory_service.py` convention).
- `backend/integrations/__init__.py` — exports the 5 orphaned adapter classes.

---

## 2. LLM Providers (`backend/core/llm/`)

### 2.1 Provider Registry (canonical source: `backend/core/llm/llm_gateway/registry.py`)

The `_MODEL_KEY_MAP` dict is the **single source of truth** for provider → settings-attribute mapping. Adding a provider = adding a row here (no code duplication).

| Provider | Settings Attr | API Base | Tier | Status | Retired Models |
|---|---|---|---|---|---|
| groq | `groq_api_key` | (default) | 🔵 Governed Provider | Active | — |
| gemini | `gemini_api_key` | (default) | 🔵 Governed Provider | Active | `gemini-2.0-flash`, `gemini-1.5-pro`, `gemini-1.5-flash` (retired 2026-09-13) |
| openai / gpt | `openai_api_key` | (default) | 🔵 Governed Provider | Active | — |
| deepseek | `deepseek_api_key` | `https://api.deepseek.com/v1` | 🔵 Governed Provider | Active | — |
| openrouter | `openrouter_api_key` | (default) | 🔵 Governed Provider | Active | — |
| hf / huggingface | `hf_api_key` | (default) | 🔵 Governed Provider | Active | — |
| nvidia | `nvidia_api_key` | (default) | 🔵 Governed Provider | Active | — |
| moonshot | `MOONSHOT_API_KEY` | (default) | 🔵 Governed Provider | Active | — |
| together | `TOGETHER_API_KEY` | (default) | 🔵 Governed Provider | Active | — |
| ollama | `OLLAMA_API_KEY` | (local) | 🔵 Governed Provider (local) | Active | — |
| hf_space | `HF_API_KEY` | (default) | 🔵 Governed Provider | Active | — |
| bynara | `bynara_api_key` | `https://router.bynara.id/v1` | 🔵 Governed Provider (zero-cost router) | Active — admin-verified (#3080 risk review) | — |
| bai | `bai_api_key` | `https://api.b.ai/v1` | 🔵 Governed Provider (zero-cost router) | Active — admin-verified (#3080) | — |
| mistral | `mistral_api_key` | (default) | 🔵 Governed Provider | Active | — |
| anthropic | `ANTHROPIC_API_KEY` | `https://api.anthropic.com` | 🔵 Governed Provider | Active (prompt caching via PLAN-001) | — |

### 2.2 Rejected Providers (do NOT re-add)
- **v0** (`v0.dev`): Removed in #3076 — `api.v0.dev/v1` returns HTTP 404; v0.dev has no public OpenAI-compatible API. Fallback-walk only wasted time.

### 2.3 Provider Adapters (`backend/core/llm/providers/`)
| Adapter | File | Tier | Purpose |
|---|---|---|---|
| Cloud Adapter | `cloud_adapter.py` | 🟢 Internal | Anthropic prompt caching (PLAN-001), OpenAI-compatible cloud providers |
| Ollama Adapter | `ollama_adapter.py` | 🟢 Internal | Local Ollama execution (governed provider, local tier) |

### 2.4 Provider Routing Layer
- `backend/core/llm/provider_registry.py` — runtime provider registry (#3214); capability-based selection (TEXT/VISION/TOOL_CALLING/REASONING/EMBEDDING); `ProviderHealth.AVAILABLE/UNAVAILABLE`; `NoCompatibleProviderError` (fail-honest, no silent fallback).
- `backend/core/llm/provider_router.py` — routing logic.
- `backend/core/llm/advanced_model_router.py` — advanced routing (32KB, capability + cost + latency aware).
- `backend/core/llm/llm_gateway/` — gateway package (`completion.py`, `routing.py`, `resilience.py`, `spend_meter.py`, `streaming.py`, `registry.py`, `gateway.py`, `http_client.py`, `litellm_runtime.py`, `context.py`, `errors.py`).

### 2.5 Provider Key Pool (security-critical)
- `backend/core/llm/llm_gateway/registry.py` → `_ProviderKeyPool` — multi-key rotation (comma-joined env vars split + round-robin + cooldown). Cooldown escalation for auth errors: 5min → 1h → 24h (cap). This is the **single shared instance** — no duplicate key pools anywhere else.

### 2.6 Token Budget + Telemetry
- `backend/core/llm/token_budget.py` — token budget management (20KB).
- `backend/core/llm/token_deductor.py` — token counting/deduction (13KB).
- `backend/core/llm/telemetry.py` — provider call telemetry (11KB).
- `backend/core/llm/free_tier_tracker.py` — free-tier quota tracking (17KB).
- `backend/core/llm/distributed_budget.py` — distributed budget coordination (2.9KB).

---

## 3. External Service Dependencies (wired into `service_topology.py`)

Source: `backend/api/routes/service_topology.py` → `COMPLETE_SERVICE_REGISTRY` (14 services).

| Service | Category | Critical | Health Check | Tier | Status |
|---|---|---|---|---|---|
| Render Backend | infrastructure | ✅ | `/api/v1/health` (15s timeout — cold start) | 🔵 Governed Provider | Active |
| Render Admin API | infrastructure | ✅ | `/api/v1/health` (15s) | 🔵 Governed Provider | Active |
| Scraper Microservice | infrastructure | ❌ | `/health` (10s) | 🔵 Governed Provider | Active |
| Supabase Database | database | ✅ | `/rest/v1/` (api check, 8s) | 🔵 Governed Provider (core DB) | Active — env-driven URL (#3226) |
| Firebase Auth | auth | ✅ | `/v1/projects/{id}:lookup` (8s) | 🔵 Governed Provider | Active — env-driven project-id (#3226) |
| Cloud Firestore | database | ✅ | `/v1/projects/{id}/databases/...` (8s) | 🔵 Governed Provider | Active — env-driven (#3226) |
| Cloudflare Edge Worker | edge | ✅ | `/health` (5s) | 🔵 Governed Provider | Active (env `EDGE_WORKER_URL`) |
| Cloudflare DNS | edge | ❌ | DNS query (5s) | 🔵 Governed Provider | Active |
| GitHub API | ci_cd | ❌ | `/rate_limit` (8s) | 🔵 Governed Provider | Active |
| GitHub Actions CI | ci_cd | ❌ | HTTP check (10s) | 🔵 Governed Provider | Active |
| Vercel Deployment | ci_cd | ❌ | `/v2/deployments` (8s) | 🔵 Governed Provider | Active (flakiness tracked #3694) |
| Krogger Monitoring | monitoring | ❌ | `/v1/status` (6s) | 🔵 Governed Provider | Active |
| Sentry Error Tracking | monitoring | ❌ | `/projects/` (6s) | 🔵 Governed Provider | Active |
| Infisical Secrets Manager | secrets | ✅ | `/v1/secrets` (6s) | 🔵 Governed Provider (critical — secret source) | Active |

### Service Topology Honest-Status Pattern (#3225 / #3226)
- `ServiceStatus` enum: `HEALTHY` / `DEGRADED` / `UNHEALTHY` / `UNKNOWN` / `MAINTENANCE` / `SKIPPED`
- `_has_unresolved_placeholder()` — detects `<project-ref>`, `<project-id>`, `<your-`, `<env>`, `<todo>` tokens → probe SKIPPED (not false-UNHEALTHY). Critical: configured ≠ broken.
- 401 (AUTH_INVALID) classified as WARN not FAIL per #3260 / #3288.

---

## 4. Memory & Learning Capabilities

| Component | File | Tier | Status | Purpose |
|---|---|---|---|---|
| Memory Repository | `backend/core/ai_memory/repository.py` | 🟢 Internal | Active (canonical) | pgvector-backed persistent memory (single source of truth per Rule 5) |
| Episodic Memory | `backend/memory/episodic_memory.py` | 🟢 Internal | Active | Time-ordered episode storage |
| Long-Term Memory | `backend/memory/long_term_memory.py` | 🟢 Internal | Active | Consolidated long-term store |
| Memory Consolidator | `backend/evolution/memory_consolidator.py` | 🟢 Internal | Active | Episodic → long-term promotion |
| Experience DB | `backend/adaptive_engine/experience_db.py` | 🟢 Internal | Active | Experience/learning storage |
| Learning Pipeline | `backend/evolution/learning_pipeline.py` | 🟢 Internal | Active | Pattern mining from decisions (Phase 5.3 will extend) |
| Experience | `backend/learning/experience.py` | 🟢 Internal | Active | Experience record model |
| Pattern Detector | `backend/learning/pattern_detector.py` | 🟢 Internal | Active | Pattern mining |
| Evidence Analyzer | `backend/learning/evidence_analyzer.py` | 🟢 Internal | Active | Evidence analysis |
| Outcome Analyzer | `backend/learning/outcome_analyzer.py` | 🟢 Internal | Active | Outcome analysis |
| ChromaDB Store | `backend/memory/chromadb_store.py` | 🟢 Internal | Active (optional) | Local vector store alternative |
| SQLite Store | `backend/memory/sqlite_store.py` | 🟢 Internal | Active | SQLite-backed memory |
| Sliding Window | `backend/memory/sliding_window.py` | 🟢 Internal | Active | Context window management |
| Checkpoint Resume | `backend/memory/checkpoint_resume.py` | 🟢 Internal | Active | Checkpoint/resume support |
| RAG Pipeline | `backend/memory/rag_pipeline.py` | 🟢 Internal | Active | RAG retrieval |
| Memory MCP Server | `backend/memory/mcp_server.py` | 🟢 Internal | Active | Memory via MCP |

---

## 5. MCP (Model Context Protocol)

| Component | File | Tier | Status | Purpose |
|---|---|---|---|---|
| MCP Client | `backend/brain/mcp_client.py` | 🟢 Internal | Active | MCP client (brain layer) |
| MCP Server (stdio KG) | `backend/tools/mcp/mcp_server.py` | 🟢 Internal | Active | stdio knowledge-graph MCP |
| MCP Cloud Deploy | `backend/tools/mcp/mcp_cloud_deploy.py` | 🟢 Internal | Active | Cloud deploy MCP |
| MCP GitHub CI/CD | `backend/tools/mcp/mcp_github_cicd.py` | 🟢 Internal | Active | GitHub CI/CD MCP |
| MCP IDE Trio | `backend/tools/mcp/mcp_ide_trio.py` | 🟢 Internal | Active | IDE integration MCP |
| MCP Neon | `backend/tools/mcp/mcp_neon.py` | 🟢 Internal | Active | Neon DB MCP |
| MCP Observability | `backend/tools/mcp/mcp_observability.py` | 🟢 Internal | Active | Observability MCP |
| MCP Supabase | `backend/tools/mcp/mcp_supabase.py` | 🟢 Internal | Active | Supabase MCP |
| MCP Telegram | `backend/tools/mcp/mcp_telegram.py` | 🟢 Internal | Active | Telegram MCP |
| MCP Workspace | `backend/tools/mcp/mcp_workspace.py` | 🟢 Internal | Active | Workspace MCP |

---

## 6. Deploy & CI/CD (`scripts/deploy/`)

| Script | Purpose | Tier |
|---|---|---|
| `render_*.py` (6 scripts) | Render service management (check, create, list, rollback, suspend-guard, auto-deploy) | 🟢 Internal |
| `blue_green_deploy.py` | Blue-green deployment | 🟢 Internal |
| `canary_deploy.py` | Canary deployment | 🟢 Internal |
| `disaster_recovery_test.py` | DR rehearsal | 🟢 Internal |
| `infrastructure_as_code_validator.py` | IaC validation | 🟢 Internal |
| `rollback_rehearsal_preflight.py` | Rollback preflight | 🟢 Internal |
| `add_secrets_to_infisical.py` | Infisical secret injection | 🟢 Internal |
| `generate_firebase_config.py` | Firebase config gen | 🟢 Internal |

---

## 7. Agent System (`scripts/agents/`)

| Script | Purpose | Tier |
|---|---|---|
| `continuous_agent_loop.py` | Main agent loop (CLAIM → WORK → VERIFY → PR → EXIT) | 🟢 Internal |
| `agent_identity.py` | Git-push-CAS identity + role lock + cooldown | 🟢 Internal |
| `rules_breaker.py` | Scanner (Team Leader pattern — #3973) | 🟢 Internal |
| `ecosystem_learning.py` | Ecosystem learning (predecessor of Phase 5.3) | 🟢 Internal |
| `credential_manager.py` | Infisical credential minting | 🟢 Internal |
| `agent_dashboard.py` | Agent dashboard | 🟢 Internal |
| `heartbeat_ping.py` | Agent heartbeat | 🟢 Internal |
| `gh_label_ensure.py` | GitHub label management | 🟢 Internal |
| `create_issue.py` | Issue creation helper | 🟢 Internal |
| `acquire_role_slot.py` | Role slot acquisition | 🟢 Internal |
| `dynamic_credential_broker.py` | Dynamic credential broker | 🟢 Internal |
| `dynamic_naming.py` | Dynamic branch naming | 🟢 Internal |
| `dispatch_browser_task.py` | Browser task dispatcher | 🟢 Internal |
| `check_slot_registry_drift.py` | Slot registry drift check | 🟢 Internal |
| `agent_trace.py` | Agent trace | 🟢 Internal |
| `agent_solution_memory.py` | Agent solution memory | 🟢 Internal |
| `issue_fingerprint.py` | Issue fingerprinting (dedup) | 🟢 Internal |
| `group_taxonomy.py` | Group taxonomy | 🟢 Internal |
| `a2a_messaging_bus.py` | Agent-to-agent messaging | 🟢 Internal |

---

## 8. External Repos Analyzed for Ecosystem Intelligence (Roadmap v2)

> These are external repos studied for adoption ideas. **NONE are runtime dependencies** — they are 🟡 Research Sources until evidence-based adoption (Rule 4) completes.

| # | Repo | Category | Tier | Action | Priority | Owner Issue |
|---|---|---|---|---|---|---|
| 1 | Browser Use | Browser automation | 🟠 Orphaned (audit) | Audit → Revive/Retire | P1 | #4044 |
| 2 | OpenHands | Coding agent | 🟠 Orphaned (audit) | Audit → Revive/Retire | P1 | #4045 |
| 3 | OpenViking | Hierarchical context | 🟡 Research Source | Adapt L0/L1/L2 tier concepts | P1 | #4051 |
| 4 | Agent-Reach | Ecosystem scout | 🟡 Research Source | Prototype as Scout data layer | P1 | #4055 |
| 5 | Cerebras | Speed-optimized LLM | 🟡 Research Source | Add as governed provider | P2 | #4048 |
| 6 | agentmemory | Decision metadata | 🟡 Research Source | Adapt decision metadata model | P2 | #4052 |
| 7 | DuckDB | Analytics engine | 🟡 Research Source | Workload-driven adoption (P3) | P3 | #4056 |
| 8 | Memanto | Memory governance | 🟡 Research Source | Adapt policy-driven TTL concepts | P3 | #4053 |
| 9 | Strata | Local inference | 🟡 Research Source | Benchmark vs llama.cpp | P4 | #4060 |
| 10 | Colibrì | VRAM/RAM staging | 🟡 Research Source | Research only | P4 | #4060 |
| 11 | Dify | Workflow UX | 🟡 Research Source | Reference only | P3 | — |
| 12 | Excalidraw | UI visualization | 🟡 Research Source | Mission Control viz (if gap) | P3 | #4059 |
| 13 | Metatron | Security sandbox | 🟡 Research Source | Research only | P3 | #4058 |
| 14 | LibreChat | Chat UX | 🟡 Research Source | Reference only | P4 | #4061 |
| 15 | Anarlog | Voice/meeting | 🟡 Research Source | Future | P4 | — |
| 16 | Screego | WebRTC screen-share | 🟡 Research Source | Peripheral | P4 | — |
| 17 | Node.js Best Practices | Security knowledge | 🟡 Research Source | Auditor knowledge source | P4 | — |
| 18 | PocketBase | Local edition backend | 🟡 Research Source | Local Edition research | P4 | #4062 |
| 19 | Appwrite | BaaS | ⛔ Rejected | Over-engineering risk — do NOT add | — | — |
| 20 | HackProduct | Productivity | ⛔ Rejected | Weak recommendation — read only | — | — |
| 21 | Supabase | BaaS | 🟢 Internal (already core) | No action — already canonical | — | — |
| 22 | Qdrant | Vector DB | 🟢 Internal (covered) | pgvector = primary; Qdrant = specialized if needed | — | — |
| 23 | Vite | Frontend bundler | 🟢 Internal (already used) | No action | — | — |
| 24 | anthropic-tools | Tooling | ⛔ Rejected | Archived + deprecated (#4063) | — | #4063 |

---

## 9. Mission Control (`apps/mission-control/`)

| Component | Path | Tier | Status |
|---|---|---|---|
| Mission Control App | `apps/mission-control/` | 🟢 Internal | Active (Next.js + Prisma) |
| Admin API surface | `backend/api/routes/admin*.py` + `backend/admin/` | 🟢 Internal | Active |

---

## 10. Cross-References

- **Product capability surfaces** (auth, chat, llm-gateway as features): `docs/CAPABILITY_INVENTORY.md` (issue #1101) + `docs/capability_inventory.json` + `scripts/ci/validate_capability_inventory.py`
- **Module status registry** (orphaned modules — escrow, rider/delivery, diagram parser, etc.): `docs/operations/MODULE_STATUS_REGISTRY.md` (issue #449)
- **Ecosystem Intelligence Roadmap v2**: `docs/architecture/ECOSYSTEM_INTELLIGENCE_ROADMAP.md` (PR #4042)
- **Service topology honest-status pattern**: #3225 / #3226 / #3260 / #3288
- **Provider key pool security pattern**: `_ProviderKeyPool` in `backend/core/llm/llm_gateway/registry.py`
- **Team Leader scanner pattern**: #3973 (`scripts/agents/rules_breaker.py`)

---

## 11. Inventory Maintenance Protocol (Rule 4 — Evidence Before Adoption)

### Adding a new integration adapter
1. Add file under `backend/integrations/`
2. Add row to `inventory.yaml` (machine-readable) with: `name`, `file`, `tier`, `status`, `flag`, `health_check`, `fallback`, `owner_issue`
3. Add row to Section 1 table above (human-readable)
4. CI guard `scripts/agents/inventory_lint.py` must pass (fails if adapter file exists without inventory entry)

### Adding a new LLM provider
1. Add row to `_MODEL_KEY_MAP` in `backend/core/llm/llm_gateway/registry.py`
2. If OpenAI-compatible non-default base: add to `_PROVIDER_API_BASES`
3. Add row to `inventory.yaml` Section 2 + Markdown Section 2.1
4. If retired models exist: add to `_RETIRED_MODELS` set
5. CI guard passes if registry entry exists without inventory row → fails (catches drift)

### Adopting an external repo (Roadmap v2 Rule 4)
1. Discovery: Scout pipeline (#4055) discovers repo
2. Capability inventory check: does SupremeAI already have this capability? (cross-reference `inventory.yaml`)
3. Gap analysis: is this a real gap?
4. Benchmark: correctness + latency + cost + security (Evaluation Engine #4047)
5. Security review
6. Maintenance cost assessment
7. Decision: Adopt / Adapt / Reference / Reject
8. If Adopt: add as Governed Provider (Section 1 or 2), wire health check, document fallback, Policy Engine gate
9. If Reject: add to Section 8 with `⛔ Rejected` tier + rationale (prevents re-audit)

---

*Generated: 2026-10-06 · Issue #4043 · Verified against `main` @ d958940 · Companion: `inventory.yaml` · CI guard: `scripts/agents/inventory_lint.py`*
