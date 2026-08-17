# SupremeAI 2.0 — ডকুমেন্টেশন প্ল্যান (মাস্টার ব্লুপ্রিন্ট)
**উদ্দেশ্য:** প্রজেক্টের প্রতিটা ছোট ছোট অংশের জন্য আলাদা আলাদা "কীভাবে সমাধান করা হয়েছে" ডকুমেন্ট বানানোর জন্য একটা সম্পূর্ণ, রিয়েল-কোড-ভেরিফায়েড প্ল্যান।
**তারিখ:** ২৭ জুলাই, ২০২৬

---

## ০. আগে একটা সততার নোট — তোমার আপলোড করা ইনভেন্টরি নিয়ে

তোমার `PROJECT_MODULES_COMPLETE_INVENTORY.md` ফাইলটা ভালো একটা শুরু, কিন্তু আমি রিপোতে গিয়ে সরাসরি চেক করে দেখলাম কিছু path ভুল/পুরনো:

| ইনভেন্টরিতে যা লেখা | আসলে রিপোতে যা আছে |
|---|---|
| `backend/core/billing/quota_enforcer.py` | আসল লোকেশন: `scripts/billing/quota_enforcer.py` |
| `backend/evolution/digital_twin/simulation_sandbox.py` | এই নামে ফাইল নেই — আসল ফাইলগুলো: `simulator.py`, `topology.py`, `remediation_engine.py` |
| `backend/evolution/digital_twin/world_model.py` | এই নামেও ফাইল নেই |
| `backend/core/llm_router.py`, `backend/engine/smart_router.py`, `backend/core/tier8/skill_marketplace_curator.py` | ✅ এগুলো সঠিক আছে |

**এর মানে:** ইনভেন্টরি সম্ভবত মেমরি/প্ল্যান থেকে লেখা হয়েছিল, কোড থেকে সরাসরি generate করা হয়নি। তাই **এই প্ল্যানের একটা core rule হওয়া উচিত: প্রতিটা ডকুমেন্ট লেখার আগে ফাইল আসলেই আছে কিনা, আর তার ভেতরে যা লেখা হচ্ছে তা বাস্তবে match করে কিনা — verify করে নেওয়া, শুধু আগের নোট থেকে কপি না করা।** নিচের প্ল্যানে আমি সরাসরি রিপো স্ক্যান করে যাচাই করা path/সংখ্যা দিয়েছি।

---

## ১. কেন আগের ইনভেন্টরি "সম্পূর্ণ ডকুমেন্টেশন" মনে হচ্ছে না — ঠিক ধরেছ

আগের ইনভেন্টরি একটা **flat feature-list** (এক লাইনে কী আছে তার নাম)। কিন্তু "ডকুমেন্টেশন" আর "ইনভেন্টরি" আলাদা জিনিস:

- **ইনভেন্টরি** বলে: *"CircuitBreaker আছে, `circuit_breaker.py`-তে, এটা CLOSED/OPEN/HALF-OPEN স্টেট হ্যান্ডল করে।"*
- **ডকুমেন্টেশন** বলে: *"কেন CircuitBreaker দরকার হলো (কোন প্রবলেম সমাধান করতে), কীভাবে এটা কাজ করে ধাপে ধাপে, কোন থ্রেশহোল্ডে state change হয়, fail হলে কী হয়, কোন module গুলো এটার উপর নির্ভর করে, কী কী edge case মিস হতে পারে, এখনো কী বাকি আছে।"*

তাই নিচে আমি একটা **per-module documentation template** আর তার উপর ভিত্তি করে **প্রতিটা অংশের জন্য আলাদা ডকুমেন্ট-স্লট** এর তালিকা দিচ্ছি — যাতে পরে একটা একটা করে ভরাট করা যায়।

---

## ২. প্রতিটা ডকুমেন্টের জন্য ফিক্সড টেমপ্লেট (সব ডকুমেন্ট এই কাঠামো মেনে চলবে)

প্রতিটা মাইক্রো-ডকুমেন্ট নিচের ৯টা সেকশন থাকবে — ছোট মডিউলে কিছু সেকশন সংক্ষিপ্ত হতে পারে, কিন্তু কাঠামো একই থাকবে:

```markdown
# [মডিউলের নাম]

## ১. এক লাইনে কী এটা
## ২. কোন সমস্যাটা সমাধান করে (Problem Statement)
## ৩. কীভাবে কাজ করে (ধাপে ধাপে / ফ্লো-ডায়াগ্রাম সহ)
## ৪. মূল ফাইল ও ফাংশন (ফাইল পাথ + প্রতিটা গুরুত্বপূর্ণ ফাংশনের সংক্ষিপ্ত বিবরণ)
## ৫. ইনপুট/আউটপুট ও ডিপেন্ডেন্সি (এটা কী থেকে ডেটা নেয়, কাকে ডেটা দেয়, কোন মডিউলের উপর নির্ভরশীল)
## ৬. কনফিগারেশন (env var, config flag যা এটাকে প্রভাবিত করে)
## ৭. এজ কেস ও এরর হ্যান্ডলিং (কী কী ভুল হতে পারে, কীভাবে হ্যান্ডল করা হয়েছে/হয়নি)
## ৮. টেস্ট কভারেজ (কোন টেস্ট ফাইল এটা কভার করে, কতটুকু কভার করে)
## ৯. পরিচিত সমস্যা ও ভবিষ্যৎ কাজ (Known Issues / TODO)
```

---

## ৩. ডকুমেন্ট-ট্রি — প্রজেক্টের প্রতিটা অংশ (রিপো স্ক্যান করে যাচাই করা)

নিচে প্রতিটা সাব-সিস্টেমকে একটা "ডকুমেন্ট গ্রুপ" আকারে ভাগ করা হয়েছে। প্রতিটা লাইন = ভবিষ্যতে একটা আলাদা `.md` ফাইল হতে পারে। সংখ্যা (ফাইল কাউন্ট) পাশে দেওয়া আছে যাতে scope বোঝা যায়।

### গ্রুপ A — `backend/core/` (১৯২ ফাইল, ২৪টা সাবসিস্টেম) — সবচেয়ে বড় গ্রুপ, তাই সাব-গ্রুপে ভাগ করা হলো

| সাব-ফোল্ডার | প্রস্তাবিত ডকুমেন্ট | অগ্রাধিকার |
|---|---|---|
| `core/security/` | ০১. Security & AutonoGuard — RBAC, secret_hunter, rate_limiter, credential_store, prompt_firewall | 🔴 P0 |
| `core/resilience/` | ০২. Resilience Layer — circuit_breaker, retry logic | 🔴 P0 |
| `core/persistence/` | ০৩. Persistence Layer — pooled_pg, write_behind (নতুন Postgres মাইগ্রেশন) | 🔴 P0 |
| `core/database/` | ০৪. Database Session Management | 🔴 P0 |
| `core/orchestration/` | ০৫. Agent Orchestration — orchestrator, swarm_orchestrator, crew_departments | 🟠 P1 |
| `core/tier8/` | ০৬. Tier-8 Self-Evolution Engine (আগের রিপোর্টে "সেরা ফিচার" হিসেবে চিহ্নিত) | 🟠 P1 |
| `core/llm/` | ০৭. LLM Routing & Token Management — llm_router, free_tier_tracker, token_deductor | 🟠 P1 |
| `core/messaging/` | ০৮. Event Bus & Queue System (Redis/GCP Pub-Sub) | 🟠 P1 |
| `core/queue/` | ০৯. Task Queue Internals | 🟠 P1 |
| `core/health/` | ১০. Self-Healing System — self_healer, auto_healer_service | 🟠 P1 |
| `core/observability/` | ১১. Audit Logging & Observability | 🟠 P1 |
| `core/optimization/` | ১২. Performance Optimizer | 🟡 P2 |
| `core/evolution/` | ১৩. Auto Skill Creator & Evolution Utilities | 🟡 P2 |
| `core/skills/` | ১৪. Skill Manager (dynamic skill exec sandbox) | 🔴 P0 (সিকিউরিটি-সংবেদনশীল, exec() ব্যবহার করে) |
| `core/middleware/` | ১৫. Middleware Stack (auth, CORS, idempotency) | 🟠 P1 |
| `core/prompts/` | ১৬. Prompt Templates & Management | 🟡 P2 |
| `core/models/` | ১৭. Core Data Models | 🟡 P2 |
| `core/cache/` | ১৮. Redis Cache Manager | 🟠 P1 |
| `core/telemetry/` | ১৯. Telemetry & Metrics Collector | 🟡 P2 |
| `core/deployment/` | ২০. Deployment Helpers | 🟡 P2 |
| `core/accessibility/`, `core/localization/` | ২১. Accessibility & i18n | 🟢 P3 |
| `core/testing/` | ২২. Internal Testing Utilities | 🟢 P3 |
| `core/utils/` | ২৩. Shared Utility Functions | 🟢 P3 |
| top-level `core/*.py` (app.py, lifespan.py, error_handler.py ইত্যাদি) | ২৪. App Bootstrap & Lifespan Management | 🔴 P0 |

### গ্রুপ B — `backend/agents/` ও `backend/brain/` (এজেন্ট লজিক)

| মডিউল | প্রস্তাবিত ডকুমেন্ট | অগ্রাধিকার |
|---|---|---|
| `agents/sentinel_agent.py` | Sentinel — Prompt Injection Scanner | 🔴 P0 |
| `agents/performance_guardian.py`, `vulnerability_prophet.py` | Guardian Agents (পারফরম্যান্স + দুর্বলতা পূর্বাভাস) | 🟠 P1 |
| `agents/churn_prophet.py`, `insight_mage.py` | Business Intelligence Agents | 🟡 P2 |
| `agents/devops/` (auto_healer, cost_sage, cloud_watchman) | DevOps Automation Agents | 🟠 P1 |
| `agents/ephemeral_executor.py`, `headless_terminal_agent.py` | Code Execution Agents (স্যান্ডবক্স) | 🔴 P0 (সিকিউরিটি-সংবেদনশীল) |
| `agents/skill_gc.py`, `skill_ingestor.py`, `skill_librarian.py` | Skill Lifecycle Management | 🟠 P1 |
| `brain/supreme_learning_engine.py` + বাকি ২৩ ফাইল | Core Learning Brain | 🟠 P1 |

### গ্রুপ C — `backend/memory/` (মেমরি সিস্টেম — আগের রিপোর্টে honorable mention)

| মডিউল | প্রস্তাবিত ডকুমেন্ট | অগ্রাধিকার |
|---|---|---|
| `episodic_memory.py`, `long_term_memory.py` | Memory Architecture — Episodic vs Long-Term | 🔴 P0 |
| `rag_pipeline.py`, `chromadb_store.py`, `vector_store_config.py` | RAG & Vector Search Pipeline | 🟠 P1 |
| `sqlite_store.py`, `cloud_postgres_store.py`, `supabase_store.py`, `unified_db_manager.py` | Storage Backend Abstraction (এবং SQLite→Postgres মাইগ্রেশন স্ট্যাটাস) | 🔴 P0 |
| `checkpoint_resume.py` | Checkpoint & Resume System | 🔴 P0 |
| `summary_tree.py`, `sliding_window.py` | Context Window Management | 🟠 P1 |

### গ্রুপ D — `backend/evolution/` (কগনিটিভ/গবেষণা মডিউল)

| মডিউল | প্রস্তাবিত ডকুমেন্ট | অগ্রাধিকার |
|---|---|---|
| `theory_of_mind/tom_system.py` (৮২৯ লাইন) | Theory-of-Mind System — কীভাবে "Belief/Desire/Intention" মডেল করে | 🟠 P1 |
| `digital_twin/` (simulator.py, topology.py, remediation_engine.py) | Digital Twin — Simulation, Topology Mapping, Auto-Remediation | 🟠 P1 |
| `federated_learning/fed_learning.py` | Federated Learning Module | 🟡 P2 |
| `adversarial_defense/defense_system.py` | Adversarial Defense System | 🟠 P1 |
| `continual_learning/ewc.py` | Catastrophic Forgetting Prevention (EWC) | 🟡 P2 |
| `neural_symbolic/`, `temporal_abstraction/` | (এগুলো এখনো কী গভীরতায় আছে যাচাই করা দরকার — নাম আছে কিন্তু কনটেন্ট অডিট বাকি) | 🟢 P3 |

### গ্রুপ E — `backend/api/` (৮৪ ফাইল — সব রুট/এন্ডপয়েন্ট)

সব endpoint আলাদা ডকুমেন্ট না দিয়ে **route-group অনুযায়ী** ভাগ করা ভালো:
- Auth & User Management endpoints
- Admin endpoints (`admin.py`, `admin_dashboard.py`)
- Billing/Marketplace endpoints
- WebSocket/real-time endpoints (`websocket_agent.py`)
- Feedback/site-actions endpoints
- **প্রতিটা গ্রুপে**: কোন route কী করে, auth লাগে কিনা, rate-limit আছে কিনা — এটা টেবিল আকারে।
- অগ্রাধিকার: 🔴 P0 (এগুলোই বাইরের world-এর সাথে সরাসরি ইন্টারফেস)

### গ্রুপ F — `backend/tools/` (১২৫ ফাইল — সবচেয়ে বেশি micro-feature ঘনত্ব)

বড় বলে সাব-গ্রুপ করা দরকার:
- `tools/security_tools/` — মাল্টি-অ্যাকাউন্ট রোটেটর ইত্যাদি (🔴 P0, সিকিউরিটি)
- `tools/code/` — safe_executor, code_smell_detector, image_to_code (🔴 P0, exec() ব্যবহার করে)
- `tools/social/` — email_agent, telegram_bot (🟠 P1)
- `tools/billing/` — monthly_cost_reporter (🟠 P1)
- `tools/knowledge/` — git_knowledge_extractor (🟡 P2)
- `tools/devops/` — docker_sandbox (🔴 P0)
- `tools/media/`, `tools/learning/` — TTS, style_learner (🟢 P3)
- `checkpoint_manager.py`, `health_checker.py`, `seed_database.py` (top-level tools) (🟠 P1)

### গ্রুপ G — `backend/services/` (নতুন যোগ হওয়া, `voice_service.py`, `vision_service.py` সহ)

| মডিউল | প্রস্তাবিত ডকুমেন্ট | অগ্রাধিকার |
|---|---|---|
| `voice_service.py`, `vision_service.py` | Voice & Vision Multi-Modal Services (সদ্য যোগ হয়েছে — verify করে দেখতে হবে কতটুকু বাস্তবায়িত) | 🟠 P1 |
| `memory_service.py` | Memory Service Layer | 🔴 P0 |

### গ্রুপ H — Multi-Tenant, Billing, Admin (`scripts/billing/`, `backend/admin/`, `backend/models/`)

| মডিউল | প্রস্তাবিত ডকুমেন্ট | অগ্রাধিকার |
|---|---|---|
| `scripts/billing/quota_enforcer.py`, `fraud_detector.py`, `usage_reporter.py` | Billing & Quota System | 🔴 P0 |
| `backend/admin/god.py` | Admin "God Mode" — Constitutional Rules Engine | 🔴 P0 |
| `backend/core/security/rbac.py` | Role-Based Access Control | 🔴 P0 |
| `backend/models/pending_tasks.py` + বাকি ২৯ ফাইল | Data Models Reference | 🟡 P2 |

### গ্রুপ I — Frontend (`apps/studio-client/` — ~২৪৩ ফাইল, ২১টা component ক্যাটাগরি)

| এলাকা | প্রস্তাবিত ডকুমেন্ট | অগ্রাধিকার |
|---|---|---|
| `store/authStore.ts`, `store/adminStore.ts` | State Management — Auth & Admin Store (🔴 নোট: এখানে আগের অডিটে টোকেন-স্টোরেজ ইস্যু পাওয়া গিয়েছিল) | 🔴 P0 |
| `components/chat/`, `components/customer/` (ChatPanel সহ) | Chat UI System (🔴 নোট: XSS ইস্যু এখানে ছিল) | 🔴 P0 |
| `components/admin/`, `pages/admin/` | Admin Console UI | 🟠 P1 |
| `components/swarm/`, `components/graph/`, `components/nodes/` | Agent Visualization (Swarm/Graph View) | 🟠 P1 |
| `components/editor/` | Code Editor Integration | 🟠 P1 |
| `components/simulator/` | Digital-Twin Simulator UI | 🟡 P2 |
| `services/api/` | API Client Layer | 🟠 P1 |
| `services/audio/`, `components/audio/` | Voice/Audio UI (Voice Service-এর সাথে যুক্ত) | 🟡 P2 |
| `i18n/` | Internationalization | 🟢 P3 |
| `dataconnect-generated/` | Firebase Data Connect (auto-generated — কম ডকুমেন্টেশন দরকার, শুধু "কীভাবে regenerate করা হয়" লিখলেই যথেষ্ট) | 🟢 P3 |
| `hooks/`, `contexts/`, `providers/`, `lib/`, `utils/` | Shared Frontend Utilities | 🟡 P2 |

### গ্রুপ J — Admin Portal (`admin/dashboard`, `admin/dashboard_light`)

| এলাকা | প্রস্তাবিত ডকুমেন্ট | অগ্রাধিকার |
|---|---|---|
| `admin/dashboard/` vs `admin/dashboard_light/` | কেন দুইটা আলাদা ড্যাশবোর্ড আছে, কোনটা কবে ব্যবহার হয় | 🟡 P2 |

### গ্রুপ K — Infrastructure & Deployment

| এলাকা | প্রস্তাবিত ডকুমেন্ট | অগ্রাধিকার |
|---|---|---|
| `render.yaml` + Render সার্ভিস স্ট্রাকচার | Render Deployment Topology (backend/admin/frontend আলাদা কেন) | 🔴 P0 |
| `.github/workflows/supreme-core-ci.yml` (১৪২০ লাইন — সবচেয়ে জটিল ফাইল) | CI/CD Pipeline — Full Flow ডকুমেন্টেশন (job-by-job) | 🔴 P0 |
| বাকি ২০+ workflow file (auto-fix, disaster-recovery-drill, k6-load-testing, sentinel_agent.md ইত্যাদি) | প্রতিটা workflow-এর জন্য এক-প্যারা সারাংশ (কবে ট্রিগার হয়, কী করে) | 🟠 P1 |
| `infrastructure/terraform/` (byoc_gcp, gcp) | Terraform IaC ডকুমেন্টেশন | 🟡 P2 |
| `infrastructure/cloudflare/`, `cloudflare-worker/` | Cloudflare Worker (৮-মিনিট cron ping কেন দরকার) | 🟡 P2 |
| `infrastructure/firebase_functions/` | Firebase Functions | 🟡 P2 |
| `infrastructure/zero_cost/` | Zero-Cost Hosting Strategy (এইটা প্রজেক্টের একটা ইউনিক constraint — নিজস্ব ডকুমেন্ট প্রাপ্য) | 🟠 P1 |
| `backend/Dockerfile`, `backend/Dockerfile.ci` | Docker Build Strategy (multi-stage, layer-cache) | 🟠 P1 |

### গ্রুপ L — Scripts (`scripts/` — ৩৫টা সাব-ফোল্ডার)

সব স্ক্রিপ্ট আলাদা ডকুমেন্ট দরকার নেই — এগুলো এক-লাইন সারাংশ টেবিল আকারে একটা মাস্টার "Scripts Reference" ডকুমেন্টে থাকতে পারে, শুধু নিচেরগুলো আলাদা গভীর ডকুমেন্ট প্রাপ্য কারণ এগুলো প্রোডাকশন-critical:
- `scripts/deploy/blue_green_deploy.py`, `canary_deploy.py`, `disaster_recovery_test.py` (🔴 P0 — আগের অডিটে shell-injection পাওয়া গিয়েছিল এখানে)
- `scripts/security/` (৭ ফাইল) (🔴 P0)
- `scripts/backup/` (🔴 P0)

### গ্রুপ M — টেস্টিং (৩৫২ ফাইল)

আলাদা ডকুমেন্ট না, বরং একটা "Test Strategy" ডকুমেন্ট:
- কোন layer-এ কী ধরনের টেস্ট আছে (unit/integration/e2e)
- coverage gap কোথায় (৩০% থ্রেশহোল্ড CI-তে সেট করা আছে — এটা যথেষ্ট কিনা আলোচনা করা)
- 🟠 P1

---

## ৪. ডকুমেন্ট লেখার ধাপ (Process)

1. **ফোল্ডার স্ট্রাকচার বানাও** `docs/modules/` এর নিচে — গ্রুপ অনুযায়ী সাব-ফোল্ডার (`docs/modules/security/`, `docs/modules/memory/`, ইত্যাদি) যাতে উপরের গ্রুপ A–M সরাসরি ফোল্ডারে ম্যাপ হয়।
2. **প্রতিটা ডকুমেন্ট লেখার আগে কোড খুলে verify করো** — উপরে যেমন inventory-তে ভুল পাওয়া গেছে, প্রতিটা path/ফাংশন নাম লেখার আগে রিপোতে গিয়ে কনফার্ম করে নেওয়া (এটা একটা checklist item হওয়া উচিত)।
3. **P0 গ্রুপ দিয়ে শুরু করো** — এগুলো security-critical বা production-critical অংশ, এগুলোর ডকুমেন্টেশন সবচেয়ে বেশি দরকার (এবং ডকুমেন্ট লেখার সময় স্বাভাবিকভাবেই বাগও চোখে পড়বে, যেটা আগের অডিটে হয়েছিল)।
4. **প্রতিটা ডকুমেন্টে "Known Issues" সেকশন honest রাখো** — আগের অডিটে পাওয়া বাগগুলো (XSS, shell-injection, ephemeral storage ইত্যাদি) সংশ্লিষ্ট ডকুমেন্টে link/note করে রাখলে ভবিষ্যতে কেউ ভুলে যাবে না।
5. **একটা মাস্টার ইনডেক্স রাখো** (`docs/modules/README.md`) যেটা এই প্ল্যানের টেবিলগুলোর লিংকড ভার্সন — কোন ডকুমেন্ট লেখা হয়ে গেছে, কোনটা বাকি, স্ট্যাটাস ট্র্যাক করার জন্য (✅ Done / 🚧 In Progress / ⬜ Not Started কলাম)।

---

## ৫. সারসংক্ষেপ সংখ্যায়

| গ্রুপ | আনুমানিক ডকুমেন্ট সংখ্যা |
|---|---|
| A. Core (২৪ সাবসিস্টেম) | ~২৪টা ডকুমেন্ট |
| B. Agents/Brain | ~৭টা |
| C. Memory | ~৫টা |
| D. Evolution/Cognitive | ~৬টা |
| E. API Routes | ~৫-৬টা (গ্রুপ করে) |
| F. Tools | ~৮টা (সাব-গ্রুপ করে) |
| G. Services | ~২টা |
| H. Billing/Admin | ~৪টা |
| I. Frontend | ~১১টা |
| J. Admin Portal | ~১টা |
| K. Infrastructure | ~৮টা |
| L. Scripts | ~১টা মাস্টার + ৩টা deep-dive |
| M. Testing | ~১টা |
| **মোট** | **~৮০-৯০টা ফোকাসড মাইক্রো-ডকুমেন্ট** (আগের ১টা ফ্ল্যাট ইনভেন্টরির বদলে) |

এটাই তোমার বলা "৮০০+ পৃষ্ঠার ম্যানুয়াল"-এর বাস্তব রোডম্যাপ — প্রতিটা ডকুমেন্ট গড়ে ৮-১০ পৃষ্ঠা হলেও মোট ~৮০০ পৃষ্ঠায় পৌঁছাবে, কিন্তু প্রতিটা অংশ manageable, verifiable, আর independently আপডেট করা যাবে।

---

চাইলে আমি এখনই যেকোনো একটা P0 গ্রুপ (যেমন Security, বা Memory, বা CI/CD Pipeline) ধরে সরাসরি প্রথম পূর্ণাঙ্গ মডিউল-ডকুমেন্ট বানিয়ে দিতে পারি, উপরের টেমপ্লেট অনুযায়ী, যাতে বাকিগুলো একই প্যাটার্নে বানানো যায়।
