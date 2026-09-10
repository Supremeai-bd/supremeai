# SupremeAI — Common Mistakes & Error Tracking Master List

> **উদ্দেশ্য:** এই ডকুমেন্টে SupremeAI-তে যেসব ভুল বারবার হয়, সেগুলো ক্যাটাগরি অনুযায়ী লিস্ট করা আছে।  
> প্রতিটি error-এর পাশে বলা আছে — **ইতিমধ্যে CI/Schedule-এ আছে কিনা, নাকি Add করতে হবে।**  
> Source: `AUDIT_REPORT`, `LESSONS_LEARNED.md`, `ci.yml`, `scheduled-deep-audit.yml`, `maintenance.yml`

---

## Legend

| Badge | মানে |
|---|---|
| ✅ **CI-GATED** | প্রতিটি PR/push-এ CI fail করে |
| 🕐 **SCHEDULED** | Nightly/scheduled audit-এ ধরা পড়ে |
| 🔧 **MANUAL** | Maintenance workflow-এ manually trigger করতে হয় |
| ❌ **NOT TRACKED** | এখনো কোনো automated check নেই — **Add করতে হবে** |

---

## 🔴 Category 1: CI/Build Failures (Most Frequent)

| # | Error Pattern | কেন হয় | Status | কোথায় Check |
|---|---|---|---|---|
| 1.1 | **Coverage threshold fail** — backend/frontend test coverage নির্দিষ্ট % এর নিচে নামলে CI fail | নতুন ফিচার যোগ করে test না লিখলে, বা demo/storybook ফাইল কমালে coverage পড়ে যায় | ✅ **CI-GATED** | `ci.yml` → `MIN_BACKEND_COVERAGE: 30`, `MIN_FRONTEND_COVERAGE: 16` |
| 1.2 | **F821 undefined-name** — script/tools-এ import না করেই variable/class ব্যবহার | `scripts/`, `tools/`, `packages/` directory CI lint-এর বাইরে ছিল | ✅ **CI-GATED** | `ci.yml` → ruff check (backend only — **scripts/ tools/ এর জন্য partially fixed**) |
| 1.3 | **Hardcode Scanner fail** — `os.getenv()` direct call করা | `backend/` এর বাইরে `settings` object bypass করে raw env var read করা | ✅ **CI-GATED** | `ci.yml` → Hardcode Configuration Scanner job |
| 1.4 | **mypy crash on Windows** — non-ASCII comment in config file | `mypy.ini`-তে Bengali comment → Windows cp1252 encoding crash | ✅ **CI-GATED** | `ci.yml` → Backend Type Check (Linux পাস, Windows dev locally ধরা পড়ে) |
| 1.5 | **respx/module import error** — test collection fail | dev dependency install না করে বা unused import রেখে দিলে | ✅ **CI-GATED** | `ci.yml` → Backend Tests (pytest collection) |
| 1.6 | **Missing conftest tier registration** — নতুন test module CI-র ভুল tier-এ পড়ে | `backend/tests/conftest.py`-এ `_CRITICAL_TEST_PARTS` বা `_IMPORTANT_TEST_PARTS` update না করলে | ✅ **CI-GATED** | `ci.yml` → conftest.py tier system |

---

## 🟠 Category 2: Code Quality Regressions (Sneaky — Non-Blocking but Decaying)

| # | Error Pattern | কেন হয় | Status | কোথায় Check |
|---|---|---|---|---|
| 2.1 | **ESLint `no-explicit-any`** — TypeScript-এ `any` type ব্যবহার | দ্রুত কোড লিখতে গিয়ে type skip করা | ⚠️ **CI WARNING** (not blocking) | `ci.yml` → Frontend Lint (126 warnings বর্তমান) |
| 2.2 | **ESLint `no-unused-vars`** — import করা কিন্তু ব্যবহার না করা | refactoring-এ পুরনো import না সরানো | ⚠️ **CI WARNING** (not blocking) | `ci.yml` → Frontend Lint |
| 2.3 | **`no-console` in production** — `console.log` production code-এ | Debug করতে গিয়ে রেখে দেওয়া | ⚠️ **CI WARNING** (not blocking) | `ci.yml` → Frontend Lint |
| 2.4 | **`react-hooks/exhaustive-deps`** — useEffect dependency array incomplete | Hook dependency manually লিখলে ভুল হওয়া স্বাভাবিক | ⚠️ **CI WARNING** (not blocking) | `ci.yml` → Frontend Lint |
| 2.5 | **Blind `except:` / bare except** — সব exception চুপচাপ গিলে ফেলা | দ্রুত error handle করতে গিয়ে broad catch করা | ❌ **NOT TRACKED** | রুফ rule `BLE001` backend-এ manually চালাতে হয় — **CI job add করতে হবে** |
| 2.6 | **Duplicate exports** — একই component দুবার export | Refactoring-এ default + named export দুটোই রাখা | 🕐 **SCHEDULED** | `scheduled-deep-audit.yml` → knip (nightly) |

---

## 🔴 Category 3: Security & Secret Management (Critical)

| # | Error Pattern | কেন হয় | Status | কোথায় Check |
|---|---|---|---|---|
| 3.1 | **Secret/token in URL** — `?token=xxx` query param দিয়ে auth | SSE/WebSocket connection-এ সহজ পথ বেছে নেওয়া | ✅ **CI-GATED** | `ci.yml` → Secret Scanning (gitleaks/trufflehog) |
| 3.2 | **API key committed to repo** — `.env` বা code-এ hardcoded secret | ভুলে `.env` commit করা বা key string সরাসরি code-এ লেখা | ✅ **CI-GATED** | `ci.yml` → Secret Scanning + pre-commit hook |
| 3.3 | **AI chat transcript with secrets** — conversation log repo-তে push | Debug করতে গিয়ে transcript file commit করা | 🕐 **SCHEDULED** | `scheduled-deep-audit.yml` → trufflehog full scan |
| 3.4 | **Third-party API key exposed to frontend** — thin client violation | Backend bypass করে frontend থেকে directly external API call | ✅ **CI-GATED** | `ci.yml` → Frontend scan (OpenRouter/API key pattern check) |
| 3.5 | **`allow-same-origin` in iframe** — strict sandboxing violation | Iframe embed করতে গিয়ে সহজ পথ নেওয়া | ❌ **NOT TRACKED** | **Scheduled audit-এ HTML/iframe scan add করতে হবে** |
| 3.6 | **Token rotation না করা** — compromised key active থাকা | Key leak হলে rotation না করা | 🔧 **MANUAL** | `maintenance.yml` → Telegram Vault Backup + manual rotation |

---

## 🟡 Category 4: Architecture & Design Mistakes

| # | Error Pattern | কেন হয় | Status | কোথায় Check |
|---|---|---|---|---|
| 4.1 | **Unmounted router** — APIRouter define করা কিন্তু `ALL_ROUTERS`-এ register না করা → silent 404 | নতুন router file তৈরি করে mount step ভুলে যাওয়া | ✅ **CI-GATED** | `feature_parity_sentinel.py` → `unmounted-router` check |
| 4.2 | **Frontend-backend path drift** — frontend `/api/v1/foo` call করে কিন্তু backend `/api/v2/foo` | API versioning update করার সময় frontend sync না করা | ✅ **CI-GATED** | `feature_parity_sentinel.py` → `missing-backend-route` check |
| 4.3 | **Dead nav link** — `<Link to="/route">` কিন্তু কোনো `<Route path>` নেই | Route remove করার সময় nav link না সরানো | ✅ **CI-GATED** | `feature_parity_sentinel.py` → `dead-nav-link` check |
| 4.4 | **Ghost UI** — component build করা কিন্তু কোথাও render না করা | Feature half-done অবস্থায় pause হওয়া | ✅ **CI-GATED** | `feature_parity_sentinel.py` → `ghost-ui` check |
| 4.5 | **Dual migration system** — Alembic + raw SQL দুটো একসাথে | Legacy SQL আর Alembic কে reconcile না করা | 🕐 **SCHEDULED** | `scheduled-deep-audit.yml` → full audit (partially) — **dedicated check নেই** |
| 4.6 | **Pydantic strict type mismatch** — `str` field-এ `dict` pass করা | Hub-and-spoke architecture-এ metadata দেওয়ার সময় | ✅ **CI-GATED** | `ci.yml` → Backend Tests (pytest) |
| 4.7 | **Isolated module / Architectural island** — নতুন subsystem central governance-এ connect না করে | Feature-centric thinking, centralization rule ignore করা | 🕐 **SCHEDULED** | `scheduled-deep-audit.yml` → `audit_isolated_modules_and_capabilities.py` |
| 4.8 | **Duplicate logic / code duplication** — same function দুই জায়গায় | Copy-paste করা, DRY principle ভুলে যাওয়া | 🕐 **SCHEDULED** | `scheduled-deep-audit.yml` → `duplicate_detector.py` (nightly) |

---

## 🟡 Category 5: Test & Dependency Issues

| # | Error Pattern | কেন হয় | Status | কোথায় Check |
|---|---|---|---|---|
| 5.1 | **Skipped tests for deleted modules** — module মুছে ফেলা কিন্তু test রেখে দেওয়া | "No Dead Code" policy বুঝতে ভুল — module delete করে test archive না করা | ⚠️ **CI WARNING** | `ci.yml` → Backend Tests (skip report) |
| 5.2 | **Half-deleted circle** — billing/feature-এর tests আছে কিন্তু implementation নেই | Feature incomplete অবস্থায় branch merge | ❌ **NOT TRACKED** | **CI-তে "orphan test" detector add করতে হবে** |
| 5.3 | **Unused dependencies** — `package.json`/`pyproject.toml`-এ declare কিন্তু কোথাও import নেই | Dependency add করে পরে feature বাদ দেওয়া | 🕐 **SCHEDULED** | `scheduled-deep-audit.yml` → knip (frontend), pip-audit (backend) |
| 5.4 | **Dev dependency not in install docs** — local-এ `respx` missing | `poetry install` mandatory কিন্তু docs-এ mention নেই | ✅ **CI-GATED** | Fixed — `poetry install` enforced in CI |
| 5.5 | **Mutation testing রegressions** — core logic পরিবর্তন হলে mutation score drop | Mutation testing result না দেখে merge করা | 🕐 **SCHEDULED** | `scheduled-deep-audit.yml` → `mutation_testing.py` (nightly) |
| 5.6 | **One-off script repo-তে ফেলে রাখা** — কাজ শেষে patch/debug script prune না করা | Urgency-তে কাজ করে cleanup ভুলে যাওয়া | 🔧 **MANUAL** | `scripts/` hygiene audit (manual) — **scheduled prune check নেই** |

---

## 🟠 Category 6: Memory & Runtime Leaks

| # | Error Pattern | কেন হয় | Status | কোথায় Check |
|---|---|---|---|---|
| 6.1 | **useEffect without cleanup** — `componentEventBus.subscribe()` কিন্তু `useEffect` return-এ `unsubscribe()` নেই | React hook pattern না মানা | ❌ **NOT TRACKED** | **ESLint custom rule বা scheduled scan add করতে হবে** |
| 6.2 | **Memory leak in agent loops** — agent loop limit না থাকায় infinite run | Loop guard না রাখা | 🕐 **SCHEDULED** | `scheduled-deep-audit.yml` → `agent_loop_limiter_check.py` (nightly) |
| 6.3 | **DLQ (Dead Letter Queue) পূর্ণ হয়ে যাওয়া** — failed tasks accumulate | Queue health monitor না থাকলে চুপচাপ error জমে | 🕐 **SCHEDULED** | `scheduled-deep-audit.yml` → `queue_health_checker.py` (nightly) |
| 6.4 | **AI embedding drift** — model পরিবর্তন হলে পুরনো vector আর valid না | AI provider switch করার সময় re-embedding না করা | 🕐 **SCHEDULED** | `scheduled-deep-audit.yml` → `embedding_drift_detector.py` (nightly) |
| 6.5 | **Metrics cardinality explosion** — label-এ dynamic value যোগ করা | High-cardinality label যেমন user_id, request_id metrics-এ | 🕐 **SCHEDULED** | `scheduled-deep-audit.yml` → `metrics_cardinality_auditor.py` (nightly) |

---

## 🟡 Category 7: Deployment & Infrastructure Mistakes

| # | Error Pattern | কেন হয় | Status | কোথায় Check |
|---|---|---|---|---|
| 7.1 | **Uncommitted WIP** — local changes push না করে ভুলে থাকা | Context switch করার সময় | ❌ **NOT TRACKED** | **Pre-push hook বা scheduled dirty-tree check add করতে হবে** |
| 7.2 | **Render env var missing** — production-এ নতুন env var sync না করা | Local `.env`-এ add করে Infisical/Render sync ভুলে যাওয়া | 🔧 **MANUAL** | `maintenance.yml` → env sync task; `scripts/sync_render_secrets.py` |
| 7.3 | **Coverage gate too low** — 9% বা 35%-এ gate রাখলে regression protect করে না | Quick fix করতে গিয়ে gate নামিয়ে দেওয়া | ✅ **CI-GATED** | `ci.yml` → fail-under enforced (30%/16%) |
| 7.4 | **Free-tier limit breach** — Render/Supabase/Redis free tier অতিক্রম | Resource monitoring না থাকা | 🕐 **SCHEDULED** | `scripts/free-tier-health-check.sh` (nightly বা manual) |
| 7.5 | **GitHub Actions supply chain** — action SHA pin না থাকলে hijack risk | `uses: actions/checkout@v4` style → SHA pin mandatory | ✅ **CI-GATED** | `ci.yml` → actionlint (SHA check) |
| 7.6 | **Dependency vulnerability** — outdated package-এ known CVE | Automated update না থাকলে পুরনো থাকে | 🕐 **SCHEDULED** | `scheduled-deep-audit.yml` → `auto_vulnerability_scanner.py` (nightly) |
| 7.7 | **CORS misconfiguration** — wrong origin whitelist | Local dev করতে গিয়ে `*` CORS রেখে দেওয়া | ❌ **NOT TRACKED** | **CI CORS policy scan add করতে হবে** |

---

## 🔴 Category 8: AI/Agent-Specific Mistakes

| # | Error Pattern | কেন হয় | Status | কোথায় Check |
|---|---|---|---|---|
| 8.1 | **AI memory integrity loss** — pgvector-এ corrupt বা stale embedding | Memory write এর সময় validation না করা | 🕐 **SCHEDULED** | `scheduled-deep-audit.yml` → `ai_memory_integrity_audit.py` (nightly) |
| 8.2 | **Prompt injection vulnerability** — user input থেকে system prompt override | Input sanitization না করা | 🕐 **SCHEDULED** | `scripts/safety_guard.py` (CI-তে partially) |
| 8.3 | **Hallucination pattern accumulation** — AI wrong response pattern repeat হওয়া | `hallucination_patterns.db` monitor না করলে | ❌ **NOT TRACKED** | **Scheduled report generate করতে হবে** |
| 8.4 | **Multi-model validator fail** — provider switch করলে response format ভাঙা | Provider-agnostic design না করা | 🔧 **MANUAL** | `scripts/multi_model_validator.py` |
| 8.5 | **Feature parity drift** — backend feature আছে frontend-এ নেই বা উল্টো | Large feature PR-এ দুই দিক sync না হওয়া | ✅ **CI-GATED** | `feature_parity_sentinel.py` (6 detection engines) |

---

## 📋 Summary: What Needs to Be Added

> এই section-এ `❌ NOT TRACKED` items গুলো কোথায় add করলে সেরা হবে তা বলা আছে।

| Priority | Error | Action Required | Where to Add |
|---|---|---|---|
| 🔴 HIGH | **2.5** — Blind `except:` in backend | ruff `BLE001` rule CI-তে enforce করো | `ci.yml` → Backend Lint job |
| 🔴 HIGH | **5.2** — Orphan tests (half-deleted circles) | pytest marker দিয়ে "orphan" test detect করো | `ci.yml` → new step: `python scripts/detect_orphan_tests.py` |
| 🟠 MEDIUM | **3.5** — `allow-same-origin` iframe check | HTML scan regex | `scheduled-deep-audit.yml` → new step |
| 🟠 MEDIUM | **6.1** — Missing `useEffect` cleanup / event bus leak | ESLint custom rule বা grep-based scanner | `ci.yml` → Frontend Lint বা `scheduled-deep-audit.yml` |
| 🟠 MEDIUM | **7.1** — Uncommitted WIP detection | `git status --porcelain` check on schedule | `scheduled-deep-audit.yml` → new step |
| 🟡 LOW | **7.7** — CORS misconfiguration | CORS origin policy scan | `scheduled-deep-audit.yml` → new step |
| 🟡 LOW | **8.3** — Hallucination pattern report | `hallucination_patterns.db` trend analysis | `maintenance.yml` → MLOps nightly job-এ add |
| 🟡 LOW | **4.5** — Dual migration system dedicated check | Alembic vs raw SQL reconcile script | `scheduled-deep-audit.yml` → new step |
| 🟡 LOW | **5.6** — One-off script auto-prune reminder | Age-based script staleness check | `scheduled-deep-audit.yml` → new step |

---

## ✅ Already Covered Summary

```
CI Pipeline (ci.yml) — প্রতিটি PR/push:
├── Backend lint (ruff) — backend/ only
├── Frontend lint (ESLint) — warnings tracked
├── Backend type check (mypy)
├── Frontend type check (tsc)
├── Backend tests + coverage gate (30%)
├── Frontend tests + coverage gate (16%)
├── Secret scanning (gitleaks)
├── Hardcode scanner (custom)
├── Feature parity sentinel (6 engines)
├── Action SHA pin check (actionlint)
└── Supply chain security

Scheduled Deep Audit (03:00 UTC daily):
├── Duplicate logic detector
├── Auto vulnerability scanner (deps + code + SBOM)
├── Mutation testing
├── Performance benchmark
├── Isolation & capability audit
├── Full CI audit (ci-full-audit.sh)
├── AI memory integrity audit
├── Embedding drift detector
├── Queue health checker (DLQ)
├── Metrics cardinality auditor
└── Agent loop limiter check

Maintenance Workflow (02:00 UTC daily + manual):
├── Smart CI failure summary
├── Database schema contract check
├── MLOps nightly evolution & governance
├── Render account cooldown recheck
└── Old workflow run cleanup
```

---

*Last updated: 2026-09-11 | Source: AUDIT_REPORT, LESSONS_LEARNED, ci.yml, scheduled-deep-audit.yml, maintenance.yml*
