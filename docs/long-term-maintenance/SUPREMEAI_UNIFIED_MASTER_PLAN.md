# SupremeAI 2.0 — UNIFIED MASTER PLAN (Living Single Source of Truth)

**Version:** 1.0 · **Status:** Active · **Purpose:** এই একটা ফাইল প্রজেক্টের multi-purpose central reference — architecture snapshot, non-negotiable principles, stabilization + feature-rollout সিকোয়েন্স, recurring maintenance calendar, audit governance, ও decision log — সব একসাথে। অন্য সব ব্লুপ্রিন্ট (Command Center, AI Evolution, Desktop App, Documentation Plan, Audit Plan, Master Blueprint) **বাতিল হয় না** — তারা থাকে "how to build X" স্পেক হিসেবে; এই ফাইল বলে **"কখন, কোন অর্ডারে, কী নিয়মে"**।

> **কীভাবে ব্যবহার করবেন:** প্রতিটা নতুন কাজ শুরুর আগে এই ফাইলের Section ৩ (Sequencing) আর Section ৫ (Calendar) চেক করুন। প্রতি মাসে Section ৮ (Decision Log)-এ এন্ট্রি যোগ করুন। এই ফাইল নিজেই version-controlled ও রিপো রুটে থাকবে (`MASTER_PLAN.md`)।

---

## ১. প্রজেক্ট স্ন্যাপশট (Architecture Reference)

```
supremeai/ (monorepo)
├── backend/
│   ├── core/          (~205 files) — resilience, config, security-critical
│   ├── api/+middleware/+database/ (~104) — 74+ routers
│   ├── agents/+brain/+adaptive_engine/+evolution/ (~86) — LiteLLM router, swarm
│   ├── tools/+scripts/+utils/ (~154)
│   ├── memory/+skills/+models/+schemas/ (~55) — ChromaDB/SQLite/Supabase
│   ├── sandbox/+ws/+p2p/+admin/ (~43)
│   └── tests/ (367)
├── apps/
│   ├── studio-client/ (348, React19/Vite7/Tailwind4)
│   ├── mobile/ (92, Flutter/GoRouter)
│   ├── desktop-app/ (planned — Tauri/Electron, "AETHEL Studio")
│   ├── web-chat/
│   └── hf-space/
├── tools/vscode-extension/ (50)
├── infrastructure/ (Render + Vercel + Firebase + Cloudflare + Infisical)
├── packages/+shared/ (~20+)
└── docs/kb/ (12-pillar knowledge base)
```

**Philosophy (৭টা non-negotiable, Master Blueprint থেকে):** Zero Cost (free-tier only) · High Scalability (async non-blocking) · Zero Breakage (delta patching) · Human-in-loop minimal friction · JIT OTP malware immunity · Self-Healing (`autonoguard_engine.py`) · Failure-Aware context routing।

**Multi-DB topology:** Supabase/Postgres (relational) · Redis/Upstash (cache) · Firestore (mobile/web sync) · ChromaDB (vector/RAG) · SQLite (local/offline)।

**Deployment:** Render (API+workers) · Vercel (web) · Firebase (admin god-mode) · Cloudflare (edge/WAF) · Infisical (secrets vault, synced via `sync_all_platforms_env.py`)।

---

## ২. বর্তমান যাচাইকৃত অবস্থা (Verified, not claimed — সর্বশেষ audit থেকে)

| ID | Severity | সমস্যা | স্ট্যাটাস |
|---|---|---|---|
| AUDIT-018 | P1 | `/skills/catalog`, `/voice/voices`, `/files/{path}` — client কল করে, backend route নেই → 404 | 🔴 Open |
| AUDIT-015 | P1 | `CostGuard.validate_budget()` টেস্টেই সীমাবদ্ধ, `task_router.py`-তে wire হয়নি (0% coverage) → budget bypass সম্ভব | 🔴 Open |
| AUDIT-014 | P1 | ৯টা প্যাকেজে ৫৪টা known CVE (aiohttp, cryptography, litellm, pillow, ইত্যাদি) | 🟡 Remediation guide আছে |
| AUDIT-006 | P2 | GitHub Actions ১৫১টা `@vX` reference, SHA-pinned না | 🟡 Open |
| — | P3 | `API-swagger.yaml` ৬০+ router-এর মধ্যে মাত্র `/health` ডকুমেন্টেড | 🟡 Open |
| — | — | Full test suite ৪৮%-এ থেমে গেছে (`test_headless_terminal_agent.py` fail); coverage target মাত্র ৩৮% | 🔴 Open |
| — | ✅ | Tenant isolation — CLEAN (verified) | ✅ Closed |
| AUDIT-017 | P2 | OTP/verification-link plaintext logging | ✅ FIXED |

*(এই টেবিলটা প্রতি অডিট পাসের পর আপডেট হবে — এটাই "current truth", কোনো README claim না।)*

---

## ৩. মাস্টার সিকোয়েন্সিং — কী আগে, কী পরে

### Stabilization Gate (ব্লকিং — নিচের সব বন্ধ না হওয়া পর্যন্ত কোনো নতুন মেগা-ফিচার কোড শুরু হবে না)
1. AUDIT-018 বন্ধ (broken client contracts)
2. AUDIT-015 বন্ধ বা explicitly scoped-and-documented (cost guard bypass)
3. AUDIT-014 trackable প্যাকেজ আপগ্রেড
4. Full test suite সম্পূর্ণ pass (headless terminal agent fix সহ)
5. GitHub Actions SHA-pin

### এরপর রোলআউট অর্ডার (একসাথে সর্বোচ্চ ১টা মেগা-ফিচার active code-এ)
| ক্রম | উদ্যোগ | কেন এই অর্ডারে |
|---|---|---|
| 1 | Command Center P0-P3 | Existing backend-এর উপর, নতুন attack surface কম |
| 2 | Desktop App Phase 1-2 (shell + extension parity) | Command Center-এর design token পুনর্ব্যবহার করে |
| 3 | AI Evolution পর্ব ১ (নিরাপত্তা+কনটেক্সট) | Sandbox/memory ভিত্তি শক্ত করে, পরের পর্বের প্রি-রিকুইজিট |
| 4 | Command Center P4-P9 | — |
| 5 | Desktop App Phase 3-5 | — |
| 6 | AI Evolution পর্ব ২-৩ (swarm debate, fine-tuning, multi-modal) | সবচেয়ে বেশি নতুন risk surface — সবার শেষে, সবচেয়ে বেশি guardrail সহ |

---

## ৪. Non-Negotiable Rules (সব ফেজে প্রযোজ্য, একত্রীকৃত)

1. **Empirical Evidence Required** — grep/test/log প্রমাণ ছাড়া "Fixed"/"Done" দাবি নিষিদ্ধ।
2. **Independent Verification** — যে ফিচার/ফিক্স করেছে সে নিজে সেটা "Verified" ট্যাগ দিতে পারবে না।
3. **P0 Stop-the-Line** — P0 পেলে সাথে সাথে hotfix branch, বাকি কাজ থামিয়ে।
4. **Docs ≠ Truth** — README/`docs/`-এর দাবি না, সরাসরি কোড/deployed state চেক করতে হবে।
5. **No Hardcoded Displayed Values** — কোনো UI নম্বর `Math.random()`/static array থেকে না; API fail করলে "degraded (—)" দেখাবে, fake number না।
6. **Anti-Silent Failure** — কোনো খালি `catch {}` না; প্রতিটা error → central error bus → alert/toast।
7. **One Mega-Feature at a Time** (Section ৩ দেখুন)।

---

## ৫. রিকারিং অপারেশন ক্যালেন্ডার (এই সেকশনটাই "long-term maintenance"-এর মূল)

| ফ্রিকোয়েন্সি | কাজ | মালিক/মেকানিজম |
|---|---|---|
| **প্রতি PR** | Docs freshness diff (`app.openapi()` vs committed spec) | CI gate |
| **প্রতি PR** | `gitleaks`, `ruff`/`eslint`, unpinned-action check | pre-commit + CI |
| **সাপ্তাহিক** | AI Evolution: synthetic data pipeline রান (যদি পর্ব ২+ শুরু হয়) | Cron + content filter |
| **২ সপ্তাহে ১ বার** | Docs-vs-Code drift পাস (Phase 15 রিপিট) | Scheduled |
| **মাসে ১ বার** | Dependency/CVE triage (`pip-audit`+`npm audit`+`flutter pub outdated`) | Scheduled CI job |
| **মাসে ১ বার** | Backup-backend sync চেক (cron ইতিমধ্যে ৬ ঘণ্টায় আছে — মাসিক রিভিউ যোগ) | Cron + manual review |
| **প্রতি রিলিজ** | Full E2E + coverage রিপোর্ট (Phase 16 রিপিট) | CI |
| **প্রতি মেগা-ফিচার শিপের ৩ দিনের মধ্যে** | স্কোপড সিকিউরিটি অডিট (নতুন module-specific) | Independent reviewer |
| **প্রতি ফাইন-টিউন রান** | Eval harness + shadow deploy (কখনো সরাসরি প্রোড না) | AI Evolution pipeline gate |
| **প্রতি স্প্রিন্ট** | কমপক্ষে ২০% সময় tracked backlog (P1/P2) কমানোয় | টিম নীতি |
| **কোয়ার্টারলি** | পূর্ণ Master Plan রিভিউ — Section ২ (verified state) ও Section ৩ (sequencing) আপডেট | ম্যানুয়াল |

---

## ৬. অডিট ও কোয়ালিটি ফ্রেমওয়ার্ক (রেফারেন্স — বিস্তারিত `SUPREMEAI_MASTER_AUDIT_PLAN_v2.md`-এ)

- Severity Matrix: P0 (XSS/Injection/Prompt-Injection→Tool-Exec/Secret leak/Auth bypass/Data loss) → P1 (False-positive claim/Silent failure/Sandbox escape/Cost breach) → P2 (CSP/CORS/Config drift/Contract breakage) → P3 (dead code/style)।
- Issue format: `[ID] [Severity] [Technical Term] [ফাইল:লাইন]` + সমস্যা/root cause/প্রমাণ/guard।
- ফেজ তালিকা ও ফাইল কাউন্ট: Audit Plan v2 দেখুন (Phase 0-17, AI/Agent Security 6.5, Contract Testing 13.5, RBAC 14.5, Cost Guard 14.75)।

---

## ৭. AI Evolution Safety Net (রেফারেন্স — বিস্তারিত Long-Term Maintenance Plan-এ)

Self-fine-tuning শুরুর আগে বাধ্যতামূলক ৪টা জিনিস: (১) Eval harness — benchmark prompt set-এ score ড্রপ করলে auto-reject, (২) Shadow deployment ১-৩ দিন, (৩) Versioned checkpoint + one-click rollback, (৪) Synthetic training data-তে content/poisoning filter। **এগুলো ছাড়া AI Evolution পর্ব ২ (Self-Evolution Engine) শুরু হবে না।**

---

## ৮. সিদ্ধান্ত লগ (Decision Log — প্রতিবার বড় সিদ্ধান্তে এন্ট্রি যোগ করুন)

```markdown
## [তারিখ] — [সিদ্ধান্ত শিরোনাম]
- প্রেক্ষাপট: কেন এই সিদ্ধান্ত দরকার হলো
- সিদ্ধান্ত: কী ঠিক হলো
- Stabilization Gate স্ট্যাটাস তখন: [পাস/আংশিক/ফেল]
- Active মেগা-ফিচার তখন: [কোনটা active development-এ ছিল]
- প্রভাব: কোন Section আপডেট হলো (২/৩/৫)
```

*(প্রথম এন্ট্রি এখানে যোগ করুন যখন Stabilization Gate-এর প্রথম আইটেম বন্ধ হবে।)*

---

## ৯. সম্পর্কিত ডকুমেন্ট (এই মাস্টার প্ল্যান এগুলোর উপরে বসে, প্রতিস্থাপন করে না)

| ফাইল | ভূমিকা |
|---|---|
| `SUPREMEAI_MASTER_BLUEPRINT.md` | Architecture ও component inventory-র বিস্তারিত সোর্স |
| `SUPREMEAI_MASTER_AUDIT_PLAN_v2.md` | Phase-by-phase অডিট প্রসিডিউর |
| `SUPREMEAI_LONG_TERM_MAINTENANCE_PLAN.md` | Governance রুলের পূর্ণ ব্যাখ্যা (এই ফাইলের Section ৩,৫,৭-এর উৎস) |
| `PHASES_13-17_AUDIT_REPORT.md` | সর্বশেষ empirical evidence — Section ২-এর সোর্স |
| `COMMAND_CENTER_MASTER_PLAN.md`, `AI_INTELLIGENCE_EVOLUTION_PLAN.md`, `DESKTOP_APP_MASTER_PLAN.md` | ফিচার-লেভেল "how to build" স্পেক |
| `master-documentation-plan-and-benefits.md` | `docs/kb/` ১২-pillar কাঠামো |
| `PHASE_LOG.md` | প্রতিটা অডিট ফেজের রান-লগ |

---

## ১০. সাফল্যের মানদণ্ড (এই প্ল্যান কাজ করছে কিনা বোঝার উপায়)

- [ ] Section ২-এর টেবিলে কোনো P0/P1 ৩০ দিনের বেশি "Open" থাকে না
- [ ] একই সময়ে একটার বেশি মেগা-ফিচার active code-এ নেই
- [ ] Decision Log-এ প্রতি মাসে অন্তত ১টা এন্ট্রি
- [ ] Quarterly review নিয়মিত হচ্ছে (Section ২/৩ স্ট্যাল না)
- [ ] Recurring calendar (Section ৫)-এর কোনো আইটেম miss হচ্ছে না ২ সাইকেলের বেশি

---

_SupremeAI 2.0 — Unified Master Plan · এই ফাইলটাই root-level single source of truth, বাকি সব প্ল্যান এর সাপোর্টিং ডকুমেন্ট।_
