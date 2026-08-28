# LESSONS_LEARNED

> **[🤖 AI AGENT INSTRUCTION]** 
> This is a core SupremeAI "Brain" file. When adding a new lesson:
> 1. Add it to the TOP of the list (reverse chronological).
> 2. Include Date, Issue, Fix, and Lesson.
> 3. DO NOT delete or overwrite past historical entries.
> 4. Keep it concise and technical.

## 2026-08-25 — 🔐 Security CVE Fix: Manual poetry.lock Patching is Forbidden

- **সমস্যা:** CVE ফিক্স করতে `poetry.lock`-এ সরাসরি version string patch করা হয়েছিল (`48.0.1` → `50.0.0`)। কিন্তু lock file-এ Poetry নিজস্ব content hash ও pyproject.toml fingerprint store করে, তাই manual patch করলে CI-তে `"pyproject.toml changed significantly since poetry.lock was last generated"` এরর দিয়ে `poetry install` ব্যর্থ হয়।
- **ফিক্স:** `poetry lock` command দিয়ে lock file সম্পূর্ণ regenerate করতে হবে। `infisical-python` downgrade block করলে `--no-update` flag ব্যবহার করতে হবে অথবা constraint আলগা করতে হবে।
- **লেসন:** **`poetry.lock` কখনো manually edit করা যাবে না।** CVE ফিক্স = `pyproject.toml` constraint আপডেট → `poetry lock` → commit। একই নিয়ম `pnpm-lock.yaml`-এর ক্ষেত্রেও প্রযোজ্য — Trivy বলে এলে `pnpm update <pkg>` চালাতে হবে, lock file hex-edit করা যাবে না।

## 2026-08-25 — 🧪 Test Isolation: Production Guard Bypassing in Unit Tests

- **সমস্যা:** CI-তে `ENV=test` থাকলেও কিছু tests production mode-এ চলছিল কারণ `settings.env` সরাসরি singleton থেকে পড়া হচ্ছিল। `local_code_executor.py`-এ production guard আগেই block করছিল, ফলে `mock_subprocess` কল হচ্ছিল না।
- **ফিক্স:** Tests-এ `patch("tools.code.local_code_executor.settings") as mock_settings: mock_settings.env = "test"` দিয়ে production guard bypass করা হয়েছে।
- **লেসন:** Unit test-এ production-specific guard থাকলে `settings` object-কে mock করে env override করতে হবে। pytest conftest-এ global `ENV=test` সেট করলেও singleton settings reload হয় না।

## 2026-08-25 — 🔀 Refactoring: Facade Module-এ Mock Path Update

- **সমস্যা:** Phase-1 refactoring-এ `tools/ai_agents/browser_agent.py` একটি facade হয়ে গেছে (`from core.agents.live.browser_agent import ...`)। কিন্তু tests-এ এখনো `patch("tools.browser_agent.is_safe_url")` ব্যবহার করা হচ্ছিল — `AttributeError` আসছিল।
- **ফিক্স:** Mock path → `patch("core.agents.live.browser_agent.is_safe_url")`।
- **লেসন:** Module refactoring বা facade তৈরির পর সব associated test-এর `patch()` path একসাথে আপডেট করতে হবে। `grep -r "patch(\"old.module"` দিয়ে সব test খুঁজে বের করতে হবে।



- **সমস্যা:** (১) P0 Vulnerability: `server.py`, `chat.py`, `browser.py`, `byoc_api.py` তে কোনো Authentication Dependency ছিল না, ফলে API রুটগুলো এক্সপোজড ছিল; (২) ফ্রন্টএন্ডে `DashboardShell.tsx`-এ AI এর ফেক রেসপন্স টাইমার (`setTimeout`) রেস কন্ডিশনের শিকার হতো, ইউজার দ্রুত সেশন পালটালে ভুল ট্যাবে মেসেজ যেত; (৩) `supremeShared.ts`-এ লিগ্যাসি ব্যাকএন্ড URL হার্ডকোড করা ছিল যা URL Drift এর কারণ হতো।
- **ফিক্স:** (১) `server.py` এর নির্দিষ্ট রুটগুলোতে এবং অন্যান্য API ফাইলের `APIRouter` ডিক্লারেশনে `dependencies=[Depends(get_current_user_token)]` অ্যাড করা হয়েছে; (২) `DashboardShell.tsx`-এ `activeSessionId` এর স্টেল ক্লোজার ফিক্স করতে `useRef` এবং `setTimeout` ক্লিয়ার করতে `useEffect` ব্যবহার করা হয়েছে; (৩) হার্ডকোড করা URL সরিয়ে `import.meta.env.VITE_BACKEND_URL` এর মাধ্যমে ডায়নামিক ফলব্যাক তৈরি করা হয়েছে।
- **লেসন:** ব্যাকএন্ডে API রুটগুলোতে ডে-১ থেকেই Auth ডিপেন্ডেন্সি এনফোর্স করা বাধ্যতামূলক। React-এ `setTimeout` বা অ্যাসিঙ্ক কাজের ক্ষেত্রে স্টেল ক্লোজার এড়াতে সবসময় `useRef` দিয়ে লেটেস্ট ভ্যালু ট্র্যাক করতে হবে। ক্লায়েন্ট সাইডে কোনো সার্ভার/API URL হার্ডকোড করা উচিত নয়, এনভায়রনমেন্ট ভ্যারিয়েবল (Vite env) ব্যবহার করা বেস্ট প্র্যাকটিস।

## 2026-08-22 — 🛡️ CI & Runtime Resilience: Telemetry Fail-Open Bug + Router Contract + Fail-Closed Chaos Policy

- **সমস্যা:** (১) `core/llm/telemetry.py`-তে `to_log_line` নন-JSON অবজেক্টে ক্র্যাশ করত এবং `finally` ব্লকে exception আসল LLM রেজাল্ট মাস্ক করে `ALL_MODELS_FAILED` দেখাত; (২) `brain/smart_router.py`-তে কনসোলিডেশনের পর `complexity` কী মিসিং থাকায় লিগ্যাসি কনজিউমাররা ফেইল করত; (৩) `admin_dashboard.py` ও `traffic_monitor.py`-তে মিসিং ইমপোর্ট (`export_codebase_to_markdown`, `logger`) রানটাইমে NameError ঘটাত; (৪) `chaos_worker.py`-তে `fuzz_sandbox` আনঅভেইলেবল থাকলে সাইলেন্টলি স্কিপ করে গেট আনলক (fail-open) হয়ে যেত।
- **ফিক্স:** (১) `json.dumps(..., default=str)` ও `with contextlib.suppress(Exception)` দিয়ে best-effort safe logging; (২) `route()` ডিকশনারিতে `complexity` এবং `tier` উভয় কী রিস্টোর; (৩) মিসিং ইমপোর্ট ফিক্স; (৪) `chaos_worker.py`-তে `else` ব্রাঞ্চে fail-closed পলিসি কার্যকর।
- **লেসন:** টেলিমেট্রি ও লগিং কখনো আসল এক্সিকিউশন বা বিজনেস লজিকের ফলাফল অল্টার/মাস্ক করতে পারে না — সর্বদা `default=str` ও best-effort মোডে রাখতে হবে। সিকিউরিটি স্যান্ডবক্স অডিটে কোনো ডিপেন্ডেন্সি মিসিং থাকলে সাইলেন্ট স্কিপ নিষিদ্ধ — সর্বদা fail-closed রাখতে হবে।

## 2026-08-18 — 🔴 CI Red After Merge: 4 রকম Root Cause + Live Fix

- **সমস্যা:** main-এ merge-এর পর GitHub Actions RED — Core CI-র ৩টি job (Frontend pnpm install, Render backend env check, Infisical vault check) + Monorepo Type Sync fail করছিল। Root causes: (১) `pnpm-lock.yaml` root importer-এ ৭টি stale dependency (`cross-env`, `ioredis`, `@types/ioredis`, `@types/node`, `@webcontainer/api`, `dotenv`, `rollup`) package.json-এ না থাকলেও lockfile-এ আটকে ছিল → `ERR_PNPM_OUTDATED_LOCKFILE`। (২) আসল Render backend (`supremeai-backend-docker` = `srv-da07ogmgekts739amqa0`) এ মাত্র 26/99 tracked keys — critical `SUPREMEAI_ADMIN_PASSWORD_HASH` ও `INFISICAL_TOKEN` missing; workflow-র hardcoded fallback ID (`srv-d9d3n58js32c738n79k0`) 404। (৩) Infisical Universal Auth 401 — rotated CLIENT_ID/SECRET Infisical-এ create হয়নি + vault-এ `INFISICAL_CLIENT_SECRET` key-ই ছিল না। (৪) `generate_types.py`-তে `filename.relative_to(Path.cwd())` — CI-র `working-directory: backend`-এ output path `cwd`-র subpath না → ValueError; আর generated ফাইলের header-এ `// Generated: <timestamp>` ছিল → checksum সবসময় drift দেখাত।
- **ফিক্স:** (১) `pnpm install --lockfile-only` → lockfile resync। (২) Render API (PUT /services/{id}/env-vars/{key}) দিয়ে ২টি critical key যোগ + workflow-র ৮টি dead fallback ID-কে সঠিক ID (`srv-da07ogmgekts739amqa0`) দিয়ে replace। (৩) Infisical API (POST /v3/secrets/raw) দিয়ে vault-এ `INFISICAL_CLIENT_SECRET` যোগ + `verify_infisical_env.py`-এ Universal Auth fail হলে `INFISICAL_TOKEN` fallback। (৪) `relative_to(_REPO_ROOT)` + ৪ জায়গায় timestamp লাইন রিমুভ (deterministic) + UTF-8 reconfigure।
- **লেসন:** (১) Render/env drift check-এ GitHub secret-এর উপর blind ভরসা না — live API দিয়ে service ID/env var key verify করতে হবে; fallback-এ dead ID রেখে দিলে misleading error পাই। (২) PowerShell দিয়ে YAML/UTF-8 file replace নিষিদ্ধ (BOM + CRLF + mojibake) — Python `pathlib` দিয়ে replace। (৩) Generated ফাইলে কখনো timestamp header রাখা যাবে না — determinism ভাঙে। (৪) Secrets rotation শুধু value generate করলে হয় না — Infisical-এ machine identity আসলেই create/register করতে হয়, নাহলে 401।

### 2026-08-29: Config Validator Infisical Fix
- **Issue**: Application crashed on Render during startup with \SystemExit: 1\ due to \alidate_config()\ failing on required variables (e.g., \JWT_SECRET\).
- **Root Cause**: \alidate_config\ was checking \os.getenv()\ directly, bypassing the Infisical lazy-loaded secrets stored in the \settings\ object.
- **Fix**: Updated \_validate_var\ in \core/config_validator.py\ to also check properties inside the \settings\ object if \os.getenv()\ returns None.
