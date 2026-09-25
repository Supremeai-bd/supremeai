# SupremeAI প্ল্যান বিশ্লেষণ রিপোর্ট — "কোনটা রাখব, কোনটা ফেলব, কীভাবে একসাথে করব"

> **তৈরি:** 2026-09-25 · **উৎস:** `main` branch fresh clone (commit `76de370`)
> **স্কোপ:** 183টি প্ল্যান ফাইল + আসল কোডবেস (backend/frontend/MCP/infra/CI)
> **পদ্ধতি:** ৭টা প্যারালেল ডিপ-রিড এজেন্ট (architecture / crown_jewel / design / features / infrastructure / phases / codebase-ground-truth) → এক সিনথেসিস

---

## ০. এক নজরে ফলাফল (Executive Summary)

তোমাদের প্রজেক্ট একটা **কাজ করছে এমন প্রোডাক্ট** — কিন্তু একটা **কাজ করছে না এমন ডকুমেন্টেশন**। ১৮৩টি প্ল্যান ফাইলের মধ্যে:

| বিভাগ | সংখ্যা | অর্থ |
|---|---|---|
| সত্যিকারের ক্যানোনিকাল (রাখবে) | **~২৫** | এই ফাইলগুলো আসল সত্যের উৎস |
| মার্জ করা দরকার (অন্য ফাইলে মিশে যাবে) | **~২০** | ভালো কন্টেন্ট আছে কিন্তু ডুপ্লিকেট |
| আর্কাইভ রেফারেন্স (ইতিহাসের জন্য) | **~৯০** | পড়তে হবে না, কিন্তু মুছবে না |
| ডিলিট/স্টেল (বাদ দেওয়া উচিত) | **~৪৮** | জাভা যুগের, কন্ট্রাডিক্টরি, বা শুধু নয়েজ |

**এক লাইনে ডায়াগনসিস:** তোমাদের সমস্যা "অনেক প্ল্যান" না — সমস্যা হলো **৫টা মাস্টার প্ল্যান, ৯টা "Phase 1", ৩টা স্ট্যাক যুগের ওভারল্যাপ, আর কোনো relationship লেয়ার নেই**।

**এক লাইনে সমাধান:** প্রতিটা প্ল্যানকে একটা **ক্যানোনিকাল ফাইলে ভেতরে রাখো** (extend-not-replace), আর পুরো সিস্টেমকে একটাই **"Capability → Run → Verify" লুপ** হিসেবে চালাও — বাকি সব ডুপ্লিকেশন সেই লুপের ভেতর দিয়ে গলে যাবে।

---

## ১. আসল প্রোডাক্টটা কী (Ground Truth — কোড থেকে প্রমাণ)

প্ল্যান ফাইলগুলো যা বলে তার চেয়ে কোড অনেক বেশি পরিণত। **মেশিন-ভেরিফাইড সত্য** (`STATUS-PROOF.md`, CI-তে diff-gated):

### যা সত্যিই বানানো আর কাজ করছে ✅

1. **FastAPI ব্যাকএন্ড** — ১২১টা রাউটার, **৭৬২টা রেজিস্টার্ড রাউট** (মেশিন-কাউন্টেড), ৩৮টা সার্ভিস, ৪৭টা সাবসিস্টেম। ৬২/৬২ মিশন টেস্ট পাস।
2. **MCP Control Tower** — ১,২৮৬-লাইনের আসল টাইপস্ক্রিপ্ট সার্ভার, **~৮০টা MCP টুল**, stdio + HTTP Streamable দুই ট্রান্সপোর্ট, টেন্যান্ট রেজিস্ট্রি, PR Guardian (improvement-gated অটো-মার্জ)।
3. **React 19 + Vite 7 ফ্রন্টএন্ড** — ১৩টা Zustand স্টোর, ৪০+ সার্ভিস, ১১০টা ভাইটেস্ট ফাইল, ৪টা Playwright E2E, `localFirstDb` অফলাইন-ফার্স্ট পারসিস্টেন্স।
4. **৫-সার্ভিস Docker Compose টপোলজি** — core / worker / scraper / mcp / cloudflare-worker, VERSION-tagged ইমেজ।
5. **প্রোডাকশন চেইন প্রথমবার রান করেছে ২০২৬-০৯-১৭**, লাইভ ভেরিফাইড ২০২৬-০৯-১৮ — SPA 200, CORS ভেরিফাইড, health live/ready 200।
6. **ভেন্ডর-অ্যাগনস্টিক LLM গেটওয়ে** — ১৪টা প্রোভাইডার (Gemini/OpenRouter/OpenAI/Mistral/Groq/Anthropic/DeepSeek/Cohere/Bynara/BAI/Together/HF/Nvidia/Ollama), N=0 হলে honest graceful রেসপন্স।
7. **ফ্রি-টিয়ার ফেডারেশন সত্যিই কাজ করছে** — ৪টা Render অ্যাকাউন্টে ৪টা সার্ভিস, Cloudflare Worker edge রাউটার KV-based circuit breaker + edge rate-limit + always-on keepalive পিং।
8. **diff-gated ডকুমেন্ট ট্রুথফুলনেস** — `generate_status_proof.py` প্রতি CI রানে STATUS.md-এর দাবা কোডের সাথে মিলিয়ে দেখে, drift হলে CI ফেল।
9. **spec-kit এক্সিকিউশন ফ্রেমওয়ার্ক** — ২টা অ্যাক্টিভ স্পেক (config hardening, crawler upgrade), প্রতিটায় constitution check + DoD gate।
10. **৩০টা GitHub workflow + ৯৭টা স্ক্রিপ্ট** — governance, audit, security, observability, deploy gates, live smoke, DAST।

### যা বানানো আছে কিন্তু ভেরিফাই হয়নি 🟡

- Async Worker (deployed, runtime-unprobed)
- MCP Control Tower runtime (build+deploy OK, probe pending)
- Cloudflare Edge Router (wrangler deploy OK, smoke chain probe নেই)
- DB query-path liveness (schema contract OK, query path unprobed)
- Thin clients (Tauri/Electron + VS Code ext — শুধু build gate)

### যা দাবি করা আছে কিন্তু মৃত/ডুপ্লিকেট ❌

- **৯টা রেট-লিমিটার** (দুই জায়গায় `tenant_rate_limiter.py`)
- **৬টা LLM গেটওয়ে** ফাইল
- **৮+ প্রোভাইডার লিস্ট** কনফিগে ভাসছে
- **৪টা ফ্রন্টএন্ড HTTP স্ট্যাক**
- **~৩৬টা মেমরি ফাইল, ৩টা API রাউট**
- **৮টা Zustand স্টোর** (`useStore` vs `unifiedStore` ওভারল্যাপ)
- **৩টা ENV রেজিস্ট্রি** drift করছে (`CONFIG_SCHEMA` ~130 + `ENV_REGISTRY` ~50 + `CONFIG_SPECS` 200+)
- **৩টা রাউট ইনভেন্টরি** drift করছে (762 vs 816 vs 568)
- **305KB DOCUMENTATION_MASTER_INDEX.md** মুছে যাওয়া `.kilo/` ডিরেক্টরির 428 ফাইল ইনডেক্স করছে

> **পাঁচটা সবচেয়ে গুরুত্বপূর্ণ লেসন (LESSONS_LEARNED.md থেকে):**
> 1. **Zero local-machine dependency** — কাজের ১%-ও লোকাল PC-র উপর নির্ভর করবে না
> 2. **Zero-hardcode mandate** — কিছুই হার্ডকোড না; সব ড্যাশবোর্ড/DB থেকে কন্ট্রোল
> 3. **"Scanner having a vuln type" ≠ "app is secure"** — প্রতিটা কন্ট্রোলের বিহেভিয়র-লেভেল টেস্ট দরকার
> 4. **Bare `localhost` সম্পূর্ণ নিষিদ্ধ** — সব জায়গায় প্রোডাকশন ডোমেইন বা টানেল
> 5. **Silent 404 contracts** — ফ্রন্টএন্ড যে এন্ডপয়েন্ট কল করে সেটা ব্যাকএন্ডে নাও থাকতে পারে; রানটাইম প্যারিটি অডিট দরকার

---

## ২. প্ল্যান জঙ্গলের ডায়াগনসিস

### ২.১ পাঁচটা মাস্টার প্ল্যান একসাথে লড়ছে

| মাস্টার প্ল্যান | লাইন | দাবি | সত্য |
|---|---|---|---|
| `SUPREMEAI_MASTER_PLAN_CANONICAL.md` | 1,037 | canonical SoT | ✅ সবচেয়ে ভালো, কিন্তু ৪টা রোল এক ফাইলে |
| `UNIFIED_ECOSYSTEM_ARCHITECTURE_PLAN.md` | 1,950 | ৭ চুক্তি + ৪ প্লেন | ✅ ৭-চুক্তি মডেল সেরা, বাকিটা ডুপ্লিকেট |
| `codebase_aligned_master_roadmap.md` | 817 | Phase 0-13 hardening | ✅ "What NOT to Do" লিস্ট দারুণ, বাকি ডুপ্লিকেট |
| `self_learning_ecosystem_transformation_roadmap.md` | 2,141 | ১০টা Principle A-J | ✅ Principle গুলো সেরা, বাকি ২,০০০ লাইন ডুপ্লিকেট |
| `living_autonomous_intelligence_synthesis.md` | 170 | "Cognitive Twin Engine" | ❌ মার্কেটিং-গ্রেড ফ্যান্টাসি |

**ফলাফল:** ৫টা মাস্টার প্ল্যানের ভেতর থেকে সত্যিকারের ক্যানোনিকাল আইডিয়া বের করলে ~৩,৫০০ লাইন হয় — এখন ২৪,৫০০ লাইন। ৭× রিডাকশন, জিরো ইনফরমেশন লস।

### ২.২ নয়টা "Phase 1" সংজ্ঞা ঘুরছে

`phase1_foundation.md` (weeks 1-4), `phase_1_execution_patch_notes.md` (master plan Phase 1), `MASTER_PLAN_CANONICAL` Phase 1, `codebase_aligned` Phase 1, `self_learning` Phase 1, `production_upgrade_v2` Phase 1, `PLATFORM_OSS` Phase 1, `UNIFIED_ECOSYSTEM` Phase 1, `SOFTWARE_ENGINEERING_EXCELLENCE` Phase 1, `CANONICAL_PLANNING_RECONCILIATION` Phase 1।

**আসল ফেজ মডেল:** `MASTER_PLAN_CANONICAL`-এর **Phase 0 → Phase 6** (৭-ফেজ): Stop the Bleed → Capability Completion → Reliability Moat → Own Model v1 → Public Benchmark → Production Hardening → Compounding। বাকি সব `historical`।

### ২.৩ তিনটা স্ট্যাক যুগের ওভারল্যাপ

| যুগ | স্ট্যাক | কোথায় দেখা যায় | অবস্থা |
|---|---|---|---|
| **Pre-pivot** | Java/Spring Boot + Firebase + Flutter | `phase4_optimization.md`, `file_disposition_and_retention_list.md`, `supremeai_quick_start_onboarding_checklist.md` | ❌ সম্পূর্ণ স্টেল |
| **Mid-pivot** | Flask + Firebase + MongoDB + Vue | `cross_module_dependency_matrix.md`, `agent_and_engineer_skill_requirements.md` | ❌ ভুল স্ট্যাক |
| **Post-pivot (বর্তমান)** | Python/FastAPI + React + Render + Supabase + Cloudflare + Alembic | `STATUS.md`, `implementation_and_milestone_trackers.md`, সত্যিকারের কোড | ✅ এটাই সত্য |

> ১৪টা phases/ ফাইলের মধ্যে মাত্র ৪টা বর্তমান স্ট্যাক রিফ্লেক্ট করে। বাকি ১০টা ভুল স্ট্যাক বর্ণনা করে — যে কেউ এগুলো পড়ে কাজ শুরু করলে ভুল জায়গায় কাজ করবে।

### ২.৪ কন্ট্রাডিকশন (একে অপরের সাথে লড়াই)

1. **মাল্টি-অ্যাকাউন্ট কোটা vs ফ্রি-টিয়ার পলিসি** — `cloudflare_7node` + `kaggle_6node` প্ল্যান স্পষ্টভাবে `free_tier_scaling_constitution` Rule 2 ভায়োলেট করে
2. **ভেক্টর স্টোর: Qdrant vs pgvector** — `Plan_03` বলে Qdrant, `PLAN_004`/`PLAN_006` বলে Supabase pgvector (সত্য: pgvector)
3. **অনবোর্ডিং: zero-config vs API-key-first** — `customer_onboarding_flow.md` বলে "60 সেকেন্ডে প্রথম টাস্ক, কোনো API কী নয়", কিন্তু আসল `OnboardingWizard.tsx` = `StepApiKey → StepModelSelect → StepFirstChat` — প্রথম ধাপেই API কী!
4. **ডার্ক মোড** — মাস্টার প্ল্যান বলে "dark-first", `ux_ui_best_practices` বলে "dark mode default নয়, option থাকুক"

---

## ৩. প্রতিটা ক্লাস্টারের ফলাফল — কোনটা বেস্ট, কোনটা বাদ

### ৩.১ Architecture cluster (৩৫ ফাইল, ২৪.৫K লাইন)

**৩টা সত্যিকারের ক্যানোনিকাল:**
- `SUPREMEAI_MASTER_PLAN_CANONICAL.md` — ভিশন + অডিট + রোডম্যাপ (৫টা ভাইবলিং ফাইল একটায় মার্জ করলে এটাই হবে)
- `PLAN_LIFECYCLE_POLICY.md` + `CANONICAL_PLANNING_RECONCILIATION_AND_GUARDRAILS_PLAN.md` — গভর্নেন্স স্পাইন (৭-স্টেট স্টেট মেশিন + evidence discipline)
- `PLAN_TO_CODE_TRACEABILITY_MATRIX.md` + `implementation_plan.md` + `IMPLEMENTATION_TRACK_EXECUTION_ORDER_2026-09-18.md` — এক্সিকিউশন + ভেরিফিকেশন ত্রয়ী

**বাদ দেওয়া উচিত:** `ROADMAP_ECOSYSTEM_ARCHITECTURE_BN.md` (নিজেই `superseded` ঘোষণা করেছে), `visual_component_integration_topology.md` (পিওর ডুপ্লিকেট), `ai_model_comparative_matrix_bangla.md` (সাবজেক্টিভ, স্টেল)।

**আর্কাইভ:** `unified_fastmcp_control_tower_multitenant_master_plan_bn.md` (৩,৭০৫ লাইন! লাইভ MCP টাওয়ার দ্বারা সুপারসিডেড), `SUPREME_TELEPORT_MULTI_DEVICE_REMOTE_CONTROL_PLAN.md` (০% কোড, ডিপ্রায়োরিটাইজড)।

### ৩.২ Crown Jewel series (২৪ মডিউল)

**৬টা আসল "crown jewel":**
1. **MODULE_03 (LLM Gateway)** — `InferenceContext` + Zero-Bypass Inference Boundary = পুরো প্ল্যাটফর্মের স্পাইন
2. **MODULE_15 (Security Organ Deep)** — deception-feedback loop, OWASP LLM Top-10 ম্যাপিং, anti-cargo-cult rejection log (PromptGuard-2 arXiv প্রমাণ সহ রিজেক্ট)
3. **MODULE_01 (Memory)** — ERR-F02 একমাত্র OPEN ফাউন্ডেশনাল ডিফেক্ট; ৩-পিলার স্ট্যাক (PLAN_002 in-session + PLAN_004 write-quality + PLAN_006 write-identity)
4. **MODULE_09 (Dormant Tools)** — এজেন্টরা আজ ০টা টুল কল করে; ReAct লুপ আনব্লক করার সবচেয়ে বড় লেভার
5. **MODULE_21 (Truth-Mirror Governance)** — ২৩টা অডিট ডককে পার্মানেন্ট গভর্নেন্সে রূপান্তর করে; honest-mock vs dishonest-fabrication ক্লাসিফিকেশন
6. **MODULE_19 (i18n Bengali)** — language-tax-reduction (৫× Indic টোকেন কস্ট); ব্র্যান্ডের গভীর আইডেন্টিটি

**এক্সিকিউশন প্রুফ আছে শুধু ২টায়:** MODULE_10 (P-A Wave-1) + MODULE_18 (P-A + P-B)। বাকি ২১টা `proposed`।

**১০+ নামকরা ডকট্রিন:** extend-not-replace (ERR-F02), store-before-carrier (M20), supervisor-as-heartbeat (M22), activation-gate (M18), meter-first (M16), retrieval-proof (M23), language-tax-reduction (M19), one-bridge-many-doors (M17), deception-feedback-loop (M15), exclusion-ratchet (M21)।

### ৩.৩ Features cluster (৭৬ ফাইল — সবচেয়ে বড়)

**মাত্র ৫টা ফাইলে হার্ড কমিট-SHA + টেস্ট-কাউন্ট প্রমাণ আছে:**
- `PLAN_001_ANTHROPIC_PROMPT_CACHING` (built, 10/10 + 70/70 tests)
- `PLAN_002_CLAUDE_STYLE_CONTEXT_COMPACTION` (built, commit `2fbe7fcd`, 11/11 tests)
- `PLAN_003_AIDER_STYLE_REPO_MAP` (built, commit `6a2e0464`)
- `PLAN_004_LETTA_STYLE_MEMORY_DISTILLATION` (built, commit `4575104f`, 13/13 tests)
- `PLAN_006_MEM0_STYLE_MEMORY_CONSOLIDATION` P-A (built, commit `2a39b5e9`, 12 tests)

**~৫০টা ফাইল নিরাপদে আর্কাইভ করা যায়:** জাভা যুগের স্টেল ডক, aspirational ভিশন ডক, ডুপ্লিকেট হাইজিন অডিট।

**সবচেয়ে বড় ডুপ্লিকেশন:** মেমরি স্টাইল প্ল্যান (৬টা), কোডবেস হাইজিন প্ল্যান (৭টা), self-evolution ভিশন (৯টা)।

### ৩.৪ Design cluster (১৪ ফাইল)

**৩টা ক্যানোনিকাল:**
- `supremeai_2_product_ui_ux_completeness_master_plan.md` — 70/20/10 ডকট্রিন, Workspace/Command Center, কালার টোকেন (আসল কোডে ইমপ্লিমেন্টেড)
- `single_frontend_role_based_auth_migration_roadmap.md` — আর্কিটেকচারাল স্পাইন (App.tsx কমেন্টে প্রমাণ: Phase 1/7 ডিন)
- `admin_dashboard_visual_and_api_gap_analysis.md` — একমাত্র ground-truth ভেরিফিকেশন আর্টিফ্যাক্ট (১৪টা নির্দিষ্ট ফেইলিং কম্পোনেন্ট নাম সহ)

**বাদ:** `dashboard_design_mockups.md` (broken `file:///C:/Users/...` ইমেজ লিংক), `dashboard_tab_design_plan.md` + `admin_dashboard_plan.md` (মৃত "Mission Command" ইসথেটিক, কোডে পরিবর্তিত)।

**সবচেয়ে বড় UX রিস্ক:** OnboardingWizard প্ল্যানের মূল থিসিস ভায়োলেট করে — "zero-config, 60s" প্ল্যানের বিপরীতে আসল উইজার্ড প্রথম ধাপে API কী চায়।

### ৩.৫ Infrastructure cluster (১৫ ফাইল)

**৪টা ক্যানোনিকাল:**
- `CI_CD_PIPELINE_ARCHITECTURE.md` — ৫-লেয়ার মডেল, SHA-pinned অ্যাকশন (লাইভ ও অ্যাকুরেট)
- `render_production_runtime_error_cleanup_plan.md` — capability-based log-severity ডকট্রিন (সত্যিই দারুণ লেখা)
- `third_party_env_and_secrets_operational_checklist.md` — সেরা সিক্রেট ইনভেন্টরি
- `supabase_database_schema_and_connection_management_plan.md` — DB সোর্স অফ ট্রুথ

**বাদ:** `production_upgrade_implementation_plan_v2.md` (aspirational enterprise-rewrite: Istio/Kong/NATS — Render ফ্রি-টিয়ারে অসম্ভব, বাস্তবতার বিপরীত), `cloud_ai_multi_provider_deployment_plan.md` (৫টা কাল্পনিক GCP Cloud Run URL)।

**ফ্রি-টিয়ার ফেডারেশন সত্যিই কাজ করছে** — কিন্তু সবচেয়ে বড় রিস্ক: **Render 512MB-এ ~৯০% মেমরি প্রেশার + সাইলেন্ট SQLite ফলব্যাক যা প্রোডাকশনে ডেটা হারায়**।

### ৩.৬ Phases cluster (১৯ ফাইল)

**মাত্র ৪টা ক্যানোনিকাল:**
- `implementation_and_milestone_trackers.md` — সবচেয়ে কংক্রিট ফাইল (আসল ফাইল পাথ, আসল স্ট্যাটাস, ব্যাচ কমান্ড)
- `plan_reconciliation_register.md` — ৯টা প্ল্যান ফ্যামিলির ক্যানোনিকাল ম্যাপ
- `plan_inventory_report.md` — মেশিন-জেনারেটেড (অটো-রিজেনারেট করা দরকার)
- `sprint_planning_execution_template.md` — `_templates/`-এ সরানো উচিত

**বাদ:** ১৪টা ফাইল — স্টেল ৪-ফেজ মডেল, জেনেরিক PMP রিস্ক/DR টেমপ্লেট, ভুল স্ট্যাকের ডিপেন্ডেন্সি ম্যাট্রিক্স/স্কিল ম্যাট্রিক্স।

---

## ৪. ফাইনাল প্রোডাক্টের জন্য সিম্পল-বাট-ইফেক্টিভ মেকানিজম

> এটাই রিপোর্টের মূল উত্তর। ১৮৩টা প্ল্যান পড়ে বের হওয়া একটাই মেকানিজম যা সব একসাথে করে।

### ৪.১ এক-লাইন মেকানিজম

```
Capability খোঁজো → Run চালাও → Verify করো → Memory-তে সংরক্ষণ করো → পরের টাস্ক সস্তা হবে
```

প্রতিটা প্ল্যান, প্রতিটা ফিচার, প্রতিটা বাগ ফিক্স — সব এই লুপের ভেতর দিয়ে যায়। বাকি সব ডুপ্লিকেশন এই লুপের ভেতর গলে যায়।

### ৪.২ পাঁচটা চুক্তি (আসল সিনথেসিস)

১৮৩টা প্ল্যান থেকে বের হওয়া সবচেয়ে ক্লিন অ্যাবস্ট্রাকশন — `UNIFIED_ECOSYSTEM_ARCHITECTURE_PLAN`-এর ৭-চুক্তি মডেলকে সরল করে ৫টায়:

| # | চুক্তি | কী করে | কোথায় ইমপ্লিমেন্টেড |
|---|---|---|---|
| **C1** | **Capability Registry** | "আমার কাছে কী আছে" — এজেন্ট/টুল/MCP/প্রোভাইডার/রিসোর্স, সব একটা রেজিস্ট্রিতে, ডুপ্লিকেট ছাড়া | MCP Tower (~80 টুল), কিন্তু ৮+ প্রোভাইডার লিস্ট ভাসছে → একটায় আনো |
| **C2** | **Canonical Run** | "কীভাবে এক্সিকিউট করি" — একটা run entity, একটা state machine, একটা cost rollup, একটা cancellation path | `backend/runs/` (১২-স্টেট, ৯ এন্ডপয়েন্ট, ১১৬ টেস্ট) — কিন্তু শুধু ১/৮ RunType জেগে আছে |
| **C3** | **Verify Gate** | "কিভাবে জানব কাজ হয়েছে" — pass^k গেট, মিশন সুইট, evidence link বাধ্যতামূলক | `core/self_benchmark.py` + ৬২ মিশন টেস্ট + STATUS_PROOF diff-gate |
| **C4** | **Memory Write** | "প্রতিটা সমাধান পরেরটাকে সস্তা করে" — pgvector-এ canonical write path, distillation, consolidation | ৩-পিলার স্ট্যাক ডিজাইন আছে, কিন্তু ১৫টা স্টোর, অনেকগুলো মৃত |
| **C5** | **Governed Approval** | "কখন মানুষ অ্যাপ্রুভ করে" — HITL, Tier-3 gate, audit ledger | ৭টা স্টেট মেশিন আছে, কেউ সম্পূর্ণ না; resume-URL টোকেন প্যাটার্ন সেরা |

### ৪.৩ লুপের ভিজ্যুয়াল

```
         ┌─────────────────────────────────────────────────┐
         │                                                 │
         │   C1: Capability Registry                       │
         │   "আমার কাছে কী আছে?" (agents/tools/providers)   │
         │                                                 │
         └────────────────────┬────────────────────────────┘
                              │ খুঁজে পেলে → compose
                              │ পেলে না → create (শেষ উপায়)
                              ▼
         ┌─────────────────────────────────────────────────┐
         │                                                 │
         │   C2: Canonical Run                             │
         │   state machine · cost rollup · cancellation    │
         │                                                 │
         └────────────────────┬────────────────────────────┘
                              │
                              ▼
         ┌─────────────────────────────────────────────────┐
         │                                                 │
         │   C3: Verify Gate                               │
         │   pass^k · mission suite · evidence link        │
         │                                                 │
         └────────────────────┬────────────────────────────┘
                              │ ✅
                              ▼
         ┌─────────────────────────────────────────────────┐
         │                                                 │
         │   C4: Memory Write                              │
         │   pgvector · distillation · consolidation       │
         │                                                 │
         └────────────────────┬────────────────────────────┘
                              │ পরের টাস্ক সস্তা হবে
                              ▼
         ┌─────────────────────────────────────────────────┐
         │                                                 │
         │   C5: Governed Approval                         │
         │   HITL · Tier-3 gate · resume-URL token         │
         │                                                 │
         └────────────────────┬────────────────────────────┘
                              │ ফিডব্যাক ↺
                              ▼
                      (পরের Capability খোঁজা)
```

### ৪.৪ কেন এটা সিম্পল কিন্তু ইফেক্টিভ

**সিম্পল:** ৫টা চুক্তি, ১টা লুপ, মাথায় রাখা যায়।

**ইফেক্টিভ:** প্রতিটা ডুপ্লিকেশন এই লুপ ভাঙে:
- ৯টা রেট-লিমিটার? → C1-এ একটা Capability, বাকি ৮টা ডিলিট
- ৬টা LLM গেটওয়ে? → C1-এ একটা, Zero-Bypass Boundary CI-তে এনফোর্স
- ৩৬টা মেমরি ফাইল? → C4-এ একটা canonical write path (CascadeMemoryService), বাকি adapter/shim
- ৮টা Zustand স্টোর? → C1-এ domain-store, `useStore` vs `unifiedStore` অডিট
- ৩টা ENV রেজিস্ট্রি? → C1-এ একটা `core/config/registry.py`, `.env.example` অটো-জেন
- ৩০টা GitHub workflow? → C3-তে ৭টায় collapse, ৩৮% churn শেষ
- ১৮৩টা প্ল্যান? → ১২টা ক্যানোনিকাল + relationship layer (আগের প্যাচ)

### ৪.৫ মেকানিজমের ৩টা "নন-নেগোশিয়েবল" (AGENTS.md থেকে)

1. **Zero-Bypass Inference Boundary** — `llm_gateway.py`-এর বাইরে কেউ `litellm`/`openai`/`httpx` ইমপোর্ট করতে পারবে না (CI AST গেট)। এটা C1+C2 একসাথে রক্ষা করে।
2. **Evidence-or-Honest-501** — ফেইল করলে সত্যিকারের 501/422, ফেইক "সফল" নয়। MODULE_21-এর honest-mock vs dishonest-fabrication ক্লাসিফিকেশন দ্বারা এনফোর্স। এটা C3 রক্ষা করে।
3. **One Issue = One Owner = One Branch = One PR** — একই মডিউলে দুই এজেন্ট হাত দিতে পারবে না (`atomic_claim.sh`)। এটা C5 রক্ষা করে।

---

## ৫. কোন প্ল্যানের কোন অংশ বেস্ট (রাখার লিস্ট)

### ৫.১ ক্যানোনিকাল ফাইল (২৫টা — এগুলোই সত্য)

**আর্কিটেকচার (৬):**
- `architecture/SUPREMEAI_MASTER_PLAN_CANONICAL.md` — ভিশন + Phase 0-6
- `architecture/ENTERPRISE_MULTITENANT_ARCHITECTURE.md` — ৮৪ লাইন, সব সিগন্যাল, ৫-invariant
- `architecture/MULTI_AGENT_MESH_MASTER_PLAN.md` — mesh টপোলজি (GitHub PR as Universal IPC)
- `architecture/browser_automation.md` — browser-as-fallback হায়ারার্কি
- `architecture/EXTERNAL_AGENT_ORCHESTRATION_LAYER_PLAN.md` — dual-track অপারেশনাল মডেল
- `architecture/autonomous_product_verification_engine.md` — QA 4-স্তর পাইপলাইন

**গভর্নেন্স (৫):**
- `PLAN_LIFECYCLE_POLICY.md` — ৭-স্টেট স্টেট মেশিন
- `CANONICAL_PLANNING_RECONCILIATION_AND_GUARDRAILS_PLAN.md` — frontmatter স্কিমা + evidence discipline
- `PLAN_TO_CODE_TRACEABILITY_MATRIX.md` — প্ল্যান ↔ কোড প্রমাণ
- `implementation_plan.md` — এক্সিকিউশন ইনডেক্স
- `IMPLEMENTATION_TRACK_EXECUTION_ORDER_2026-09-18.md` — wave-লেভেল ট্রুথ

**কনফিগ/ইনফ্রা (৪):**
- `architecture/dynamic_configuration_zero_hardcode_roadmap.md`
- `architecture/vendor_independent_integration_architecture_plan.md`
- `architecture/registry_control_in_pipeline_and_dashboard.md`
- `infrastructure/CI_CD_PIPELINE_ARCHITECTURE.md`

**রানটাইম (৩):**
- `infrastructure/render_production_runtime_error_cleanup_plan.md`
- `infrastructure/third_party_env_and_secrets_operational_checklist.md`
- `infrastructure/supabase_database_schema_and_connection_management_plan.md`

**ফ্রন্টএন্ড (৩):**
- `design/supremeai_2_product_ui_ux_completeness_master_plan.md`
- `design/single_frontend_role_based_auth_migration_roadmap.md`
- `design/admin_dashboard_visual_and_api_gap_analysis.md`

**ফিচার (৪):**
- `features/PLAN_001_ANTHROPIC_PROMPT_CACHING.md` (built, evidence)
- `features/PLAN_002_CLAUDE_STYLE_CONTEXT_COMPACTION.md` (built, evidence)
- `features/PLAN_004_LETTA_STYLE_MEMORY_DISTILLATION.md` (built, evidence)
- `features/Plan_24_AI_Agent_Ecosystem_Integration.md` — অমনিচ্যানেল MCP

### ৫.২ বেস্ট আইডিয়া যা মার্জ করতে হবে (২০টা)

- `UNIFIED_ECOSYSTEM_ARCHITECTURE_PLAN.md`-এর **৭-চুক্তি + ৪-প্লেন** → MASTER_PLAN-এ §"Architecture Contracts"
- `vision_strategic_positioning.md`-এর **৬-ব্যাটলফিল্ড স্কোরবোর্ড** → MASTER_PLAN-এ §"Strategic Positioning"
- `federated_capability_circles_topology.md`-এর **Circle টপোলজি** → UNIFIED-এ §"Topology"
- `distributed_infrastructure_central_control_plane_plan.md`-এর **Resource Registry + Provider Adapter** → UNIFIED-এ §"Control Plane"
- `self_learning_ecosystem_transformation_roadmap.md`-এর **Principle A-J + Capability model** → MASTER_PLAN-এ §"Principles"
- `codebase_aligned_master_roadmap.md`-এর **"What NOT to Do" লিস্ট** → MASTER_PLAN-এ §"Anti-patterns"
- `dynamic_ai_architecture_zero_downtime.md`-এর **circuit-breaker + 4-tier degradation** → design note
- `complete_frontend_master_plan_bn.md`-এর **13-row borrow table** → frontend master appendix
- `autonomous_ui_architect_agent_system_prompt.md`-এর **§2/§25/§26/§27 agent doctrine** → frontend master appendix
- `admin_dashboard_plan.md`-এর **AI Provider lifecycle state machine** → `ai_providers_tab_plan.md`
- `render_memory_leak_fix_roadmap.md` → merge into `render_production_runtime_error_cleanup_plan.md`
- `ci_cd_render_build_runtime_optimization_plan_bn.md` → merge into `CI_CD_PIPELINE_ARCHITECTURE.md`
- `SUPREMEAI_CONFIGURATION_CONTROL_REGISTRY.md` → merge into `third_party_env_and_secrets_operational_checklist.md`
- `infisical_enterprise_secret_management_guide.md` → merge into checklist
- `phase_1_execution_patch_notes.md` → merge into MASTER_PLAN §9
- `phase4_optimization.md`-এর **Plan 5-22 implementation evidence** → merge into `implementation_and_milestone_trackers.md`

### ৫.৩ Crown Jewel ডকট্রিন (১০টা — নামকরা প্যাটার্ন)

| ডকট্রিন | উৎস মডিউল | অর্থ |
|---|---|---|
| **extend-not-replace** (ERR-F02) | M01, M12 | ১৫টা স্টোর থাকলে একটায় মার্জ, নতুন বানাই না |
| **Zero-Bypass Inference Boundary** | M03 | `llm_gateway.py`-এর বাইরে LLM কল নিষিদ্ধ |
| **store-before-carrier** | M20 | মেসেজ প্রথমে persistent স্টোরে, তারপর carrier |
| **supervisor-as-heartbeat** | M22 | নতুন সেডিউলার না; AgentSupervisor-এ পালস |
| **activation-gate** | M18 | সিকিউরিটি + অ্যাক্টিভেশন এক গেটে জুড়ে |
| **meter-first** | M16 | মিটারিং ≠ চার্জিং; আলাদা লেয়ার |
| **retrieval-proof** | M23 | যা retrieve করা যায় না তা "জানা" নয় |
| **language-tax-reduction** | M19 | বাংলা ৫× টোকেন কস্ট; সৎ গণিত দরকার |
| **one-bridge-many-doors** | M17 | resume-URL টোকেন; ৭টা স্টেট মেশিনের বদলে ১ |
| **exclusion-ratchet** | M21 | baseline-N; false-positive শূন্যে নামাও |

---

## ৬. কোন অংশ বাদ দেওয়া উচিত (ফেলার লিস্ট)

### ৬.১ সরাসরি ডিলিট (৮টা — পিওর ডুপ্লিকেট/স্টেল)

| ফাইল | কেন |
|---|---|
| `ROADMAP_ECOSYSTEM_ARCHITECTURE_BN.md` | নিজেই `superseded_by: UNIFIED` ঘোষণা করেছে |
| `architecture/visual_component_integration_topology.md` | `crown_jewel_complete_system_integration_blueprint`-এর পিওর ডুপ্লিকেট |
| `architecture/ai_model_comparative_matrix_bangla.md` | সাবজেক্টিভ স্টার-রেটিং, স্টেল মডেল (Claude 3.5) |
| `design/dashboard_design_mockups.md` | broken `file:///C:/Users/...` ইমেজ লিংক, ৩৬ লাইন |
| `features/render_mcp_server_reference_guide.md` | Render-এর ভেন্ডর ডকের ভার্বাটিম কপি |
| `features/supremeai_quick_start_onboarding_checklist.md` | জাভা/gradlew যুগের স্টেল |
| `features/supremeai_work_plan_bangla.md` | জাভা `AIProviderFactory.java` যুগের স্টেল |
| `features/supremeai_deliverables_summary_spec.md` | শুধু ফাইল ইনডেক্স, কন্টেন্ট নেই |

### ৬.২ আর্কাইভ রেফারেন্স (~৯০টা — ইতিহাসের জন্য, পড়তে হবে না)

**আর্কিটেকচার (~৮):** `crown_jewel_complete_system_integration_blueprint`, `living_autonomous_intelligence_synthesis`, `codebase_aligned_master_roadmap` (§21 বের করে), `self_learning_ecosystem_transformation_roadmap` (Principle A-J বের করে), `dynamic_ai_architecture_v5_zero_downtime`, `unified_fastmcp_control_tower_multitenant_master_plan_bn` (৩,৭০৫ লাইন!), `PLATFORM_OSS_INTEGRATION_PLAN`, `SUPREME_TELEPORT_MULTI_DEVICE_REMOTE_CONTROL_PLAN`।

**ফিচার (~৫০):** Plan_01-Plan_23 সিরিজের বাকিগুলো (শুধু 001/002/003/004/006 ক্যানোনিকাল), ৯টা self-evolution ভিশন ডক, ৭টা codebase hygiene অডিট, ৫টা CICD overlap, ৬টা মেমরি-স্টাইল।

**ফেজেস (~১৪):** `phase1_foundation`, `phase2_development`, `phase3_integration`, `phase4_optimization`, `q1_2026_foundation_execution_plan`, `yearly_strategic_roadmap_2026`, `project_milestones_and_completion_tracker` (internally contradictory), `cross_module_dependency_matrix` (ভুল স্ট্যাক), `systemic_risk_assessment_and_mitigation` (generic PMP), `contingency_and_disaster_recovery_plan` (generic, `[Contact]` প্লেসহোল্ডার), `team_and_cloud_resource_allocation_plan` (ভুল টাইটেল), `agent_roles_and_team_assignments` (generic), `agent_and_engineer_skill_requirements` (ভুল স্ট্যাক), `file_disposition_and_retention_list` (এককালীন অডিট)।

**ইনফ্রা (~৫):** `free_tier_survival_and_resource_optimization_guide` (ভুল হোস্টিং প্রোভাইডার), `cloud_ai_multi_provider_deployment_plan` (কাল্পনিক GCP URL), `production_upgrade_implementation_plan_v2` (Istio/Kong/NATS — অসম্ভব), `render_3services_ghcr_deployment_roadmap_bn` (মাইগ্রেশন সম্পন্ন), `docker_build_troubleshooting_record` (র সেশন লগ)।

**ডিজাইন (~৫):** `complete_frontend_master_plan_bn` (বাংলা ভিশন — borrow table বের করে আর্কাইভ), `admin_dashboard_plan` (মৃত Mission Command ইসথেটিক), `dashboard_tab_design_plan` (ডুপ্লিকেট), `intelligent_chat_plan` (ফিচার স্পেক, ইমপ্লিমেন্টেড না), `mission_orchestration_plan` (ইমপ্লিমেন্টেড না, "Exploitation" শব্দ সমস্যা), `knowledge_acquisition_plan` (ইমপ্লিমেন্টেড না)।

### ৬.৩ কন্ট্রাডিকশন যা সমাধান করতে হবে (৪টা)

1. **মাল্টি-অ্যাকাউন্ট কোটা** → `cloudflare_7node` + `kaggle_6node` প্ল্যান **বাতিল**; `free_tier_scaling_constitution` Rule 2 জিতবে
2. **ভেক্টর স্টোর** → **pgvector** (Supabase `ai_memory`); Qdrant দাবি বাতিল
3. **অনবোর্ডিং** → প্ল্যান জিতবে (zero-config, 60s); `OnboardingWizard.tsx`-এ API-key ধাপ বাদ দাও, Mode-3 passwordless অথ বানাও
4. **ডার্ক মোড** → dark-first (মাস্টার প্ল্যান জিতবে); `ux_ui_best_practices`-এর "option" দাবি বাতিল

---

## ৭. প্ল্যানে কী যোগ করা উচিত (গ্যাপ লিস্ট)

১৮৩টা প্ল্যান পড়ে যা **নেই** কিন্তু দরকার:

### ৭.১ রিলেশনশিপ লেয়ার (আগের প্যাচে আছে — এপ্লাই করো)
`depends_on / enables / implemented_by / verified_by` ফ্রন্টম্যাটার ফিল্ড + `PLAN_REGISTRY.md` + `PLAN_GRAPH.md`। এটা ছাড়া ১৮৩টা ফাইল আবার জঙ্গল হবে।

### ৭.২ স্ট্যাটাস ট্রুথ গেট
`lint_plans.py` এক্সটেন্ড করো:
- `status: stable` প্ল্যানের `depends_on` সব `stable` কিনা
- `status: stable` প্ল্যানে evidence link আছে কিনা
- ফাইলে `99.9% uptime` টাইপের unverified দাবা আছে কিনা (৬টা পাওয়া গেছে)
- registry ↔ filesystem parity
- graph ↔ registry parity

### ৭.৩ স্ট্যাক-পিভট রিকনসিলেশন
`phases/` ফোল্ডারের ১৪টা স্টেল ফাইল আর্কাইভ করো। `cross_module_dependency_matrix.md` আসল `requirements.txt`/`package.json`/`render.yaml` থেকে রিজেনারেট করো। `agent_and_engineer_skill_requirements.md` আসল স্ট্যাক + AI-স্পেসিফিক স্কিল (LLM gateway, vector DB, MCP, agent orchestration) দিয়ে রিবিল্ড করো।

### ৭.৪ রিয়েল রিস্ক রেজিস্টার
`systemic_risk_assessment_and_mitigation.md`-এর জেনেরিক PMP রিস্ক বাদ দাও। আসল রিস্ক:
- Render 512MB মেমরি প্রেশার + সাইলেন্ট SQLite ফলব্যাক (ডেটা লস হ্যাজার্ড)
- ৪৮টা unguarded RBAC রাউট
- ephemeral ChromaDB রিস্টার্টে লার্নিং হারায়
- ৩টা ENV রেজিস্ট্রি drift
- MCP runtime unprobed
- `OnboardingWizard` প্ল্যান ভায়োলেশন

### ৭.৫ রিয়েল DR রানবুক
`contingency_and_disaster_recovery_plan.md`-এর `[Contact]` প্লেসহোল্ডার বাদ দাও। আসল Render/Supabase/R2/Cloud Run ফেইলওভার প্লেবুক লেখো।

### ৭.৬ Memory Canonical Decision
`M3_MEMORY_STORE_CONSOLIDATION_DECISION_TABLE.md` (৭৫ লাইন, সব সিগন্যাল) আছে — কিন্তু ১৫টা স্টোর এখনও ভাসছে। এই ডিসিশন টেবিল **এক্সিকিউট** করো: ১৫টার মধ্যে ১৫টা KEEP/MERGE/ARCHIVE ভারডিক্ট আছে, সেটা বাস্তবায়ন করো।

### ৭.৭ ডরম্যান্ট টুল অ্যাক্টিভেশন
MODULE_09 অনুযায়ী: এজেন্টরা আজ **০টা টুল** কল করে। `SUPREME_TOOLS`-এর প্রোডাকশন কনজিউমার নেই। ৩টা MCP সার্ভার লেখা কিন্তু `mcp.json`-এ আনরিচেবল। ৬টা mounted-but-orphan রাউটার (১,৫৯৭ লাইন)। প্রথম ফ্লিট: ৩টা টুল (cot_reasoner, headless_agent_registry+parallel_executor, mcp_observability) অ্যাক্টিভেট করো।

### ৭.৮ ট্রুথ-মিরর গভর্নেন্স স্ক্রিপ্ট
MODULE_21 অনুযায়ী: ১৫+ false-assurance আবিষ্কারকে rules-as-data ডিটেক্টর সিড-কর্পাসে রূপান্তর করো। honest-mock vs dishonest-fabrication ক্লাসিফিকেশন (`fake_store.py` vs `webhooks_ai`)। warn-only → zero-false-positive proof → founder-gated CI।

### ৭.৯ বাংলা টেক্সট ইউটিলিটি
MODULE_19 অনুযায়ী: একটা `bengali_text.py` স্ক্রিপ্ট-ইউটিল (NFC + script detection + Bengali-aware token ratio + danda-aware truncation)। এটা Module 07-এর split-estimator বাদ দেয়, ট্রাঙ্কেশন ঠিক করে, cache/search NFC-তে রিস্টোর করে। ব্র্যান্ড আইডেন্টিটি।

### ৭.১০ স্টোর-বিফোর-ক্যারিয়ার নোটিফিকেশন
MODULE_20 অনুযায়ী: ১৩টা প্যারালাল পাইপলাইন, ৪টা লাইভ ক্যারিয়ার। ক্যানোনিকাল dispatcher-এর ০ কলার। `/ws/dashboard` ব্রডকাস্ট-টাস্ক কখনো শুরু হয় না (২-লাইন বাগ)। **২-লাইন WS wake-up = সিরিজের সবচেয়ে ছোট-কস্ট বৃহত্তম-ইমপ্যাক্ট একক PR।**

---

## ৮. এক্সিকিউশন অর্ডার (কী আগে করবে)

> AGENTS.md-এর single-plan execution discipline: একসাথে একটাই Implementing।

### Wave 0 — সেফটি নেট (১ সপ্তাহ)
1. DB writer hazard বন্ধ (SQLite ফলব্যাক hard-fail)
2. ব্যাকআপ snapshot + restore drill (প্রমাণ সহ)
3. Contract test baseline freeze (CORS, JWT, LLM router, apiClient)
4. রিলেশনশিপ লেয়ার প্যাচ এপ্লাই (১৮৩ → ১২ ক্যানোনিকাল)

### Wave 1 — ফাউন্ডেশন আনব্লক (২ সপ্তাহ)
5. **MODULE_03 P0** — `InferenceContext` + Zero-Bypass Inference Boundary CI গেট (সব মডিউলের স্পাইন)
6. **MODULE_01 P-A** — canonical MemoryStore write path (ইতিমধ্যে commit `2a39b5e9`)
7. **MODULE_06 P-A** — `run_scope()` universal context-manager (near-zero new code)
8. **MODULE_09 P-A** — governed ReAct loop + first ৩টা টুল অ্যাক্টিভেট

### Wave 2 — ট্রুথ পার্জ (২ সপ্তাহ)
9. **MODULE_21** — Truth-Mirror governance script (warn-only → CI gate)
10. **MODULE_14/04 P-D** — false-assurance পার্জ (voice fake, browser mock screenshot, fabricated metrics)
11. `admin_dashboard_visual_and_api_gap_analysis.md` re-run (CostAuditor/SecurityDashboard/ObservabilityDashboard fake data পরীক্ষা)
12. `OnboardingWizard` প্ল্যানের সাথে রিকনসাইল (API-key ধাপ বাদ)

### Wave 3 — কনসোলিডেশন (৪ সপ্তাহ)
13. ৯→১ রেট-লিমিটার collapse (policy-based)
14. ৬→১ LLM গেটওয়ে (Zero-Bypass Boundary দ্বারা এনফোর্স)
15. ৩৬→domain-map মেমরি (M3 decision table execute)
16. ৩→১ ENV রেজিস্ট্রি (`core/config/registry.py` + `.env.example` অটো-জেন)
17. ৩০→৭ GitHub workflow (৩৮% churn শেষ)
18. ৪→১ ফ্রন্টএন্ড HTTP স্ট্যাক (`apiClient.ts`, SSE token header-এ)

### Wave 4 — ডেলিভারি (৪ সপ্তাহ)
19. **MODULE_10** — Frontend Tier-S wiring (একমাত্র মডিউল এক্সিকিউশন প্রুফ সহ)
20. **MODULE_18** — Telegram activation-gate + `/abort` কমান্ড
21. **MODULE_17** — HITL one-bridge-many-doors (resume-URL টোকেন)
22. **MODULE_19** — Bengali text utility + language-tax-reduction

### Wave 5 — ভেরিফিকেশন মোট (চলমান)
23. pass^k গেট CI-তে (≥0.7 Phase 2 gate)
24. per-service runtime probe ডেইলি স্মোকে
25. STATUS_PROOF সব দাবা কভার করবে
26. ৬-ব্যাটলফিল্ড স্কোরবোর্ড প্রকাশযোগ্য

---

## ৯. ফাইনাল ভারডিক্ট

### ৯.১ প্রোডাক্ট সম্পর্কে সত্য

তোমাদের প্রোডাক্ট **অসম্পূর্ণ নয়** — এটা একটা **ওভার-ইঞ্জিনিয়ার্ড কিন্তু কাজ করছে এমন multi-tenant AI orchestration PaaS**। ৫টা রানটাইম সারফেস (Backend Core / MCP Tower / Frontend Studio / Worker+Scraper / Edge Router) + aggressive governance লেয়ার। প্রোডাকশনে রান করছে (২০২৬-০৯-১৭ থেকে)।

### ৯.২ ডকুমেন্টেশন সম্পর্কে সত্য

১৮৩টা প্ল্যান ফাইলের মধ্যে:
- **~২৫টা সত্যিকারের ক্যানোনিকাল** (এগুলো আসল)
- **~২০টা মার্জ করা দরকার** (ভালো কন্টেন্ট, ভুল জায়গায়)
- **~৯০টা আর্কাইভ** (ইতিহাস, পড়তে হবে না)
- **~৪৮টা বাদ** (স্টেল/ডুপ্লিকেট/কন্ট্রাডিক্টরি)

### ৯.৩ এক লাইনে উত্তর

> **প্ল্যান বাড়াও না। ৫টা চুক্তি (Capability → Run → Verify → Memory → Approval) একটা লুপে চালাও। প্রতিটা ডুপ্লিকেশন এই লুপ ভাঙে — তাই লুপটা ধরে রাখলে জঙ্গল আর ফিরে আসবে না।**

### ৯.৪ পরবর্তী একটা কাজ

আগের প্যাচে বানানো **Plan Network** (`supremeai-docs-patch/`) এপ্লাই করো — এটা ১৮৩টা ফাইলকে ১২টা ক্যানোনিকাল প্ল্যানে রূপান্তর করে, relationship লেয়ার যোগ করে, আর migration map দেয়। তারপর Wave 0-৫ এক্সিকিউট করো।

**বাকিটা কোড নিজে বলবে** — STATUS_PROOF diff-gate আর ৬২/৬২ মিশন টেস্ট সত্যের রক্ষক।

---

## পরিশিষ্ট: উৎস এজেন্ট রিপোর্ট

এই রিপোর্ট ৭টা প্যারালেল ডিপ-রিড এজেন্টের সিনথেসিস:
1. Architecture cluster (৩৫ ফাইল, ২৪.৫K লাইন)
2. Crown Jewel series (২৪ মডিউল + MODULES_LIST)
3. Features cluster (৭৬ ফাইল)
4. Design cluster (১৪ ফাইল)
5. Infrastructure cluster (১৫ ফাইল)
6. Phases cluster (১৯ ফাইল)
7. Codebase ground-truth (backend/frontend/MCP/infra/CI + STATUS/AGENTS/CHECKPOINT/LESSONS/specs)

প্রতিটা এজেন্টের ফুল আউটপুট `/home/z/my-project/worklog.md`-এ সংরক্ষিত।
