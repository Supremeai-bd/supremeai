# 🎯 SupremeAI Final Roadmap — "Simple নয়, Perfect"

> **সংস্করণ:** ১.২ (Final + রিভিউ ফাইন-টিউনিং + ফেজ-টেবিলে ইন্টিগ্রেশন + প্রমাণ-সংশোধন)
> **তৈরি:** দুটি স্বাধীন বিশ্লেষণের মার্জ ও সংশোধনের ভিত্তিতে
> **উৎস ডকুমেন্ট:**
> 1. `docs/audit_reports/PROJECT_COMPLEXITY_ANALYSIS_BN.md` (রিপোর ভেতরে) — Complexity Candidate Map (A/B/C পদ্ধতি)
> 2. স্বাধীন গভীর-অডিট রিপোর্ট — সিস্টেম/অপারেশন/CI/নিরাপত্তা বিশ্লেষণ
> 3. রিপোর নিজের স্বীকৃতি: `PROJECT_STATUS_DISCREPANCY_REGISTER.md` (R1–R11), `MODULE_STATUS_REGISTRY.md` (#449), `STATUS.md`
>
> **দর্শন:** এই রোডম্যাপ কোনো deletion plan নয় — এটি একটি **Execution Contract**। প্রতিটি কাজের সাথে Evidence → Verification Gate → DoD (Definition of Done) → Rollback আছে। "Perfect" মানে কম ফাইল নয় — **এক responsibility-র একটাই source of truth, যাচাইযোগ্য সীমা ও মালিকানা সহ।**

> **v1.2 রিভিউ-সংযোজন (৫টি ফাইন-টিউনিং — এখন সংশ্লিষ্ট ফেজ-টেবিলেও বসানো):**
> 1. **Feature vs Refactor Lock:** Phase 0–2 চলাকালে ফিচার/ফিক্স সহাবস্থান করবে, কিন্তু **Phase 3 (ভারী কনসোলিডেশন) চলাকালে নতুন আর্কিটেকচারাল ফিচার-ব্রাঞ্চ ফ্রিজ** (MESH-3 ধাঁচের ফিচার থামবে না, তবে নতুন routing/config/memory-স্পর্শকারী ব্রাঞ্চ খোলা যাবে না)।
> 2. **DB Migration টুলিং স্ট্যান্ডার্ড:** স্কিমা পরিবর্তনের একক ক্যানোনিকাল রানার = **Alembic** — হার্ড প্রমাণ: `backend/alembic.ini` + `backend/alembic_migrations/versions/` (৩১টি revision, R7-এর `2026_09_12_190000_add_user_execution_mode.py` সহ)। নতুন কোনো ad-hoc SQL migration path খোলা যাবে না। Supabase SQL script শুধু Supabase-সাইড অবজেক্টের জন্য, এবং প্রতিটিতে Alembic revision জোড়া থাকবে। `performance_metrics` ড্রপ-ও Alembic revision দিয়েই।
> 3. **Desktop/Offline টেস্ট গেট (3.3 DoD-তে যোগ):** `apiClient.ts` মাইগ্রেশনের DoD-তে **Electron IPC fallback টেস্ট + `localFirstDb` অফলাইন-মোড ইন্টিগ্রেশন টেস্ট** বাধ্যতামূলক — ওয়েব-টেস্ট পাস যথেষ্ট নয়।
> 4. **মাল্টি-এজেন্ট কনকারেন্সি রুল:** রিপোর `AGENTS.md`-এর **"One Issue = One Owner = One Branch = One Focused PR"** নীতি এই রোডম্যাপের বাধ্যতামূলক অংশ — Phase 3-এর প্রতিটি migration-এ দুই এজেন্ট একই মডিউলে হাত দিতে পারবে না (atomic claim নিচের প্রক্রিয়া-অংশে যুক্ত)।
> 5. **রোলব্যাক ড্রিল (0.6):** Phase 0-তেই non-production এনভায়রনমেন্টে **অন্তত ১ বার আসল restore ড্রিল** — snapshot থেকে ফিরে আসা প্রমাণ না হলে backup গণ্য হবে না। *(Phase 0 টেবিলে 0.6 রো হিসেবে যুক্ত)*
> 6. **প্রমাণ-সংশোধন (v1.2):** আইটেম 1.1-এর সঠিক অ্যালিয়াস `SUPREMEAI_CREDENTIAL_ENC_KEY` (আগের খসড়ায় ভুলবশত `SUPREMEAI_ENCRYPTION_KEY` লেখা হয়েছিল) — প্রমাণ: `backend/api/routes/keys.py:22`, `secure_credential_store.py:101`, `.env.example:372`, টেস্ট ফিক্সচার। এই ফিক্স ইতিমধ্যে PR #1153 (issue #1152) হিসেবে জমা।

---

## 📐 অংশ ১: দুই বিশ্লেষণের তুলনা ও মার্জ-সিদ্ধান্ত

### ১.১ কোন ডকুমেন্ট কী ধরেছে (অদ্বিতীয় ফাইন্ডিংস)

| এলাকা | Candidate Map (আপনার) | স্বাধীন অডিট (আমার) | মার্জ-সিদ্ধান্ত |
|---|---|---|---|
| Config registry ট্রিপল-সোর্স (`CONFIG_SCHEMA` ~130 + `ENV_REGISTRY` ~50 + `CONFIG_SPECS` 200+) | ✅ A-ক্যাটাগরি, file:line সহ | ✅ ৩-দিকের ড্রিফট সংখ্যা (৩৬০/২৪১/৪০৬) | **একত্র:** `core/config/registry.py` canonical + সেখান থেকে `.env.example` অটো-জেনারেশন |
| রেট-লিমিটার | 🟠 "৯→১ merge খুব সরলীকরণ" — Policy-based হওয়া উচিত | 🔴 ৯টি ফাইল গণনা | **Candidate Map গ্রহণ:** `RateLimitService` + UserPolicy/ProviderPolicy/GlobalPolicy; তবে হুবহু ডুপ্লিকেট (দুই জায়গার `tenant_rate_limiter.py`) আসল merge হবে |
| Memory ৫ স্ট্যাক | 🟡 "Verify first — AI-তে একাধিক memory লেয়ার বৈধ" | 🔴 ~৩৬ ফাইল, ৩টি API রুট | **Candidate Map গ্রহণ:** আগে domain-map, পরে শুধু প্রমাণিত overlap-এ facade |
| Infisical অপারেশন | ❌ নেই | ✅ ভল্ট গেট `continue-on-error`, `PROJECT_SLUG` vs `PROJECT_ID`, `sync_render_secrets.py` এতিম | **অডিট গ্রহণ** — Candidate Map পুরোপুরি রানটাইম secret-বিমূর্তকরণে ফোকাসড, অপারেশন ধরেনি |
| docker-compose মিসওয়্যারিং | ❌ নেই | ✅ মৃত `DATABASE_URL` + `HARD_REQUIRED_SECRETS` টেমপ্লেটে মিসিং | **অডিট গ্রহণ** |
| DB read-only pooler + নীরব SQLite ফলব্যাক | ❌ নেই | ✅ ডেটা-লস হ্যাজার্ড | **অডিট গ্রহণ** — এটা Phase 0-র safety net |
| Frontend HTTP ৪ স্ট্যাক | ✅ A — `apiClient.ts` canonical (Electron fallback সহ) | ✅ + SSE token query-string ঝুঁকি | **একত্র:** migration + security fix একসাথে |
| Frontend state (৮ Zustand + ৫ dead Redux stub) | ✅ A/C — mega-store নয়, domain store | ❌ নেই | **Candidate Map গ্রহণ** |
| CI ব্যুরোক্রেসি (৩০ workflow, ci-doctor বট) | ❌ নেই (কোড-লেভেল ফোকাসড) | ✅ ৮,৬৮১ লাইন YAML, ৩৮% চার্ন | **অডিট গ্রহণ** — Candidate Map-এর workflow কিন্তু CI ছাড়া চলবে না, তাই Phase 2-এ আগে CI ডায়েট |
| বড় ফাইল / lock files | ✅ "poetry.lock/pnpm-lock ধরবেন না" | — | **গ্রহণ** — lock file স্পর্শ নিষিদ্ধ |
| অরফান মডিউল সিদ্ধান্ত | ❌ নেই | ✅ ৮টি মডিউল OWNER DECISION pending | **অডিট + রিপোর নিজের registry গ্রহণ** |

### ১.২ পদ্ধতিগত সিদ্ধান্ত (Methodology Adoption)

Candidate Map-এর এই ৪টি নীতি **পুরো রোডম্যাপের স্পাইন** হবে:

```
পাইপলাইন: Evidence confirm → Owner map → Canonical design → Tests
           → CI green → Deprecate (warning) → Migrate → Delete
```

1. **ফাইল-সংখ্যা = জটিলতা নয়; একাধিক source of truth = জটিলতা।**
2. **A/B/C বাধ্যতামূলক শ্রেণিবিন্যাস:** 🟢 A = Confirmed (এখনই), 🟡 B = Audit-এর-পরে, 🟠 C = Intentional (boundary পরিষ্কার, merge নয়)।
3. **Deprecate-before-delete:** সরাসরি মুছবে না — warning দিয়ে migration window।
4. **প্রতিটি কাজে ৫-ফিল্ড টেমপ্লেট:** Evidence / Owners / Overlap / Canonical / Verification Gate।

**সংশোধন (আমার আগের রিপোর্টের):** "৯ রেট-লিমিটার → ১ ক্লাস", "মেমরি ৫→১ facade", "validate_all()" — এগুলো সরলীকরণ ছিল; চূড়ান্ত রোডম্যাপে policy-based / domain-mapped / 4-tier সংস্করণ বসানো হয়েছে।

---

## 🗺️ অংশ ২: ফাইনাল রোডম্যাপ — ৭টি ফেজ

> **ক্রমের যুক্তি:** Safety net ছাড়া কোনো রিফ্যাক্টর নয় (Phase 0) → ঝুঁকিমুক্ত জয় দিয়ে বিশ্বাস গড়া (Phase 1) → CI ডায়েট আগে, কারণ বাকি সব কাজ CI-র ভেতর দিয়ে যাবে (Phase 2) → তারপর ভারী কনসোলিডেশন (Phase 3–4) → শেষে স্থায়ী "perfect" অবস্থা লক করা (Phase 5–6)।

---

### 🔒 Phase 0 — Safety Nets & Baseline (আগে কিছু ভাঙার আগে)
**লক্ষ্য:** এমন জাল বুনা যাতে পরের সব পরিবর্তন বিপর্যয় হলেও ধরা পড়ে ও ফিরিয়ে আনা যায়।
**সময়: ~১ সপ্তাহ | ঝুঁকি: নিম্ন | কাজের ধরন: অবকাঠামো**

| # | কাজ | বিস্তারিত | DoD (Definition of Done) |
|---|---|---|---|
| 0.1 | **DB writer হ্যাজার্ড বন্ধ** | `SUPABASE_DATABASE_URL_WRITER` প্রোডাকশনে মিসিং হলে warning নয় — **hard-fail** (এখন নীরবে ephemeral SQLite-এ ফলব্যাক করে ডেটা হারায়) | প্রোডাকশন বুট টেস্ট: WRITER ছাড়া বুট = স্পষ্ট এরর; সাথে থাকলে DDL write সফল |
| 0.2 | **Backup snapshot** | প্রতিটি ফেজ শুরুর আগে tag + branch snapshot (`pre-phase-1`, `pre-phase-2`...) | প্রতিটি tag থেকে restore টেস্ট ১ বার সফল |
| 0.3 | **Contract test বেসলাইন freeze** | বর্তমান আচরণের golden tests: CORS parse আউটপুট, JWT validation, LLM router resolve, apiClient retry matrix | বেসলাইন suite সবুজ; রিফ্যাক্টর চলাকালে এগুলোই রক্ষী |
| 0.4 | **টোকেন রোটেশন সম্পন্ন-করা যাচাই** | R10 ঘটনার পর পরামর্শকৃত Render/GitHub টোকেন রোটেশন সত্যিই হয়েছে কিনা যাচাই | রোটেটেড টোকেন দিয়ে deploy সফল; পুরনো টোকেন revoked |
| 0.5 | **Open discrepancy নিবন্ধন** | R4 (SKIPPED_TESTS doc নেই, আসল skip=125), R5 (coverage ৩০/১৬ vs ১০০% প্ল্যান), R9 (`performance_metrics` মৃত টেবিল), R11 ("১০০% complete" মিথ্যা দাবি) — ৪টি OPEN আইটেম এই রোডম্যাপের সংশ্লিষ্ট ফেজে বাঁধা | রেজিস্টারে প্রতিটি R-এর পাশে ফেজ-রেফারেন্স লেখা |
| 0.6 | **রোলব্যাক ড্রিল (প্রমাণসহ)** | non-production এনভায়রনমেন্টে অন্তত ১ বার আসল restore ড্রিল: পুরনো snapshot/backup থেকে সম্পূর্ণ ফিরে আসা — ডেটা + স্কিমা + সার্ভিস | restore-এর লগ/প্রমাণ নথিভুক্ত; **প্রমাণ ছাড়া backup গণ্য হবে না**; ড্রিল প্রতি বড় ফেজে পুনরাবৃত্ত |

**Verification Gate (ফেজ-লেভেল):** বেসলাইন test suite + backup tags + R-নিবন্ধন = ৩টিই ছাড়া পরের ফেজ শুরু নিষিদ্ধ।

---

### ⚡ Phase 1 — Category A: Confirmed Duplication (ঝুঁকিমুক্ত দ্রুত জয়)
**লক্ষ্য:** Candidate Map-এর 🟢 A-তালিকা + অডিটের নিম্ন-ঝুঁকি ফিক্স। প্রতিটি আইটেম স্বতন্ত্র PR, এক সেশনে শেষ হওয়ার মতো ছোট।
**সময়: ~২ সপ্তাহ | ঝুঁকি: নিম্ন–মধ্যম**

| অগ্রাধিকার | কাজ | ক্যাটাগরি | Canonical | Verification Gate |
|---|---|---|---|---|
| 1.1 ✅ | ২টি আক্ষরিক বাগ ফিক্স: `os.getenv("ENCRYPTION_KEY") or os.getenv("ENCRYPTION_KEY")` — **ডেলিভারড: PR #1153 (issue #1152)** | 🟢 বাগ | দ্বিতীয় অপারেন্ড = সঠিক অ্যালিয়াস **`SUPREMEAI_CREDENTIAL_ENC_KEY`** (ক্যানোনিকাল প্র্যাটার্ন: `backend/api/routes/keys.py:22`) | byte-level diff রিভিউ + secret vault boot test |
| 1.2 | Dead Redux stubs মুছুন (৫টি ১-লাইন slice) + `migration_map.ts` | 🟢 A | — | `grep` = zero import → delete |
| 1.3 | Deprecated shim মুছুন: `error_handler.py`, `error_bus.py`, `security/ssrf_protection.py` shim | 🟢 A | আসল implementation | প্রতিটির repo-wide import search = 0 |
| 1.4 | CORS → `parse_origin_list()` (`core/config_parsers.py` — issue #1173 অনুযায়ী flat leaf module, প্যাকেজ নয়) | 🟢 A | এক parser | JSON/comma/empty/malformed ৪-টেস্ট + ৬ caller migrate (cors_policy, origin_validator, server, _render_proxy, config_validation, config_secrets) + প্রোডাকশন CORS অপরিবর্তিত |
| 1.5 | Backend URL → `getApiBaseUrl()` universally | 🟢 A | বিদ্যমান ফাংশন কাঁটাছাঁট নয় | grep: কম্পোনেন্টে `import.meta.env.VITE_API_URL` = 0 হিট |
| 1.6 | `docs/generated/`-এ hand-edit ব্লকার | 🟢 A | CI-only | CI চেক: manual modification = fail |
| 1.7 | `round*_comments/` ৪ রাউন্ডের ডুপ্লিকেট → `ACTIVE_AUDIT.md` মার্জ → archive | 🟢 A | ACTIVE_AUDIT.md | সব issue-ID এক জায়গায়; পুরনো ৪ ডিরেক্টরি archived |
| 1.8 | প্ল্যান-সাবডিরেক্টরির ৭টি README → ১টি | 🟢 A | `docs/plans/README.md` | — |
| 1.9 | `NETIFY_API_KEY` typo + `PAYMENT_FAILED` জাঙ্ক এন্ট্রি মুছুন | 🟢 A | — | registry + template sync |
| 1.10 | R9: `performance_metrics` — **REVISED (issue #1177)**: writer/reader wired ছিল (`performance_oracle` + `agent_breeding` routes); টেবিল live | 🟢 | — | drop-migration `k5l6m7n8o9p0` neutralize করা হয়েছে idempotent recreate `t7u8v9w0x1y2` দিয়ে (Alembic) + R9 register হালনাগাদ |

**ফেজ DoD:** সব PR একত্রে বেসলাইন suite সবুজ; `backend/core`-এ ≥৮ ফাইল কম; কোনো আচরণ-পরিবর্তন নেই।

---

### 🧹 Phase 2 — CI/Governance Diet (কারণ বাকি সব কাজ CI-র পেটের ভেতর দিয়ে যাবে)
**লক্ষ্য:** ৩০ workflow (৮,৬৮১ লাইন) + ১০০ `scripts/ci` গেট → এমন CI যা রাস্তা দেখায়, বাধা দেয় না। শেষ ৫০ কমিটের ৩৮% ছিল CI-ফাইট — এটা না ঠিক করলে Phase 3–4-এর প্রতিটি PR আটকাবে।
**সময়: ~২ সপ্তাহ | ঝুঁকি: মধ্যম**

| # | কাজ | বিস্তারিত | DoD |
|---|---|---|---|
| 2.1 | **ci-doctor বট বন্ধ** | `ci-doctor.yml` (৭৩৮ লাইন) আর `artifact-regen.yml`-এর main-এ অটো-কমিট/self-merge বন্ধ — গেট যদি generated-file freshness নিয়ে লড়ে, গেটটাই ভুল | `main`-এ আর কোনো `[skip ci]` রোবট-কমিট আসবে না |
| 2.2 | **Workflow ৩০ → ৭**: build+test, lint+type, security-scan, e2e-smoke, deploy-prod, deploy-preview, dependency-update | র‍্যাচেট/proof/doc-consistency/circle-architecture/monitor গেট মুছুন — এরা আগের গভর্নেন্স-আর্টিফ্যাক্টের চাপ ম্যানেজ করতেই জন্মেছিল (self-referential) | কমিট-চার্নে CI-fix কমিটের অনুপাত ৩৮% → <৫% (৪ সপ্তাহ মেজার) |
| 2.3 | **Infisical ভল্ট গেট সত্যিকার করুন** | `continue-on-error: true` সরান → critical সিক্রেট মিসিং = লাল পাইপলাইন; `INFISICAL_PROJECT_ID`/`PROJECT_SLUG` এক নামে ইউনিফাই (সব workflow + Python টুলিং); `INFISICAL_ENV`, `INFISICAL_TIMEOUT` টেমপ্লেটে যোগ | `--strict` চেক ব্লক করে; দুই নামের ব্যবহার = ১ |
| 2.4 | **`sync_render_secrets.py` wire বা delete** | ভল্ট→Render sync কোনো workflow ডাকে না — হয় scheduled workflow-এ ধরুন, নাহলে মুছে ম্যানুয়াল-ধাপ হিসেবে docs-এ লিখুন | হয় অটোমেটেড sync প্রমাণ, নাহয় স্পষ্ট নথিভুক্ত ম্যানুয়াল প্রক্রিয়া |
| 2.5 | **Zero-hardcode স্ক্যানার নিজের ছাড় তুলে নিন** | `check_hardcoded_deployment_config.py` থেকে `scripts/ci` exemption সরান; `deploy_doctor.py`-এর ৪টি হার্ডকোড Render URL config-এ সরান; `auto_repair_cloudflare_vault.py`-এর হার্ডকোড Infisical UUID সরিয়ে rotate করুন | স্ক্যানার নিজেই নিজের ডিরেক্টরি স্ক্যান করে; ০ hardcode হিট |
| 2.6 | **রুট-আর্টিফ্যাক্ট একতা** | route_inventory (৭৬২) vs route_consumer_inventory (৮১৬) vs পুরনো ৫৬৮ — এক canonical স্ক্যানার, এক JSON, বাকি সব generate-from-it | ৩ আর্টিফ্যাক্ট → ১ সোর্স; পুরনোগুলো deleted |
| 2.7 | **R5 মীমাংসা** | কভারেজ গেট (৩০/১৬) বনাম `COVERAGE_90_PLAN.md` (১০০%) — বাস্তবসম্মত ratchet টার্গেট বসিয়ে প্ল্যান রিফ্রেশ | প্ল্যান ও গেট একই সংখ্যা বলে |
| 2.8 | **GitHub সিক্রেট ক্যাপ (১০০/১০০) কৌশল** | environment-scoped secrets + Infisical-direct ব্যবহার; নতুন কী আর `.env.example`-এ লিক হবে না | ক্যাপ <৯০; registry coverage ১০০% |

**ফেজ DoD:** একটি সাধারণ feature PR হেডলেসভাবে মার্জ হয় (কোনো "unblock main" লাগে না); CI মোট YAML লাইন ≤ ৩,০০০।

---

### 🏗️ Phase 3 — Category B: Verified Consolidation (আগে অডিট, তারপর মাইগ্রেট)
**লক্ষ্য:** Candidate Map-এর 🟡 B-আইটেমগুলো — প্রতিটির জন্য আগে **Ownership Map** PR (শুধু ডকুমেন্ট+ডায়াগ্রাম, কোনো কোড পরিবর্তন নয়), অনুমোদনের পর migration PR।
**সময়: ~৪–৬ সপ্তাহ | ঝুঁকি: মধ্যম–উচ্চ (তাই দুই-ধাপে)**

> **🚫 Feature/Refactor Lock (এই ফেজের জন্য বাধ্যতামূলক):**
> - Phase 3 চলাকালে **নতুন আর্কিটেকচারাল ফিচার-ব্রাঞ্চ ফ্রিজ** — routing/config/memory/state-স্পর্শকারী নতুন ব্রাঞ্চ খোলা যাবে না।
> - MESH-3 (#927, Agent Mailbox) ইতিমধ্যে মার্জড — চলমান MESH-4 (HITL Gate, #942) ও MESH-6 এই ফেজে **শুরু হবে না**; চাইলে Phase 4-এর পরে নতুন baseline-এ।
> - ব্যতিক্রম: শুধু bug-fix + security-fix PR (আলাদা ইস্যু, ছোট scope)।
>
> **🤝 মাল্টি-এজেন্ট কনকারেন্সি রুল (AGENTS.md §3 বাধ্যতামূলক):** এই ফেজের প্রতিটি migration-এ **"One Issue = One Owner = One Branch = One Focused PR"** — `scripts/ci/atomic_claim.sh` দিয়ে atomic claim ছাড়া কোনো এজেন্ট মডিউল স্পর্শ করতে পারবে না; একই মডিউলে দুই এজেন্ট = STOP।

| # | আইটেম | ধাপ ১ (Audit PR) | ধাপ ২ (Migration PR) | Canonical |
|---|---|---|---|---|
| 3.1 | **ENV Registry ইউনিফিকেশন** | ম্যাপ: `CONFIG_SCHEMA` (~130) + `ENV_REGISTRY` (~50) + `CONFIG_SPECS` (200+) — প্রতিটি ভ্যারিয়েবল কে পড়ে/লেখে | নতুন `core/config/registry.py`-এ সব মেটা-ডেটা একত্র → পুরনো ৩ registry ডেপ্রিকেট-ওয়ার্নিং → পরের রিলিজে delete; **সাথে** registry থেকে `.env.example` + `secrets_registry.yaml` অটো-জেনারেশন (৩৬০/২৪১/৪০৬ ড্রিফট → এক সোর্স) | `core/config/registry.py` |
| 3.2 | **LLM Provider Registry** | ৮+ মডিউলের provider-list ম্যাপ (config_validator, env_validator, config_validation, config_secrets, secret_vault, model_router, capabilities, syncguard) | `LLM_PROVIDER_REGISTRY` → সব consumer import; "নতুন provider = ১ জায়গায় পরিবর্তন" টেস্ট | `core/config/registry.py` |
| 3.3 | **Frontend HTTP → apiClient.ts** | ৪ স্ট্যাকের behavior-matrix: কোন status retry, টোকেন কোথায় যায়, timeout কত | `apiClient.ts`-এ circuit-breaker মার্জ + **SSE টোকেন query-string → header** (নিরাপত্তা ফিক্স একসাথে) + Electron fallback সংরক্ষণ। **DoD অতিরিক্ত গেট:** Electron IPC fallback টেস্ট + `localFirstDb` অফলাইন-মোড ইন্টিগ্রেশন টেস্ট বাধ্যতামূলক — ওয়েব-টেস্ট পাস যথেষ্ট নয় | `services/apiClient.ts` |
| 3.4 | **Router Responsibility Audit** | ৬ রাউটারের Input/Output/Responsibility/Consumers/Overlap% টেবিল — HTTP ≠ Intent ≠ Task ≠ Model, এরা ভিন্ন লেয়ার | শুধু প্রমাণিত overlap মার্জ; `unified_router.py` কেবল সেখানেই canonical | responsibility ভিত্তিক |
| 3.5 | **Cache Type Audit** | L1-memory ≠ L2-Redis ≠ semantic — কোন কী-গুলো ২+ জায়গায় ক্যাশ হয় | `core/cache/`-এ `CacheAbstraction` interface (Redis/Memory/Semantic backend আলাদাই থাকবে) | interface |
| 3.6 | **Memory Domain Map** | ~৩৬ ফাইলের প্রতিটির: memory type, reader/writer, API route | শুধু প্রমাণিত ডুপ্লিকেট মার্জ; ৩টি API রুট → ১ facade রুট | `core/memory/` (ownership স্পষ্ট হলে) |
| 3.7 | **Secret Provider Abstraction** | `secret_vault` vs `secure_credential_store` vs `security_vault` vs `config_secrets` — retrieval ≠ encryption ≠ tenant-isolation | `SecretProvider` interface + Environment/Infisical/KMS/EncryptedStorage providers; **নিরাপত্তা-রিভিউ বাধ্যতামূলক**; টেন্যান্ট-আইসোলেশন টেস্ট আগে | interface (একাধিক implementation বৈধ) |
| 3.8 | **Rate Limit Policy Architecture** | ৯ ফাইলের প্রতিটির policy ম্যাপ: user-quota ≠ API-RPM ≠ provider-RPM ≠ tenant ≠ cost | `RateLimitService` + UserPolicy/ProviderPolicy/GlobalPolicy; হুবহু ডুপ্লিকেট (`middleware/tenant_rate_limiter.py` vs `tools/tenant_rate_limiter.py`) আগেই এক হবে | policy-based |
| 3.9 | **State Architecture** | ৮ Zustand store-এর usage-matrix; `useStore` vs `unifiedStore` overlap | এক **নিয়ম** (domain store), mega-store নয়; `localFirstDb` sync-strategy হিসেবে | architecture rule |

**ফেজ DoD:** প্রতিটি B-আইটেমের audit-PR মার্জড + অনুমোদিত overlap-গুলো মাইগ্রেট + পুরনো পাথ deprecation warning সহ; বেসলাইন suite অটুট।

---

### 🧭 Phase 4 — Category C: Boundary Clarity + System Integration (অডিটের ইউনিক ফাইন্ডিং)
**লক্ষ্য:** 🟠 C-আইটেম (merge নয়, সীমানা স্পষ্টীকরণ) + Candidate Map যে সিস্টেম-লেভেল ভাঙা ওয়্যারিং ধরেনি সেগুলো।
**সময়: ~৩ সপ্তাহ | ঝুঁকি: মধ্যম**

| # | কাজ | ধরন | DoD |
|---|---|---|---|
| 4.1 | **docker-compose.production ঠিক করা** | অডিট | compose-এর `DATABASE_URL` মৃত-ওয়্যারিং সরান → ইঞ্জিন যা পড়ে (`SUPABASE_DATABASE_URL_POOLER`) সেটাই assemble হবে; `.env.production.example`-এ `SUPABASE_URL/KEY/POOLER` (HARD_REQUIRED) যোগ — টেমপ্লেট-অনুসারী ডিপ্লয় আর বুটে ক্র্যাশ করবে না |
| 4.2 | **4-tier Validation Framework** | 🟠 C | Schema(parse) ≠ Semantic(business) ≠ Startup(deps) ≠ Runtime(health) — এক framework-contract, `validate_all()` নয় |
| 4.3 | **Service-role নাম পরিষ্কার** | অডিট | `SERVICE_ROLE` (user/admin) → `PORTAL_ROLE`; `SUPREMEAI_SERVICE_ROLE` (core/worker/scraper) অপরিবর্তিত — নামের মিল ক্রস-ওয়্যারিং আটকাবে |
| 4.4 | **`RENDER_CORE_URL` রেজিস্ট্রি-বাউন্ড** | অডিট | live-smoke টার্গেট সিক্রেটটি `secrets_registry.yaml`-এ যোগ → হেলথ-চেক এখন থেকে যাচাই করবে |
| 4.5 | **SSE টোকেন পরিবহন** | নিরাপত্তা | query-string থেকে header/last-event-id — 3.3-এর সাথে একসাথে শিপ |
| 4.6 | **অরফান মডিউল OWNER DECISION শেষ** | রিপোর নিজের #449 registry | ৮টি মডিউল (escrow, delivery_fleet+rider pair, 5 adapter) — প্রতিটির সিদ্ধান্ত: archive / extract-repo / wire-next; registry-র Decision কলাম পূরণ |
| 4.7 | **pyerrorfix/ + Java-in-extension + reports/ artifacts** | অডিট | ৩৭-ফাইলের vendored linter, ৭টি Java ফাইল, কমিটেড audit-artifacts — সিদ্ধান্ত ও অপসারণ |
| 4.8 | **R4: SKIPPED_TESTS.md পুনর্নির্মাণ** | রিপো OPEN | 125 skip / 53 ফাইলের সত্যিকারের অডিট ডক |
| 4.9 | **R11: সততা স্কোরবোর্ড** | রিপো OPEN | "১০০% complete" ধরনের দাবির বদলে phase-gate scoreboard (`MASTER_PLAN.md` §7) |

**ফেজ DoD:** টেমপ্লেট-অনুসারী ডিপ্লয় প্রথমবারেই সফল; ৮/৮ owner-decision নথিভুক্ত; R4/R9/R11 CLOSED।

---

### 📚 Phase 5 — Docs & Knowledge Architecture
**লক্ষ্য:** ৪৩২ markdown → "এক টপিক, এক জীবন্ত সত্য"। Candidate Map-এর স্ট্রাকচার গ্রহণ (mega `master_docs/` **নয়**)।
**সময়: ~২ সপ্তাহ | ঝুঁকি: নিম্ন**

```
docs/
├── ARCHITECTURE.md      ← জীবন্ত canonical
├── SECURITY.md          ← জীবন্ত canonical
├── OPERATIONS.md        ← জীবন্ত canonical (Infisical প্রক্রিয়া, sync, rotation)
├── DEPLOYMENT.md        ← জীবন্ত canonical (compose সত্য, env চুক্তি)
├── ROADMAP.md           ← এই ডকুমেন্টের লাইভ সংস্করণ
├── ACTIVE_AUDIT.md      ← চলমান অডিট (round-comments মার্জড)
├── generated/           ← CI-only, hand-edit = fail
└── archive/             ← ১৯০ প্ল্যান + ৪৬ পুরনো audit
```

- **রাখা হবে:** ~২০ canonical doc + MASTER_PLAN; **archive:** `docs/plans/` (১৮৮), `docs/audit_reports/` পুরনো রাউন্ড, `crown_jewel_series/`, `docs/generated/` কমিট বন্ধ (২.৬MB) + `backend/openapi.json` কমিট বন্ধ (১.১MB, CI-জেনারেটেড)।
- **পরিশীলন:** `DOCUMENTATION_MASTER_INDEX.md` (৩০০KB) এখন মুছে-ফেলা `.kilo/`-এর ৪২৮ ফাইল ইনডেক্স করে — রিজেনারেট।
- **R2-প্রতিরোধ:** STATUS.md-ধর্মী যেকোনো doc-এ ডুপ্লিকেট-ব্লক ডিটেক্টর (সাধারণ lint)।

**ফেজ DoD:** markdown ৪৩২ → ≤৬০; প্রতিটি টপিকের ঠিক ১টি জীবন্ত মালিক; index সত্য।

---

### 🔝 Phase 6 — "Perfect" State: স্থায়ী গেট ও KPI
**লক্ষ্য:** একবার ঠিক করা অবস্থা যেন **আর ফিরে আসতে না পারে**। এটাই "simple নয়, perfect"-এর পার্থক্য — perfect মানে মাপা ও লক করা।
**সময়: চলমান | ঝুঁকি: নিম্ন**

**স্থায়ী গেট (নতুন CI-তে এই ৬টিই থাকবে):**
1. **Source-of-Truth গেট:** কোনো নতুন ENV ভ্যারিয়েবল `core/config/registry.py` ছাড়া প্রবেশ করতে পারবে না (generator + drift-check)।
2. **Ownership গেট:** প্রতিটি নতুন মডিউল-ফাইলে owner + purpose docstring (MODULE_STATUS_REGISTRY ধাঁচে)।
3. **URL গেট:** কম্পোনেন্টে `import.meta.env.VITE_*` = 0 (শুধু `getApiBaseUrl()`)।
4. **Secret গেট:** vault `--strict` blocking; registry-তে না থাকা live-path সিক্রেট = fail।
5. **Orphan গেট:** নতুন রুট/মডিউল consumer-হীন হলে PR-এই flag (পুরনোগুলোর prune কোয়ার্টারলি)।
6. **Complexity Budget:** fan-in/fan-out + duplicate-block স্কোর মাসিক রিপোর্ট — ratchet নয়, **দৃশ্যমানতা** (আগের ব্যর্থ ratchet-পাঠ শিক্ষা)।

**KPI (Definition of "Perfect"):**

| KPI | বর্তমান | টার্গেট | মাপার উপায় |
|---|---|---|---|
| এক responsibility-র একাধিক canonical | ৯ limiter / ৬ LLM-gw / ৮ provider-list | **১** প্রতিটিতে | import-graph scan |
| ENV ড্রিফট (টেমপ্লেট↔registry↔কোড) | ৩৬০/২৪১/৪০৬, মিল ~০ | **৩ সেট অভিন্ন, জেনারেটেড** | drift-check CI |
| CI workflow / লাইন | ৩০ / ৮,৬৮১ | **৭ / ≤৩,০০০** | wc |
| CI-fix কমিট অনুপাত | ৩৮% | **<৫%** | git log ক্লাসিফায়ার |
| ডকুমেন্ট | ৪৩২ | **≤৬০ জীবন্ত + archive** | গণনা |
| প্রোডাকশন ডিপ্লয় (টেমপ্লেট-অনুসারী) | বুটে ক্র্যাশ-প্রবণ | **first-try সফল** | smoke test |
| Vault গেট | সবসময় সবুজ (মিথ্যা) | **blocking ও সত্য** | `--strict` |
| অরফান রুট | ২৯৬ (৩৬%) | **≤১০% + কোয়ার্টারলি prune** | route inventory |
| Open discrepancy (R-series) | ৪ OPEN | **০** | রেজিস্টার |
| Secret hygiene ঘটনা | R10 + hardcoded UUID | **০, টোকেন সব রোটেটেড** | scan |

---

### 📋 অংশ ৩: এক-পাতার এক্সিকিউশন অর্ডার (Gantt-সংক্ষেপ)

```
সপ্তাহ:      1    2    3    4    5    6    7    8    9   10   11   12
Phase 0    ████
Phase 1         ████████
Phase 2                  ████████
Phase 3 (audit-PR)               ████████
Phase 3 (migration)                      ██████████████
Phase 4                                          ████████
Phase 5                                                  ████████
Phase 6                                                          → চলমান
```

**প্রতিটি ফেজের প্রবেশ-মানদণ্ড:** আগের ফেজের DoD সম্পূর্ণ + backup tag + বেসলাইন suite সবুজ।
**প্রতিটি ফেজের রোলব্যাক:** ফেজ-tag থেকে restore + deprecation-window বন্ধ না-করা।

---

### ⚖️ অংশ ৪: ঝুঁকি রেজিস্টার (উচ্চ-ঝুঁকি আইটেমের বিশেষ নিয়ম)

| ঝুঁকি | আইটেম | প্রশমন |
|---|---|---|
| Secret migration-এ ডেটা লস | 3.7 SecretProvider | টেন্যান্ট-আইসোলেশন টেস্ট **আগে**, security-review বাধ্যতামূলক, dual-read shadow period |
| Memory facade ভুল domain ধরে নেওয়া | 3.6 | audit-PR ছাড়া migration নিষিদ্ধ; ৩ API রুটের consumer-count আগে মাপা |
| CI ডায়েটে আসল নিরাপত্তা-চেক হারানো | Phase 2 | security-scan workflow অপরিবর্তিত রাখা — কাটা হবে শুধু self-referential গেট |
| `.env.example` জেনারেশনে registry-বহির্ভূত কী হারানো | 3.1 | generator = add-only প্রথম মাসে; diff-report প্রতি PR |
| Pooler read-only আবিষ্কার নতুন কী-তে | 4.1 | WRITER URL প্রোডাকশনে আসার আগে কোনো DDL migration নয় |

---

## 🏁 শেষ কথা (Bottom Line)

> SupremeAI-র সমস্যা ফিচার-সংখ্যা নয় — **একই responsibility-র একাধিক source of truth** (config, limiter, provider-list, HTTP client, memory, secret), এবং সেগুলোকে পাহারা দিতে জন্মানো একটি **স্ব-নির্দেশিত CI-ব্যুরোক্রেসি**।
>
> এই রোডম্যাপ দুই বিশ্লেষণের মার্জ: Candidate Map-এর **পদ্ধতি** (A/B/C, deprecate-before-delete, verification gate) + স্বাধীন অডিটের **অপারেশনাল ফাঁক** (Infisical, compose, DB writer, CI বট) + রিপোর নিজের **OPEN স্বীকৃতি** (R4/R5/R9/R11, #449)।
>
> **Perfect = মাপা:** শেষ অবস্থায় প্রতিটি responsibility-র ১টি মালিক, ১টি চুক্তি, ১টি যাচাই-গেট থাকবে — এবং সেই অবস্থা নিজেই নিজেকে রক্ষা করবে (Phase 6)।

---
*উৎস-ডকুমেন্ট ক্রস-রেফারেন্স: `docs/audit_reports/PROJECT_COMPLEXITY_ANALYSIS_BN.md` (রিপো @ 310abd0), স্বাধীন গভীর-অডিট রিপোর্ট (স্যান্ডবহে agent-zai সংগৃহীত), `docs/architecture/PROJECT_STATUS_DISCREPANCY_REGISTER.md`, `docs/operations/MODULE_STATUS_REGISTRY.md`।*
