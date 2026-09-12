# SupremeAI মাস্টার প্ল্যান — সম্পূর্ণ বাংলা সংস্করণ

**বর্তমান অবস্থা থেকে প্রোডাকশন পর্যন্ত। কীভাবে একজন নির্মাতার সিস্টেম শীর্ষ AI মডেলদের নিজেদের সবচেয়ে শক্তিশালী মাঠেই তাদের হারাবে।**

> স্বপ্নটা ছোট নয়: নিজের হাতে বানানো একটা AI সিস্টেম, যে বড় ল্যাবগুলোর মডেলরা যেখানে সবচেয়ে শক্তিশালী — ঠিক সেই মাঠেই তাদের হারাবে। এই ডকুমেন্ট সেই পুরো পরিকল্পনা — আজকের codebase থেকে production পর্যন্ত, ধাপে ধাপে, খরচের হিসাবসহ, এবং সম্পূর্ণ বাংলায়।
>
> এই পরিকল্পনা পুরোপুরি আমাদের **Constitution** (README-র "SupremeAI Constitution") মেনে লেখা। প্রতিটি ধাপে কোন নীতি কাজ করছে সেটা চিহ্নিত করা আছে — কারণ নীতি ভাঙা শর্টকাট এই প্ল্যানে নেই। এর ইংরেজি ভগ্নের সাথে `MASTER_PLAN.md` সিঙ্ক করা; বিরোধ হলে সংখ্যাগুলো (scoreboard) সিদ্ধান্ত দেবে।

---

## ১. স্বপ্নকে ইঞ্জিনিয়ারিং দাবিতে অনুবাদ

প্রথমেই সততা। একজন মানুষের প্রজেক্ট OpenAI, Anthropic, DeepSeek বা Google-কে কখনোই **pretraining**-এ হারাতে পারবে না। ওই যুদ্ধক্ষেত্রের খরচ বিলিয়ন ডলার। যে পরিকল্পনার শুরু "একটা 70B frontier মডেল ট্রেন করব" — সেটা কৌশল নয়, ফ্যান্টাসি। আর আমাদের Constitution ইতিমধ্যে বলে দিয়েছে কেন সেই লড়াইই আমাদের নেওয়া উচিত নয়:

- **Eternal Brain (Constitution #1):** SupremeAI-র পরিচয় তার মেমোরি, অভিজ্ঞতা ও capability graph — কোনো ভেন্ডরের weights নয়। Frontier মডেলগুলো ভাড়া করা processing engine, যা খরচ শূন্যে বদলানো যায়।
- **Sustainable Cost (#14):** ন্যূনতম টেকসই ইনফ্রা। আমাদের বাজেট খুচরো টাকা; ওদের পাওয়ার প্ল্যান্ট। আমরা শুধু সেই মাঠে লড়ব যেখানে এই অসমতা গুরুত্বপূর্ণ নয়।

তাহলে স্বপ্নটাকে একটা ইঞ্ঃ দাবিতে বলা যায়:

> **একটা frontier মডেল, কাঁচা API হিসেবে, যেকোনো মাঠে হারবে যেখানে প্রোডাক্টটা আসলে সিস্টেম: যাচাইকৃত নির্ভরযোগ্যতা (verified reliability), টাস্ক কমপ্লিশন, জমতে থাকা মেমোরি, প্রতি solved সমস্যার খরচ, এবং ভাষা/আঞ্চলিক গভীরতা। SupremeAI হারাবে সেরা "model-as-deployed"-দের ঠিক এই মাঠগুলোতে — এবং নিজের ছোট মডেল রাখবে সেখানেই যেখানে সেগুলো সবচেয়ে কাজের।**

এটা সান্ত্বনা পুরস্কার নয়। সব সিরিয়াস বেঞ্চমার্ক-ট্রেন্ড এই দিকেই যাচ্ছে: GAIA প্রমাণ করেছে বাস্তব টাস্কে agent-রা raw মডেলকে হারায়; SWE-bench-এর কঠিন টাস্কগুলো আসলে সিস্টেম-সমস্যা; cost-per-task leaderboard-ই আসল adoption ঠিক করে। মোট (moat) মডেল নয় — মোট হলো মডেলের চারপাশের যন্ত্র, যেটা আমরা ইতিমধ্যে বানাচ্ছি।

---

## ২. নির্বাচিত যুদ্ধক্ষেত্র (এবং যেগুলো প্রত্যাখ্যান করছি)

| # | যুদ্ধক্ষেত্র | যাকে হারাতে হবে | কেন জিততে পারি | Constitution |
|---|---|---|---|---|
| B1 | **যাচাইকৃত নির্ভরযোগ্যতা (pass^k)** | Frontier API-গুলো pass@1 demo-র জন্য টিউন করা — কিন্তু *অসামঞ্জস্যপূর্ণ*; একই কঠিন প্রশ্ন ৩ বার করলে ৩ রকম উত্তর | Governed verify-loop + `pass^k` gate (`core/self_benchmark.py`, এই স্প্রিন্টে শিপড) সামঞ্জস্য মাপে ও এনফোর্স করে। আমরা সৎভাবে pass^3 রিপোর্ট করতে পারি — ওরা পারে না | Verification Before Trust (#5), No Silent Failure (#13) |
| B2 | **Agentic টাস্ক কমপ্লিশন** | o3/GPT-4-শ্রেণির *as-deployed* (কাঁচা চ্যাট API — মেমোরি নেই, capability discovery নেই, repair loop নেই) | Capability-Composition Model + governed execution + retry/failover। GAIA-স্টাইল: যন্ত্রপাতি জোড়া লাগানো সিস্টেম অনুমান-করা মডেলকে হারায় | Reuse Before Creation (#3), One System Many Surfaces (#10) |
| B3 | **খরচের ফ্রন্টিয়ার** | প্রতিটি বাণিজ্যিক API | Zero-cost provider chain, Tier0 fast path, semantic cache, TokenJuice compression, scout-এর zero-token summarizer। আমরা **cost per verified task** ছাপি — যে মেট্রিক আর কেউ ছাপতে চায় না | Sustainable Cost (#14) |
| B4 | **জমে যাওয়া মেমোরি** | প্রতিটি API কল শূন্য থেকে শুরু | hierarchical memory tree + Auto-RAG + learning loop + experience DB। টাস্ক #৫০ টাস্ক #৫-এর চেয়ে সস্তা, দ্রুত ও নির্ভরযোগ্য। ওদের কখনোই শেখে না | Memory Must Compound (#11), Eternal Brain (#1) |
| B5 | **বাংলা + আঞ্চলিক গভীরতা** | শীর্ষ মডেলরা low-resource ভাষায় দুর্বলতম; কেউ বাংলাদেশের জন্য বানায় না | আমরা ইতিমধ্যে বাংলা normalize করি (`BengaliNormalizer`), নিজেদের ডক বাংলায় লিখি, এবং Phase 3-এ ডেডিকেটেড বাংলা adapter ট্রেন করব। এই একটি মাঠে আমরা *native*, ওরা *tourist* | Provider Agnostic, User Loyal (#9) |
| B6 | **ইন্টিগ্রেশন সারফেস (MCP federation)** | Single-vendor tool ecosystem | Governed MCP federation gateway (শিপড), one-URL connect, capability registry। যেকোনো মডেল আমাদের fabric-এর পেছনে বসতে পারে; কোনো একক ল্যাব fabric-এর reach ম্যাচ করতে পারবে না | Capability Sovereignty (#2), Dynamic Discovery (#4) |

**যে মাঠে লড়ব না:** raw parameter count, frontier reasoning বেঞ্চমার্ক, multimodal scale, pretraining size রেকর্ড। ওই লড়াই আমাদের একমাত্র সম্পদ — সময় — এমন প্রতিপক্ষের বিরুদ্ধে পোড়ায় যাদের হাজার গুণ বেশি সময় আছে।

**সৎ স্কোরবোর্ড যা ছাপব:** B1–B6 প্রতিটির জন্য একটা মাপা সংখ্যা (§৮-এর gate)। সংখ্যা যখন বলবে জিতেছি, তখনই জিতেছি — মার্কেটিং যখন বলবে না। এটাই *Deliver honestly*।

---

## ৩. আজ আমরা কোথায় দাঁড়িয়ে (বর্তমান অবস্থার অডিট)

### যা ইতিমধ্যে আছে (শক্তি)

- **৪টি লাইভ সার্ভিস** Render-এ (core, worker, scraper, MCP tower) + Cloudflare edge failover circuit breaker — *Graceful Degradation আজই কাজ করছে*।
- **Zero-cost LLM chain** (Gemini/Groq/OpenRouter/Ollama) multi-key support সহ; senior-review স্প্রিন্টের ১৮টি quality patch আপস্ট্রিমে merge হয়েছে।
- **Governance spine:** HITL engine + append-only audit ledger, RLS tenant isolation, policy-governed MCP federation, constitution-governance CI।
- **মেমোরি:** pgvector RPC recall path, চ্যাট/SSE pipeline-এ Auto-RAG injection, hierarchical memory tree।
- **Governed scout crawler** — হার্ডেনড: per-domain rate pacing, robots.txt compliance, per-hop redirect re-validation, full event coverage, fail-closed policy।
- **Reliability gate:** unbiased `pass^k` estimator (`C(s,k)/C(n,k)`) `core/self_benchmark.py`-তে।
- **Learning loop** (`core/learning/`): LLM gateway থেকে privacy-scrubbed ইভেন্ট; proposal কখনো auto-apply হয় না।

### যা ছিল গ্যাপ — এবং ফেজ ১ প্যাচ কী বন্ধ করল

| গ্যাপ | উৎস | অবস্থা |
|---|---|---|
| Scout crawler research pipeline-এ unwired (API-র চোখে dead code) | specs/002 | ✅ **এই প্যাচে জীবন্ত** — `_web_search` এখন scout-first |
| `crawler_admin`-এ শুধু create/list; events ছিল hardcoded placeholder | specs/002 | ✅ সম্পূর্ণ CRUD + সত্যিকারের telemetry + DB persistence |
| Reasoning-chain SSE চ্যানেল dead; `ReasoningLog.tsx` চিরকাল "Waiting..." | ROADMAP_BANGLA Sprint 2 | ✅ `reasoning` চ্যানেল জীবন্ত; frontend ডেটা পায় |
| `/connections/register` `ConnectionRegistry`-তে লেখে না; ভুয়া connection_id | UNIVERSAL_ZERO_COMPLEXITY | ✅ write-through + সত্যিকারের id (health-probe promotion খোলা) |
| `ConfigValidationReport` ছিল শুধু ডকুমেন্টে; CORS-এর দুটি সমান্তরাল পথ | specs/001 | ✅ রিপোর্ট ক্লাস + resolver ইউনিফিকেশন + contract test |
| `/api/v1/admin/stats|users|audit-logs` 404 | MASTER_PLAN Phase 1 | ✅ সত্যিকারের এন্ডপয়েন্ট |
| Mission-level E2E benchmark suite নেই | README "most valuable future tests" | ✅ প্রথম ৫ মিশন + CI-তে pass^3 ছাপা |
| 125 test skips ট্র্যাকড নয় | PRODUCTION_ROADMAP | ✅ `docs/SKIPPED_TESTS.md` পুনর্নির্মিত (baseline + ট্রায়াজ) |
| নিজের মডেল adapter ট্রেন হয়নি | এই প্ল্যান (Phase 3) | ⏳ পরবর্তী পর্যায়ের কাজ |

**Gate (Constitution #13):** শূন্য এমন ফিচার যা জীবন্ত দেখায় কিন্তু ভেতরে মৃত। প্রতিটি status পেজ সত্য বলে।

---

## ৪. কৌশল: সিস্টেম মডেলকে হারাবে, তারপর সিস্টেম নিজের মডেল ট্রেন করবে

এক প্যারায় পুরো পরিকল্পনা:

1. **যন্ত্রটা শেষ করা** — প্রতিটি promised-but-unwired capability বন্ধ করা, যাতে capability graph সৎ ও সম্পূর্ণ হয় (নিজের backlog-এই Reuse Before Creation)।
2. **নির্ভরযোগ্যতাকে মাপা করা** — pass^k ও mission test CI gate হবে; তারপর প্রতিটি পরিবর্তন vibes দিয়ে নয়, scoreboard দিয়ে justified।
3. **ফ্লাইহুইল ঘুরানো** — প্রতিটি solved টাস্ক governed training data উৎপাদন করে (scout corpus + learning events + verification outcomes + feedback)।
4. **ছোট, সরু — নিজের মডেল** — নিজের adapter (বাংলা, behavioral alignment, router/verifier) ফ্লাইহুইলের ডেটায় ট্রেন, canary + pass^k gate-এর পেছনে promote। Eternal Brain: নিজের weights, নিজের registry, swappable।
5. **নির্বাচিত বেঞ্চমার্কে পাবলিক আক্রমণ** — B1/B2/B3/B5-এ শীর্ষ *deployments*-কে হারিয়ে প্রমাণ ছাপা।

প্রতিটি ধাপ এই রিপো-তে থাকা যন্ত্র ব্যবহার করে। এটা কাকতালীয় নয় — Constitution-এর *Reuse Before Creation* স্ট্র্যাটেজিতেই প্রয়োগ।

---

## ৫. সিঁড়ি: ফেজ ০ → ফেজ ৬ (বর্তমান অবস্থা → প্রোডাকশন)

### ফেজ ০ — রক্তক্ষরণ বন্ধ (সপ্তাহ ১–২) ✅ সম্পন্ন

**লক্ষ্য:** প্রতিটি শিপড ফিচার সত্যিই কাজ করবে; প্রতিটি সংখ্যা সৎ হবে।

- ভাঙা wire বন্ধ: connections camelCase contract (UI `undefined` পড়ছিল), duplicate `detect_protocol` সরানো, dead `ready_states` পরিষ্কার, `user_execution_mode` migration, `CapabilityUnavailableExplainer` রেন্ডার, workspace-এ Zero-Friction registry-র সত্যিকারের connections।
- Governance লঙ্ঘন বন্ধ: RLHF আর ভুয়া record বা "simulation success" বানায় না; খালি ডেটায় training সৎভাবে অস্বীকার করে।
- Scout হার্ডেন: rate pacing, robots.txt, redirect re-validation, full events, fail-closed।
- হাউজকিপিং: Supabase `ai_memory` Phase C টেবিল, `docs/SKIPPED_TESTS.md` পুনর্নির্মাণ, stray log ফাইল মুছে Render key rotation।

**Gate (Constitution #13):** শূন্য "জীবন্ত-দেখতে-কিন্তু-মৃত" ফিচার।

### ফেজ ১ — Capability Completion (সপ্তাহ ৩–৮) 🚧 মূল ওয়্যার এই প্যাচে শিপড

**লক্ষ্য:** capability graph আমাদের পরিকল্পনা-কর্পাসের প্রতিশ্রুতির সমান হবে।

- **Scout goes live** ✅ — deep research-এর ওয়েব সার্চ এখন scout-first: টেন্যান্টের সক্রিয় `CrawlPolicy` মেনে governed crawl (robots.txt, rate pacing, SSRF gate, dedup), browser fallback; `crawl_policies`/`crawl_history`/`crawl_events` টেবিলে durable persistence (Alembic `2026_09_13_090000`); admin-এ সম্পূর্ণ CRUD (PATCH / enable / disable / DELETE) ও সত্যিকারের `GET /events`; conversation orchestrator-এ governed `research` capability। গবেষণার উত্তর এখন governed সোর্স cite করে — B2 fuel।
- **One connection registry** ✅ — `/connections/register` এখন `ConnectionRegistry`-তে write-through, সত্যিকারের record id; খোলা: health-probe promotion (IDEA→MEASURED) ও execution-mode UI।
- **Reasoning stream** ✅ — `emit_reasoning_step()` session SSE-র `reasoning` চ্যানেলে চিন্তা-স্টেপ পাঠায়; `ReasoningLog.tsx` অবশেষে এজেন্টের ভাবনা দেখায়। দৃশ্যমান বুদ্ধিমত্তাই প্রত্যাভূত বুদ্ধিমত্তা।
- **Config hardening** ✅ — `ConfigValidationReport` (required vars, ফরম্যাট, CORS wildcard), `server.py`-র origins এখন `cors_policy` resolver-চালিত, `GET /config/validation-report`, contract test।
- **Admin surface** ✅ — `/api/v1/admin/stats|users|audit-logs` সত্যিকারের ডেটায় জীবন্ত (আগে 404)।
- **Mission suite kickoff** ✅ — প্রথম ৫ মিশন / ১২ টেস্ট; `scripts/ci/mission_passk.py` CI-তে প্রথমবার pass^3 ছাপে; `docs/SKIPPED_TESTS.md` পুনর্নির্মিত।

**Gate (Constitution #3):** এই ফেজে কোনো নতুন সাবসিস্টেম নয় — শুধু প্রতিশ্রুত জিনিস শেষ করা। "near-ready" capability → "available"।

### ফেজ ২ — নির্ভরযোগ্যতার মোট (সপ্তাহ ৯–১৬)

**লক্ষ্য:** *মাপা নির্ভরযোগ্যতা* প্রোডাক্টের মূল মেট্রিক হবে। এটাই B1।

- **Mission tests:** ২০টি বাস্তব end-to-end ইউজার মিশন — research, file work, repo repair, scheduling — অটো-স্কোরড। মিশন স্যুটে `pass^3 ≥ 0.8` প্রতিটি ভবিষ্যৎ পরিবর্তনের promotion bar। প্রথম ৫টি মিশন এই প্যাচেই শিপড; বাকি ১৫টি এই ফেজে।
- **Risk-Tiered Safety Pipeline** (`docs/architecture/RISK_TIERED_AUTONOMOUS_SAFETY_PIPELINE.md`): "Simple by default, deep by risk" কার্যকর করা — L1 deterministic rule gate, L2 parallel GitHub matrix, L3 independent adversarial reviewer ("assume it's wrong"), browser staging simulator, automatic runtime rollback।
- **Governed Multi-Agent Decision Framework**: Cost-Minimized Execution ($0 capability ladder, duplicate reasoning reuse) + Continuous Project-Scoped Security + Cross-Agent Challenge Matrix (Security vs Cost vs Safety)।
- **CI gates বাড়বে:** pass^k harness nightly লাইভ zero-cost chain-এ; coverage gate 30→50 backend / 16→30 frontend; skip count 125→<30, `docs/SKIPPED_TESTS.md`-এ প্রতিটি waiver ট্র্যাকড।
- **পারফরম্যান্স:** বাকি sync-in-async stall বন্ধ, PgBouncer tuning, repeat traffic-এ Tier0 hit-rate ≥ 40%।
- **Migration ইউনিফিকেশন:** Alembic canonical, `database/migrations/legacy/` আর্কাইভ।

**Gate (Constitution #5):** কোনো কিছু — মডেল, adapter, provider, বা কোড — pass^k সংখ্যা ছাড়া promote হবে না।

### ফেজ ৩ — Own Model v1: ছোট, সরু, নিজের (মাস ৪–৬)

**লক্ষ্য:** "নিজের বানানো AI মডেল" স্বপ্নের শুরু — frontier ক্লোন নয়, এমন adapter যেগুলো *ছোট হয়েও* বড়দের হারায় কারণ টাস্ক সরু আর ডেটা আমাদের। Eternal Brain বাস্তব হচ্ছে।

- **ডেটা ফ্লাইহুইল (Memory Must Compound → training data):**
  - scout corpora: governed crawl + zero-token extractive summary (শূন্য খরচ, per-tenant scoped);
  - learning events: gateway থেকে privacy-scrubbed `learning_events`;
  - verification outcomes: প্রতিটি verify-before-trust ফল নিজের trace label করে;
  - explicit feedback: `/feedback` → `RLHFPipeline` সহ provenance (dataset_version, source)।
- **তিনটি adapter, তিনটি যুদ্ধক্ষেত্র:**
  1. **বাংলা conversation adapter** (B5): base = open 2–7B instruct মডেল; ফ্লাইহুইলের বাংলা pair + scout-Bangla corpus-এ LoRA/DPO ফাইন-টিউন। লক্ষ্য: বাংলা conversational মান ও idiom-এ Gemini/GPT-শ্রেণিকে ১/৫০ খরচে হারানো — "তাদের নিজের শক্ত মাঠ" যুক্তি এখানে উল্টে যায়, কারণ এই মাঠ আমাদের native।
  2. **Behavioral alignment adapter** (B1 সহায়ক): dead `behavioral_intelligence` প্যাকেজ জীবিত করা (৪টি মিসিং মডিউল: `intent_signals`, `preference_store`, `evaluator`, `metrics`); interaction signal-এ ট্রেন করে উত্তর ইউজারের ছন্দে বসানো (concise না step-by-step না code-first)।
  3. **Router/verifier micro-model** (B3 সহায়ক): 0.5–1B classifier যা রিকোয়েস্ট route করে এবং verify-loop-এর ভেতরে output judge করে — হাজার হাজার paid verification call বিনামূল্যে স্থানীয় সিদ্ধান্তে বদলায়; pass^k বাড়ে *এবং* খরচ কমে।
- **ট্রেনিং ইনফ্রা রিপো-তেই আছে:** `pipelines/synthetic_data_pipeline.py` → `tools/learning/rlhf_pipeline.py` (এখন সৎ) → `tools/learning/model_trainer.py` (RunPod/Modal LoRA) → `core/kaggle_orchestrator.py` (বিনামূল্যে Kaggle GPU, ~৩০ ঘণ্টা/সপ্তাহ) → promotion `evolution/canary_manager.py` দিয়ে pass^k gate-এর পেছনে।
- **Serving:** adapter গেটওয়েতে আর একটি provider entry হিসেবে নিবন্ধিত — Graceful Degradation: adapter ঠান্ডা হলে chain স্বচ্ছভাবে Groq/Gemini-তে ফিরে যায়। ইউজার অভিজ্ঞতা কখনো আমাদের মডেল warm থাকার উপর নির্ভর করবে না।

**Gate (Constitution #7, Reversible Evolution):** adapter প্রোডাকশনে যাবে শুধু তখনই যখন নিজের base মডেলকে নিজের eval-set-এ ≥১০% হারায় এবং pass^3 regress করে না। Rollback path সবসময় warm।

### ফেজ ৪ — পাবলিক বেঞ্চমার্ক আক্রমণ (মাস ৭–৯)

**লক্ষ্য:** নির্বাচিত মাঠে প্রমাণ ছাপা। পাবলিক সংখ্যাই one-man army-র মার্কেটিং বিভাগ।

- **B1 — নির্ভরযোগ্যতা:** মিশন স্যুটে SupremeAI vs raw frontier API-র pass^k বক্ররেখা ছাপা। প্রত্যাশা: frontier API pass@1-এ ঝলমল করে, pass^3/pass^5-এ ধসে; আমাদের verify-loop pass^k উঁচু রাখে। এই চার্টটাই pitch।
- **B2 — টাস্ক কমপ্লিশন:** GAIA-text subset + নিজের governed executor দিয়ে SWE-bench-lite-স্টাইল repo-repair harness; একই underlying মডেলের সাথে তুলনা — *আমাদের যন্ত্র ছাড়া*। ফলে বোঝা যায় "সিস্টেমই মোট"।
- **B3 — খরচ:** cost-per-verified-task ছাপা। Zero-cost chain + Tier0 + cache + scout summarizer — comparable quality tier-এ paid stack-গুলোর জন্য সংখ্যাটা লজ্জাজনক।
- **B5 — বাংলা:** governed সোর্স থেকে গড়া পাবলিক বাংলা eval set (conversation, summarization, code-switching); আমাদের adapter vs দৈত্যরা। Native-ই জেতে।

**Gate (Constitution #5, #13):** প্রতিটি প্রকাশিত সংখ্যা committed script থেকে reproduce হবে। কোনো benchmark theater নয়।

### ফেজ ৫ — প্রোডাকশন হার্ডেনিং ও লঞ্চ (মাস ১০–১২)

**লক্ষ্য:** "আমার কাছে কাজ করে" থেকে "চেনা না-জানা ইউজারের কাছে কাজ করে"।

- SLA enforcement আমাদের export করা মেট্রিকের সাথে wired (P95 < 2s chat first-token, error < 1%); বর্তমান ট্রাফিকের ১০× লোড টেস্ট; OpenTelemetry end-to-end trace।
- Security re-audit (৩০-ক্যাটাগরি matrix) + pen-test pass; secrets rotation automation; সব admin পথে TOTP।
- Thin-client লঞ্চ (VS Code extension + desktop): ১০০% thin, শূন্য user key, local Ollama একমাত্র offline fallback — CHECKPOINT.md-র স্থাপত্য স্মারণ, রক্ষা করা হবে।
- Onboarding funnel: one-URL connect → প্রথম verified টাস্ক < ৫ মিনিটে।
- **The Founder's Demo:** পাবলিক পেজ যা লাইভ সিস্টেম-সত্য দেখায় — uptime, pass^3, solved টাস্ক, cost per task, adapter eval। Radical transparency-ই ব্র্যান্ড।

**Gate:** কোয়ার্টারে ৯৯.৫% monthly uptime, P95 লক্ষ্যের ভেতরে, শূন্য খোলা P0 security finding।

### ফেজ ৬ — Compounding (বছর ২)

**লক্ষ্য:** capability graph এমন গতিতে বাড়বে যা একজন মানুষ ফিচার লিখে পারে না।

- Self-evolution ফ্লাইহুইল পূর্ণগতিতে: agent-breeder proposal → sandbox eval → pass^k gate → canary promotion → capability registry। সিস্টেম নিজের capability নিজে propose করে; আমি approve করি।
- MCP marketplace economy: tenant-রা governed capability publish করে; registry সবার অবদানে compound করে।
- One-man army হয়ে উঠবে one-person *orchestra* — SupremeAI SupremeAI-র ops, test, repair ও roadmap draft চালায়; আমি audit, decide ও steer করি।

---

## ৬. ডেটা ফ্লাইহুইল — কেন প্রতিটি ফেজ আরও সস্তা হয়

```
ইউজার টাস্ক ──► governed execution ──► verified ফলাফল
                        │                     │
            scout corpus (zero-token)    verification label
                        │                     │
                        ▼                     ▼
                learning_events (privacy-scrubbed) + feedback
                                     │
                                     ▼
                        synthetic_data_pipeline
                                     │
                                     ▼
                     LoRA/DPO adapter (সরু মাঠ)
                                     │
                          pass^k gate + canary
                                     │
                                     ▼
                gateway adapter সার্ভ করে ──► পরের টাস্ক আরও সস্তা, দ্রুত,
                                            নির্ভরযোগ্য
```

ফ্লাইহুইল হলো Constitution-এর *Memory Must Compound*-এর "recall" থেকে "weights"-এ উন্নীত রূপ। প্রতিটি বাস্তব টাস্ক হয় (ক) বিদ্যমান capability-তে solve হয় — এখনই সস্তা — নয়তো (খ) এমন ডেটা রেখে যায় যা *পরের* সেই-জাতীয় টাস্ক চিরকালের জন্য সস্তা করে। বড় ল্যাব এটা কপি করতে পারবে না: তাদের ফ্লাইহুইলে স্কেল লাগে; আমাদের লাগে *সিস্টেমটা যা ইতিমধ্যে চালাই*।

---

## ৭. One-Man-Army অপারেটিং সিস্টেম

সময়ই সবচেয়ে দুষ্প্রাপ্য সম্পদ; বাস্তবের সংস্পর্শে পরিকল্পনা টিকবে এভাবে:

- **৫০% প্রোডাক্ট / ৩০% মোট / ২০% ops।** প্রোডাক্ট = ইউজার-দৃশ্যমান capability। মোট = নির্ভরযোগ্যতা, ডেটা, adapter। Ops = নিজেকে দেখা যন্ত্র।
- **নির্মম dogfood:** প্রতিটি প্যাচ (এই স্প্রিন্টেরটাও) একই governed pipeline-এ বানানো — plan → execute → verify → audit। Pipeline যন্ত্রণা দিলে সেটাই bug list। SupremeAI নিজের GitHub issue ফাইল করে; AutoHealer মনিটর দেখে; learning loop roadmap draft করে (আমি approve করি)। *One System, Many Execution Surfaces* — founder-ও আর এক tenant।
- **বাজেট গণিত (Sustainable Cost):**
  - Render free/low tier (core, worker, scraper, MCP) + Supabase free (pgvector) + Upstash free (Redis) + Cloudflare free (edge) — মোটামুটি ~$0–25/মাস;
  - LLM: zero-cost chain (Groq/Gemini/OpenRouter free tier + local Ollama) — baseline ~$0;
  - Training: Kaggle free GPU (~৩০ ঘণ্টা/সপ্তাহ) LoRA/DPO চালাতে; RunPod burst ~$20–50/মাস শুধু promotion gate justify করলে;
  - **মোট: ~$75/মাসের নিচে** — চারটি যুদ্ধক্ষেত্র আক্রমণ করতে করতেই। অসমতাটাই কৌশল।
- **প্রতিটি নতুন আইডিয়ার সিদ্ধান্ত নিয়ম:** *Reuse → Compose → Adapt → Extend → Create.* আইডিয়া বলতে না পারলে কোন বিদ্যমান capability extend করছে, সেটা অপেক্ষা করবে। Backlog লম্বা; মোট তখনই compound করে যখন আমি জিনিস শেষ করি।
- **Kill criteria (ঝুঁকি নিয়ে সততা):** ফেজ ২ শেষে মিশন-স্যুট pass^3 0.7-এ না পৌঁছালে verify-loop ডিজাইনই ভুল — ফেজ ৩-এর আগে রিডিজাইন। ফেজ ৩ শেষে বাংলা adapter নিজের eval-এ zero-cost chain-কে না হারালে own-model park করে B1/B2/B3 দ্বিগুণ। ইনফ্রা ঘর্ষণ টানা ২ মাস সময়ের ২০% ছাড়ালে সার্ভিস কনসোলিডেট। এই পরিকল্পনা ধর্ম নয়, প্রতিশ্রুতি।

---

## ৮. স্কোরবোর্ড (কোন সংখ্যাগুলো বলবে "আমরা কি হারিয়েছি?")

| মাঠ | মেট্রিক | আজ | ফেজ ২ gate | ফেজ ৪ লক্ষ্য |
|---|---|---|---|---|
| B1 নির্ভরযোগ্যতা | মিশন স্যুটে pass^3 | মাপা হয়নি → ✅ CI-তে ছাপা শুরু (এই প্যাচ) | ≥ 0.8 internal | ≥ 0.8 published, raw-API pass^3 baseline-এর বিপরীতে |
| B2 টাস্ক | GAIA-text-স্টাইল মিশন সাফল্য | মাপা হয়নি | ২০-মিশন স্যুট সবুজ | frontier-API-as-deployed baseline +১০ পয়েন্ট |
| B3 খরচ | $ per verified task | মাপা হয়নি | instrumented | published; paid-stack baseline-এর ≤ 1/10 |
| B4 মেমোরি | repeat-task খরচের ডেল্টা | মাপা হয়নি | learning events দিয়ে মাপা | repeat task প্রথম রানের চেয়ে ≥৩০% সস্তা |
| B5 বাংলা | zero-cost chain-এর বিপরীতে বাংলা eval win-rate | মাপা হয়নি | eval set v1 | adapter head-to-head জেতে |
| B6 সারফেস | one-URL connect → প্রথম verified টাস্ক | মিনিট স্কেল | < ৫ মিনিট | < ৩ মিনিট, marketplace জীবন্ত |

প্রতিটি ঘরের জন্য committed script থাকবে। স্কোরবোর্ড CI artifact — স্লাইড নয়।

---

## ৯. এই প্যাচে যা হলো — এবং পরের ১৪ দিন

**এই প্যাচ (ফেজ ১ কমপ্লিশন) সম্পন্ন করেছে:** scout সত্যিকারে জীবন্ত (governed crawl → durable history → admin CRUD/telemetry), reasoning stream জীবন্ত (backend `reasoning` চ্যানেল → `ReasoningLog.tsx`), admin surface জীবন্ত (`/api/v1/admin/stats|users|audit-logs`), config contract জীবন্ত (`ConfigValidationReport` + CORS resolver ইউনিফিকেশন), connection registry write-through, প্রথম ৫টি mission test + CI-তে প্রথম pass^3, এবং `docs/SKIPPED_TESTS.md` পুনর্নির্মাণ। ভেরিফিকেশন: ৪৫ টেস্ট সবুজ, pass^3 = 1.0000 (n=12)।

**পরের ১৪ দিন:**

1. এই প্যাচটি রিভিউ ও merge করা; `alembic upgrade head` চালিয়ে crawl টেবিল প্রোভিশন করা।
2. Supabase `ai_memory` Phase C SQL চালানো (ফেজ ০ সমাপ্তি)।
3. মিশন স্যুট ৫ → ১২ টেস্টে বাড়ানো (research/file/scheduler জুড়ে)।
4. Capability health-probe promotion (IDEA → MEASURED) জীবন্ত করা — খোলা Phase 1 আইটেম।
5. Settings-এ execution-mode UI; ফ্রন্টএন্ডে `SCRAPER_BACKEND_URL` resolver।
6. নাইটলি pass^k লাইভ zero-cost chain-এ — প্রথম scoreboard artifact প্রকাশ।

স্কোরবোর্ড মাপা শুরু করে দিয়েছে। তারপর প্রতিটি সপ্তাহে একটা করে সংখ্যা সোজা হবে — এবং সংখ্যাগুলোই আমাদের স্বপ্নের সাক্ষী দেবে।

