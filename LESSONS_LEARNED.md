# LESSONS_LEARNED

> **[🤖 AI AGENT INSTRUCTION]** 
> This is a core SupremeAI "Brain" file. When adding a new lesson:
> 1. Add it to the TOP of the list (reverse chronological).
> 2. Include Date, Issue, Fix, and Lesson.
> 3. DO NOT delete or overwrite past historical entries.
> 4. Keep it concise and technical.

## 2026-09-05 — ⚡ Async Resilience & Realtime Guardrails: Task Death Prevention & Exponential Backoff Supervisor

- **সমস্যা:** (১) পাইথনে `asyncio.create_task()` আনট্র্যাকড থাকলে এক্সেপশন সাইলেন্টলি কনসোলে ড্রপ হতে পারত অথবা টাস্ক মরে গিয়ে ইউজার ব্রডকাস্ট/মেমোরি সেভিং চিরতরে বন্ধ হয়ে যেত; (২) WebSocket Redis PubSub লিসেনার নেটওয়ার্ক বা কানেকশন ত্রুটিতে ক্র্যাশ করলে বা টাইট লুপে পড়লে সিপিইউ স্পাইক ও লুপ ট্র্যাপ ঘটত; (৩) ফ্রন্টএন্ডে WebSocket মেসেজ রিসিভ করার সময় আনগার্ডেড `JSON.parse` থাকার কারণে করাপ্টেড বা নন-JSON মেসেজে পুরো ইউআই কম্পোনেন্ট আনমাউন্ট হতো।
- **ফিক্স:** (১) `backend/core/utils/background_tasks.py`-তে `track_task` এবং `safe_create_task` উন্নত করে অটোমেটিক ডান-কলব্যাক (`_task_done_callback`) এবং এক্সেপশন লগিং যুক্ত করা হয়েছে; (২) `websocket_agent.py` ও `session_stream.py`-তে এক্সপোনেনশিয়াল ব্যাকঅফ (১s → ২s → ৪s, সর্বোচ্চ ৩০s ক্যাপ) সহ সুপারভাইজড রিট্রাই যুক্ত করা হয়েছে; (৩) ফ্রন্টএন্ডে `CostDashboard.tsx` এবং `ScreencastViewer.tsx`-এ `try/catch` গার্ড দিয়ে আনহ্যান্ডেলড পার্সিং এক্সেপশন প্রতিরোধ করা হয়েছে।
- **লেসন:** ব্যাকগ্রাউন্ড অ্যাসিনক্রোনাস কাজে ফায়ার-অ্যান্ড-ফরগেট প্যাটার্ন বিপজ্জনক; প্রতিটি ব্যাকগ্রাউন্ড টাস্ক অবশ্যই রেফারেন্স-ট্র্যাকড এবং ডান-কলব্যাক দ্বারা সংরক্ষিত থাকতে হবে। রিয়েলটাইম লিসেনারে কোনো নেটওয়ার্ক ফেইলিওরে কখনো সাথে সাথে পুনরায় কল না করে এক্সপোনেনশিয়াল ব্যাকঅফ বাধ্যতামূলক।

## 2026-09-05 — 🧪 Test Diagnostics & Router Hardening: JUnit Parser Inaccuracy & FastAPI Subrouter Prefix Double-Nesting

- **সমস্যা:** (১) `scripts/ci/build_test_failure_trend.py` Pytest এর JUnit XML আউটপুট পার্স করার সময় `suite.get("passed", 0)` রিড করত, কিন্তু Pytest XML আউটপুটে কোনো `passed` অ্যাট্রিবিউট থাকে না (কেবল `tests`, `failures`, `errors`, `skipped` থাকে)—ফলে শতভাগ টেস্ট পাস করলেও রিপোর্টে `passed: 0` প্রদর্শিত হতো; (২) `backend/api/routes/commandcenter/` সাব-রাউটারগুলোতে একই `/admin-api/commandcenter` প্রিফিক্স প্যারেন্ট ও চাইল্ড উভয় স্থানে হার্ডকোড থাকায় FastAPI ডাবল-নেস্টিং তৈরি করছিল (`/admin-api/commandcenter/admin-api/commandcenter/overview`), ফলে টেস্ট ও ক্লায়েন্ট কলে 404 আসত।
- **ফিক্স:** (১) JUnit পার্সার লজিকে `passed = max(0, total - failures - errors - skipped)` ক্যালকুলেশন প্রয়োগ করা হয়েছে; (২) সব commandcenter সাব-রাউটারে `prefix=""` সেট করে প্যারেন্ট মাউন্টিংয়ে একক প্রিফিক্স `/admin-api/commandcenter` কার্যকর করা হয়েছে।
- **লেসন:** টেস্টিং ও রিপোর্টিং টুলে বিভিন্ন ফ্রেমওয়ার্কের (Pytest, JUnit, Jest) XML স্কিমার পার্থক্য যাচাই করে ডেটা এক্সট্র্যাক্ট করতে হবে। সাব-রাউটার ডিজাইনে প্রিফিক্স কখনো চাইল্ড ও প্যারেন্ট উভয় জায়গায় ডুপ্লিকেট করা যাবে না।

## 2026-09-03 — 🛡️ Zero-Cost Protection: Render 4-Node Build Budget Guard (450m Cap Enforcement)

- **সমস্যা:** রেন্ডার ফ্রি-টিয়ারে প্রতি অ্যাকাউন্টে প্রতি মাসে ৫০০ বিল্ড মিনিট বরাদ্দ থাকে। ঘন ঘন পুশ বা ডকার বিল্ডের কারণে কোনো অ্যাকাউন্টের কোটা শেষ হয়ে গেলে অ্যাকাউন্ট ব্যান বা পেইড ওভারএজ চার্জ হওয়ার ঝুঁকি ছিল।
- **ফিক্স:** (১) `scripts/ci/render_build_budget_guard.py` তৈরি করা হয়েছে যা ৪টি রেন্ডার নোডের বর্তমান ক্যালেন্ডার মাসের মোট ব্যবহৃত বিল্ড মিনিট ক্যালকুলেট করে; (২) ব্যবহার ৪৫০ মিনিট বা তার বেশি হলেই স্বয়ংক্রিয়ভাবে রেন্ডার REST API কল করে সংশ্লিষ্ট সার্ভিসের `autoDeploy: no` করে দেয়; (৩) ক্যালেন্ডার মাস রিসেট হলে বা কোটা সেফ জোনে থাকলে স্বয়ংক্রিয়ভাবে `autoDeploy: yes` রিস্টোর করে; (৪) `.github/workflows/ci.yml`-এ `render-budget-guard` প্রি-ডিপ্লয় গেট জব হিসেবে যুক্ত করা হয়েছে।
- **লেসন:** ফ্রি-টিয়ার ইনফ্রাস্ট্রাকচারে অটো-বিল্ড সুবিধা নেওয়ার সময় অবশ্যই একটি স্বয়ংক্রিয় বাজেট গার্ড থাকতে হবে, যাতে বিল্ড টাইমের সীমা শেষ হওয়ার আগেই সিস্টেম নিজে সেফটি ব্রেক ট্রিগার করে।

## 2026-09-03 — 🌐 Render 4-Microservice Discovery, MCP Tower Awakening & Cloudflare Edge Keepalive Consolidation

- **সমস্যা:** (১) লোকাল `.env` ফাইলে ৪ নম্বর Render অ্যাকাউন্টের চাবি (`RENDER_API_KEY_4`) এবং `RENDER_MCP_SVC_ID` অনুপস্থিত থাকায় MCP Control Tower ক্লাউড নোড অফলাইন মনে হচ্ছিল; (২) Cloudflare Worker (`cloudflare_worker.js` ও `wrangler.toml`)-এ কেবল ৩টি ব্যাকএন্ড কনফিগার করা ছিল—ফলে ৪র্থ নোড `supremeai-mcp-tower` ক্রন পিং না পাওয়ায় রেন্ডারের ফ্রি-টিয়ার ১৫ মিনিটের ইনঅ্যাক্টিভ কোল্ড স্লিপে চলে যাচ্ছিল।
- **ফিক্স:** (১) Infisical প্রোডাকশন ভল্ট থেকে `RENDER_API_KEY_4` (`rnd_jiat...7Hjk`) ও সার্ভিস আইডি ফেচ করে রুট ও কন্ট্রোল-প্লেন `.env`-এ সিনক্রোনাইজ করা হয়েছে; (২) `infrastructure/cloudflare_worker.js`-এ `MCP_URL` (`render-mcp`, health: `/health`) যুক্ত করে ৪টি নোডের ২৪/৭ এজিং ও রাউটিং কনফিগার করা হয়েছে; (৩) `wrangler.toml`-এ `MCP_URL` যুক্ত করে Cloudflare Edge-এ সফলভাবে ডিপ্লয় করা হয়েছে (`https://supremeai-worker.paykaribazaronline.workers.dev`, cron: `*/8 * * * *`)।
- **লেসন:** মাল্টি-অ্যাকাউন্ট ফ্রি-টিয়ার আর্কিটেকচারে প্রতিটা নোডের ডেডিকেটেড ক্রন পিং পাথ থাকা আবশ্যক। সিক্রেট কি কেবল ভল্টে রাখলেই হবে না, লোকাল কনফিগারেশন ও এজ রাউটারে একই সাথে সিঙ্ক রাখতে হবে যাতে কোনো নোড কোল্ড স্লিপে না যায়।
