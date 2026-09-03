# LESSONS_LEARNED

> **[🤖 AI AGENT INSTRUCTION]** 
> This is a core SupremeAI "Brain" file. When adding a new lesson:
> 1. Add it to the TOP of the list (reverse chronological).
> 2. Include Date, Issue, Fix, and Lesson.
> 3. DO NOT delete or overwrite past historical entries.
> 4. Keep it concise and technical.

## 2026-09-03 — 🛡️ CI & API Security: CI Truthfulness, Startup Semantics & Approval Error Sanitization

- **সমস্যা:** (১) CI পাইপলাইনে `main.py` টেস্ট সার্ভার বুট করার সময় `ENV: production` কিন্তু নিচে SQLite pooler (`sqlite+aiosqlite`) ব্যবহার করা হচ্ছিল এবং শুধুমাত্র `/live` প্রোব চেক করা হচ্ছিল (রেডিনেস প্রোব বাদ থাকায় ডাটাবেস সত্যতা প্রমাণ হচ্ছিল না); (২) CI রানের ঠিক পূর্বে `ruff check --fix` সোর্স কোড মিউটেট করছিল; (৩) `approval_manager.py`-তে ইন্টারনাল ডাটাবেস/সিস্টেম এরর স্ট্রিং (`str(exc)`) ক্লায়েন্টকে রিটার্ন করা হচ্ছিল যা ডেটাবেস স্কিমা বা সেনসিটিভ তথ্য লিক করার ঝুঁকিতে ফেলেছিল; (৪) `config_validator.py`-তে `local` ও `test` এনভায়রনমেন্ট মিসিং থাকায় ওয়ার্নিং জেনারেট হচ্ছিল এবং ভ্যালিডেশন এররে রিয়াল সিক্রেট প্রিন্ট হওয়ার ঝুঁকি ছিল।
- **ফিক্স:** (১) `.github/workflows/ci.yml`-এ টেস্ট বুটে `ENV: test` এবং PostgreSQL pooler ব্যবহার নিশ্চিত করা হয়েছে, এবং `/api/v1/health/live` এর সাথে `/api/v1/health/ready` প্রোব যুক্ত করা হয়েছে; (২) CI থেকে অটো-ফিক্স সরিয়ে স্ট্রিক্ট ভেরিফিকেশন মোড নিশ্চিত করা হয়েছে; (৩) `approval_manager.py`-তে ক্লায়েন্ট এরর মেসেজ স্যানিটাইজ করা হয়েছে এবং শুধুমাত্র অনুমোদিত `ApprovalStateError` মেসেজ ক্লায়েন্টে পাঠিয়ে বাকি এররে জেনেরিক ফলব্যাক দেওয়া হয়েছে; (৪) `config_validator.py`-তে `allowed_values`-এ `local`/`test` যুক্ত করা হয়েছে এবং এরর লগে সেনসিটিভ টোকেন `[REDACTED]` ফিল্টার প্রয়োগ করা হয়েছে।
- **লেসন:** CI পাইপলাইনে কখনো প্রোডাকশন এনভায়রনমেন্ট ডিক্লেয়ার করে ডামি SQLite চালানো যাবে না। লাইভ প্রোবের সাথে রেডিনেস প্রোব এবং এপিআই রেসপন্সে ইন্টারনাল এক্সেপশন স্যানিটাইজেশন প্রোডাকশন ক্যান্ডিডেট সিস্টেমের অখণ্ডতার জন্য অপরিহার্য।

## 2026-09-03 — 🧹 Architecture: Dead Middleware Deletion & Broken Subsystem Imports Cleanup

- **সমস্যা:** (১) `backend/core/middleware/db_optimization_middleware.py` মডিউল-লেভেলে আনইমপ্লিমেন্টেড সাবসিস্টেম `core.database.query_optimizer` ইমপোর্ট করছিল এবং ইনস্ট্যানশিয়েট হওয়ার কারণে মডিউল লোডেই `ModuleNotFoundError` ঘটাত। (২) রিকোয়েস্টে SQL ইনজেকশন চেকের কাজ অলরেডি লাইভ `core/middleware/security.py` হ্যান্ডেল করছিল, ফলে এই ফাইলটি ডুপ্লিকেট, ডেড এবং রানটাইম ক্র্যাশ ঝুঁকি ছিল।
- **ফিক্স:** (১) অপ্রয়োজনীয় ও মৃত `db_optimization_middleware.py` ফাইলটি স্থায়ীভাবে রিমুভ করা হয়েছে। (২) `browser_routes.py`, `auto_healer.py`, এবং `self_improving_agent.py`-এর সব ব্রোকেন ও ইনভ্যালিড প্রিফিক্স ইমপোর্ট ক্যানোনিকাল পাথে রি-পয়েন্ট করা হয়েছে।
- **লেসন:** কোনো সাবসিস্টেম বা মিডলওয়্যার ডিক্লেয়ার করার সময় ফ্যান্টম ডিপেন্ডেন্সি বা আনইমপ্লিমেন্টেড মডিউলের রেফারেন্স কোডবেসে রেখে দেওয়া যাবে না। অ্যাক্টিভ মিডলওয়্যার দ্বারা কভার হওয়া ডুপ্লিকেট লজিক নিয়মিত ক্লিন করা কোডবেসের লাইটওয়েট ও রিগ্রেশন-মুক্ত আর্কিটেকচারের জন্য আবশ্যক।

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
