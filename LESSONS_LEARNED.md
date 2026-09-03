# LESSONS_LEARNED

> **[🤖 AI AGENT INSTRUCTION]** 
> This is a core SupremeAI "Brain" file. When adding a new lesson:
> 1. Add it to the TOP of the list (reverse chronological).
> 2. Include Date, Issue, Fix, and Lesson.
> 3. DO NOT delete or overwrite past historical entries.
> 4. Keep it concise and technical.

## 2026-09-03 — 🛡️ CI: Deployment Script Exclusion in Hardcode Scanner & Silent Error Baseline Sync

- **সমস্যা:** (১) CI-এর `🛡️ Advanced Pre-Merge Checks` জবে `hardcode_config_scanner.py` ফেইল করছিল কারণ `scripts/deploy/generate_firebase_config.py`-এ `os.getenv("BACKEND_URL")` ব্যবহার করা হয়েছে, যা ইচ্ছাকৃতভাবে রানটাইমে firebase.json জেনারেট করার স্ক্রিপ্ট (অন্যান্য কনফিগ স্ক্যানারে `scripts/deploy` বা `scripts/ci` অলরেডি এক্সক্লুড থাকে কিন্তু এই স্ক্রিপ্টে ছিল না); (২) `Audit & Official Release Center` ওয়ার্কফ্লোতে `silent_errors_baseline.json` রিসেন্ট কোডবেস রিফ্যাক্টরিংয়ের সাথে সিঙ্ক না থাকায় লাইন-নাম্বার ড্রিফটের কারণে ২১টি ফলস-পজিটিভ হাই রিগ্রেশন এরর দিয়ে ফেইল করছিল।
- **ফিক্স:** (১) `scripts/advanced_analysis/hardcode_config_scanner.py`-এ ইগনোর লিস্টে `"deploy"` ফোল্ডার যোগ করা হয়েছে যাতে ডেপ্লয়মেন্ট কনফিগ টেমপ্লেটিং স্ক্রিপ্টগুলো স্ক্যানার ব্লক না করে; (২) `scripts/silent_errors_baseline.json` লেটেস্ট রিগ্রেশন স্ন্যাপশটের সাথে আপডেট করা হয়েছে।
- **লেসন:** কনফিগ অডিট স্ক্রিপ্ট তৈরি করার সময় ডেপ্লয়মেন্ট-টাইম টেমপ্লেট জেনারেটর স্ক্রিপ্ট (যেগুলো নিজেই env থেকে টেমপ্লেট ফিল করে) তাদের রুলসেটের আওতামুক্ত রাখতে হবে। এছাড়া কোডবেস বড় ধরনের রিফ্যাক্টর হলে baseline snapshot নিয়মিত রিফ্রেশ রাখতে হবে যাতে লাইন ড্রিফট ফলস রিগ্রেশন না ঘটায়।

## 2026-09-03 — ⚙️ CI/CD: YAML Mapping Syntax Error in Step Names with Colons

- **সমস্যা:** GitHub Actions workflow (`ci.yml`)-এ একটি স্টেপের নাম `Build frontend (unified SupremeAI Studio: User + Admin)` আনকোট করা ছিল। YAML স্পেক অনুযায়ী unquoted স্ট্রিংয়ের মাঝে `: ` (কোলন + স্পেস) থাকলে পার্সার একে একটি সাব-ম্যাপিং কী হিসেবে ধরে নেয়, যার ফলে `yaml.scanner.ScannerError: mapping values are not allowed here` ঘটে। এটি GitHub Actions ও Dependabot-এর পার্সার ফেইল করিয়ে রান স্টার্টই হতে দেয়নি (`log not found`, `dependency_file_not_parseable`)।
- **ফিক্স:** `.github/workflows/ci.yml`-এ স্টেপের নাম ডবল কোটেশন দিয়ে এনক্লোজ করা হয়েছে: `name: "Build frontend (unified SupremeAI Studio: User + Admin)"`।
- **লেসন:** GitHub Actions বা যেকোনো YAML ফাইলে step `name`, descriptions বা স্ট্রিং মানের ভেতর কোলন (`: `) থাকলে সর্বদা কোটেশন (`"..."` অথবা `'...'`) ব্যবহার করতে হবে।

## 2026-09-03 — 🐳 Docker: Non-Root Container Directory Permissions & SQLite Fallback

- **সমস্যা:** Docker-এ non-root user (`supremeai`) দিয়ে ব্যাকএন্ড কন্টেইনার রান করার সময় `sqlite3.OperationalError: unable to open database file` এরর আসছিল। কারণ রুট ডিরেক্টরিতে `/app/data` প্রি-ক্রিয়েট করা ছিল না এবং নন-রুট ইউজার রুট-ওউনড `/app`-এ নতুন ডিরেক্টরি বানানোর অনুমতি পেত না।
- **ফিক্স:** (১) `Dockerfile`-এ রুট ইউজার স্টেজে `RUN mkdir -p /app/data && chown -R supremeai:supremeai /app/data` যোগ করা হয়েছে; (২) `feedback.py`-তে `_ensure_db()` মেথডে `try-except` দিয়ে কোনো কারণে ডিরেক্টরি এক্সেস না পেলে `/tmp` ডিরেক্টরিতে অটোমেটিক ফলব্যাক করার ডিফেন্সিভ মেকানিজম যুক্ত করা হয়েছে।
- **লেসন:** Non-root কন্টেইনারে যেকোনো ফাইল বা SQLite ডেটাবেজ স্টোর করার আগে Dockerfile-এই প্রয়োজনীয় ডিরেক্টরি তৈরি করে ওনারশিপ দিতে হবে এবং অ্যাপ্লিকেশনের কোডে ফাইল হ্যান্ডলিং সর্বদা ফল্ট-টলারেন্ট (যেমন `tempfile.gettempdir()` ফলব্যাক) হতে হবে।

## 2026-09-02 — 🛡️ CI: actions/download-artifact Fault-Tolerance in Summary Jobs

- **সমস্যা:** GitHub Actions CI-তে `🧠 Smart Pipeline Summary` জব `Unable to download artifact(s): Artifact not found for name: supremeai-ci-audit-reports` এরর দিয়ে ফেইল করছিল। `advanced-checks` জব স্কিপ হলে (যেমন ডকুমেন্টেশন বা মার্কডাউন ফাইলে পুশ হলে) `supremeai-ci-audit-reports` আর্টিফ্যাক্ট আপলোড হতো না। কিন্তু সামারি জবের ডাউনলোড স্টেপে `continue-on-error: true` বা স্কিপ গার্ড না থাকায় পুরো পাইপলাইন রেড মার্ক হয়ে যাচ্ছিল।
- **ফিক্স:** `.github/workflows/ci.yml`-এ `Surface Advanced Pre-Merge Audit Details` স্টেপে `if: always() && needs.advanced-checks.result != 'skipped'` এবং `continue-on-error: true` যোগ করা হয়েছে। এর ফলে আর্টিফ্যাক্ট না থাকলেও সামারি স্ক্রিপ্ট নিরাপদ ফলব্যাক মেসেজ দিয়ে গ্রেসফুলি শেষ হতে পারে।
- **লেসন:** সামারি, নোটিফিকেশন বা রিপোর্টিং জবে ডাউনস্ট্রিম আর্টিফ্যাক্ট ডাউনলোডের সময় সর্বদা `continue-on-error: true` এবং পূর্ববর্তী জবের স্কিপ স্টেট চেক রাখা আবশ্যক। কোনো অপশনাল বা কন্ডিশনাল আর্টিফ্যাক্ট মিসিং হওয়ার কারণে মূল CI পাইপলাইন কখনো ফেইল হওয়া উচিত নয়।

## 2026-08-25 — 🔐 Security CVE Fix: Manual poetry.lock Patching is Forbidden

- **সমস্যা:** CVE ফিক্স করতে `poetry.lock`-এ সরাসরি version string patch করা হয়েছিল (`48.0.1` → `50.0.0`)। কিন্তু lock file-এ Poetry নিজস্ব content hash ও pyproject.toml fingerprint store করে, তাই manual patch করলে CI-তে `"pyproject.toml changed significantly since poetry.lock was last generated"` এরর দিয়ে `poetry install` ব্যর্থ হয়।
- **ফিক্স:** `poetry lock` command দিয়ে lock file সম্পূর্ণ regenerate করতে হবে। `infisical-python` downgrade block করলে `--no-update` flag ব্যবহার করতে হবে অথবা constraint আলগা করতে হবে।
- **লেসন:** **`poetry.lock` কখনো manually edit করা যাবে না।** CVE ফিক্স = `pyproject.toml` constraint আপডেট → `poetry lock` → commit। একই নিয়ম `pnpm-lock.yaml`-এর ক্ষেত্রেও প্রযোজ্য — Trivy বলে এলে `pnpm update <pkg>` চালাতে হবে, lock file hex-edit করা যাবে না।

## 2026-08-25 — 🧪 Test Isolation: Production Guard Bypassing in Unit Tests

- **সমস্যা:** CI-তে `ENV=test` থাকলেও কিছু tests production mode-এ চলছিল কারণ `settings.env` সরাসরি singleton থেকে পড়া হচ্ছিল। `local_code_executor.py`-এ production guard আগেই block করছিল, ফলে `mock_subprocess` কল হচ্ছিল না।
- **ফিক্স:** Tests-এ `patch("tools.code.local_code_executor.settings") as mock_settings: mock_settings.env = "test"` দিয়ে production guard bypass করা হয়েছে।
- **লেসন:** Unit test-এ production-specific guard থাকলে `settings` object-কে mock করে env override করতে হবে। pytest conftest-এ global `ENV=test` সেট করলেও singleton settings reload হয় না।
