# LESSONS_LEARNED

> **[🤖 AI AGENT INSTRUCTION]** 
> This is a core SupremeAI "Brain" file. When adding a new lesson:
> 1. Add it to the TOP of the list (reverse chronological).
> 2. Include Date, Issue, Fix, and Lesson.
> 3. DO NOT delete or overwrite past historical entries.
> 4. Keep it concise and technical.

## 2026-08-22 — 🛡️ CI & Runtime Resilience: Telemetry Fail-Open Bug + Router Contract + Fail-Closed Chaos Policy

- **সমস্যা:** (১) `core/llm/telemetry.py`-তে `to_log_line` নন-JSON অবজেক্টে ক্র্যাশ করত এবং `finally` ব্লকে exception আসল LLM রেজাল্ট মাস্ক করে `ALL_MODELS_FAILED` দেখাত; (২) `brain/smart_router.py`-তে কনসোলিডেশনের পর `complexity` কী মিসিং থাকায় লিগ্যাসি কনজিউমাররা ফেইল করত; (৩) `admin_dashboard.py` ও `traffic_monitor.py`-তে মিসিং ইমপোর্ট (`export_codebase_to_markdown`, `logger`) রানটাইমে NameError ঘটাত; (৪) `chaos_worker.py`-তে `fuzz_sandbox` আনঅভেইলেবল থাকলে সাইলেন্টলি স্কিপ করে গেট আনলক (fail-open) হয়ে যেত।
- **ফিক্স:** (১) `json.dumps(..., default=str)` ও `with contextlib.suppress(Exception)` দিয়ে best-effort safe logging; (২) `route()` ডিকশনারিতে `complexity` এবং `tier` উভয় কী রিস্টোর; (৩) মিসিং ইমপোর্ট ফিক্স; (৪) `chaos_worker.py`-তে `else` ব্রাঞ্চে fail-closed পলিসি কার্যকর।
- **লেসন:** টেলিমেট্রি ও লগিং কখনো আসল এক্সিকিউশন বা বিজনেস লজিকের ফলাফল অল্টার/মাস্ক করতে পারে না — সর্বদা `default=str` ও best-effort মোডে রাখতে হবে। সিকিউরিটি স্যান্ডবক্স অডিটে কোনো ডিপেন্ডেন্সি মিসিং থাকলে সাইলেন্ট স্কিপ নিষিদ্ধ — সর্বদা fail-closed রাখতে হবে।

## 2026-08-18 — 🔴 CI Red After Merge: 4 রকম Root Cause + Live Fix

- **সমস্যা:** main-এ merge-এর পর GitHub Actions RED — Core CI-র ৩টি job (Frontend pnpm install, Render backend env check, Infisical vault check) + Monorepo Type Sync fail করছিল। Root causes: (১) `pnpm-lock.yaml` root importer-এ ৭টি stale dependency (`cross-env`, `ioredis`, `@types/ioredis`, `@types/node`, `@webcontainer/api`, `dotenv`, `rollup`) package.json-এ না থাকলেও lockfile-এ আটকে ছিল → `ERR_PNPM_OUTDATED_LOCKFILE`। (২) আসল Render backend (`supremeai-backend-docker` = `srv-da07ogmgekts739amqa0`) এ মাত্র 26/99 tracked keys — critical `SUPREMEAI_ADMIN_PASSWORD_HASH` ও `INFISICAL_TOKEN` missing; workflow-র hardcoded fallback ID (`srv-d9d3n58js32c738n79k0`) 404। (৩) Infisical Universal Auth 401 — rotated CLIENT_ID/SECRET Infisical-এ create হয়নি + vault-এ `INFISICAL_CLIENT_SECRET` key-ই ছিল না। (৪) `generate_types.py`-তে `filename.relative_to(Path.cwd())` — CI-র `working-directory: backend`-এ output path `cwd`-র subpath না → ValueError; আর generated ফাইলের header-এ `// Generated: <timestamp>` ছিল → checksum সবসময় drift দেখাত।
- **ফিক্স:** (১) `pnpm install --lockfile-only` → lockfile resync। (২) Render API (PUT /services/{id}/env-vars/{key}) দিয়ে ২টি critical key যোগ + workflow-র ৮টি dead fallback ID-কে সঠিক ID (`srv-da07ogmgekts739amqa0`) দিয়ে replace। (৩) Infisical API (POST /v3/secrets/raw) দিয়ে vault-এ `INFISICAL_CLIENT_SECRET` যোগ + `verify_infisical_env.py`-এ Universal Auth fail হলে `INFISICAL_TOKEN` fallback। (৪) `relative_to(_REPO_ROOT)` + ৪ জায়গায় timestamp লাইন রিমুভ (deterministic) + UTF-8 reconfigure।
- **লেসন:** (১) Render/env drift check-এ GitHub secret-এর উপর blind ভরসা না — live API দিয়ে service ID/env var key verify করতে হবে; fallback-এ dead ID রেখে দিলে misleading error পাই। (২) PowerShell দিয়ে YAML/UTF-8 file replace নিষিদ্ধ (BOM + CRLF + mojibake) — Python `pathlib` দিয়ে replace। (৩) Generated ফাইলে কখনো timestamp header রাখা যাবে না — determinism ভাঙে। (৪) Secrets rotation শুধু value generate করলে হয় না — Infisical-এ machine identity আসলেই create/register করতে হয়, নাহলে 401।

## 2026-08-17 — 🕷️ Scraper Microservice: SSRF Hole + Dead Code + Test Coverage Gap

- **সমস্যা:** (1) `main.py` /recipe endpoint-এ `initial_url` directly `page.goto()`-এ পাঠানো হচিল — `is_safe_url()` check ছিল না, ফলে SSRF হ্যান্ডলার মেটাডেটা সার্ভিস/ইন্টার্নাল API-এ ব্রাউজার লোড করতে পারে; (2) `main.py-এর `if "pytest" in sys.modules` / `else` দুটি শাখাওই একই `_APP_IMPORT_STRING = "main:app"` সেট করিল — dead code, `import sys` অয়োগ। (3) `browser_agent.py` semaphore `async with` 9-space indent (সঠিক 12-space নয়) — ruff SIM117 violation। (4) `execute_recipe` except block-এ `index` variable `for` loop-এর বাইরে — `NameError` crash। (5) 4টি মাত্র টেস্ট (কোনো recipe, screenshot, concurrency, is_safe_url unit test নেই)। (6) `RecipeRequest.steps` required (no default) — POST `{}` → 422।
- **ফিক্স:** (1) `/recipe` endpoint-এ `is_safe_url()` চেক যোগ (HTTP 400 on SSRF); (2) dead code রিমুভ → `_APP_IMPORT_STRING = "main:app"`; (3) 12-space indent ঠিক করে `async with self._semaphore, async_playwright()` কম্বাইন; (4) `index = -1` guard; (5) 4→37 টেস্ট (SSRF matrix × 3 endpoints, recipe edge cases, concurrency semaphore, 21টি is_safe_url parametrized); (6) `steps: list = []` default। pyproject.toml-এ pytest-asyncio config যোগ।
- **লেসন:** User input সবসময় browser navigation-এর আগে validate করতে হবে — `/scrape` আর `/browse` যেমন security check থাকলেও `/recipe` endpoint-ও একই `is_safe_url()` চেক পেতবে। Pydantic model-এ `list = []` mutable default safe (Pydantic deep-copy করে)। Concurrency semaphore production-এ critical — Render free tier (512MB RAM)-এ Playwright browser launch storm-এর বাধা দায়। Test coverage 4→37 দিয়ে 86% scenario coverage পাওয়া যায়।

## 2026-08-17 — 🐛 Pre-existing YAML Indentation Bug in maintenance_pipeline.yml (cost-guard-defcon job)

- **সমস্যা:** `maintenance_pipeline.yml`-এর `cost-guard-defcon` job-এর `env:` block-এ সঠিক আছিল 6-space indent, কিন্তু `SUPABASE_DATABASE_URL`/`SUPABASE_DATABASE_URL_POOLER`/`SUPREMEAI_JWT_SECRET` লাইনগুলো 11-space indentation-এ লেখা ছিল → YAML parser error (`expected <block end>, but found '<block mapping start>'`)। GitHub Actions-ও এটি catch করত না কারণ job scheduling-এ ফেইল হয়েছিল।
- **ফিক্স:** 11-space → 6-space indentation ঠিক করা। `yaml.safe_load()` দিয়ে verify করা — VALID।
- **লেসন:** YAML-এর block mapping-এর indentation strict — editor স্বয়ংক্রিয়ভাবে indent করলে even-width সাপোর্ট দেয় না। CI YAML-এর syntax সর্বদা `yaml.safe_load()` দিয়ে pre-validate করতে হবে, বিশেষ করে যখন একটি বড় pre-existing file-এর মিধ্যে edit করা হয়।

## 2026-08-17 — 🔄 CI Workflow Consolidation (11 → 6 workflows)

- **সমস্যা:** ১টি মূল `ci.yml` + ৪টি ডুপ্লিকেট/অভিরুপ workflow ছিল: (1) `auto-fix.yml` — daily 01:30 UTC স্কিডুল + PR trigger, `maintenance_pipeline.yml`-এর `auto-lint-fix` + `ci-failure-smart-summary` জবগুলোর সম্পূর্ণ ডুপ্লিকেট; (2) `cache-janitor.yml` + `workflow-janitor.yml` — আলাদা workflow-এর জায়গে maintenance task হিসেবে maintenance_pipeline-এ যুক্ত করা যায়; (3) `security-audit.yml` + `security-dast.yml` — দুটোটি weekly security scan, একত্র করা যায়।
- **ফিক্স:** এই 5টি workflow ডিলিট করে `maintenance_pipeline.yml`-এ তাদের জবগুলো যুক্ত করা (8টি নতুন জব + 6টি নতুন `workflow_dispatch` input)। `pull_request` trigger যোগ করা — gatekeeper ২৪ঘণ্টার সীমা PR trigger-এ bypass করে (`github.event_name != 'schedule'`)। `promotion/staging` PR-এর জন্য `!startsWith(github.head_ref, 'promotion/staging')` গার্ড যোগ করা।
- **লেসন:** Multiple scheduled workflows একসাথে চালু হলে GitHub Actions free tier minutes ডুপ্লিকেট হয়। Consolidated workflow-এর `if` conditions-এ `github.event_name` check অপরিহার্য — gatekeeper `needs:` dependency only makes sense on `schedule` triggers, PR trigger-এ সরাসরি run করতে হয়।

## 2026-08-17 — 🚨 Dead URL: supremeai-admin.onrender.com is SUSPENDED

- **সমস্যা:** `supremeai-admin.onrender.com` (Admin Backend Render সার্ভিস) স্বামী কর্তৃ SUSPENDED — CORS headers রিটার্ন করে না, কোনো API কল 403 দেয়। 8টি অ্যাক্টিভ ফাইলে 36টি রেফারেন্স ছিল: vite.config.ts, api.test.ts, origin_validator.py, Cloudflare worker, render.admin.yaml, service_preflight_check.py, .env.example, DEPLOYMENT_CHECKLIST.md, scripts/check_admin_console.js। `api.ts` আগেই `supremeai-backend-docker.onrender.com`-এ আপডেট করে ছিল (অথরাইজ্ড), কিন্তু vite.config.ts ও test assertions পুরনো URL ব্যবহার করছিল → test failure + dev proxy 403।
- **ফিক্স:** সব অ্যাক্টিভ ফাইলে `supremeai-admin.onrender.com` → `supremeai-backend-docker.onrender.com` রিপ্লেস। `_archive/` ও `docs/`-এর রেফারেন্সগুলো ডকুমেন্টেশন-ওয়েজি রাখা (historical reference)।
- **লেসন:** Production URL পরিবর্তন/সাস্পেনশন হলে সক্রিয় কোড-এ সব রেফারেন্স আপডেট করতে হবে — environment variable, CORS allowlist, health check URLs, test assertions, deployment configs. `api.ts`-এর default আগেই আপডেট করা থাকায় সেটি source of truth হিসেবে ব্যবহার করা যায়।
