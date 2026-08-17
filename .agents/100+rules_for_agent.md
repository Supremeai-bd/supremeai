বস, আপনার এই মাইন্ডসেটটাই একজন সাধারণ প্রোগ্রামারকে একজন **"Tech Lead"** বা **"Chief Architect"** থেকে আলাদা করে! নতুন ডেভেলপারদের অনবোর্ডিংয়ের জন্য একটি সলিড রুলবুক বা **"Manifesto"** থাকাটা যেকোনো এন্টারপ্রাইজ প্রজেক্টের (বিশেষ করে SupremeAI 2.0 এর মতো বিশাল প্রজেক্টের) জন্য ফরজ।

আমি SupremeAI 2.0-এর আর্কিটেকচার এবং এলিট ডেভেলপমেন্ট স্ট্যান্ডার্ডের ওপর ভিত্তি করে **"The Supreme Developer Manifesto: 100+ Golden Rules"** তৈরি করে দিলাম। এটি নতুন ডেভেলপারদের জন্য একটি "Dev Bible" হিসেবে কাজ করবে।

---

# 📜 The SupremeAI Elite Developer Manifesto

## 🏛️ সেকশন ১: Core Architecture & Mindset (১-১০)

১. **Fail-Fast, Fail-Loud:** কনফিগারেশন বা সিক্রেট মিসিং থাকলে সিস্টেম স্টার্ট হতে দেওয়া যাবে না, সাথে সাথে ক্র্যাশ করান।
২. **Zero-Touch Operations (ZTO):** যে কাজ দুবার ম্যানুয়ালি করতে হয়, তা অটোমেট করে ফেলুন।
৩. **Stateless Always:** API বা মাইক্রোসার্ভিসে কখনো স্টেট (State) সেভ করবেন না। স্টেট থাকবে শুধুমাত্র ডেটাবেস বা ক্যাশে (Redis)।
৪. **Single Source of Truth (SSOT):** একই লজিক বা ডেটা দুই জায়গায় ডিফাইন করবেন না (DRY Principle)।
৫. **YAGNI (You Aren't Gonna Need It):** ভবিষ্যতে কাজে লাগতে পারে ভেবে আজই কোনো ওভার-ইঞ্জিনিয়ার্ড ফিচার বানাবেন না।
৬. **KISS (Keep It Simple, Stupid):** যত কম কোড লিখে কাজ করা যায়, তত ভালো। কমপ্লেক্সিটি হলো মেইনটেন্যান্সের শত্রু।
৭. **Graceful Degradation:** যদি কোনো থার্ড-পার্টি API (যেমন: OpenAI) ডাউন থাকে, তবে পুরো অ্যাপ যেন ক্র্যাশ না করে, ফলব্যাক মডেলে (Gemini) শিফট করুন।
৮. **Event-Driven Over Synchronous:** ভারী কাজগুলো (Video Generation, Scraping) কখনো মেইন থ্রেডে করবেন না, Event Bus বা Task Queue তে পাঠিয়ে দিন।
৯. **Assume Network will Fail:** যেকোনো নেটওয়ার্ক কলে (API, DB) обов্যই Timeout এবং Retry (Circuit Breaker) লজিক রাখবেন।
১০. **Secure by Default:** সবকিছুকে প্রাইভেট ধরুন, যতক্ষণ না পর্যন্ত সেটি পাবলিক করার কোনো স্পেসিফিক কারণ থাকে।

## 🧹 সেকশন ২: Refactoring & Clean Code (১১-২০)

১১. **Merge First, Delete Second:** কোনো পুরোনো ফাইল বা ফাংশন ডিলিট করার আগে তার ইউনিক লজিক নতুন ফাইলে মার্জ করুন।
১২. **The Boy Scout Rule:** যে ফাইলটি ওপেন করেছেন, কাজ শেষে সেটি আগের চেয়ে একটু হলেও ক্লিন করে তারপর ক্লোজ করুন।
১৩. **No Commented-out Code:** ডেড কোড কমেন্ট করে রাখবেন না। গিট হিস্ট্রিতে সব থাকে, নির্দ্বিধায় ডিলিট করুন।
১৪. **Code Documents Itself:** ভেরিয়েবল এবং ফাংশনের নাম এত ক্লিয়ার রাখুন যেন কমেন্ট পড়ার দরকার না পড়ে।
১৫. **No Magic Numbers:** কোডের ভেতর `86400` না লিখে `SECONDS_IN_A_DAY = 86400` কনস্ট্যান্ট ব্যবহার করুন।
১৬. **Max Line Length:** এক লাইনে ১২০ ক্যারেক্টারের বেশি কোড লিখবেন না।
১৭. **Pure Functions:** ফাংশন যত ছোট এবং সাইড-ইফেক্ট মুক্ত হবে, টেস্ট করা তত সহজ হবে।
১৮. **Type Hinting is Mandatory:** Python (Pydantic) এবং React (TypeScript) এ কোনো `Any` বা টাইপলেস কোড লেখা সম্পূর্ণ নিষিদ্ধ।
১৯. **Avoid Deep Nesting:** `if-else` এর নেস্টিং ৩ লেভেলের বেশি হলে সাথে সাথে Guard Clauses (Early Return) ব্যবহার করুন।
২০. **Leave No TODOs Unassigned:** `TODO` লিখলে সাথে টিকিট নম্বর বা ইস্যু লিঙ্ক দিন, নাহলে তা ডিলিট করুন।

## 🌿 সেকশন ৩: Git & Version Control (২১-৩০)

২১. **Never Push to Main:** `main` বা `develop` ব্রাঞ্চে সরাসরি পুশ করা মহাপাপ। সব সময় PR (Pull Request) করবেন।
২২. **Conventional Commits:** কমিট মেসেজগুলো `feat:`, `fix:`, `docs:`, `refactor:` দিয়ে শুরু করুন।
২৩. **Branch Naming Standard:** `feature/auth-login`, `bugfix/redis-crash`, `hotfix/stripe-webhook` ফরম্যাট ফলো করুন।
২৪. **Small, Atomic Commits:** এক কমিটে ১০টা ফিচার পুশ করবেন না। প্রতিটি কমিট যেন একটি সিঙ্গেল লজিক্যাল চেঞ্জ হয়।
২৫. **Squash Before Merge:** অনেকগুলো ছোট ছোট "wip" কমিট থাকলে, মার্জ করার আগে স্কোয়াশ (Squash) করে ক্লিন হিস্ট্রি রাখুন।
২৬. **Pull Frequently:** কাজ শুরু করার আগে এবং পুশ করার আগে অবশ্যই মেইন ব্রাঞ্চ থেকে `pull --rebase` করে নিন।
২৭. **Don't Commit Secrets:** `.env`, API Keys, বা Password ভুলেও গিট-এ কমিট করবেন না। `.gitignore` আপডেট রাখুন।
২৮. **Delete Merged Branches:** PR মার্জ হয়ে গেলে সাথে সাথে সোর্স ব্রাঞ্চ ডিলিট করে দিন।
২৯. **Draft PRs for WIP:** কাজ শেষ না হলে Draft PR ওপেন করুন যাতে অন্যরা দেখতে পারে আপনি কী করছেন।
৩০. **Self-Review First:** কাউকে রিভিউ করতে ডাকার আগে নিজের PR নিজে একবার পুরোটা পড়ে দেখুন।

## 🤖 সেকশন ৪: CI/CD & Deployment (৩১-৪০)

৩১. **CI Must Pass:** GitHub Actions-এর সব চেক (Linting, Tests) গ্রিন না হওয়া পর্যন্ত PR মার্জ বাটন ছোঁয়া নিষেধ।
৩২. **Infrastructure as Code (IaC):** কোনো সার্ভারে ম্যানুয়ালি ঢুকে কনফিগারেশন চেঞ্জ করবেন না (যেমন: Render, Vercel)।
৩৩. **Immutable Releases:** একবার প্রোডাকশনে রিলিজ হয়ে গেলে সেই একই রিলিজ ওভাররাইট করবেন না, নতুন ভার্সন রিলিজ দিন।
৩৪. **Database Migrations in CI:** প্রোডাকশন ডেপ্লয়মেন্টের আগে CI-তে `alembic upgrade head` টেস্ট করে নিন।
৩৫. **Automated Rollback:** ডেপ্লয়মেন্টের পর হেলথ চেক ফেইল করলে যেন অটোমেটিক আগের ভার্সনে ফিরে যায়।
৩৬. **Strict Linting:** `Ruff`, `Black`, `ESLint` এর কোনো ওয়ার্নিং বাইপাস করা যাবে না।
৩৭. **Build Once, Deploy Anywhere:** কন্টেইনার ইমেজ একবার বিল্ড করে সেটাই স্ট্যাজিং এবং প্রোডাকশনে প্রমোট করুন।
৩৮. **Pre-commit Hooks:** লোকাল মেশিনে কমিট করার আগেই লিন্টার যেন কোড ফিক্স করে দেয় (Pre-commit config)।
৩৯. **Dependency Caching:** CI টাইম কমানোর জন্য Python/Node মডিউলগুলো ক্যাশ (Cache) করুন।
৪০. **Semantic Versioning:** রিলিজের ক্ষেত্রে `Major.Minor.Patch` (e.g., v2.1.4) পলিসি কঠোরভাবে মানুন।

## 🔐 সেকশন ৫: Security & Authentication (৪১-৫০)

৪১. **Zero Trust Policy:** কোনো ইউজার বা ইন্টারনাল সার্ভিসকে অন্ধভাবে বিশ্বাস করবেন না, প্রতিটি রিকোয়েস্ট ভ্যালিডেট করুন।
৪২. **Hash All Passwords:** প্লেইন টেক্সট পাসওয়ার্ড সেভ করা অপরাধ। `bcrypt` বা `Argon2` ব্যবহার করুন।
৪৩. **JWT Expiry & Rotation:** এক্সেস টোকেন শর্ট-লাইভড (১৫-৩০ মিনিট) এবং রিফ্রেশ টোকেন সিকিউরড (HttpOnly Cookie) রাখুন।
৪৪. **Sanitize Inputs:** ফ্রন্টএন্ড থেকে আসা ডেটা ব্লাইন্ডলি ডেটাবেসে ঢুকাবেন না। Pydantic/Zod দিয়ে স্কিমা ভ্যালিডেশন মাস্ট।
৪৫. **Rate Limiting Everywhere:** প্রতিটা পাবলিক API-এ IP বা User ID ভিত্তিক রেট লিমিট (Redis) থাকতে হবে।
৪৬. **CORS Strictness:** প্রোডাকশনে `*` (Wildcard) CORS সম্পূর্ণ নিষিদ্ধ। নির্দিষ্ট ডোমেইন হোয়াইটলিস্ট করুন।
৪৭. **Avoid SQL Injection:** ORM (SQLAlchemy) ব্যবহার করুন। কখনোই স্ট্রিং ফরম্যাটিং দিয়ে SQL কুয়েরি লিখবেন না।
৪৮. **Log Auditing:** কে কখন ডেটাবেস মডিফাই করছে বা অ্যাডমিন প্যানেলে ঢুকছে তার অডিট লগ রাখুন।
৪৯. **Least Privilege:** ডেটাবেস বা ক্লাউড সার্ভিসের API Key-কে শুধুমাত্র তার কাজের জন্য যতটুকু পারমিশন দরকার ততটুকুই দিন।
৫০. **Don't Log Secrets:** `print()` বা `logger` এর ভেতরে ভুলেও পাসওয়ার্ড, ক্রেডিট কার্ড বা API Key প্রিন্ট করবেন না।

## 💾 সেকশন ৬: Database & State Management (৫১-৬০)

৫১. **Migrations are Sacred:** ডেটাবেস স্কিমা কখনোই ম্যানুয়ালি চেঞ্জ করবেন না, শুধুমাত্র `Alembic` মাইগ্রেশনের মাধ্যমে করবেন।
৫২. **Index Smartly:** যেসব কলামে বেশি ফিল্টার বা সার্চ হয়, সেগুলোতে ইনডেক্স (`CREATE INDEX`) অ্যাড করুন।
৫৩. **Soft Deletes:** ইউজারের কোনো ডেটা ফিজিক্যালি ডিলিট করবেন না। `is_deleted = True` ফ্লাগ ব্যবহার করুন।
৫৪. **Use Connection Pools:** প্রতি রিকোয়েস্টে নতুন DB কানেকশন ওপেন না করে PgBouncer বা SQLAlchemy Pool ব্যবহার করুন।
৫৫. **Beware the N+1 Problem:** ORM দিয়ে ডেটা ফেস করার সময় লুপের ভেতর কুয়েরি করবেন না, `joinedload` ব্যবহার করুন।
৫৬. **Pagination is Mandatory:** লিস্ট API-তে কখনোই সব ডেটা একসাথে রিটার্ন করবেন না, Limit-Offset বা Cursor Pagination মাস্ট।
৫৭. **ACID Properties:** পেমেন্ট বা ক্রিটিকাল আপডেটের ক্ষেত্রে `Transaction` (Commit/Rollback) ব্যবহার করুন।
৫৮. **UUIDs for Public IDs:** পাবলিক API-তে কখনোই ডেটাবেসের `id=1,2,3` এক্সপোজ করবেন না, UUID (v4) ব্যবহার করুন।
৫৯. **Cache Heavy Queries:** যেসব ডেটা সহজে চেঞ্জ হয় না (যেমন: Pricing Plan), সেগুলো Redis-এ ক্যাশ করে রাখুন।
৬০. **Data Anonymization:** ডেভেলপার বা থার্ড-পার্টিকে ডেটাবেস ডাম্প দেওয়ার আগে ইউজারের পার্সোনাল ডেটা মাস্ক করে নিন।

## 🧪 সেকশন ৭: Testing & QA (৬১-৭০)

৬১. **Test the Happy & Sad Paths:** শুধু সাকসেস কেস নয়, এরর বা ফেইলর কেসগুলোও টেস্ট করুন।
৬২. **No UI Dependencies in Backend Tests:** ব্যাকএন্ড টেস্ট করার জন্য ফ্রন্টএন্ডের দরকার নেই (Mock API Client)।
৬৩. **80% Coverage Rule:** ক্রিটিকাল লজিকের (Payment, Auth, AI routing) কভারেজ ১০০% এবং ওভারঅল ৮০% রাখতে হবে।
৬৪. **Don't Test External APIs:** Stripe বা OpenAI-এর রিয়েল API-তে হিট করবেন না, `unittest.mock` বা `responses` দিয়ে মক করুন।
৬৫. **Flaky Tests are Bugs:** যদি কোনো টেস্ট মাঝে মাঝে পাস করে আর মাঝে মাঝে ফেইল করে, তবে তা ইমিডিয়েটলি ফিক্স করুন।
৬৬. **Test Boundaries:** 0, Null, Negative values, এবং Max Length দিয়ে সিস্টেমের লিমিট টেস্ট করুন।
৬৭. **Given-When-Then Structure:** টেস্ট লেখার সময় Setup (Given), Action (When), এবং Assert (Then) প্যাটার্ন ফলো করুন।
৬৮. **Keep Tests Fast:** স্লো টেস্ট ডেভেলপারদের প্রোডাক্টিভিটি নষ্ট করে। Database I/O কমান।
৬৯. **API Contract Testing:** ফ্রন্টএন্ড এবং ব্যাকএন্ডের ডেটা মডেল যেন মিসম্যাচ না হয় তা নিশ্চিত করুন (OpenAPI Spec)।
৭০. **Automated E2E Tests:** ইউজার লগইন থেকে শুরু করে পেমেন্ট পর্যন্ত ফ্লো Playwright বা Cypress দিয়ে অটোমেট করুন।

## 📡 সেকশন ৮: API & Network Design (৭১-৮০)

৭১. **RESTful Naming:** URL-এ ভার্ব ইউজ করবেন না (`/get-users` ❌ -> `GET /users` ✅)।
৭২. **API Versioning:** সব সময় রুট URL-এ ভার্সন রাখুন (যেমন: `/api/v1/users`), যাতে ভবিষ্যতে ব্রেকিং চেঞ্জ ম্যানেজ করা যায়।
৭৩. **Standard Status Codes:** সঠিক HTTP কোড দিন (200 OK, 201 Created, 400 Bad Request, 401 Unauth, 404 Not Found, 500 Server Error)।
৭৪. **Meaningful Error Messages:** 500 Error দিলে ইউজারকে ডিটেইলস না দেখিয়ে "Internal Server Error" দিন, কিন্তু 400 এর ক্ষেত্রে স্পেসিফিক ফিল্ডের ভুল ধরিয়ে দিন।
৭৫. **Use Async Everywhere (FastAPI):** I/O বাউন্ড টাস্কে (DB, Network) `def` এর বদলে `async def` এবং `await` ব্যবহার করুন।
৭৬. **Dependency Injection:** FastAPI-তে ডেটাবেস সেশন বা অথেন্টিকেশন ভেরিফাই করার জন্য `Depends()` ব্যবহার করুন।
৭৭. **Idempotent APIs:** `PUT` বা `DELETE` রিকোয়েস্ট একাধিকবার করলেও যেন স্টেট সেম থাকে।
৭৮. **Payload Size Limits:** বিশাল বড় ফাইল বা JSON বডি ব্লক করতে Max Size রুল সেট করুন।
৭৯. **Always Return JSON:** API রেসপন্স যেন কখনোই প্লেইন টেক্সট বা HTML না হয়।
৮০. **Document While Coding:** কোড লেখার সাথেই `docstrings` এবং Pydantic Field Description দিন, যা থেকে Swagger/OpenAPI অটো জেনারেট হবে।

## 🎯 সেকশন ৯: Error Handling & Observability (৮১-৯০)

৮১. **Don't Swallow Exceptions:** `except Exception: pass` লেখা ডেভেলপারদের জন্য সবচেয়ে বড় অপরাধ।
৮২. **Catch Specific Exceptions:** জেনেরিক `Exception` না ধরে `KeyError`, `TimeoutError` বা `ValueError` স্পেসিফিকভাবে ধরুন।
৮৩. **Centralized Error Handling:** গ্লোবাল এক্সেপশন হ্যান্ডলার (FastAPI Middleware) ব্যবহার করুন।
৮৪. **Structured JSON Logging:** লগে শুধু টেক্সট না রেখে `{ "user_id": 123, "event": "login_failed" }` ফরম্যাটে JSON লগিং করুন।
৮৫. **Correlation IDs:** ফ্রন্টএন্ড রিকোয়েস্ট থেকে শুরু করে মাইক্রোসার্ভিস পর্যন্ত ট্র্যাক করার জন্য প্রতিটি রিকোয়েস্টে একটি ইউনিক `X-Request-ID` যুক্ত করুন।
৮৬. **Alert on Critical Only:** ছোটখাটো ওয়ার্নিংয়ের জন্য Discord/Slack-এ অ্যালার্ট পাঠাবেন না (Alert Fatigue)।
৮৭. **Use Sentry/Datadog:** স্ট্যাকট্রেস ট্র্যাক করার জন্য থার্ড-পার্টি অবজাভিবিলিটি টুল মাস্ট।
৮৮. **Context is King:** লগ মেসেজের সাথে কন্টেক্সট দিন (যেমন: কোন মডেলে, কোন ইউজারের জন্য এরর হয়েছে)।
৮৯. **Health Checks:** `/health` এন্ডপয়েন্ট শুধু API আপ আছে কিনা তা নয়, বরং DB এবং Redis কানেকশনও আপ আছে কিনা তা চেক করবে।
৯০. **Always Close Resources:** File, Network Socket, বা DB Connection ওপেন করলে ফাইনালি ব্লকে বা Context Manager (`with` block) দিয়ে তা ক্লোজ করুন।

## 🧠 সেকশন ১০: AI & Prompt Engineering Specifics (৯১-১০০)

৯১. **System Prompts are Sacred:** সিস্টেম প্রম্পটের ভেতর রুলস হার্ডকোড করুন এবং একে ইনজেকশন থেকে সুরক্ষিত রাখুন।
৯২. **Temperature Tuning:** ক্রিয়েটিভ কাজের জন্য Temperature বেশি (0.7-1.0) এবং ডেটা এক্সট্রাকশনের জন্য কম (0.0-0.2) রাখুন।
৯৩. **Token Limitations:** LLM-এ পাঠানোর আগে প্রম্পটের টোকেন কাউন্ট চেক করুন (`tiktoken`), যাতে লিমিট ক্রস না করে।
৯৪. **Semantic Caching:** একই প্রশ্ন বারবার আসলে LLM-কে কল না করে Vector DB থেকে ক্যাশড রেজাল্ট রিটার্ন করুন।
৯৫. **Guard against Prompt Injection:** ইউজারের ইনপুট সরাসরি সিস্টেম প্রম্পটের সাথে মেলাবেন না। স্পেশাল ডিলিমিটার (`"""` বা `<user_input>`) ব্যবহার করুন।
৯৬. **Fallback Mechanisms:** একটি AI মডেল ফেইল করলে (Rate limit), অটোমেটিকভাবে অন্য প্রোভাইডারে রিকোয়েস্ট রাউট করুন (LiteLLM Router)।
৯৭. **Stream Responses:** চ্যাট ইন্টারফেসে পুরো রেজাল্ট জেনারেট হওয়ার জন্য ওয়েট না করে `Streaming Response` ব্যবহার করুন (UX এর জন্য)।
৯৮. **Structured Outputs:** AI থেকে ডেটা রিটার্ন পাওয়ার জন্য সব সময় `JSON Mode` বা Function Calling (Tool use) ব্যবহার করুন।
৯৯. **Cost Tracking per Request:** প্রতিটি AI কলের টোকেন ইউজ এবং কস্ট ক্যালকুলেট করে ডেটাবেসে অডিট লগ রাখুন।
১০০. **Continuous Evaluation:** প্রম্পট বা মডেলে কোনো চেঞ্জ আনলে, "LLM Evaluator" দিয়ে রিগ্রেশন টেস্ট করুন।

---

> **"Perfection is achieved, not when there is nothing more to add, but when there is nothing left to take away."**
> *Welcome to the SupremeAI Elite Team. Code smart, build fast, and automate everything.*

---

বস, এই ১০০টি রুল একটি প্রজেক্টের রুট ডিরেক্টরিতে `DEVELOPER_GUIDELINES.md` হিসেবে রাখলে যেকোনো নতুন ডেভেলপার প্রজেক্টে এসেই বুঝবে তারা একটি ওয়ার্ল্ড-ক্লাস এন্টারপ্রাইজ টিমে কাজ করছে। আপনার কি মনে হয় কোনো নির্দিষ্ট সেকশনে আরও কিছু স্পেসিফিক রুল যোগ করার প্রয়োজন আছে? 🛠️🚀🎖️


১. 🤖 এজেন্টদের জন্য "Golden Rules" (এজেন্টরা যা সবসময় চেক করবে)
এজেন্টরা যখন কাজ করবে, আপনার তৈরি সেই AI Sentinel তাদের এই লজিকগুলো দিয়ে মনিটর করবে:

Context Token Budget (রুল ১০১): কোনো এজেন্ট তার প্রম্পট বা কনটেক্সট উইন্ডোর ৮০% এর বেশি ব্যবহার করতে পারবে না। করলে সে সাথে সাথে তার মেমোরি Vector DB-তে আর্কাইভ করবে।

Action Verifiability (রুল ১০২): কোনো এজেন্ট কোনো সেনসিটিভ অ্যাকশন (যেমন: ইমেইল পাঠানো, কোড পুশ করা) নেওয়ার আগে অবশ্যই একটি human-in-the-loop কনফার্মেশন চাইবে।

Fail-Safe Memory (রুল ১০৩): এজেন্ট তার পূর্বের ভুল থেকে শেখার জন্য একটি Correction Log মেনটেইন করবে। আগের ভুল করা লজিক সে দ্বিতীয়বার ট্রাই করবে না।

Zero-Hallucination Policy (রুল ১০৪): এজেন্ট যদি কোনো তথ্যের ব্যাপারে ১০০% শিওর না হয়, তবে সে সেটি ইনভেন্ট করবে না। বরং বলবে: "I need to perform a search or query the memory to be sure."

Scope Isolation (রুল ১০৫): একটি এজেন্ট তার ডোমেইন (যেমন: পেমেন্ট এজেন্ট) ছেড়ে অন্য ডোমেইনে (যেমন: কোড এক্সিকিউশন) নাক গলাবে না।

২. 🛠️ ইউজারদের জন্য "End-to-End Life-Cycle" গাইডলাইন
ইউজার বা নতুন ডেভেলপাররা যেন পুরো প্রোজেক্টে পথ না হারায়, সেজন্য তাদের জন্য এই ৫টি স্টেজ মেনটেইন করা মাস্ট:

স্টেজ ১: Onboarding & Sandbox (শুরু)
গাইডলাইন: নতুন কোড বা ফিচার যোগ করার আগে অবশ্যই strix বা pydantic দিয়ে স্কিমা ডিফাইন করতে হবে।

কাজ: নতুন ফিচার সব সময় feature/* ব্রাঞ্চে হবে। কোনো কিছুই মেইন ব্রাঞ্চে সরাসরি যাবে না।

স্টেজ ২: Contract-Driven Development (ডেভেলপমেন্ট)
গাইডলাইন: কোড লেখার আগে API এন্ডপয়েন্ট বা এজেন্টের ইন্টারফেস ডিজাইন করুন।

কাজ: FastAPI-এর Swagger (OpenAPI) জেনারেট হচ্ছে কি না তা চেক করুন। ইন্টারফেস কনট্রাক্ট না মিললে CI বিল্ড ফেল করবে।

স্টেজ ৩: Automated Validation (যাচাইকরণ)
গাইডলাইন: Supreme Sentinel এজেন্টের ওয়ার্নিংগুলোকে "পরামর্শ" হিসেবে নয়, বরং "নির্দেশ" হিসেবে নেবেন।

কাজ: PR ওপেন করার পর এজেন্ট যদি কোনো রুল ব্রেক করার কথা বলে, তবে সেই ফিক্স না করা পর্যন্ত ডেভেলপার মার্জ করতে পারবে না।

স্টেজ ৪: Deployment & Health Observability (ডিপ্লয়মেন্ট)
গাইডলাইন: ডিপ্লয়মেন্টের পর আমাদের API Health & Route Coverage রিপোর্ট দেখুন।

কাজ: যদি আপনার এন্ডপয়েন্ট রিপোর্টে Yellow বা Red সিগন্যাল দেখায়, তবে পরবর্তী ফিচার তৈরির আগে সেই পুরনো ডেট চেক ঠিক করতে হবে।

স্টেজ ৫: Feedback & Evolution (পরিপক্কতা)
গাইডলাইন: সিস্টেমের প্রতিটি এরর বা ফেইলরকে "লার্নিং অপরচুনিটি" হিসেবে দেখুন।

কাজ: কোনো এরর হলে সেটি অটোমেটিক incident_report হিসেবে জমা হচ্ছে কি না দেখুন। প্রতি সপ্তাহে এই রিপোর্টগুলো দেখে সিস্টেমের ইভলুশন ইঞ্জিনে নতুন রুলস ইনজেক্ট করতে হবে।

💡 বস, আমার পরামর্শ:
এই রুলগুলো আপনি একটি "Agentic Knowledge Graph" হিসেবে রাখতে পারেন। অর্থাৎ, আপনার এজেন্টরা যখন কাজ করবে, তারা তাদের নিজস্ব প্রোমপ্ট ইঞ্জিনে এই নলেজ গ্রাফের রেফারেন্স রাখবে।

আপনার জন্য একটা কিলার আইডিয়া:
আমরা কি একটি agent_rules.json ফাইল তৈরি করব? যেখানে এই রুলগুলো থাকবে। এজেন্টরা কাজ করার আগে এই JSON ফাইলটি পড়ে নেবে (System Prompt এর অংশ হিসেবে)। এতে করে কোনো এজেন্ট যদি রুল ব্রেক করে, তবে সে নিজেই বুঝতে পারবে—"আমি আমার JSON রুলবুকের রুল #১০৪ ব্রেক করেছি!"

এটি কি আপনার এজেন্টের সেলফ-করেকশন লজিককে অনেক বেশি শক্তিশালী করবে না? 🛠️🚀🎖️
