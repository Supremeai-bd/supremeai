# 🏛️ SupremeAI 2.0 — চূড়ান্ত বাস্তবায়ন পরিকল্পনা (v3 — Tooling Finalized)
### Source: `docs/-01-admin's plan/next step/` — 15-Step Master Blueprint
### Status: ✅ ALL DECISIONS LOCKED — READY FOR EXECUTION

---

## ✅ Design Decisions (All Locked)

| Question | Decision |
|---|---|
| **VPN/Proxy** | Hybrid: Free proxies default, Premium (Bright Data) for sensitive ops only |
| **P2P Credits** | Credit/Reputation system + **Global Kill-Switch (default: OFF)** |
| **BYOC Phase 1** | GCP-only (existing infra) |
| **Evolution Branch** | `feature/auto-<timestamp>` → HITL → `develop` (never direct to `main`) |
| **Model Gateway** | **LiteLLM** — single interface for 100+ models |
| **Agentic Flow** | **LangGraph** for stateful loops, **CrewAI** for multi-agent crews |
| **Vector DB** | **ChromaDB** (local/dev) + **Qdrant** (production scale) |
| **BYOC IaC** | **Terraform** for GCP resource provisioning |
| **Observability** | **LangSmith** (AI traces) + **Prometheus + Grafana** (system metrics) |

---

## 🗺️ Tooling Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    SupremeAI 2.0 — Tool Stack               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🧠 AI LAYER                                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  LiteLLM Gateway  ←── single API for 100+ models    │  │
│  │  ├── Ollama (local, free)                            │  │
│  │  ├── OpenRouter (free tier)                          │  │
│  │  ├── Gemini Flash / Pro                              │  │
│  │  ├── GPT-4o / GPT-4o-mini                           │  │
│  │  └── DeepSeek / Mistral / Claude                    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  🤖 AGENTIC LAYER                                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  LangGraph  ←── Stateful loops (self-healing, HITL) │  │
│  │  CrewAI     ←── Multi-agent crews (Master Planner)  │  │
│  │  ├── AuditorAgent  (cost & performance audit)        │  │
│  │  ├── CoderAgent    (patch generation)                │  │
│  │  ├── TesterAgent   (sandbox test runner)             │  │
│  │  └── PlannerAgent  (proposal generation)             │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  🗄️ MEMORY LAYER                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ChromaDB  ←── local/dev semantic search             │  │
│  │  Qdrant    ←── production vector search              │  │
│  │  SQLite/Firestore ←── structured data                │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ☁️ INFRASTRUCTURE LAYER                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Terraform  ←── GCP resource provisioning (BYOC)    │  │
│  │  K3s        ←── (Phase 2) lightweight Kubernetes     │  │
│  │  Docker     ←── sandbox containers (Step 7)          │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  📊 OBSERVABILITY LAYER                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  LangSmith     ←── AI decision trace & reasoning    │  │
│  │  Prometheus    ←── metrics collection               │  │
│  │  Grafana       ←── metrics visualization            │  │
│  │  Sentry (✅)   ←── error tracking (already active)  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Dependency Status Table

| Tool | Already in `pyproject.toml`? | Action |
|------|------------------------------|--------|
| `prometheus-client` | ✅ YES (`^0.20.0`) | Wire to Grafana only |
| `chromadb` | ✅ YES (`^0.4.0`, ml group) | Use in Experience DB |
| `qdrant-client` | ✅ YES (`^1.9.0`, ml group) | Use in production |
| `sentence-transformers` | ✅ YES (ml group) | Vector embeddings |
| `playwright` + `playwright-stealth` | ✅ YES (tools group) | Browser stealth (Step 6) |
| `docker` SDK | ✅ YES (tools group) | Sandbox (Step 7) |
| `boto3` | ✅ YES (tools group) | AWS (Phase 2 BYOC) |
| `litellm` | ❌ MISSING | **Add to core deps** |
| `langgraph` | ❌ MISSING | **Add to ml group** |
| `crewai` | ❌ MISSING | **Add to ml group** |
| `langsmith` | ❌ MISSING | **Add to tools group** |
| `grafana` | N/A (external service) | Docker Compose setup |
| `terraform` | N/A (CLI tool) | `infrastructure/terraform/` |

### `pyproject.toml` additions needed:
```toml
[tool.poetry.dependencies]
# নতুন AI গেটওয়ে — সব মডেলের জন্য একটি ইন্টারফেস
litellm = "^1.40.0"

[tool.poetry.group.ml.dependencies]
# অটোনোমাস এজেন্টিক ফ্লো-র জন্য
langgraph = "^0.2.0"
crewai = "^0.80.0"

[tool.poetry.group.tools.dependencies]
# AI সিদ্ধান্ত ট্রেসিং-এর জন্য
langsmith = "^0.1.0"
```

---

## 🔷 Layer 1: Foundation & Security (Steps 1–3)

---

### Step 1 — CI/CD Pipeline Optimization
**Status:** ✅ Partially Built | **New Tool:** None

#### [MODIFY] `.github/workflows/monorepo_ci_cd.yml`
```diff
+ - name: Cache pip/pnpm dependencies
+   uses: actions/cache@v4
+ - name: Smoke test post-deploy
+   run: curl -f ${{ secrets.CLOUD_RUN_URL }}/health || exit 1
+ - name: Discord deploy notification
+   uses: sarisia/actions-status-discord@v1
+   with: { webhook: ${{ secrets.DISCORD_WEBHOOK }} }
```

#### [NEW] `scripts/setup_ci_runner.py`

---

### Step 2 — User Profiling & Goal Alignment
**Status:** ⚠️ Missing | **New Tool:** LiteLLM (for intent classification)

#### [NEW] `backend/core/user_profiler.py`
```python
# ব্যবহারকারীর লক্ষ্য বিশ্লেষণ করে মোড নির্ধারণ
# LiteLLM দিয়ে fast local model ব্যবহার করে classification
import litellm

class UserProfiler:
    MODES = ["FAST_TRACK", "LEARNING", "PRODUCTION"]
    
    async def classify_user(user_id: str) -> UserProfile
    async def update_from_history(user_id: str, task: Task) -> None
```

#### [MODIFY] [adaptive_engine/intent_parser.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/adaptive_engine/intent_parser.py)
- Add `extract_goal(prompt) -> UserGoal` using LiteLLM local model

#### [MODIFY] [api/routes/onboarding.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/api/routes/onboarding.py)
- `POST /onboarding/profile`, `GET /onboarding/mode`

---

### Step 3 — Human-in-the-Loop (HITL) Approval ⚡ BUILD FIRST
**Status:** ❌ Missing | **New Tool:** LangGraph (approval state machine)

> [!IMPORTANT]
> HITL must be built first. Every step that involves autonomous action (VPN switch, evolution patch, domain crawl) routes through this gate.

#### LangGraph State Machine for HITL:
```python
# LangGraph দিয়ে HITL অ্যাপ্রুভাল স্টেট মেশিন
from langgraph.graph import StateGraph

# States: PENDING → [APPROVED | REJECTED] → EXECUTED | CANCELLED
hitl_graph = StateGraph(HITLState)
hitl_graph.add_node("await_approval", await_human_input)
hitl_graph.add_node("execute", execute_task)
hitl_graph.add_node("cancel", cancel_task)
hitl_graph.add_conditional_edges("await_approval", route_by_decision)
```

#### [NEW] `backend/api/approval_manager.py`
- Queue: `CODE_PUSH`, `NEW_SITE_VISIT`, `SKILL_GENERATION`, `VPN_SWITCH`, `AUTO_EVOLUTION_PATCH`
- Endpoints: `GET /hitl/pending`, `POST /hitl/approve/{id}`, `POST /hitl/reject/{id}`
- WebSocket `/ws/hitl` for real-time admin alerts

#### [NEW] `backend/models/pending_tasks.py`
- Fields: `task_id` (UUID), `task_type`, `payload` (JSON), `status`, `created_at`, `resolved_by`

#### [MODIFY] [api/routes/admin_dashboard.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/api/routes/admin_dashboard.py)
- HITL feed + WebSocket notifications

#### [MODIFY] Studio Client — `AdminConsole.tsx`
- Approval panel with real-time badge counter

---

## 🔷 Layer 2: Brain & Efficiency (Steps 4–7)

---

### Step 4 — Experience Database (Vector Memory)
**Status:** ✅ Built (isolated) | **New Tool:** ChromaDB + Qdrant (already in deps!)

> [!TIP]
> ChromaDB & Qdrant are **already in `pyproject.toml`** (ml group). Just wire them to the experience_db module.

#### Architecture:
```
Prompt → sentence-transformers embedding → ChromaDB (dev) / Qdrant (prod)
       → cosine similarity search → if score > 0.85 → return cached solution
       → else → call external AI → save result back to vector DB
```

#### [MODIFY] [adaptive_engine/experience_db.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/adaptive_engine/experience_db.py)
```python
# sentence-transformers দিয়ে embedding, ChromaDB-তে স্টোর
from sentence_transformers import SentenceTransformer
import chromadb  # dev | qdrant_client for prod

class ExperienceDB:
    async def find_similar(prompt: str, threshold: float = 0.85) -> Optional[Experience]
    async def save_outcome(prompt: str, result: str, metadata: dict) -> None
    async def get_collection_stats() -> DBStats
```

#### [MODIFY] [core/semantic_cache.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/core/semantic_cache.py)
- Hook `find_similar()` as first cache layer before any LiteLLM call

#### [NEW] `backend/core/decision_engine.py`
- Pipeline: Experience DB → Semantic Cache → LiteLLM (cheapest route)
- **LangSmith** trace every decision path for observability

---

### Step 5 — Smart Cost-Optimization Engine
**Status:** ⚠️ Partial | **New Tool:** LiteLLM (replaces per-provider custom code!)

> [!IMPORTANT]
> **LiteLLM is the biggest code-complexity reducer here.** Instead of 15 different provider clients, one LiteLLM call handles routing, fallback, and cost tracking automatically.

#### LiteLLM Integration Pattern:
```python
# একটি কলেই সব মডেলে পৌঁছানো যাবে — আলাদা কোড দরকার নেই
import litellm

litellm.set_verbose = True  # LangSmith-এ লগ পাঠাবে
litellm.success_callback = ["langsmith"]
litellm.failure_callback = ["langsmith", "sentry"]

response = await litellm.acompletion(
    model="ollama/llama3.2",   # স্বয়ংক্রিয়ভাবে সঠিক provider বেছে নেবে
    messages=[{"role": "user", "content": prompt}],
    fallbacks=["openrouter/mistral-7b", "gemini/gemini-flash"]
)
```

#### [NEW] `backend/engine/cost_optimizer.py`
```python
# LiteLLM-এর উপরে complexity-based routing layer
class CostOptimizer:
    ROUTE_LADDER = [
        "ollama/llama3.2",           # score 1-3: $0
        "openrouter/mistral-7b-free", # score 4-6: $0
        "gemini/gemini-flash",        # score 7-8: ~$0.001/1K
        "openai/gpt-4o-mini",         # score 9-10: premium
    ]
    async def get_optimal_route(task: Task, user_mode: str) -> str
```

#### [MODIFY] [core/free_tier_tracker.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/core/free_tier_tracker.py)
- Add `is_free_available(provider: str) -> bool`

#### [NEW] `backend/utils/api_tracker.py`
- Hook into LiteLLM callbacks for automatic cost logging

---

### Step 6 — Autonomous Networking (VPN/Proxy — Hybrid)
**Status:** ✅ Base exists | **New Tool:** `playwright-stealth` (already in deps!)

**Decision:** Free proxies (pubproxy) default → Premium (Bright Data) for payment/KYC ops → HITL-gated switch.

#### [MODIFY] [tools/vpn_switcher.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/tools/vpn_switcher.py)
```python
# 429/403 ডিটেক্ট হলে HITL অনুমোদনের পর প্রক্সি সুইচ
async def rotate_on_block(status_code: int) -> ProxyConfig
async def get_free_proxy() -> ProxyConfig       # pubproxy.com/api
async def get_premium_proxy(use_case: str) -> ProxyConfig  # Bright Data, HITL-gated
```

#### [NEW] `backend/tools/browser_stealth.py`
```python
# playwright-stealth (already in deps) ব্যবহার করে fingerprint মাস্ক
from playwright_stealth import stealth_async

async def create_stealth_browser() -> BrowserContext
async def simulate_human_behavior(page: Page) -> None  # random delays, mouse jitter
```

#### [NEW] `config/proxy_list.json`
```json
{
  "free_providers": ["pubproxy.com/api", "api.proxyscrape.com"],
  "premium_providers": {
    "bright_data": { "enabled": false, "use_cases": ["payments", "kyc"] }
  },
  "rotation_strategy": "round_robin",
  "max_retries": 3,
  "hitl_required_for_premium": true
}
```

---

### Step 7 — Sandboxed Testing Logic
**Status:** ✅ Base exists | **New Tool:** LangGraph (healing retry loop)

#### LangGraph Self-Healing Loop:
```python
# LangGraph দিয়ে test-fail-fix-retry লুপ তৈরি
from langgraph.graph import StateGraph

heal_graph = StateGraph(HealingState)
heal_graph.add_node("run_tests", run_sandbox_tests)
heal_graph.add_node("analyze_error", analyze_with_litellm)
heal_graph.add_node("apply_fix", apply_patch)
heal_graph.add_node("escalate_hitl", send_to_approval_queue)

# লুপ: run → fail → analyze → fix → run (max 3 retries)
heal_graph.add_conditional_edges("run_tests", 
    lambda s: "escalate_hitl" if s.retries >= 3 else "analyze_error")
```

#### [NEW] `backend/scripts/self_healing_tests.py`
- Wraps LangGraph heal_graph execution
- Uses LiteLLM for error analysis (cheapest model)

#### [MODIFY] [tools/cloud_sandbox_orchestrator.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/tools/cloud_sandbox_orchestrator.py)
- `run_with_healing(code, tests) -> SandboxResult`

#### [NEW] `backend/core/error_remediation.py`
- Pattern match in Qdrant/ChromaDB error DB → LiteLLM patch generation

---

## 🔷 Layer 3: Distributed Ecosystem (Steps 8–10)

---

### Step 8 — Universal BYOC Hub (GCP Phase 1 with Terraform)
**Status:** ❌ New Module | **New Tool:** Terraform IaC

> [!IMPORTANT]
> **Terraform** provisions GCP resources automatically. When a user connects their GCP account, Terraform creates Cloud Run services, storage buckets, and networking — zero manual setup.

#### Terraform Architecture:
```
User connects GCP Service Account
        ↓
backend/byoc/cloud_connector.py
        ↓  
infrastructure/terraform/gcp/
  ├── main.tf          (Cloud Run service definition)
  ├── storage.tf       (GCS bucket for skill artifacts)
  ├── networking.tf    (VPC + firewall rules)
  └── variables.tf     (per-user variable injection)
        ↓
terraform apply → GCP resources created automatically
```

#### [NEW] `infrastructure/terraform/gcp/main.tf`
```hcl
# ইউজারের GCP অ্যাকাউন্টে অটো রিসোর্স তৈরি করা
resource "google_cloud_run_v2_service" "skill_runner" {
  name     = "supremeai-skill-${var.user_id}"
  location = var.region
  template {
    containers {
      image = var.skill_docker_image
    }
  }
}
```

#### [NEW] `backend/byoc/__init__.py`
#### [NEW] `backend/byoc/cloud_connector.py`
- GCP auth via Service Account JSON
- `ping() -> CloudStatus`, `list_resources() -> List[CloudResource]`

#### [NEW] `backend/byoc/resource_manager.py`
- Track per-user quota, region, spend
- `GET /byoc/status`, `GET /byoc/resources`

#### [NEW] `backend/byoc/container_orchestrator.py`
- Deploy via GCP Cloud Run API + Terraform apply
- Rolling updates + health checks + rollback

#### [MODIFY] Studio Client — `SettingsPage.tsx`
- "Connect Your Cloud" → GCP Service Account JSON upload
- Real-time resource gauge

---

### Step 9 — Skill Store & Auto-Configuration
**Status:** ⚠️ Backend partial, Frontend missing | **New Tool:** Terraform (skill provisioning)

#### [NEW] `backend/skills/skill_registry.py`
```python
# স্কিলের মেটাডেটা রেজিস্ট্রি
SKILLS = {
    "video_editing": {
        "dependencies": ["ffmpeg", "imagemagick"],
        "terraform_module": "gcp/skill_gpu",
        "category": "media"
    },
    "stable_diffusion": {
        "dependencies": ["torch", "diffusers"],
        "terraform_module": "gcp/skill_gpu_heavy",
        "category": "ai_media"
    }
}
```

#### [NEW] `backend/skills/provisioner.py`
```python
# Terraform দিয়ে ইউজারের ক্লাউডে স্কিল ইন্সটল
class SkillProvisioner:
    async def provision(skill_id: str, user_cloud: CloudConfig) -> ProvisionResult:
        # terraform apply -var="user_id=..." -var="skill=..."
```

#### [NEW] Studio Client — `SkillStore.tsx`
- Category grid: AI, Media, Code, Data
- Enable/Disable toggle + Terraform provisioning progress
- Status: Queued → Provisioning → Ready ✅

---

### Step 10 — Resource Bridge (P2P + Credit System)
**Status:** ❌ New Module | **New Tool:** Terraform (secure tunnel infra)

**Decision:** Credit-based. Opt-out kill-switch default OFF.

#### [NEW] `backend/p2p/resource_broker.py`
- Match idle donors with task requesters (priority: credit balance → latency → trust)

#### [NEW] `backend/p2p/credit_system.py`
```python
# ক্রেডিট লেজার — শেয়ার করলে আয়, ব্যবহার করলে খরচ
class CreditLedger:
    async def earn(user_id, amount, reason) -> Transaction
    async def spend(user_id, amount, reason) -> Transaction
    async def opt_out(user_id) -> None   # Global kill-switch
    async def opt_in(user_id) -> None
    async def balance(user_id) -> float
```

#### [NEW] `backend/p2p/secure_tunnel.py`
- WireGuard/SSH encrypted tunnel + cert pinning

---

## 🔷 Layer 4: System Evolution (Steps 11–15)

---

### Step 11 — System Self-Healing Engine
**Status:** ✅ Parts exist | **New Tool:** LangGraph (healing state machine)

#### [NEW] `backend/core/self_healing_agent.py`
```python
# LangGraph-এর মাধ্যমে continuous health monitoring loop
from langgraph.graph import StateGraph

monitor_graph = StateGraph(MonitorState)
monitor_graph.add_node("check_health", check_all_services)    # every 30s
monitor_graph.add_node("lookup_fix", query_qdrant_error_db)   # vector search
monitor_graph.add_node("apply_fix", run_remediation)
monitor_graph.add_node("escalate", send_to_hitl_queue)
```

#### [MODIFY] [core/error_pattern_db.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/core/error_pattern_db.py)
- Store resolved patterns in **Qdrant** for fast vector similarity search
- `add_resolved_pattern(error_sig, fix, success: bool)`

---

### Step 12 — Automated Cost Audit & Reports
**Status:** ⚠️ Partial | **New Tool:** Prometheus + Grafana + LiteLLM callbacks

#### Observability Stack:
```
LiteLLM callback → api_tracker.py → Prometheus metrics → Grafana dashboard
                                  → optimization_engine.py → Admin dashboard
```

#### [NEW] `backend/monitoring/cost_auditor.py`
- Subscribe to LiteLLM `success_callback` for zero-overhead cost logging
- Expose `/metrics` endpoint (Prometheus scrape target)

#### [NEW] `backend/reports/optimization_engine.py`
```python
# সাপ্তাহিক: পেইড API → ফ্রি অল্টারনেটিভ সুপারিশ
class OptimizationEngine:
    async def weekly_audit() -> OptimizationReport
    async def suggest_free_alternatives(provider: str) -> List[Alternative]
```

#### [NEW] `infrastructure/monitoring/docker-compose.monitoring.yml`
```yaml
# Prometheus + Grafana local/cloud observability stack
services:
  prometheus:
    image: prom/prometheus:latest
    volumes: ["./prometheus.yml:/etc/prometheus/prometheus.yml"]
  grafana:
    image: grafana/grafana:latest
    ports: ["3001:3000"]
    depends_on: [prometheus]
```

#### [NEW] `infrastructure/monitoring/grafana_dashboard.json`
- Pre-built dashboard: API spend, model distribution, error rates, latency

#### [NEW] Studio Client — `CostDashboard.tsx`
- Recharts line chart: daily spend by provider
- Savings recommendations panel
- CSV/PDF export

---

### Step 13 — Snapshot Learning (Scout & Scholar Loop)
**Status:** ⚠️ Indexers exist, pipeline missing | **New Tool:** Qdrant (knowledge store) + LangSmith (trace)

#### [NEW] `backend/scout/web_crawler_agent.py`
```python
# HITL-গেটেড ওয়েব ক্রলার — শুধু অ্যাপ্রুভড ডোমেইন
APPROVED_DOMAINS = ["github.com", "arxiv.org", "docs.python.org", "huggingface.co"]

async def crawl(url: str) -> CrawlResult  # HITL required for new domains
```

#### [NEW] `backend/scout/knowledge_extractor.py`
- Extract code patterns + API signatures → embed with `sentence-transformers` → store in Qdrant

#### [NEW] `backend/adaptive_engine/learning_loop.py`
```python
# প্রতিদিন রাত ২টায় নতুন জ্ঞান শিখবে (LangSmith-এ ট্রেস হবে)
class LearningLoop:
    SCHEDULE = "0 2 * * *"  # UTC
    
    async def run_cycle() -> LearningReport:
        # Scout → Extract → Embed → Store in Qdrant → Register as Skill
```

---

### Step 14 — Intelligent Model Routing (LiteLLM Dispatcher)
**Status:** ⚠️ Router exists, LiteLLM missing | **New Tool:** LiteLLM + LangSmith

> [!TIP]
> LiteLLM handles 100+ providers with a single interface. **You no longer need 15 separate provider clients.** This replaces the complexity of `brain/model_router.py` with a standard, maintained library.

#### [NEW] `backend/engine/model_dispatcher.py`
```python
# LiteLLM দিয়ে complexity-based routing + LangSmith trace
import litellm
from langsmith import traceable

@traceable(name="model_dispatch")  # LangSmith-এ প্রতিটি সিদ্ধান্ত লগ হবে
async def dispatch(task: str, complexity: int, user_mode: str) -> ModelResponse:
    model = select_model(complexity, user_mode)
    return await litellm.acompletion(
        model=model,
        messages=[{"role": "user", "content": task}],
        fallbacks=get_fallback_chain(model)
    )
```

**Routing Table:**

| Complexity | Model | Cost | Trigger |
|---|---|---|---|
| 1–3 | `ollama/llama3.2` | $0 | Simple Q&A, formatting |
| 4–6 | `openrouter/mistral-7b-free` | $0 | Moderate reasoning |
| 7–8 | `gemini/gemini-flash` | ~$0.001/1K | Complex code, analysis |
| 9–10 | `openai/gpt-4o-mini` | Premium | Frontier tasks |

#### [NEW] `backend/models/local_model_handler.py`
- Ollama health check, model listing, streaming inference
- Auto-escalate to next tier if Ollama unavailable

#### [NEW] `config/routing_policy.json`
```json
{
  "rules": [
    { "complexity_max": 3, "model": "ollama/llama3.2" },
    { "complexity_max": 6, "model": "openrouter/mistral-7b-free" },
    { "complexity_max": 8, "model": "gemini/gemini-flash" },
    { "complexity_max": 10, "model": "openai/gpt-4o-mini" }
  ],
  "user_mode_overrides": {
    "FAST_TRACK": { "prefer_local": true, "max_wait_ms": 500 },
    "LEARNING": { "explanatory_models": ["gemini/gemini-pro"] },
    "PRODUCTION": { "prefer_accuracy": true, "min_complexity": 7 }
  }
}
```

---

### Step 15 — Autonomous Evolution (CrewAI Multi-Agent System)
**Status:** ⚠️ Parts exist | **New Tool:** CrewAI + LangGraph + LangSmith

> [!CAUTION]
> Self-generated patches go to `feature/auto-<timestamp>` ONLY. No code merges to `develop` or `main` without explicit HITL approval. Hard constraint, non-configurable.

#### CrewAI Multi-Agent Architecture:
```python
# CrewAI দিয়ে মাস্টার প্ল্যানার — 4 এজেন্টের দল
from crewai import Agent, Task, Crew

# ৪টি বিশেষজ্ঞ এজেন্ট
auditor_agent = Agent(
    role="System Auditor",
    goal="Analyze performance metrics and cost reports",
    llm="ollama/llama3.2"  # LiteLLM-এর মাধ্যমে
)
coder_agent = Agent(
    role="Patch Generator", 
    goal="Write code improvements based on audit findings",
    llm="gemini/gemini-flash"
)
tester_agent = Agent(
    role="Test Validator",
    goal="Run sandbox tests on generated patches",
    llm="ollama/llama3.2"
)
planner_agent = Agent(
    role="Evolution Planner",
    goal="Coordinate team output into HITL proposals",
    llm="gemini/gemini-flash"
)

# ক্রু একসাথে কাজ করবে, মানুষের অনুমোদন ছাড়া কিছু মার্জ হবে না
evolution_crew = Crew(
    agents=[auditor_agent, coder_agent, tester_agent, planner_agent],
    tasks=[audit_task, code_task, test_task, plan_task],
    verbose=True
)
```

#### [NEW] `backend/evolution/master_planner.py`
```python
# CrewAI crew চালু করে HITL-এ প্রস্তাব পাঠায়
class MasterPlanner:
    async def run_evolution_cycle() -> List[ImprovementProposal]
    async def submit_for_hitl_review(proposal) -> str  # returns task_id
```

#### [NEW] `backend/evolution/auto_update_manager.py`
```python
# HITL অ্যাপ্রুভালের পর শুধু feature/auto-* branch-এ প্যাচ প্রয়োগ
class AutoUpdateManager:
    BRANCH_PREFIX = "feature/auto-"
    TARGET_BRANCH = "develop"  # শুধু develop-এ PR, কখনো main-এ নয়
    
    async def on_approval(proposal_id: str) -> UpdateResult:
        branch = f"{self.BRANCH_PREFIX}{timestamp()}"
        # sandbox test → create branch → commit → open PR → log
```

#### [NEW] `docs/evolution_log.md`
- Append-only: `[date] | [proposal_id] | [description] | [status] | [branch] | [crew_run_id]`

---

## 📊 Complete File Inventory

### 🆕 New Files (37 total)

| # | Path | Layer | Key Tool |
|---|------|-------|---------|
| 1 | `scripts/setup_ci_runner.py` | 1 | — |
| 2 | `backend/core/user_profiler.py` | 1 | LiteLLM |
| 3 | `backend/api/approval_manager.py` | 1 ⚡ | LangGraph |
| 4 | `backend/models/pending_tasks.py` | 1 ⚡ | SQLAlchemy |
| 5 | `backend/core/decision_engine.py` | 2 | LiteLLM + LangSmith |
| 6 | `backend/engine/cost_optimizer.py` | 2 | LiteLLM |
| 7 | `backend/utils/api_tracker.py` | 2 | LiteLLM callbacks |
| 8 | `backend/tools/browser_stealth.py` | 2 | playwright-stealth ✅ |
| 9 | `config/proxy_list.json` | 2 | — |
| 10 | `backend/scripts/self_healing_tests.py` | 2 | LangGraph |
| 11 | `backend/core/error_remediation.py` | 2 | LiteLLM + Qdrant |
| 12 | `backend/byoc/__init__.py` | 3 | — |
| 13 | `backend/byoc/cloud_connector.py` | 3 | GCP SDK |
| 14 | `backend/byoc/resource_manager.py` | 3 | Terraform |
| 15 | `backend/byoc/container_orchestrator.py` | 3 | Terraform + Cloud Run |
| 16 | `infrastructure/terraform/gcp/main.tf` | 3 | **Terraform** |
| 17 | `infrastructure/terraform/gcp/storage.tf` | 3 | Terraform |
| 18 | `infrastructure/terraform/gcp/variables.tf` | 3 | Terraform |
| 19 | `backend/skills/skill_registry.py` | 3 | — |
| 20 | `backend/skills/provisioner.py` | 3 | Terraform |
| 21 | Studio Client `SkillStore.tsx` | 3 | React |
| 22 | `backend/p2p/resource_broker.py` | 3 | — |
| 23 | `backend/p2p/credit_system.py` | 3 | SQLite/Firestore |
| 24 | `backend/p2p/secure_tunnel.py` | 3 | WireGuard |
| 25 | `backend/core/self_healing_agent.py` | 4 | **LangGraph** |
| 26 | `backend/monitoring/cost_auditor.py` | 4 | Prometheus |
| 27 | `backend/reports/optimization_engine.py` | 4 | LiteLLM |
| 28 | Studio Client `CostDashboard.tsx` | 4 | Recharts |
| 29 | `infrastructure/monitoring/docker-compose.monitoring.yml` | 4 | Prometheus + Grafana |
| 30 | `infrastructure/monitoring/grafana_dashboard.json` | 4 | Grafana |
| 31 | `backend/scout/web_crawler_agent.py` | 4 | HITL-gated |
| 32 | `backend/scout/knowledge_extractor.py` | 4 | Qdrant + sentence-transformers |
| 33 | `backend/adaptive_engine/learning_loop.py` | 4 | Qdrant + LangSmith |
| 34 | `backend/engine/model_dispatcher.py` | 4 | **LiteLLM** + LangSmith |
| 35 | `backend/models/local_model_handler.py` | 4 | Ollama |
| 36 | `config/routing_policy.json` | 4 | LiteLLM |
| 37 | `backend/evolution/master_planner.py` | 4 | **CrewAI** |
| 38 | `backend/evolution/auto_update_manager.py` | 4 | CrewAI + LangGraph |
| 39 | `docs/evolution_log.md` | 4 | — |

### ✏️ Modified Files (11 total)

| File | Change |
|------|--------|
| [adaptive_engine/intent_parser.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/adaptive_engine/intent_parser.py) | LiteLLM-based `extract_goal()` |
| [adaptive_engine/experience_db.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/adaptive_engine/experience_db.py) | ChromaDB/Qdrant vector store |
| [core/semantic_cache.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/core/semantic_cache.py) | Hook into vector experience_db |
| [core/free_tier_tracker.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/core/free_tier_tracker.py) | `is_free_available()` real-time |
| [tools/vpn_switcher.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/tools/vpn_switcher.py) | Hybrid proxy + `rotate_on_block()` |
| [tools/cloud_sandbox_orchestrator.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/tools/cloud_sandbox_orchestrator.py) | LangGraph healing pipeline |
| [core/error_pattern_db.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/core/error_pattern_db.py) | Qdrant vector search |
| [api/routes/admin_dashboard.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/api/routes/admin_dashboard.py) | HITL WebSocket feed |
| [api/routes/onboarding.py](file:///c:/Users/n/supremeai/supremeai_2.0/backend/api/routes/onboarding.py) | Profile + mode endpoints |
| `.github/workflows/monorepo_ci_cd.yml` | Cache + Discord + smoke test |
| `backend/pyproject.toml` | Add litellm, langgraph, crewai, langsmith |

---

## Verification Plan

### Automated Tests
```bash
# নতুন ডিপেন্ডেন্সি ইন্সটল
cd backend && poetry add litellm
poetry add --group ml langgraph crewai
poetry add --group tools langsmith

# Full test suite
pnpm backend:test

# Per-layer tests
pytest backend/tests/test_approval_manager.py -v   # Step 3
pytest backend/tests/test_cost_optimizer.py -v     # Step 5
pytest backend/tests/test_model_dispatcher.py -v   # Step 14
pytest backend/tests/test_master_planner.py -v     # Step 15
pytest backend/tests/test_credit_system.py -v      # Step 10
```

### Manual Verification Checkpoints

| Step | Test | Pass Criteria |
|------|------|---------------|
| Step 3 (HITL) | Trigger VPN switch → check admin panel | Appears in pending queue, action blocked |
| Step 4 (VectorDB) | Submit repeated prompt | Second call returns ChromaDB result, no API call |
| Step 5 (Cost) | Simple prompt via cost_optimizer | Routes to Ollama, LangSmith shows `ollama/llama3.2` |
| Step 6 (VPN) | Simulate 429 response | `rotate_on_block()` fires, new proxy assigned |
| Step 7 (Healing) | Submit broken code | LangGraph retries 3x, then HITL escalation |
| Step 8 (BYOC) | Upload GCP service account | Terraform creates Cloud Run service in user's GCP |
| Step 9 (Skills) | Enable "video_editing" skill | Provisioner runs `terraform apply`, FFmpeg deployed |
| Step 11 (Self-Heal) | Kill a backend service | `self_healing_agent.py` detects + attempts fix |
| Step 14 (Dispatch) | Score complexity 2 vs 9 | LangSmith shows Ollama vs GPT-4o-mini routing |
| Step 15 (Evolution) | Run master planner | `feature/auto-*` branch created, NOT merged |

---

## Implementation Timeline

| Week | Steps | Key Deliverables | New Tools Introduced |
|------|-------|-----------------|---------------------|
| Week 1 | 1, 3 | HITL system + CI/CD polish | LangGraph (HITL state machine) |
| Week 2 | 2, 4, 5 | User profiling + Vector DB + Cost optimizer | **LiteLLM**, ChromaDB/Qdrant |
| Week 3 | 6, 7, 11 | VPN hybrid + Healing loop + Self-healer | LangGraph loops, playwright-stealth |
| Week 4 | 8, 9 | BYOC GCP + Skill Store UI | **Terraform** |
| Week 5 | 12, 14 | Cost dashboard + Model dispatcher | Prometheus/Grafana, LangSmith |
| Week 6 | 13 | Scout & Scholar knowledge loop | Qdrant production, LangSmith traces |
| Week 7 | 10 | P2P Resource Bridge + Credits | WireGuard |
| Week 8 | 15 | Autonomous Evolution crew | **CrewAI** multi-agent system |

---

*v3 Final — Updated: 2026-06-29 | All tooling decisions locked*
*Agent: Antigravity | SupremeAI 2.0 Master Blueprint*
