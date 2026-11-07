# SupremeAI — PR-to-Production End-to-End System Execution Architecture

এই ডকুমেন্টে মনোরেপো (`Supremeai-bd/supremeai`) তে একটি পুল রিকোয়েস্ট (PR) ওপেন করার পর থেকে শুরু করে লাইভ প্রোডাকশনে ডিপ্লয় হওয়া পর্যন্ত পুরো সিস্টেমের প্রতিটি পদক্ষেপ, প্রোডাকশন ইনফ্রাস্ট্রাকচার, সার্ভিস ম্যাপিং, ডেটাবেস ও সিক্রেট সিঙ্কিং টেকনিক্যাল মেকানিজম কোডবেসের বাস্তব বাস্তবায়ন অনুযায়ী বিস্তারিত লিপিবদ্ধ করা হলো।

---

## পর্ব ১: Pull Request ওপেন হওয়ার পর (CI Gates & Validation)

যখনই কোনো ব্রাঞ্চ থেকে `Supremeai-bd/supremeai`-এর `main` ব্রাঞ্চ বরাবর একটি PR ওপেন হয়, GitHub Actions-এর `.github/workflows/unified-pipeline.yml` স্বয়ংক্রিয়ভাবে ট্রিগার হয়:

### ধাপ ১: Fast Safety Gate (`fast-gate` — <30s)
* **পরিবেশ:** Ubuntu 24.04 (GitHub-hosted runner)।
* **কাজ ১ (Syntax & Linter):** `ruff check core/ scripts/ci/ --select E9,F63,F7,F82 --exclude core/tests/` রান করে পাইথনের মারাত্মক সিনট্যাক্স এরর ও আনবাউন্ড ভেরিয়েবল পরীক্ষা করে।
* **কাজ ২ (Telemetry Event Bus Guard):** `pytest -q tests/unit/test_telemetry_event_bus_guard.py` দিয়ে সেন্ট্রাল ইভেন্ট বাস ঠিকমতো ইনভ্যারিয়েন্ট বজায় রাখছে কিনা যাচাই করে।
* **কাজ ৩ (Wiring Atlas Integrity):** `python scripts/ops/wiring_atlas.py --check` এক্সিকিউট করে সমস্ত ইন্টারনাল সিস্টেম ওয়্যারিং এবং সার্ভিস ডিপেন্ডেন্সি গ্রাফের ইন্টিগ্রিটি চেক করে।

### ধাপ ২: Runtime Readiness & Boundaries (`runtime-readiness` — <30s)
* **পরিবেশ:** Ubuntu 24.04 (GitHub-hosted runner)।
* **কাজ ১ (Readiness Contract):** `python scripts/ci/readiness_contract.py --self-test` এবং `--check-required-names` দিয়ে রানটাইম সার্ভিস স্পেসিফিকেশন ভ্যালিডেট করে।
* **কাজ ২ (Timeout & Silent Failure Guard):** `python scripts/ci/timeout_policy_guard.py --check` এবং `silent_failure_guard.py --check` দিয়ে অ্যাসিনক্রোনাস কলে কোনো আনহ্যান্ডলড সাইলেন্ট ফেইলিউর বা আনবাউন্ডেড টাইমআউট আছে কিনা তা প্রিভেন্ট করে।
* **কাজ ৩ (Public Surface Manifest):** `python scripts/ci/public_surface_guard.py --manifest scripts/ci/public_surface_manifest.txt` দিয়ে পাবলিক API সারফেসে কোনো অননুমোদিত এক্সপোর্ট যোগ হয়েছে কিনা গার্ড করে।

### ধাপ ৩: Heavy Test Battery (`render-heavy-gate`)
* **পরিবেশ ও এক্সিকিউশন মেকানিজম:**
  - এটি রান হয় `[self-hosted, local-pc]` রানারে (অথবা ব্যাকআপ হিসেবে Render-এর `supremeai-ci-runner`-এ)।
  - উদ্দেশ্য: ক্লাউড মিনিট অপচয় না করে (0 Cloud Mins) লোকাল পিসিতে হেভি টেস্ট চালানো।
* **টাস্ক ১ (Full Guard Suite & SAST):** `scripts/ci/run_all_guards.py` ডিসপ্যাচ করে ৪৩টি স্বয়ংক্রিয় গার্ড রান করা (যেমন: `bandit_sast_guard.py`, `js_dep_cve_guard.py`, `npm_dep_cve_guard.py`, `py_dep_cve_guard.py`, `contract_fuzz_guard.py`, `openapi_breaking_guard.py`, `boundary_contract_sentinel.py`, `satellite_residue_guard.py`)।
* **টাস্ক ২ (Unit & Component Guard Battery):** `pytest -q tests/unit/test_telemetry_event_bus_guard.py` এবং `python scripts/ops/wiring_atlas.py --check`।
* **টাস্ক ৩ (Fast Compile Integrity):** `python -m compileall -q core/ scripts/` দিয়ে পুরো কোডবেসের পাইথন বাইটকোড কম্পাইলেশন টেস্ট করে।
* **টাস্ক ৪ (Attestation Publish):** `python scripts/ci/publish_ci_attestation.py` দিয়ে MCP Control Tower-এ টেস্ট স্ট্যাটাস ও কমিট SHA অ্যাটেস্টেশন পাঠায়।

---

## পর্ব ২: অটোনোমাস ল্যান্ডিং ও মার্জ (Autonomous Auto-Landing)

### ধাপ ৪: Gated Auto-Merge (`auto-merge`)
* **শর্ত:** `fast-gate`, `runtime-readiness`, এবং `render-heavy-gate` — তিনটি গেটই যখন `success` হিসেবে ফিনিশ হয়।
* **কাজ:** `gh pr merge "$PR_NUMBER" --squash --delete-branch` স্বয়ংক্রিয়ভাবে এক্সিকিউট হয়। PR স্কোয়াশ মার্জ হয়ে `main` ব্রাঞ্চে ল্যান্ড করে এবং পিআর ব্রাঞ্চটি স্বয়ংক্রিয়ভাবে ডিলিট হয়ে যায়।

---

## পর্ব ৩: প্রোডাকশন ইনফ্রাস্ট্রাকচার ও সার্ভিস ম্যাপিং (SSOT)

SupremeAI প্রোডাকশন আর্কিটেকচার `config/service_registry.yaml` দ্বারা কঠোরভাবে পরিচালিত হয়। এখানে প্রতিটি সার্ভিসের নির্দিষ্ট রোল, পোর্ট ও লাইভ ইউআরএল রয়েছে:

| সার্ভিস কি (Key) | সার্ভিস নাম | রোল ও দায়িত্ব | হোস্ট প্ল্যাটফর্ম | পোর্ট | প্রোডাকশন ইউআরএল |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `api` | `supremeai-api` | Public API Gateway & Multi-LLM Provider Router | Render (Free) | 8787 | `https://supremeai-api-ulw0.onrender.com` |
| `core` | `supremeai-primary` | Primary Core Intelligence & Decision Runtime | Render (Free) | 8000 | `https://supremeai-primary-node-5xso.onrender.com` |
| `scraper` | `supremeai-browser` | Lightweight Stealth Cookie & Web Relay | Render (Free) | 8788 | `https://supremeai-scraper-node.onrender.com` |
| `mcp` | `supremeai-mcp-tower` | MCP Control Plane & Governed Agent Single Door | Render (Free) | 3771 | `https://supremeai-mcp-tower.onrender.com` |
| `worker` | `supremeai-worker` | Async Background Task & Queue Worker | Render (Free) | 8080 | `https://supremeai-worker-node.onrender.com` |
| `brain` | `supremeai-brain` | Dedicated Tiny AI Brain & Model Routing Node | Render (Free) | 8080 | `https://supremeai-tiny-brain.onrender.com` |
| `ci-runner` | `supremeai-ci-runner` | Remote Heavy Verification & CI Offload Runner | Render (Free) | — | Fallback CI Execution |
| `cloudflare` | `cloudflare-studio-proxy` | Edge Proxy, CORS Rewriter & Keepwarm Worker | Cloudflare Workers | Edge | `https://supremeai.live` |
| `frontend` | `supremeai-studio` | User-Facing React/Vite Cockpit UI | Cloudflare Pages | Edge | `https://studio.supremeai.lat` |

---

## পর্ব ৪: পোস্ট-মার্জ ডিপ্লয়মেন্ট প্ল্যানিং, সিক্রেট সিঙ্ক ও স্কিমা ভ্যালিডেশন

`main` ব্রাঞ্চে কোড ল্যান্ড করার সাথে সাথে `unified-pipeline.yml`-এর পোস্ট-মার্জ স্টেজ ট্রিগার হয়:

### ধাপ ৫: এক্সিকিউশন টায়ার ও কোটা রিসোলিউশন (`deploy-and-verify`)
* **কাজ ১ (Tier Resolution):** `python scripts/ci/resolve_execution_tier.py` লোকাল পিসি, রেন্ডার ফ্রি বিল্ড এবং ক্লাউড রানারের স্টেট পর্যালোচনা করে ৩-টিয়ার প্রায়োরিটি (Local PC -> Render Free -> Cloud Runner Backup) নির্ধারণ করে।
* **কাজ ২ (Quota Preflight):** `python scripts/ci/render_quota_preflight.py` একাধিক Render API কী-এর ফ্রি বিল্ড মিনিট কোটা হিসাব করে ভ্যালিডেট করে।
* **কাজ ৩ (Infisical Secret & Database Check):** ডিপ্লয়মেন্টের পূর্বে Infisical ক্লায়েন্ট (`INFISICAL_CLIENT_ID`, `INFISICAL_CLIENT_SECRET`) দিয়ে সিক্রেট যাচাই এবং Supabase স্কিমা ইন্টিগ্রিটি (`core/database/supabase`) প্রিফ্লাইট চেক নিশ্চিত করা।
* **কাজ ৪ (Change Matrix Calculation):** `python scripts/ci/plan_render_deploys.py --base "${{ github.event.before }}" --head "${{ github.sha }}"` রান করে ঠিক কোন কোন ব্যাকএন্ড সার্ভিস ফাইলে পরিবর্তন এসেছে তার একটি JSON ম্যাট্রিক্স তৈরি করে।

### ধাপ ৬: ব্যাকএন্ড সার্ভিস ডিপ্লয় ও ভেরিফিকেশন (`deploy-render-services` & `verify-render-services`)
* **কাজ ১ (Trigger & Poll):** `python scripts/ci/render_trigger_deploy.py` ম্যাট্রিক্স অনুযায়ী পরিবর্তিত Render সার্ভিসগুলোতে রিলিজ ট্রিগার করে এবং লাইভ হওয়া পর্যন্ত সর্বোচ্চ ৬০০ সেকেন্ড অপেক্ষা করে।
* **কাজ ২ (Revision Attestation):** `python scripts/ci/render_deploy_attestation.py` ডিপ্লয় হওয়া সার্ভিসের লাইভ `/health` বা রিলিজ URL থেকে সোর্স commit SHA মিলিয়ে নিশ্চিত করে যে নতুন কোডই লাইভ হয়েছে।
* **কাজ ৩ (Canary Probe):** `python scripts/ci/render_canary.py` অথরিটেটিভ সার্ভিস টার্গেটের ক্যানারি এন্ডপয়েন্টে স্মোক চেক চালায়।

---

## পর্ব ৫: ক্লাউডফ্লেয়ার এজ মেশ ও কিপ-ওয়ার্ম ডিপ্লয়মেন্ট

### ধাপ ৭: Cloudflare Keep-Warm & Studio Proxy (`deploy-cloudflare`)
* **কাজ ১ (Keep-Warm Mesh):** `infrastructure/cloudflare-render-keepwarm` ফোল্ডারে `npx wrangler deploy` দিয়ে ক্লাউডফ্লেয়ার ওয়ার্কার ডিপ্লয় হয়, যা প্রতি ৫ মিনিট পরপর সব Render সার্ভিসকে পিং করে ফ্রি-টিয়ার কোল্ড-স্টার্ট প্রতিরোধ করে।
* **কাজ ২ (Studio Edge Proxy):** `infrastructure/cloudflare-studio-proxy` ফোল্ডারে `npx wrangler deploy` রান করে স্টুডিও ডোমেইনের রাউটিং প্রক্সি ও CORS রিরুল আপডেট করে।

---

## পর্ব ৬: ফেডারেশন স্যাটেলাইট সিঙ্ক ও ক্লাউডফ্লেয়ার পেজেস ডিপ্লয়

### ধাপ ৮: স্যাটেলাইট সিঙ্ক (`federation_satellite_sync.py`)
* **ভূমিকা:** মনোরেপো (`Supremeai-bd/supremeai`) এবং স্টুডিও স্যাটেলাইট (`Supremeai-bd/supremeai-studio`) এর মধ্যে ব্রিজ।
* **কাজ:** মনোরেপোর `studio/` ডিরেক্টরির সমস্ত সোর্স কোড ও ফাইল সিঙ্ক করে সরাসরি `Supremeai-bd/supremeai-studio`-এর `main` ব্রাঞ্চে কমিট ও পুশ করে।

### ধাপ ৯: স্টুডিও স্যাটেলাইটে সিআই ও বিল্ড ভেরিফিকেশন (`deploy-pages.yml`)
যখনই স্যাটেলাইটে নতুন কোড পুশ হয়, স্টুডিওর নিজস্ব গিটহাব অ্যাকশন পাইপলাইন চালু হয়:
* **টাস্ক ১ (`pnpm install --frozen-lockfile`):** সমস্ত নোড ডিপেন্ডেন্সি লকফাইল অনুযায়ী ইনস্টল করে।
* **টাস্ক ২ (`pnpm typecheck`):** ফ্রন্টএন্ডের সমস্ত টাইপস্ক্রিপ্ট টাইপ নিরাপত্তা কঠোরভাবে কম্পাইল ও ভ্যালিডেট করে।
* **টাস্ক ৩ (`pnpm lint`):** ESLint দিয়ে স্টুডিও কোডবেসের প্রতিটি নিয়মনীতি যাচাই করে।
* **টাস্ক ৪ (`pnpm build`):** Vite দিয়ে প্রোডাকশন বান্ডেল তৈরি করে `dist/` ফোল্ডারে আউটপুট জমা করে এবং গিটহাব আর্টফ্যাক্ট আপলোড করে।

### ধাপ ১০: লাইভ ক্লাউডফ্লেয়ার পেজেস ডিপ্লয় (`deploy`)
* **কাজ:** `cloudflare/pages-action@v1` দিয়ে বিল্ড হওয়া `dist/` ফোল্ডার সরাসরি Cloudflare Pages-এ ডিপ্লয় হয়।
* **চূড়ান্ত প্রোডাকশন ডোমেইন:** `https://studio.supremeai.lat` এ নতুন ভার্সন লাইভ হয়ে যায়।

---

## পর্ব ৭: ব্যাকগ্রাউন্ড ও শিডিউলড হেভি রান (Nightly & 24h Heavy Audits)

### ১. অপর্চুনিস্টিক ২৪ ঘণ্টা অডিট (`opportunistic-nightly-audit.yml`)
* **কখন হয়:** প্রতি ২ ঘণ্টা পর পর একটি ক্রোন চেক চলে (`0 */2 * * *`)। যদি বিগত ২৪ ঘণ্টায় অডিট না হয়ে থাকে এবং লোকাল সেলফ-হোস্টেড রানার (`[self-hosted, local-pc]`) অনলাইন থাকে, তবেই এটি ট্রিগার হয়।
* **হেভি টেস্টের বিষয়বস্তু:**
  - `check_opportunistic_audit.py`: ২৪ ঘণ্টার টাইম উইন্ডো ভ্যালিডেশন।
  - ডিপ ডিপেন্ডেন্সি ও ভার্নারেবিলিটি সুইপ।
  - ৪৩+ অটোমেটিক গার্ড ও এপিআই কন্ট্রাক্ট টেস্ট।
  - ক্লাউড ফলব্যাক: যদি লোকাল রানার ৪৮ ঘণ্টার বেশি অফলাইন থাকে, তবে ইমার্জেন্সি ফলব্যাক হিসেবে ক্লাউড রানারে এই অডিট রান হয়।

### ২. কনসোলিডেটেড নাইটলি অপস ও মেইনটেন্যান্স (`ops-maintenance.yml`)
* **কখন হয়:** প্রতিদিন রাত ০৩:০০ টায় (`0 3 * * *`) এবং প্রতি রবিবার রাতে (`0 3 * * 0`)।
* **হেভি রান বিষয়বস্তু:**
  - **Tier 1 (Daily):** `workflow-runs-retention`, `db-retention`, `stale-mutex` ক্লিনআপ, `rate-limit-trend`, এবং ডেটাবেস কানেকশন পুল হেলথ অডিট।
  - **Tier 2 (Weekly Sunday):** 
    - `dast-zap.yml`: ফুল DAST সিকিউরিটি পেনিট্রেশন টেস্ট।
    - `load-locust`: হাই কনকারেন্সি লোড ও স্ট্রেস টেস্ট।
    - `chaos-suite`: ক্যাওস ইঞ্জিনিয়ারিং ও ফল্ট ইনজেকশন টেস্ট।
    - `browser-e2e`: প্লে-রাইট/ব্রাউজার অটোমেশন দিয়ে এন্ড-টু-এন্ড রিয়েল ইউজার জার্নি অডিট।
    - `deep-audit`: পাইথন ডিপেন্ডেন্সির ফুল `pip-audit` ও ট্রানজিটিভ সিকিউরিটি স্ক্যান।
