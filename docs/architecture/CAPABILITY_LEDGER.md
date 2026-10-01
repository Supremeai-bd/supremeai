# SupremeAI — Pre-Refactor Capability Ledger & Baseline Matrix
*(সক্ষমতা ইনভেন্টরি, আর্কিটেকচার ম্যাপিং ও রিফ্যাক্টর প্রিজারভেশন লেজার)*

> **Baseline Version:** `pre-refactor-v1.0`  
> **Date:** `2026-09-28`  
> **Source of Truth:** [`docs/architecture/CAPABILITY_LEDGER.md`](./CAPABILITY_LEDGER.md)  
> **Constitution Invariant:** *"আমরা কোড ও জটিলতা কমাচ্ছি, সক্ষমতা কমাচ্ছি না — জিরো ক্যাপাবিলিটি লস ও ১০১% লাভ নীতি।"*

---

## 📌 ১. ভূমিকা ও উদ্দেশ্য (Executive Intent)

SupremeAI-এর বড় ধরনের রিফ্যাক্টরিং বা মডুলার কনসোলিডেশন শুরু করার আগে এই **Capability Ledger** হলো একক ক্যানোনিকাল সত্য-দলিল (Single Source of Truth)।

### মূল পার্থক্য: কোড থাকা বনাম সক্ষমতা থাকা
একটি কোডবেসে ৩টি আলাদা ফাইলে একই লজিক কপি-পেস্ট থাকলে কোড বেশি থাকে, কিন্তু সক্ষমতা থাকে ১টি। বিপরীতভাবে, ভুল রিফ্যাক্টরিং করতে গিয়ে আসল ফিচার মুছে ফেললে কোড কমে কিন্তু সিস্টেম বিকল হয়। তাই এই ডকুমেন্টের মূল প্রশ্ন:
> **“আমরা কি কোড ছাঁটাই করছি, নাকি আসল সক্ষমতা (Capability) কমিয়ে ফেলছি?”**

### ৩টি মাস্টার ভিউ (The 3 Master Views)
1. **Master Capability Inventory:** SupremeAI ঠিক কী কী করতে পারে, কী আংশিক পারে, আর কী ভবিষ্যতে করার পরিকল্পনা আছে।
2. **Architecture & Implementation Inventory:** কোন সক্ষমতার বর্তমান ক্যানোনিকাল ইমপ্লিমেন্টেশন কোনটি, কোথায় ডুপ্লিকেট রয়েছে, এবং রিফ্যাক্টরের পর টার্গেট আর্কিটেকচার কী হবে (`CURRENT → TARGET`)।
3. **Refactor Preservation Matrix:** রিফ্যাক্টরিং চলাকালীন কোন কোন সক্ষমতা কোনো অবস্থাতেই ধ্বংস করা যাবে না (MUST PRESERVE) এবং তার ৩-স্তর ভেরিফিকেশন পদ্ধতি।

---

## 🏷️ ২. স্ট্যাটাস ও এভিডেন্স ফ্রেমওয়ার্ক (Status & Evidence Taxonomy)

“Plan আছে” আর “Capability কাজ করছে” এক জিনিস নয়। বিভ্রান্তি দূর করতে প্রতিটি সক্ষমতাকে কঠোরভাবে শ্রেণীবদ্ধ করা হলো:

### ২.১ ছয়টি সুনির্দিষ্ট স্ট্যাটাস (The 6 States)

```text
VERIFIED  →  PARTIAL  →  IN_PROGRESS  →  PLANNED  →  PROPOSED  →  DEPRECATED
```

| স্ট্যাটাস | সংজ্ঞা (Definition) | মানদণ্ড (Criteria) |
| :--- | :--- | :--- |
| **`VERIFIED`** | পূর্ণ সক্ষম ও প্রোডাকশন-রেডি | কোড ডিস্কে উপস্থিত, অটোমেটেড টেস্ট পাস, লাইভ কলার আছে, কোনো ব্লকার নেই। |
| **`PARTIAL`** | বাস্তবায়ন আংশিক বা শর্তসাপেক্ষ | আসল কোড কাজ করে কিন্তু কোনো কোনো পাথ বা কন্ট্রাক্ট অসম্পূর্ণ বা ফ্ল্যাগের পেছনে। |
| **`IN_PROGRESS`** | সক্রিয়ভাবে নির্মাণাধীন | সক্রিয় ব্রাঞ্চ/PR বা স্প্রিন্টে কোড লেখা চলছে; ভিত্তি তৈরি কিন্তু পূর্ণাঙ্গ নয়। |
| **`PLANNED`** | অনুমোদিত নকশা ও রোডম্যাপে আছে | আর্কিটেকচার ডকুমেন্ট/স্কিমা প্রস্তুত, কিন্তু কার্যকর কোড এখনও লেখা হয়নি। |
| **`PROPOSED`** | প্রস্তাবিত আইডিয়া বা ড্রাফট | RFC বা আলোচনার পর্যায়ে রয়েছে; অনুমোদন বা প্রায়োরিটাইজেশন বাকি। |
| **`DEPRECATED`** | অপসারণ-নির্ধারিত | বিকল্প ক্যানোনিকাল পাথ প্রস্তুত; নতুন ব্যবহারে নিষেধাজ্ঞা এবং শিডিউল করা ডিলিট। |

### ২.২ প্রমাণের স্তরসমূহ (Evidence Hierarchy)

| Evidence ট্যাগ | অর্থ ও স্তর | যাচাইয়ের মাধ্যম |
| :--- | :--- | :--- |
| **`CODE`** | প্রোডাকশন কোড বিদ্যমান | সোর্স ফাইলে ফাংশন/ক্লাস কার্যকরভাবে বিদ্যমান। |
| **`TEST`** | অটোমেটেড টেস্ট বিদ্যমান | `pytest` বা E2E টেস্ট দিয়ে ফাংশনালিটি অ্যাসার্ট করা। |
| **`RUNTIME`** | লাইভ রানটাইম প্রমাণ | সার্ভার বুট, API রেসপন্স বা লাইভ ডেপ্লয়মেন্টে কার্যকর। |
| **`CI`** | অটোমেটেড গেটওয়ে এনফোর্সড | GitHub Actions ওয়ার্কফ্লোতে ভ্যালিডেশন সক্রিয়। |
| **`DOCUMENT`** | স্পেসিফিকেশন ও স্কিমা | আর্কিটেকচার ড্রয়িং, স্কিমা ফাইল বা অফিসিয়াল গাইড বিদ্যমান। |
| **`PLAN_ONLY`** | শুধুমাত্র রোডম্যাপ বা ইস্যু | কোড বা টেস্ট নেই, কেবল লিখিত পরিকল্পনা রয়েছে। |

---

## 📊 ৩. ভিউ ১: মাস্টার ক্যাপাবিলিটি ইনভেন্টরি (Master Capability Inventory)

| ID | ক্যাটাগরি | সক্ষমতার নাম (Capability) | স্ট্যাটাস | এভিডেন্স (Evidence) | ক্যানোনিকাল ওনার / পাথ | প্রিজারভ? | টার্গেট আর্কিটেকচার |
| :--- | :--- | :--- | :---: | :--- | :--- | :---: | :--- |
| **`CAP-AI-01`** | **AI** | Multi-LLM Provider Engine | `VERIFIED` | `CODE`, `TEST`, `RUNTIME` | `backend/core/llm/` | **MUST** | Canonical Unified LLM Gateway |
| **`CAP-AI-02`** | **AI** | Intelligent Model & Budget Routing | `VERIFIED` | `CODE`, `TEST` | `backend/core/llm/advanced_model_router.py` | **MUST** | Dynamic Tiered Router + Fallback |
| **`CAP-AI-03`** | **AI** | Free Tier Token & Quota Tracking | `VERIFIED` | `CODE`, `TEST` | `backend/core/llm/free_tier_tracker.py` | **MUST** | Distributed Redis/DB Budget Tracker |
| **`CAP-AGT-01`** | **Agents** | Multi-Agent Orchestration Engine | `VERIFIED` | `CODE`, `TEST` | `backend/core/agents/` | **MUST** | Event-Driven Multi-Agent Bus |
| **`CAP-AGT-02`** | **Agents** | Autonomous Role & Slot Governance | `VERIFIED` | `CI`, `CODE` | `scripts/agents/acquire_role_slot.py` | **MUST** | Branch-as-Lease + Mesh Protocol |
| **`CAP-AGT-03`** | **Agents** | Collective Multi-Agent Memory & Experience | `PARTIAL` | `CODE`, `TEST` | `backend/core/ai_memory/` | **MUST** | Shared Experience & Solution Layer |
| **`CAP-AGT-04`** | **Agents** | Agent Task Queues & Mailbox | `VERIFIED` | `CODE`, `RUNTIME` | `backend/api/routes/agent_tasks.py` | **MUST** | Unified Agent Task & Mailbox Engine |
| **`CAP-MCP-01`** | **MCP** | MCP Control Tower & Fleet Presence | `VERIFIED` | `CODE`, `RUNTIME` | `backend/tools/mcp/`, MCP Tower Client | **MUST** | Central Mesh Control Tower |
| **`CAP-MCP-02`** | **MCP** | Agent-to-MCP Server Connection & Tools | `VERIFIED` | `CODE`, `TEST` | `backend/api/routes/mcp_hub.py` | **MUST** | Consolidate Stdio + REST MCP Hub |
| **`CAP-MCP-03`** | **MCP** | Tamper-Evident MCP Audit Chain | `VERIFIED` | `CODE`, `TEST` | `backend/core/mcp_audit.py` | **MUST** | Cryptographic Action Audit Ledger |
| **`CAP-MEM-01`** | **Memory** | Episodic Conversation Memory | `VERIFIED` | `CODE`, `TEST` | `backend/memory/episodic_memory.py` | **MUST** | Unified Session/Episodic Store |
| **`CAP-MEM-02`** | **Memory** | Semantic Vector Search (pgvector) | `VERIFIED` | `CODE`, `TEST` | `backend/core/ai_memory/vector_store.py` | **MUST** | Unified pgvector / Qdrant Engine |
| **`CAP-MEM-03`** | **Memory** | Problem → Attempt → Solution Reuse | `PARTIAL` | `CODE`, `DOCUMENT` | `backend/core/intelligence/` | **MUST** | Single Agent Experience Engine |
| **`CAP-MEM-04`** | **Memory** | Auto-RAG Context Injection | `VERIFIED` | `CODE`, `TEST` | `backend/core/memory/auto_rag_injector.py` | **MUST** | Context Assembly Pipeline |
| **`CAP-BRW-01`** | **Browser** | Headless Browser Automation (Playwright) | `VERIFIED` | `CODE`, `TEST` | `backend/api/routes/browser_routes.py` | **MUST** | Canonical Browser Service Provider |
| **`CAP-BRW-02`** | **Browser** | Browser Render Proxy & Action Registry | `VERIFIED` | `CODE`, `RUNTIME` | `backend/api/routes/browser/_render_proxy.py` | **MUST** | Secure Render & Event Streamer |
| **`CAP-BRW-03`** | **Browser** | Persistent Session / Authenticated State | `PARTIAL` | `CODE`, `DOCUMENT` | `backend/tools/browser/` | **MUST** | Encrypted Session Vault |
| **`CAP-EXE-01`** | **Execution** | Local Docker / Isolated Subprocess Sandbox | `VERIFIED` | `CODE`, `TEST` | `backend/sandbox/docker_sandbox.py` | **MUST** | Pluggable Execution Sandbox Engine |
| **`CAP-EXE-02`** | **Execution** | Cloud Sandbox Provider Abstraction | `PARTIAL` | `CODE`, `TEST` | `backend/tests/tools/test_cloud_sandbox_full.py` | **MUST** | E2B / Modal / Cloud Sandbox Adapter |
| **`CAP-WRK-01`** | **Workspace** | Agent Shared Workspace Management | `VERIFIED` | `CODE`, `TEST` | `backend/api/routes/agent_workspace.py` | **MUST** | Dynamic Workspace Allocation API |
| **`CAP-WRK-02`** | **Workspace** | Multi-Platform Cloud Workspace Orchestrator | `IN_PROGRESS` | `DOCUMENT`, `CODE` | `docs/architecture/MULTI_PLATFORM_...` | **MUST** | Codespaces / Gitpod Workspace Router |
| **`CAP-WRK-03`** | **Workspace** | Multi-Account Legitimate Capacity Pool | `PLANNED` | `DOCUMENT`, `PLAN_ONLY`| Roadmap / Architecture Spec | **MUST** | Capacity-Based Quota Scheduler |
| **`CAP-GIT-01`** | **GitHub** | Atomic Issue Claim & Lock Protocol | `VERIFIED` | `CI`, `CODE` | `scripts/ci/atomic_claim.sh` | **MUST** | GSPQ Autonomous Claim Engine |
| **`CAP-GIT-02`** | **GitHub** | Autonomous Branch-PR-Merge Workflow | `VERIFIED` | `CI`, `CODE` | `.github/constitution/rules.yml` | **MUST** | Zero-Human Coder Lane + PR Helper |
| **`CAP-SEC-01`** | **Security** | Secret Vault & Infisical Reconciler | `VERIFIED` | `CODE`, `CI` | `backend/core/security/`, `reconcile_...` | **MUST** | Strict Zero-Leak Vault Provider |
| **`CAP-SEC-02`** | **Security** | Autonomous Security Guardian & Gatekeeper | `PARTIAL` | `CODE`, `TEST` | `backend/adaptive_engine/security_guardian.py`| **MUST** | Pre-commit / Pre-merge Policy Engine |
| **`CAP-GOV-01`** | **Governance**| Scope, Lease & Collision CI Gates | `VERIFIED` | `CI`, `CODE` | `.github/workflows/system-gates.yml` | **MUST** | Constitutional Gate Registry |
| **`CAP-GOV-02`** | **Governance**| 3-Tier Verification (Reflection/Smoke/Pytest)| `VERIFIED` | `CI`, `CODE` | `AGENTS.md` Invariant Protocol | **MUST** | Mandatory Verification Barrier |
| **`CAP-LRN-01`** | **Learning** | Self-Evolution & Performance Oracle | `PARTIAL` | `CODE`, `DOCUMENT` | `backend/core/self_evolution/` | **MUST** | Measurable Feedback Tuning Engine |
| **`CAP-UI-01`** | **Frontend** | Public Guest Chat & Onboarding Experience | `VERIFIED` | `CODE`, `TEST` | `frontend/src/` (Guest Flows) | **MUST** | Frictionless Interactive Web Shell |
| **`CAP-UI-02`** | **Frontend** | AI Studio, Agent Hub & Skill Management | `PARTIAL` | `CODE` | `frontend/src/` (Studio Views) | **MUST** | Unified Workspace & Agent Dashboard |
| **`CAP-UI-03`** | **Frontend** | Admin Console & Health Monitoring UI | `VERIFIED` | `CODE`, `RUNTIME` | `frontend/src/components/admin/` | **MUST** | Consolidated Single Admin Portal |
| **`CAP-INF-01`** | **Infra** | Render Production Web / Worker Deployment | `VERIFIED` | `CODE`, `RUNTIME` | `render.yaml`, Deploy Scripts | **MUST** | High-Availability Production Stack |
| **`CAP-INF-02`** | **Infra** | Redis Distributed Caching & Queue Bus | `VERIFIED` | `CODE`, `TEST` | `backend/core/cache/` | **MUST** | Canonical Redis Client & Degraded Mode |
| **`CAP-OBS-01`** | **Observability**| Aggregated Health Preflight & Metrics | `VERIFIED` | `CODE`, `RUNTIME` | `backend/api/routes/health_aggregation.py` | **MUST** | Central Telemetry & Health Bus |
| **`CAP-SCH-01`** | **Scheduling**| Autonomous Cron & Agent Scheduled Jobs | `PARTIAL` | `CODE`, `TEST` | `backend/core/automation/` | **MUST** | Celery/Redis Robust Task Scheduler |

---

## 🏛️ ৪. ভিউ ২: আর্কিটেকচার ও ইমপ্লিমেন্টেশন ইনভেন্টরি (`CURRENT → TARGET`)

SupremeAI কোডবেসে প্রধান সমস্যা হলো: **ফিচার অনেক, কিন্তু বাস্তবায়নে ডুপ্লিকেশন ও ফ্র্যাগমেন্টেশন বিদ্যমান**। নিচে প্রতিটি মূল এরিয়ার বর্তমান রূপ, ডুপ্লিকেট পাথ এবং রিফ্যাক্টরের পর লক্ষ্য দেওয়া হলো:

### ৪.১ LLM Gateway & Provider Abstraction (`CAP-AI-01`, `CAP-AI-02`)

```text
CURRENT:
  ├── backend/core/llm/ (advanced_model_router, free_tier_tracker, providers)
  ├── backend/api/routes/admin_llm.py (direct admin configuration)
  └── বিভিন্ন টুলে ছড়ানো সরাসরি llm client কল

TARGET:
  Canonical LLM Gateway (backend/core/llm/gateway.py)
          ├── Provider Adapter Interface (OpenAI, Anthropic, Gemini, Groq, Ollama)
          ├── Model Router & Fallback Chain (Cost, Latency, Capability)
          ├── Token & Budget Policy Enforcement (Per-Tenant / Free-Tier)
          └── Single Observability Tap (Latency, Prompt Tokens, Completion Tokens)
```
- **Known Duplicate Paths:** `backend/tools/ensemble_router.py`, `backend/core/llm/` এর ভেতরে ওভারল্যাপিং রাউটার।
- **Preservation Invariant:** যেকোনো প্রোভাইডার ডাউন হলে যেন স্বয়ংক্রিয় ফলব্যাক কার্যকর থাকে; বাজেট লিমিট যেন ক্রস না করে।

---

### ৪.২ Agent Orchestration & Governance (`CAP-AGT-01`, `CAP-AGT-02`)

```text
CURRENT:
  ├── backend/agents/autonomous_agent.py (পুরনো সংস্করণ)
  ├── backend/brain/autonomous_agent.py (সমান্তরাল সংস্করণ)
  ├── backend/core/agents/framework/agent_registry.py
  ├── backend/core/agent_registry.py
  └── scripts/agents/acquire_role_slot.py (স্লট ও ব্রাঞ্চ লিজ ম্যানেজমেন্ট)

TARGET:
  Canonical Agent Control Plane (backend/core/agents/)
          ├── Registry & Metadata: AgentRegistry (সিঙ্গেল ক্যানোনিকাল)
          ├── Runtime Execution: AutonomousAgentRunner
          ├── Governance Engine: Role, Slot & Blast Radius Enforcement
          └── Mesh & Mailbox: Inter-Agent Message Delivery
```
- **Known Duplicate Paths:** `backend/agents/` বনাম `backend/brain/` বনাম `backend/core/agents/`।
- **Preservation Invariant:** ১ এজেন্ট = ১ স্লট = ১ ব্রাঞ্চ প্রোটোকল অক্ষত থাকতে হবে; কোনো এজেন্টের কাজ অন্য এজেন্টের ফাইলে কোলাইড করবে না।

---

### ৪.৩ Experience & Memory Engine (`CAP-MEM-01` to `CAP-MEM-04`)

```text
CURRENT:
  ├── backend/core/ai_memory/ (vector_store.py, retention.py — canonical pgvector)
  ├── backend/memory/ (episodic_memory.py, chromadb_store.py, mcp_server.py)
  ├── backend/core/memory/ (auto_rag_injector.py)
  └── backend/core/intelligence/ (অভিজ্ঞতা সংক্রান্ত র্যান্ডম লজিক)

TARGET:
  One Unified Agent Experience & Memory Layer (backend/core/memory/)
          ├── Session / Episodic Store (Short-term context & sliding window)
          ├── Vector & Semantic Store (Long-term pgvector / knowledge embeddings)
          ├── Collective Experience Engine:
          │     └── Schema: {problem_hash, attempt_trace, verified_solution, verification_hash}
          └── Auto-RAG Injector (Prompt-এ প্রাসঙ্গিক পূর্ব অভিজ্ঞতা ইনজেকশন)
```
- **Known Duplicate Paths:** `backend/memory/repository.py` বনাম `backend/core/ai_memory/repository.py`।
- **Preservation Invariant:** পূর্ববর্তী সেশনের শেখা অভিজ্ঞতা বা ফিক্স যেন হারিয়ে না যায়; একই বাগ দ্বিতীয়বার সমাধান করার সময় মেমোরি থেকে সলিউশন রিকল করতে হবে।

---

### ৪.৪ Browser Automation & Scraping (`CAP-BRW-01`, `CAP-BRW-02`)

```text
CURRENT:
  ├── backend/api/routes/browser_routes.py
  ├── backend/api/routes/browser/_render_proxy.py
  ├── backend/services/scraper/web_scraper.py
  ├── backend/tools/browser/web_scraper.py
  └── skills/dynamic/web_scraper.py

TARGET:
  Canonical Browser & Scraper Service (backend/services/browser/)
          ├── Browser Engine Adapter (Playwright Headless / Cloud Browser)
          ├── Action & Event Registry (Click, Type, Navigate, Screenshot)
          ├── Scraper Core (HTML extraction, Markdown conversion, Anti-detection)
          └── Secure Session Vault (Cookie / Auth Storage)
```
- **Known Duplicate Paths:** ৩টি আলাদা জায়গায় `web_scraper.py` ডুপ্লিকেট রয়েছে।
- **Preservation Invariant:** Headless রেন্ডারিং, লাইভ স্ক্রিনশট এবং authenticated সেশন বজায় রাখার ক্ষমতা সংরক্ষিত থাকবে।

---

### ৪.৫ Execution Sandbox & Cloud Workspaces (`CAP-EXE-01`, `CAP-WRK-01` to `CAP-WRK-03`)

```text
CURRENT:
  ├── backend/sandbox/docker_sandbox.py (লোকাল কনটেইনার)
  ├── backend/sandbox/file_isolation_gate.py (পাথ সিকিউরিটি)
  ├── backend/api/routes/agent_workspace.py (DB শেয়ার্ড ওয়ার্কস্পেস মডেল)
  └── docs/archive/MULTI_PLATFORM_AGENT_WORKSPACE_PLAN.md (উন্নত মাল্টি-অ্যাকাউন্ট প্ল্যান)

TARGET:
  Canonical Workspace & Sandbox Subsystem (backend/core/workspace/)
          ├── Workspace Abstraction Interface:
          │     ├── Local Docker Sandbox (Fast local testing)
          │     ├── Cloud Container Sandbox (E2B / Modal / RunPod)
          │     └── Cloud Development Workspace (GitHub Codespaces / Gitpod)
          ├── Legitimate Account Capacity Scheduler (Pool of quota-managed seats)
          └── File Isolation & Security Gate (Path traversal & host leak guard)
```
- **Preservation Invariant:** কোনো অবস্থাতেই হোস্ট মেশিনের কোড বা সিক্রেট স্যান্ডবক্স এজেন্টের কাছে লিক হবে না; স্যান্ডবক্স ক্র্যাশ করলে মূল সিস্টেম সুরক্ষিত থাকবে।

---

### ৪.৬ MCP Hub, Control Tower & Stdio Servers (`CAP-MCP-01` to `CAP-MCP-03`)

```text
CURRENT:
  ├── backend/tools/mcp/mcp_server.py (stdio Knowledge Graph)
  ├── backend/memory/mcp_server.py (memory KG stdio server)
  ├── backend/api/routes/mcp_hub.py (REST MCP marketplace & registry)
  └── backend/core/mcp_audit.py (tamper-evident hash chain)

TARGET:
  Unified MCP Subsystem (backend/core/mcp/)
          ├── MCP Server Core (Unified Stdio & SSE Transport)
          ├── Tool & Resource Registry (Dynamic tool discovery)
          ├── Cryptographic Audit Interceptor (প্রতিটি টুল কল হ্যাশ-চেইনে সংরক্ষিত)
          └── Tower Presence Bridge (Heartbeat & Mesh state)
```
- **Known Duplicate Paths:** ২টি আলাদা stdio mcp সার্ভার এবং ১টি আলাদা REST হাব।
- **Preservation Invariant:** এজেন্টের হার্টবিট, অডিট চেইনের অপরিবর্তনযোগ্যতা (tamper-evidence) এবং প্রয়োজনীয় টুল ইনভোকেশন সুরক্ষিত থাকবে।

---

### ৪.৭ Admin Dashboard & Surfaces (`CAP-UI-03`)

```text
CURRENT:
  ├── backend/api/routes/admin.py
  ├── backend/api/routes/admin_v1.py
  ├── backend/api/routes/admin_routes.py
  ├── backend/api/routes/admin_auth.py
  └── backend/api/routes/admin_dashboard/ (fragmented modules)

TARGET:
  Single Canonical Admin API (backend/api/routes/admin/)
          ├── Authentication & RBAC (SuperAdmin / Operator / Viewer)
          ├── System Telemetry & Health Metrics
          ├── Fleet & Agent Overseer (Presence, Kill-switch, Slots)
          └── Billing, LLM Tiers & Wallet Administration
```
- **Preservation Invariant:** অ্যাডমিন কন্ট্রোল প্যানেল থেকে সিস্টেম মনিটরিং এবং এমার্জেন্সি কিল-সুইচ পরিচালনার ক্ষমতা ১০০% অক্ষত থাকবে।

---

## 🛡️ ৫. ভিউ ৩: রিফ্যাক্টর প্রিজারভেশন ম্যাট্রিক্স (Refactor Preservation Matrix)

রিফ্যাক্টরিং বা কোড মার্জ করার সময় প্রতিটি স্টেপে নিচের ম্যাট্রিক্স মিলিয়ে অডিট সম্পন্ন করতে হবে। কোনো একটির ক্ষমতা হ্রাস পেলে রিফ্যাক্টর ব্যর্থ বলে গণ্য হবে।

```text
========================================================================================
                      THE 4-PILLAR ZERO-LOSS AUDIT RUBRIC
========================================================================================
1. System Stability   : আর্কিটেকচারে কোনো ব্রেকিং পরিবর্তন বা অঘোষিত সাইড-ইফেক্ট নেই?
2. Real Benefit       : বাস্তব উন্নতি হয়েছে? (LOC হ্রাস / ডুপ্লিকেট ছাঁটাই / নির্ভরযোগ্যতা বৃদ্ধি)
3. Zero Regression    : সব টেস্ট সফল? কোনো টেস্ট ডিলিট, স্কিপ বা ফেইক অ্যাসারশন করা হয়নি?
4. Scope Narrowness   : ঘোষিত ক্যানোনিকাল ফাইলের বাইরে ড্রাইভ-বাই রিফ্যাক্টরিং ঢুকেছে কি?
========================================================================================
```

| সক্ষমতা (Capability) | বর্তমান স্ট্যাটাস | রিফ্যাক্টর টার্গেট | প্রিজারভেশন স্ট্যাটাস | প্রাথমিক ভেরিফিকেশন পদ্ধতি |
| :--- | :---: | :---: | :---: | :--- |
| **Multi-LLM Routing & Budget** | `VERIFIED` | Consolidated Gateway | **MUST PRESERVE** | `pytest backend/tests/core/llm/` + Mock Provider failover test |
| **Autonomous Role/Slot Lock** | `VERIFIED` | Core Constitution Gate| **MUST PRESERVE** | `python scripts/agents/acquire_role_slot.py --dry-run` |
| **MCP Control Tower & Presence**| `VERIFIED` | Unified MCP Hub | **MUST PRESERVE** | `python scripts/agents/mcp_tower_client.py heartbeat` |
| **Tamper-Evident Audit Chain** | `VERIFIED` | Canonical Audit Store | **MUST PRESERVE** | `pytest backend/tests/core/test_mcp_audit.py` |
| **Episodic & Vector Memory** | `VERIFIED` | Single Experience DB | **MUST PRESERVE** | `pytest backend/tests/core/ai_memory/` |
| **Browser Headless Automation** | `VERIFIED` | Single Scraper Service| **MUST PRESERVE** | `pytest backend/tests/api/routes/test_browser_routes.py` |
| **Docker / Cloud Sandbox** | `VERIFIED` | Unified Sandbox Core | **MUST PRESERVE** | `pytest backend/tests/tools/test_cloud_sandbox_full.py` |
| **Atomic GitHub Workflow** | `VERIFIED` | CI Gate Enforced | **MUST PRESERVE** | `.github/workflows/system-gates.yml` validation |
| **Infisical & Secrets Vault** | `VERIFIED` | Security Module Core | **MUST PRESERVE** | `python scripts/ci/reconcile_secrets_registry.py` |
| **Admin Console & Telemetry** | `VERIFIED` | Clean Admin Router | **MUST PRESERVE** | `pytest backend/tests/api/routes/test_admin*.py` |
| **Guest Chat E2E Experience** | `VERIFIED` | Unbroken UI Flow | **MUST PRESERVE** | Playwright E2E smoke tests |

---

## 📋 ৬. বিস্তারিত সক্ষমতা কার্ডসমূহ (Detailed Capability Cards)

### কার্ড ১: Multi-LLM Provider Engine & Router (`CAP-AI-01`, `CAP-AI-02`)
- **Name:** Multi-LLM Gateway and Budget-Aware Model Router
- **Category:** AI Engine
- **Current Status:** `VERIFIED`
- **Evidence:** `CODE` + `TEST` + `RUNTIME`
- **Canonical Path:** `backend/core/llm/`
- **Known Duplicate Paths:** `backend/tools/ensemble_router.py`
- **Dependencies:** LiteLLM / Provider SDKs, Redis (for distributed budget), PostgreSQL
- **User-Facing Impact:** দ্রুততম ও নির্ভরযোগ্য AI রেসপন্স; মডেল ডাউন থাকলে অটো ফলব্যাক।
- **Agent-Facing Impact:** কাজ অনুযায়ী উপযুক্ত ও শক্তিশালী মডেলে টাস্ক ডেলিগেশন।
- **Must Preserve?** **YES (CRITICAL)**
- **Refactor Target:**
  ```text
  CURRENT: core/llm এবং tools/ensemble_router এর মধ্যে ডুপ্লিকেট লজিক।
  TARGET : backend/core/llm/gateway.py - একমাত্র ক্যানোনিকাল গেটওয়ে।
  ```
- **Verification Method:**
  1. Reflection: `grep -rn "class LLMGateway" backend/core/llm`
  2. Boot Smoke: `python -c "import backend.core.llm; print('LLM stack OK')"`
  3. Pytest: `pytest backend/tests/core/llm/`

---

### কার্ড ২: Autonomous Role Slot & Branch Lease Protocol (`CAP-AGT-02`, `CAP-GIT-01`)
- **Name:** Branch-as-Lease & Atomic Task Claim Protocol
- **Category:** Agents & Governance
- **Current Status:** `VERIFIED`
- **Evidence:** `CI` + `CODE` + `RUNTIME`
- **Canonical Path:** `scripts/agents/acquire_role_slot.py`, `scripts/ci/atomic_claim.sh`, `AGENTS.md`
- **Known Duplicate Paths:** নেই (সরাসরি CI ও স্ক্রিপ্টে ক্যানোনিকাল)
- **Dependencies:** GitHub CLI (`gh`), Git, bash/python
- **User-Facing Impact:** কোনো মানুষের হস্তক্ষেপ ছাড়াই এজেন্টরা নিখুঁতভাবে ব্রাঞ্চ কেটে কাজ শেষ করে PR জমা দেয়।
- **Agent-Facing Impact:** ১ এজেন্ট = ১ স্লট = ১ ব্রাঞ্চ ইনভ্যারিয়েন্ট কার্যকর থাকে; ব্রাঞ্চ কলিশন শূন্য হয়।
- **Must Preserve?** **YES (CRITICAL)**
- **Refactor Target:**
  ```text
  CURRENT: স্ক্রিপ্ট ও কনস্টিটিউশন ফাইল সমন্বয়ে পরিচালিত।
  TARGET : সেন্ট্রাল কন্ট্রোল টাওয়ারের সাথে সম্পূর্ণ টাইটলি ইন্টিগ্রেটেড স্লট লিজ ইঞ্জিন।
  ```
- **Verification Method:**
  1. Reflection: `python scripts/agents/acquire_role_slot.py --help`
  2. Test Run: `scripts/ci/atomic_claim.sh --dry-run`

---

### কার্ড ৩: Collective Experience & Memory Layer (`CAP-MEM-01` to `CAP-MEM-03`)
- **Name:** Unified Experience & Solution Memory Engine
- **Category:** Memory & Intelligence
- **Current Status:** `PARTIAL`
- **Evidence:** `CODE` + `TEST` + `DOCUMENT`
- **Canonical Path:** `backend/core/ai_memory/` (pgvector), `backend/memory/episodic_memory.py`
- **Known Duplicate Paths:** `backend/memory/repository.py` বনাম `backend/core/ai_memory/repository.py`, `backend/core/memory/`
- **Dependencies:** PostgreSQL (pgvector extension), SQLAlchemy 2.0
- **User-Facing Impact:** চ্যাট হিস্ট্রি ও পূর্ববর্তী কথোপকথনের সঠিক পারসিস্টেন্স।
- **Agent-Facing Impact:** অতীতের সফল কোডিং ফিক্স ও সলিউশন রি-ইউজ করে তাৎক্ষণিক কোড জেনারেশন।
- **Must Preserve?** **YES (HIGH)**
- **Refactor Target:**
  ```text
  CURRENT: backend/memory/ এবং backend/core/ai_memory/ এ খণ্ডিত রূপ।
  TARGET : backend/core/memory/ এর অধীনে একক ক্যানোনিকাল সার্ভিস:
           - episodic (সেশন কনটেক্সট)
           - semantic (ভেক্টর সার্চ)
           - collective_experience (টাস্ক ও সলিউশন পেয়ার ডাটাবেস)
  ```
- **Verification Method:**
  1. Reflection: `python -c "import backend.core.ai_memory; print('AI Memory OK')"`
  2. Pytest: `pytest backend/tests/core/test_ai_memory*.py`

---

### কার্ড ৪: Headless Browser & Secure Scraping Engine (`CAP-BRW-01`, `CAP-BRW-02`)
- **Name:** Headless Browser Automation & Render Proxy
- **Category:** Browser & Automation
- **Current Status:** `VERIFIED`
- **Evidence:** `CODE` + `TEST` + `RUNTIME`
- **Canonical Path:** `backend/api/routes/browser_routes.py`, `backend/services/scraper/`
- **Known Duplicate Paths:** `backend/tools/browser/web_scraper.py`, `skills/dynamic/web_scraper.py`
- **Dependencies:** Playwright, BeautifulSoup4, FastAPI
- **User-Facing Impact:** ব্রাউজার অটোমেশন, ওয়েব রিসার্চ ও ডায়নামিক পৃষ্ঠা পার্সিং।
- **Agent-Facing Impact:** এজেন্ট যেকোনো ইউআরএল ভিজিট করে রেন্ডার করা কন্টেন্ট দেখতে পারে।
- **Must Preserve?** **YES (HIGH)**
- **Refactor Target:**
  ```text
  CURRENT: ৩টি ভিন্ন ফাইলে স্ক্র্যাপিং কোড ডুপ্লিকেট।
  TARGET : backend/services/browser/ এর অধীনে ক্যানোনিকাল ব্রাউজার ও স্ক্র্যাপার মডিউল।
  ```
- **Verification Method:**
  1. Pytest: `pytest backend/tests/api/routes/test_browser_routes.py`

---

### কার্ড ৫: Multi-Platform Cloud Workspace Orchestrator (`CAP-WRK-02`, `CAP-WRK-03`)
- **Name:** Multi-Platform & Multi-Account Cloud Workspace Scheduler
- **Category:** Workspace & Compute
- **Current Status:** `IN_PROGRESS` (Architecture & Contracts designed; dynamic routing in build)
- **Evidence:** `DOCUMENT` + `CODE`
- **Canonical Path:** `docs/archive/MULTI_PLATFORM_AGENT_WORKSPACE_PLAN.md`, `backend/api/routes/agent_workspace.py`
- **Dependencies:** Codespaces API, Gitpod API, Docker, Subprocess
- **User-Facing Impact:** স্থানীয় পিসির প্রসেসর বা র‍্যামের ওপর নির্ভর না করে ক্লাউডে শত শত এজেন্ট সমান্তরালে কাজ করতে পারা।
- **Agent-Facing Impact:** ক্লাউড আইসোলেশনে সম্পূর্ণ আলাদা ডেভেলপমেন্ট ওয়ার্কস্পেস পাওয়া।
- **Must Preserve?** **YES (CORE ROADMAP)**
- **Refactor Target:**
  ```text
  CURRENT: লোকাল ডকার স্যান্ডবক্স এবং ডিবি মডেল রয়েছে; ক্লাউড শিডিউলার প্ল্যান ডকুমেন্টে।
  TARGET : Canonical WorkspaceProvider Abstraction:
           - Account Pool Manager (১৯টি অনুমোদিত অ্যাকাউন্ট থেকে ক্যাপাসিটি রিক্রুটমেন্ট)
           - Dynamic Platform Router (Codespaces / Gitpod / Local)
  ```
- **Verification Method:**
  1. Contract Tests: `pytest backend/tests/core/contracts/test_canonical_contracts.py`

---

## 🛑 ৭. রিফ্যাক্টরিং চলাকালীন সিদ্ধান্ত গ্রহণের নিয়ম (Refactoring Decision Rules)

যখনই কোনো কোডার এজেন্ট বা ডেভেলপার কোনো ফাইল মুছে ফেলার বা বড় পরিবর্তনের সিদ্ধান্ত নেবে, তখন নিচের ৫টি নিয়ম মেনে চলতে হবে:

1. **Rule 1 (Check Before Delete):** কোনো ফাইল ডিলিট করার আগে এই `CAPABILITY_LEDGER.md`-তে দেখুন সেটি কোনো ক্যানোনিকাল পাথের অন্তর্ভুক্ত কি না। যদি ডুপ্লিকেট পাথ হয়, তবে নিশ্চিত করুন ক্যানোনিকাল পাথে সমস্ত দরকারি লজিক সংরক্ষিত আছে।
2. **Rule 2 (Verify First Invariant):** অনুমানে কোনো ফাইল এডিট বা মুছে ফেলা নিষিদ্ধ। পরিবর্তনের আগে ও পরে ৩ স্তর যাচাই আবশ্যক:
   - স্তর ১: Reflection check (`grep -rn "symbol"` - কোনো রেফারেন্স বাকি আছে কিনা)
   - স্তর ২: Boot smoke test (`python -c "import main"`)
   - স্তর ৩: Pytest (`pytest <targeted-test-suite>`)
3. **Rule 3 (No Test Manipulation):** টেস্ট ম্যানিপুলেশন (টেস্ট মুছে ফেলা, স্কিপ করা, বা ডামি অ্যাসারশন তৈরি) সর্বোচ্চ গুরুতর অপরাধ। রিফ্যাক্টরিংয়ের পরেও পূর্বের টেস্ট গ্রিন থাকতে হবে।
4. **Rule 4 (Harvest Before Pruning):** ডুপ্লিকেট মডিউল মুছে ফেলার আগে তার উন্নত লজিকটি ক্যানোনিকাল ফাইলে ধারন (harvest) করতে হবে। একে বলা হয় **Zero Capability Loss Law**।
5. **Rule 5 (Maintain Bengali Communication):** কোডের সমস্ত মন্তব্যে `# বাংলা মন্তব্য:` এবং পরিবর্তন সংক্রান্ত যেকোনো ডকুমেন্টে বাংলা বা বাংলিশ ব্যবহার বাধ্যতামূলক।

---

## 🔄 ৮. পরিবর্তন ট্র্যাকিং ও অডিট লগ (Change Tracking & Audit Log)

| তারিখ | সংস্করণ | পরিবর্তনের সারসংক্ষেপ | দায়িত্বপ্রাপ্ত এজেন্ট / অডিটর |
| :---: | :---: | :--- | :--- |
| `2026-09-28` | `pre-refactor-v1.0` | প্রাথমিক বেসলাইন তৈরি: ২৬টি সক্ষমতা ক্যাটাগরাইজড, ৩টি মাস্টার ভিউ, এভিডেন্স ফ্রেমওয়ার্ক এবং ৬টি স্ট্যাটাস ট্যাক্সোনমি চূড়ান্ত। | SupremeAI Lead Architect / Admin |
