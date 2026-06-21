# 📋 Master Work TODO List (Quick Reference)

*Last updated: 2026-06-21 (Full project re-audit)*

এটি `master_work_and_implementation_plan.md` এর সংক্ষিপ্ত কুইক রেফারেন্স চেকলিস্ট।

---

## 🔴 P0 — CRITICAL (নিরাপত্তা ও জরুরী সংশোধন)

### Infrastructure & Deployments
- [x] **Railway.app ডিপ্লয়মেন্ট** — 3-node active-active mesh ✅
- [x] **Render.com ডিপ্লয়মেন্ট** — fallback node ✅
- [x] **Cloudflare Workers** load balancer setup (40/35/25% weight) — `supremeai-load-balace` Worker তৈরি সম্পন্ন ✅
- [x] **Supabase** PostgreSQL account + connection string in `.env` ✅
- [x] **Upstash Redis** account + connection string in `.env` ✅
- [x] **Telegram Bot Token** — BotFather থেকে সংগ্রহ ও `.env`-এ সেট সম্পন্ন ✅
- [ ] **Discord Bot Token** — `.env`-এ সেট
- [x] **GitHub Repository Secrets** — `GCP_SA_KEY`, `GCP_PROJECT_ID`, `TELEGRAM_BOT_TOKEN`, `SUPABASE_DATABASE_URL`, `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` সেট সম্পন্ন ✅

### Audit Remediation (Critical Security Fixes)
- [ ] **Hardcoded JWT Secret Key:** `app.py` ও `auth_middleware.py` থেকে hardcoded fallback secret সরানো।
- [ ] **Admin Login Token = Plain Password:** এডমিন ভেরিফিকেশনে plain password-এর পরিবর্তে JWT token ইস্যু করা।
- [ ] **Everyone Auto-Granted Admin Role:** `len(email) > 0` ও Firestore ফেইলওভারে এডমিন রোল দেওয়া বন্ধ করা।
- [ ] **TOTP Secret Logged in Plain Text:** `app.py` থেকে TOTP secret logging সরানো।
- [ ] **Auth Route Prefix Conflict:** `email.py` এর prefix `/auth` থেকে পরিবর্তন করে `/integrations/email` করা।
- [ ] **Weak Token Bypass:** `auth_middleware.py` থেকে `"test-token"` বাইপাস রিমুভ করা।
- [ ] **.env File Exposed via Admin API:** সব admin-api এপিআই-তে `Depends(require_admin_token)` প্রটেকশন বসানো।
- [ ] **Duplicate JSONResponse Import:** `task.py` থেকে ডুপ্লিকেট ইমপোর্ট রিমুভ করা।

---

## 🟠 P1 — HIGH PRIORITY (গুরুত্বপূর্ণ লজিক বাগ)

### Infrastructure & CI/CD
- [x] **Terraform IaC** — `infrastructure/terraform/` scripts তৈরি ✅
- [x] **CI/CD Coverage** — `--cov-fail-under=90` `.github/workflows/ci-cd.yml`-এ যুক্ত ✅
- [x] **New Module Tests** — vision_agent, video_generator, telemetry, vpn_switcher, bangla_voice, reasoning_orchestrator, agent_department, supabase_store ✅

### Audit Remediation (High Logic Fixes)
- [ ] **Two Separate config.py Files:** `backend/config.py` এবং `core/config.py` এর CORS ও ভ্যালিডেশন সিঙ্ক করা।
- [ ] **settings.validate() Called Twice:** ডাবল ভ্যালিডেশন বন্ধ করা।
- [ ] **Mutable Default Bug in Experience:** `Experience` ডাটাক্লাসে `field(default_factory=...)` ব্যবহার করা।
- [ ] **stream_chat & get_completion Non-Async:** রাউটগুলোকে `async def` করা।
- [ ] **otp.strip() NoneType Crash:** OTP যাচাইয়ের আগে Null চেক করা।
- [ ] **Unsafe intent.task_type.value Call:** `task_type` স্ট্রিং হলে `.value` কল করার বাগ ফিক্স করা।
- [ ] **GitHub /push Endpoint Hardcoded Repo:** ডামি রিপোজিটরির বদলে রিকোয়েস্ট পেলোড ব্যবহার করা।

---

## 🟡 P2 — MEDIUM PRIORITY (কোড কোয়ালিটি ও রিফ্যাক্টরিং)

### Core Features & UI
- [ ] **Self-Evolution Engine** — `core/evolution_engine.py` full logic + `evolution/auto_skill_creator.py`
- [ ] **Knowledge Base** — seed_data → ChromaDB searchable KB
- [ ] **Sliding Window Summary Tree** — `memory/sliding_window.py` extension
- [ ] **VS Code CodeFlow** visualization
- [ ] **VS Code User Auth** — API key management in extension
- [ ] **Language Routing** — GLM-5/Yi-34B integration

### Audit Remediation (Medium Fixes)
- [ ] **Fake/Hardcoded Users in Auth:** হার্ডকোডেড ক্রেডেনশিয়াল এবং সিক্রেট সরানো।
- [ ] **App.tsx "any" Type Usage:** `any` টাইপ সরিয়ে টাইপসেফ ইন্টারফেস ব্যবহার করা।
- [ ] **Admin Status Bar Hardcoded Online:** রিয়েল-টাইম এপিআই স্ট্যাটাস ইন্ডিকেটর বসানো।
- [ ] **CICDVisualizer Static Data:** মক ডেটা সরিয়ে রিয়েল পাইপলাইন ও ফিচার ফ্ল্যাগ এপিআই কানেক্ট করা।
- [ ] **ActionCard Fake Execution:** ফেক সেTimeout সরিয়ে রিয়েল এডিটর অ্যাকশন রান করা।
- [ ] **admin_dashboard.py Health Map Mock:** মক হেলথ ম্যাপ ডাটা সরানো।
- [ ] **logs_stream File Handle Leak:** ফাইল অবজেক্ট ক্লোজ করতে `try/finally` ব্লক বসানো।
- [ ] **Firebase Config Fake API Key:** ডেভেলপমেন্টের ফলব্যাক কী প্রপারলি হ্যান্ডেল করা।
- [ ] **App.tsx Indentation:** রেন্ডার ইনডেন্টেশন সিঙ্ক করা।

---

## 🔵 P3 — FUTURE (নিম্ন অগ্রাধিকার ও মাইনর ফিচার)

### Research & Edge
- [ ] **Frontier Quality Replication** — o1/R1 reasoning, Perplexity search
- [ ] **Edge Computing** — Cloudflare Workers ultra-low latency
- [ ] **Bengali TTS Full Offline** — Coqui TTS integration
- [ ] **Auto Prompt Framework** — R-A-C-E/C-L-E-A-R hardcoded in agent system prompts

### Audit Remediation (Low/Minor Fixes)
- [ ] **on_event("shutdown") Deprecated:** lifespan context manager ব্যবহার করা।
- [ ] **datetime.utcnow() Deprecated:** `datetime.now(datetime.UTC)` ব্যবহার করা।
- [ ] **sentry_dsn Inconsistent Check:** Sentry config ভ্যালিডেশন সিঙ্ক করা।
- [ ] **main.py String-Based App Ref:** uvicorn-এ app অবজেক্ট পাস করা।
- [ ] **CICDVisualizer Wrong Badge Variant:** failed স্ট্যাটাসে 'purple'-এর বদলে 'danger' ব্যবহার করা।
- [ ] **admin_dashboard.py Hardcoded Metrics:** ফেক মেট্রিক্স রিয়েল এপিআই ডাটা দিয়ে প্রতিস্থাপন করা।

---

## ✅ সম্প্রতি সম্পন্ন (Recently Completed)

- [x] GCP Cloud Run deployment (live: `https://supremeai-api-565236080752.us-central1.run.app`)
- [x] Firebase Hosting (live: `https://supremeai-a.web.app`)
- [x] GitHub Actions unified CI/CD pipeline
- [x] React Studio Client modularization
- [x] Production backend optimization
- [x] 34 test files, 125 passed, 2 skipped
- [x] Skill Marketplace API (`marketplace.py`)
- [x] Prometheus Metrics API (`metrics.py`)
- [x] Vision Agent (`vision_agent.py`)
- [x] Video Generator (`video_generator.py`)
- [x] OpenTelemetry Tracing (`telemetry.py`)
- [x] All Brain modules (reasoning_orchestrator, agent_department, autonomous_agent)

---
*Full detail: [master_work_and_implementation_plan.md](file:///c:/Users/n/supremeai/supremeai_2.0/docs/04-development/master_work_and_implementation_plan.md)*

<!-- Synced: 2026-06-21 (Full project re-audit and audit remediation integration) -->
