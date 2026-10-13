# SupremeAI — Workspace & Agent Federation Operational FAQ

> **Document Type:** Canonical Architectural Q&A & Operational Truth  
> **Source Discussion:** 2026-10-13 System & Workspace Clarification  
> **Related Docs:** [`AGENT_PORTAL_AND_FEDERATION_BRIDGE.md`](./AGENT_PORTAL_AND_FEDERATION_BRIDGE.md), [`PHASE0_BOUNDARY_CLASSIFICATION.md`](./PHASE0_BOUNDARY_CLASSIFICATION.md), [`../../AGENTS.md`](../../AGENTS.md)

---

## 📌 নির্বাহী সারসংক্ষেপ (Executive Summary)

SupremeAI ইকোসিস্টেমে একাধিক রিপোজিটরি (`supremeai`, `supremeai-open`, `supremeai-core`, `supremeai-studio`, `supremeai-sdk`) থাকার কারণে লোকাল ও ভার্চুয়াল এজেন্টদের কাজের ক্ষেত্র, সোর্স অফ ট্রুথ এবং সিঙ্কের নিয়ম নিয়ে যে সমস্ত প্রশ্ন উঠেছে—এই ডকুমেন্টে প্রতিটি প্রশ্ন ও তার পরীক্ষিত টেকনিক্যাল উত্তর বিস্তারিতভাবে লিপিবদ্ধ করা হলো।

---

## ❓ প্রশ্ন ও উত্তরের সম্পূর্ণ তালিকা (Comprehensive Q&A Ledger)

### ১. `paykaribazaronline/supremeai-open`-এর AGENTS.md বা অন্য ফাইলে কী আপডেট দরকার?
- **উত্তর:** `supremeai-open`-এর `AGENTS.md` ও `AGENT_RULES.md`-এ সমস্ত পুরনো অর্গ লিঙ্ক (`SaifulHaqueNiloy`) সরিয়ে `paykaribazaronline` করা হয়েছে। রিডিং পাথে `ECOSYSTEM_MAP.md` যুক্ত করা হয়েছে এবং এন্ট্রি পয়েন্টে ব্রিজ লেনের অপারেশনাল নোট যুক্ত করা হয়েছে।

### ২. ভার্চুয়াল এজেন্টরা কি `supremeai-open` থেকে কাজ শুরু করতে পারবে? আমরাও কি লোকাল থেকে তা করব? প্রাইভেট `supremeai` জিপ করে ব্যাকআপ রেখে কেবল ওপেন রিপোতে কাজ চালানো যাবে কি?
- **উত্তর:**
  1. ভার্চুয়াল এজেন্টরা `supremeai-open`-এ fork করে বা bridge branch দিয়ে কাজ করতে পারবে।
  2. লোকাল ডিভাইস প্রাইভেট মনোলিথ জিপ করে রেখে কেবল `supremeai-open`-এ সুইচ করতে **পারবে না**। কারণ `supremeai-open`-এ মাত্র ৮টি ইন্টারফেস ফাইল রয়েছে—মূল ব্যাকএন্ড ইঞ্জিন, ডেটাবেস, টেস্ট স্যুট এবং সিআই/সিডি অটোমেশন সবই `paykaribazaronline/supremeai`-তে অবস্থিত।
  3. সমস্ত ইস্যু ওপেনে দেওয়া উচিত নয়; কেবল যে কাজগুলো বাইরের ভার্চুয়াল বট দিয়ে করাতে চান সেগুলো ওপেনে যাবে।

### ৩. এই কাজের ফ্লো কি Admin ম্যানুয়ালি করবে নাকি Agent ও Automation নিজে করবে?
- **উত্তর:** সম্পূর্ণ স্বয়ংক্রিয় (Zero-Admin Policy, ≤ 0.01% মানব হস্তক্ষেপ)। `.github/workflows/bridge-intake.yml` এবং `scripts/bridge/bridge_intake.py` রোবট স্বয়ংক্রিয়ভাবে কোড ইনটেক করে, প্রাইভেট রিপোতে পিআর তোলে, টেস্ট চালায় এবং অটো-মার্জ করে। এডমিন হস্তক্ষেপ কেবল তখনই প্রয়োজন যখন সিক্রেট ভায়োলেশন বা প্রোটেক্টেড পাথ স্পর্শ করা হয়।

### ৪. ভার্চুয়াল বা লোকাল এজেন্ট কাজ করে `supremeai-open`-এ পুশ করবে এবং ব্রিজ অটোমেটিক সঠিক রিপোতে পৌঁছে দেবে—এই হিসেব কি সঠিক?
- **উত্তর:** হ্যাঁ, ধারণাগতভাবে এটিই আমাদের ফেডারেশন আর্কিটেকচার। `bridge-work-order.yml` বা `agent-task.yml`-এ টার্গেট রিপো (`supremeai`, `supremeai-api`, `supremeai-studio`) সিলেক্ট করা থাকে এবং ব্রিজ ইন্টেক স্বয়ংক্রিয়ভাবে সেই টার্গেট রিপোতে প্যাচ পোর্ট করে।

### ৫. কোর-এ কোনো পরিবর্তন হলে মার্জ কোথায় হবে? `supremeai-core` এবং `supremeai` উভয় জায়গায় কি মার্জ হবে?
- **উত্তর:** না, মার্জ হবে একটিমাত্র জায়গায়—**`paykaribazaronline/supremeai`**-তে। কারণ বর্তমান আর্কিটেকচারে `paykaribazaronline/supremeai` মনোলিথই হলো সক্রিয় কোর। আলাদা করে ডুপ্লিকেট মার্জ করার কোনো প্রয়োজন নেই।

### ৬. `paykaribazaronline/supremeai-core` কি সক্রিয় নয়? সেখানে কেন "No workflows found" দেখাচ্ছে?
- **উত্তর:** `paykaribazaronline/supremeai-core` হলো রোডম্যাপ **Phase 5**-এর জন্য তৈরি একটি প্লেসহোল্ডার শেল (Placeholder)। এর `README.md`-এ স্পষ্ট লেখা রয়েছে: `⚠️ Extraction status: NOT YET EXTRACTED`। এর ভেতরে বর্তমানে কোনো টেস্ট বা কোড নেই; সমস্ত সক্রিয় কোড ও ওয়ার্কফ্লো `paykaribazaronline/supremeai`-তে চলমান।

### ৭. রোডম্যাপের কোন কোন ফেজ সম্পন্ন এবং কোনগুলো বাকি?
- **সম্পন্ন ফেজসমূহ:**
  - **Phase 0:** Boundary classification & dependency probes (0 backend imports).
  - **Phase 1:** `supremeai-sdk` (পাবলিক, v0.1.0 প্যাকেজ ও স্কিমা লাইভ)।
  - **Phase 2:** `supremeai-studio` (পাবলিক, ৫৭১টি ফ্রন্টএন্ড ফাইল ও পিএনপিএম ওয়ার্কস্পেস লাইভ)।
  - **Phase 3:** `supremeai-mcp-control-plane` (প্রাইভেট, ১৪৮+ ফাইল ও ডকার লাইভ)।
  - **Phase 8:** `supremeai-open` & Federation Bridge Foundation (লাইভ)।
- **বাকি ফেজসমূহ:**
  - **Phase 3 & 4 (Internal Monolith Consolidation):** কনফিগ রেজিস্ট্রি একত্রীকরণ ও ডকার বাউন্ডারি ফিক্স।
  - **Phase 5 (Core Extraction):** `supremeai-core`-এ কোড মাইগ্রেশন (বর্তমানে ব্লকড, কারণ `backend/core`-এর সাথে `backend/brain`-এর ১৪টি ও `adaptive_engine`-এর ৮টি ফাইলের কাপলিং রয়েছে)।

### ৮. এই বাকি ফেজগুলো আগে শেষ করে নেওয়াই কি টেকনিক্যালি সেরা?
- **উত্তর:** হ্যাঁ, তবে ক্রমানুসারে (Sequenced)। আগে মনোলিথের ভেতরের কাপলিং Phase 3 ও 4-এ ছাড়িয়ে নিতে হবে। সরাসরি অকালে কোর আলাদা করতে গেলে ইমপোর্ট ফেইল করবে এবং টেস্ট চালানো অসম্ভব হয়ে পড়বে।

### ৯. বাকি ফেজগুলোর জন্য কি P0 Issue তৈরি করা হয়েছে?
- **উত্তর:** হ্যাঁ, ৩টি P0-critical ইস্যু তৈরি করা হয়েছে:
  - **Issue #124 / Open #19:** `refactor(config): [Phase-3] Unify configuration, secrets, and LLM provider registries into single SSOT`
  - **Issue #125 / Open #20:** `fix(infra): [Phase-4] Correct production docker-compose wiring, pooler credentials and live env contracts`
  - **Issue #126 / Open #21:** `refactor(architecture): [Phase-5] Decouple backend/core dependencies to enable supremeai-core repository migration`

### ১০. সবকিছু সহজ করার জন্য `paykaribazaronline/supremeai-open`-এ যেকোনো ইস্যু তৈরি করাই কি সেরা?
- **উত্তর:** হ্যাঁ। কারণ `supremeai-open` পাবলিক হওয়ায় পৃথিবীর যেকোনো ভার্চুয়াল বট বা এআই পারমিশন ছাড়াই ইস্যু পড়তে ও ক্লেইম করতে পারে। সিক্রেট ছাড়া যেকোনো টাস্ক এখানে পোস্ট করা সম্পূর্ণ নিরাপদ ও কার্যকর।

### ১১. `supremeai-open`-এর ইস্যু টেমপ্লেট কেমন হবে?
- **উত্তর:** `.github/ISSUE_TEMPLATE/agent-task.yml` তৈরি করে পুশ করা হয়েছে। এতে টার্গেট রিপো ড্রপডাউন, প্রায়োরিটি, মিশন, টাচিং ফাইলস এবং ৩-টিয়ার ভেরিফিকেশন কন্ট্রাক্ট স্বয়ংক্রিয়ভাবে অন্তর্ভুক্ত রয়েছে।

### ১২. ভার্চুয়াল এজেন্টরা কি কোড ও টেস্ট ফাইল ছাড়া কাজ করবে?
- **উত্তর:** না। ভার্চুয়াল এজেন্টরা পাবলিক রিপোর কোড সরাসরি ক্লোন করে দেখে, আর প্রাইভেট কোডের ক্ষেত্রে ইস্যু ডেসক্রিপশন, MCP টুলস (`github_read_file`) অথবা ব্রিজ সিআই-এর রানার লগ থেকে কোড ও টেস্ট বিশ্লেষণ করে কাজ করে।

### ১৩. কাজের দিক থেকে ভার্চুয়াল এজেন্ট এবং লোকাল Antigravity-র মধ্যে কি কোনো তফাৎ আছে?
- **উত্তর:** কাজের দিক থেকে কোনো তফাৎ নেই। উভয়কেই কোড পড়ে বুঝতে হবে, কোড লিখতে হবে, টেস্ট চালাতে হবে এবং ফেইল করলে ফিক্স করতে হবে। তফাৎ শুধু অ্যাক্সেসে: লোকাল এজেন্টের কাছে সরাসরি হার্ডড্রাইভ ও টার্মিনাল অ্যাক্সেস থাকে, আর ভার্চুয়াল এজেন্ট গিটহাব ও ক্লাউড রানারের মাধ্যমে ফলাফল পায়।

### ১৪. বাকি এজেন্টরা যেভাবে `supremeai-open` এবং MCP Server দিয়ে কাজ করে, লোকাল এজেন্টও কি একইভাবে কাজ করতে পারে?
- **উত্তর:** হ্যাঁ, ১০০% পারে। লোকাল এজেন্টেরও MCP কন্ট্রোল টাওয়ার ও ব্রিজ দিয়ে কাজ করার সম্পূর্ণ ক্ষমতা রয়েছে।

### ১৫. একাধিক জায়গায় এলোমেলোভাবে কাজ করলে কি আসল সমস্যা বোঝা যাবে না?
- **উত্তর:** একদম সত্য। এক এজেন্ট `supremeai`, আরেকজন `supremeai-open`, আরেকজন `supremeai-core`-এ কাজ করলে বিশৃঙ্খলা তৈরি হবে। এজন্য ক্যানোনিকাল নিয়ম হলো:
  - **টাস্কের বোর্ড:** `paykaribazaronline/supremeai-open`
  - **কোড ল্যান্ডিং ও টেস্ট রান:** `paykaribazaronline/supremeai`

---

## 🏛️ ষোলআনা বিশ্লেষণ: লোকাল ডিভাইস মূলত কোন রিপোর সাথে সিঙ্ক থাকবে?

### পরিস্থিতি বিশ্লেষণ (Deep Analysis):
1. **যদি লোকাল ডিভাইস শুধুমাত্র `supremeai-open`-এ সিঙ্ক থাকে:**
   - লোকাল ডিভাইসে কোড ডেভেলপমেন্ট, পাইথন টেস্ট চালানো বা ব্যাকএন্ড রান করা সম্ভব নয়; কারণ এখানে মাত্র ৮টি ফাইল রয়েছে।
2. **যদি লোকাল ডিভাইস `supremeai` (মনোলিথ)-তে সিঙ্ক থাকে:**
   - লোকাল ডিভাইসে সম্পূর্ণ কোডবেস (FastAPI, Alembic, Docker, Pytest) সরাসরি থাকে।
   - ভার্চুয়াল এজেন্টরা `supremeai-open`-এ যা কিছুই সাবমিট করুক, ব্রিজ রোবট সেই কোড নিয়ে এসে এই `paykaribazaronline/supremeai`-এর `main`-এই মার্জ করে দেয়।
   - তাই লোকাল মেশিনে `git pull` দিলেই ভার্চুয়াল বটদের কাজ ও ইন্টারনাল কোড সবকিছু এক জায়গায় সিঙ্ক পাওয়া যায়।

### চূড়ান্ত ক্যানোনিকাল সিদ্ধান্ত (Canonical Verdict):
> **"টাস্ক ম্যানেজমেন্টের জন্য সিঙ্গেল পয়েন্ট হলো `paykaribazaronline/supremeai-open` (পাবলিক বোর্ড), কিন্তু কোড এক্সিকিউশন ও লোকাল ডেভেলপমেন্টের জন্য সিঙ্গেল ট্রুথ হলো `paykaribazaronline/supremeai` (সক্রিয় ইঞ্জিন)।"**
