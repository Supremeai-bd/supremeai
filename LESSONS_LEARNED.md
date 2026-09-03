# LESSONS_LEARNED

> **[🤖 AI AGENT INSTRUCTION]** 
> This is a core SupremeAI "Brain" file. When adding a new lesson:
> 1. Add it to the TOP of the list (reverse chronological).
> 2. Include Date, Issue, Fix, and Lesson.
> 3. DO NOT delete or overwrite past historical entries.
> 4. Keep it concise and technical.

## 2026-09-03 — 🛡️ Zero-Cost Protection: Render 4-Node Build Budget Guard (450m Cap Enforcement)

- **সমস্যা:** রেন্ডার ফ্রি-টিয়ারে প্রতি অ্যাকাউন্টে প্রতি মাসে ৫০০ বিল্ড মিনিট বরাদ্দ থাকে। ঘন ঘন পুশ বা ডকার বিল্ডের কারণে কোনো অ্যাকাউন্টের কোটা শেষ হয়ে গেলে অ্যাকাউন্ট ব্যান বা পেইড ওভারএজ চার্জ হওয়ার ঝুঁকি ছিল।
- **ফিক্স:** (১) `scripts/ci/render_build_budget_guard.py` তৈরি করা হয়েছে যা ৪টি রেন্ডার নোডের বর্তমান ক্যালেন্ডার মাসের মোট ব্যবহৃত বিল্ড মিনিট ক্যালকুলেট করে; (২) ব্যবহার ৪৫০ মিনিট বা তার বেশি হলেই স্বয়ংক্রিয়ভাবে রেন্ডার REST API কল করে সংশ্লিষ্ট সার্ভিসের `autoDeploy: no` করে দেয়; (৩) ক্যালেন্ডার মাস রিসেট হলে বা কোটা সেফ জোনে থাকলে স্বয়ংক্রিয়ভাবে `autoDeploy: yes` রিস্টোর করে; (৪) `.github/workflows/ci.yml`-এ `render-budget-guard` প্রি-ডিপ্লয় গেট জব হিসেবে যুক্ত করা হয়েছে।
- **লেসন:** ফ্রি-টিয়ার ইনফ্রাস্ট্রাকচারে অটো-বিল্ড সুবিধা নেওয়ার সময় অবশ্যই একটি স্বয়ংক্রিয় বাজেট গার্ড থাকতে হবে, যাতে বিল্ড টাইমের সীমা শেষ হওয়ার আগেই সিস্টেম নিজে সেফটি ব্রেক ট্রিগার করে।

## 2026-09-03 — 🌐 Render 4-Microservice Discovery, MCP Tower Awakening & Cloudflare Edge Keepalive Consolidation

- **সমস্যা:** (১) লোকাল `.env` ফাইলে ৪ নম্বর Render অ্যাকাউন্টের চাবি (`RENDER_API_KEY_4`) এবং `RENDER_MCP_SVC_ID` অনুপস্থিত থাকায় MCP Control Tower ক্লাউড নোড অফলাইন মনে হচ্ছিল; (২) Cloudflare Worker (`cloudflare_worker.js` ও `wrangler.toml`)-এ কেবল ৩টি ব্যাকএন্ড কনফিগার করা ছিল—ফলে ৪র্থ নোড `supremeai-mcp-tower` ক্রন পিং না পাওয়ায় রেন্ডারের ফ্রি-টিয়ার ১৫ মিনিটের ইনঅ্যাক্টিভ কোল্ড স্লিপে চলে যাচ্ছিল।
- **ফিক্স:** (১) Infisical প্রোডাকশন ভল্ট থেকে `RENDER_API_KEY_4` (`rnd_jiat...7Hjk`) ও সার্ভিস আইডি ফেচ করে রুট ও কন্ট্রোল-প্লেন `.env`-এ সিনক্রোনাইজ করা হয়েছে; (২) `infrastructure/cloudflare_worker.js`-এ `MCP_URL` (`render-mcp`, health: `/health`) যুক্ত করে ৪টি নোডের ২৪/৭ এজিং ও রাউটিং কনফিগার করা হয়েছে; (৩) `wrangler.toml`-এ `MCP_URL` যুক্ত করে Cloudflare Edge-এ সফলভাবে ডিপ্লয় করা হয়েছে (`https://supremeai-worker.paykaribazaronline.workers.dev`, cron: `*/8 * * * *`)।
- **লেসন:** মাল্টি-অ্যাকাউন্ট ফ্রি-টিয়ার আর্কিটেকচারে প্রতিটা নোডের ডেডিকেটেড ক্রন পিং পাথ থাকা আবশ্যক। সিক্রেট কি কেবল ভল্টে রাখলেই হবে না, লোকাল কনফিগারেশন ও এজ রাউটারে একই সাথে সিঙ্ক রাখতে হবে যাতে কোনো নোড কোল্ড স্লিপে না যায়।

## 2026-09-03 — ⚡ Runtime & Security Hardening: Event-Loop Deadlock, Quota Protection, Spoof Proofing & Boot RSS Optimization

- **সমস্যা:** (১) `verify_token` রানিং ইভেন্ট লুপের ভেতর `future = run_coroutine_threadsafe(..., loop)` ও `future.result(5)` কল করায় প্রতি SSE চ্যাট বা WS কানেকশনে সার্ভার ৫ সেকেন্ড ডেডলক হয়ে থাকত; (২) `task_queue.py`-এর `BLPOP` ইগার লুপ দিনে ~১৭,০০০ রেডিস কমান্ড পাঠিয়ে Upstash ফ্রি কোটা (১০k/দিন) শেষ করে দিত; (৩) Stripe `payment_intent.succeeded` ওয়েবহুকে লেজার প্রি-চেক না থাকায় রিট্রাইয়ে ডাবল ক্রেডিট হওয়ার ঝুঁকি ছিল; (৪) `X-Forwarded-For.split(',')[0]` ক্লায়েন্ট স্পুফ করতে পারায় রেট লিমিট বাইপাস হচ্ছিল; (৫) `agent_breeder` ও `skill_manager`-এ টপ-লেভেল ইমপোর্টের কারণে বুট টাইমে `litellm` লোড হয়ে মেমোরি ৫১৪MB তে উঠে Render Free-Tier এ OOM ক্র্যাশ ঝুঁকি তৈরি করছিল।
- **ফিক্স:** (১) `verify_token_async` যোগ করে SSE ও WS-এ অ্যাসিঙ্ক ভেরিফিকেশন এবং সিঙ্ক কলিংয়ের জন্য ডেডিকেটেড ব্যাকগ্রাউন্ড থ্রেড লুপ কার্যকর করা হয়েছে; (২) টাস্ক কিউ ওয়ার্কারকে লেজি ও অন-ডিমান্ড করা হয়েছে (প্রথম `enqueue`-তে চালু, ৫ মিনিট অলস থাকলে স্বয়ংক্রিয় স্টপ) এবং এক্সপোনেনশিয়াল ব্যাকঅফ যোগ করা হয়েছে; (৩) Stripe ওয়েবহুকে `TransactionLedgerEntry` প্রি-চেক যোগ করে আইডেমপোটেন্সি নিশ্চিত করা হয়েছে; (৪) প্রক্সি-হপ সচেতন `utils/client_ip.py` হেল্পার যোগ করে `rate_limit`, `security`, `anti_hacking`-এ স্পুফিং রোধ করা হয়েছে; (৫) `litellm` গ্লোবাল সেটআপ এবং ইমপোর্টকে মেথড লেভেলে লেজি-লোড করে বুট RSS মেমোরি ৩৪৭MB তে নামানো হয়েছে।
- **লেসন:** রানিং ইভেন্ট লুপে একই থ্রেডে `future.result()` ডাকা মারাত্মক অ্যান্টি-প্যাটার্ন। ফ্রি-টিয়ার আর্কিটেকচারে ব্যাকগ্রাউন্ড লং-পোলিং লুপ অবশ্যই লেজি হতে হবে এবং ভারী প্যাকেজ (যেমন `litellm`) কখনোই বুট পাথে ইগারলি ইমপোর্ট করা যাবে না।

## 2026-09-03 — 🛡️ CI & API Security: CI Truthfulness, Startup Semantics & Approval Error Sanitization

- **সমস্যা:** (১) CI পাইপলাইনে `main.py` টেস্ট সার্ভার বুট করার সময় `ENV: production` কিন্তু নিচে SQLite pooler (`sqlite+aiosqlite`) ব্যবহার করা হচ্ছিল এবং শুধুমাত্র `/live` প্রোব চেক করা হচ্ছিল (রেডিনেস প্রোব বাদ থাকায় ডাটাবেস সত্যতা প্রমাণ হচ্ছিল না); (২) CI রানের ঠিক পূর্বে `ruff check --fix` সোর্স কোড মিউটেট করছিল; (৩) `approval_manager.py`-তে ইন্টারনাল ডাটাবেস/সিস্টেম এরর স্ট্রিং (`str(exc)`) ক্লায়েন্টকে রিটার্ন করা হচ্ছিল যা ডেটাবেস স্কিমা বা সেনসিটিভ তথ্য লিক করার ঝুঁকিতে ফেলেছিল; (৪) `config_validator.py`-তে `local` ও `test` এনভায়রনমেন্ট মিসিং থাকায় ওয়ার্নিং জেনারেট হচ্ছিল এবং ভ্যালিডেশন এররে রিয়াল সিক্রেট প্রিন্ট হওয়ার ঝুঁকি ছিল।
- **ফিক্স:** (১) `.github/workflows/ci.yml`-এ টেস্ট বুটে `ENV: test` এবং PostgreSQL pooler ব্যবহার নিশ্চিত করা হয়েছে, এবং `/api/v1/health/live` এর সাথে `/api/v1/health/ready` প্রোব যুক্ত করা হয়েছে; (২) CI থেকে অটো-ফিক্স সরিয়ে স্ট্রিক্ট ভেরিফিকেশন মোড নিশ্চিত করা হয়েছে; (৩) `approval_manager.py`-তে ক্লায়েন্ট এরর মেসেজ স্যানিটাইজ করা হয়েছে এবং শুধুমাত্র অনুমোদিত `ApprovalStateError` মেসেজ ক্লায়েন্টে পাঠিয়ে বাকি এররে জেনেরিক ফলব্যাক দেওয়া হয়েছে; (৪) `config_validator.py`-তে `allowed_values`-এ `local`/`test` যুক্ত করা হয়েছে এবং এরর লগে সেনসিটিভ টোকেন `[REDACTED]` ফিল্টার প্রয়োগ করা হয়েছে।
- **লেসন:** CI পাইপলাইনে কখনো প্রোডাকশন এনভায়রনমেন্ট ডিক্লেয়ার করে ডামি SQLite চালানো যাবে না। লাইভ প্রোবের সাথে রেডিনেস প্রোব এবং এপিআই রেসপন্সে ইন্টারনাল এক্সেপশন স্যানিটাইজেশন প্রোডাকশন ক্যান্ডিডেট সিস্টেমের অখণ্ডতার জন্য অপরিহার্য।
