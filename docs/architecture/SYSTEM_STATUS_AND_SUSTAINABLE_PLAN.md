# 🚀 SupremeAI: Current System Status & Sustainable Low-Cost Evolution Plan

**তারিখ:** ১০ সেপ্টেম্বর ২০২৬  
**ফেজ:** Phase 3.1: Architecture Consolidation & Cost Optimization  
**ডকুমেন্ট টাইপ:** Master System Status & Engineering Roadmap  
**কোর নীতি:** *Zero / Near-Zero Cost through Strict Optimization, Graceful Degradation & Full Policy Compliance.*

---

## ১. ভূমিকা ও মূল দর্শন (Executive Summary)

নতুন প্রস্তাবিত টেকসই আর্কিটেকচারটি SupremeAI-এর জন্য **৮০–৮৫% গ্রহণীয় (Adoptable)**। এটি মূলত একটি নতুন আর্কিটেকচার নয়, বরং আমাদের **বিদ্যমান আর্কিটেকচারকে সুশৃঙ্খল, নিরাপদ ও সাশ্রয়ী করার একটি রোডম্যাপ**।

তবে বাস্তব প্রোডাকশন অডিট অনুযায়ী—**"ভেন্ডর রেস্ট্রিকশন বাইপাস"**, **"৪টি রেন্ডার একাউন্টে ৪× কোটা পাওয়ার বিভ্রম"**, এবং **"ফ্রন্টএন্ডে সরাসরি রেডিস অ্যাক্সেস"**-এর মতো অবাস্তব বা ঝুঁকিপূর্ণ ধারণাগুলো পুরোপুরি বর্জন করা হয়েছে।

---

## ২. পার্ট ১: বর্তমান সিস্টেম স্ট্যাটাস (Current Status as of 2026-09-10)

আমাদের কোর আর্কিটেকচার লোকাল ডকার ও ক্লাউডে সফলভাবে সক্রিয়। তবে এক্সটার্নাল ডিপ্লয়মেন্ট অডিটে একটি নির্দিষ্ট Vercel প্রজেক্টে (`supremeai` failing, যদিও `supremeai-frontend` এবং `browser` passing) তদন্তাধীন রয়েছে।

### ক) কম্পোনেন্ট ও রানটাইম ম্যাট্রিক্স

| কম্পোনেন্ট | স্ট্যাটাস | রানটাইম / হোস্টিং | বর্তমান কার্যকারিতা ও নোট |
|---|---|---|---|
| **Backend Core** | 🟢 Live | FastAPI (Python 3.11, SQLAlchemy 2.0 Async) | Render Docker (`supremeai-primary-node`) |
| **Async Worker** | 🟢 Live | Background Task Queue / Celery Abstraction | Render Docker (`supremeai-worker-node`) |
| **Browser Scraper** | 🟢 Live | Playwright Headless Node | Render Docker (`supremeai-scraper-node`) |
| **MCP Control Tower** | 🟢 Live | Node.js MCP Server (`@modelcontextprotocol/sdk`) | Render (`supremeai-mcp-tower`) |
| **Edge Router / Keepalive** | 🟢 Live | Cloudflare Worker (`supremeai-worker`) | ২৪/৭ নোড পিং (`*/8 * * * *`), পাবলিক ক্যাশিং ও রেট লিমিট |
| **LLM Gateway** | 🟢 Live | Provider-Agnostic Matrix (Gemini, Groq, OpenRouter) | জিরো-কস্ট ডাইনামিক ফলব্যাক চেইন ও টোকেন কম্প্রেশন সক্রিয় |
| **AutoHealer** | 🟢 Live | Native FastAPI Lifespan Loop | রিং-বাফার ও প্রোব দিয়ে সেলফ-হিলিং সার্ভিস |
| **Database & Memory** | 🟢 Healthy | Supabase PostgreSQL + `pgvector` (`ai_memory`) | ১১১টি টেবিল, স্লো কুয়েরি লগার (<২০০ms), HNSW ইনডেক্স |
| **Frontend UI** | 🟡 Investigating | React 19 + Vite 7 + Design System | `supremeai-frontend` passing, legacy `supremeai` Vercel check failing |
| **Thin Clients** | 🟢 Ready | Desktop (Tauri/Electron) & VS Code Ext | ১০০% থিন ক্লায়েন্ট, নো প্রোভাইডার/কী এক্সপোজার |
| **Security & Secrets** | 🟡 Action Required | Infisical Secret Vault + Gitleaks CI | P0: Frontend `cache.manager.ts`-এ সরাসরি Upstash টোকেন কল সরানো প্রয়োজন |

---

## ৩. পার্ট ২: ৫টি গুরুত্বপূর্ণ সংশোধন ও বাস্তব সিদ্ধান্ত

| প্রস্তাবিত প্ল্যান | আমাদের অডিট পর্যবেক্ষণ | চূড়ান্ত ইঞ্জিনিয়ারিং সিদ্ধান্ত |
|---|---|---|
| **Multi-Account Strategy (Render, Cloudflare, Kaggle, GitHub)** | যেখানেই মাল্টিপল অ্যাকাউন্ট ব্যবহৃত হচ্ছে, সেখানে সম্পূর্ণ **আলাদা ও স্বতন্ত্র (Legitimate Separate Accounts)** ব্যবহার করা হচ্ছে। ফলে কোনো একটি অ্যাকাউন্টের কোটা বা লিমিট শেষ হলেও বাকিগুলো স্বাধীন থাকে। | ✅ **পূর্ণাঙ্গ ক্ষমতা গৃহীত (Resilient Multi-Account Pool):**<br>• ৪টি Render অ্যাকাউন্ট = ৩,০০০ ফ্রি ঘণ্টা (২৪/৭ অলওয়েজ-অন)<br>• মাল্টিপল Cloudflare অ্যাকাউন্ট = আনলিমিটেড MCP ও এজ ক্যাশ পুল<br>• গিটহাব ও ক্যাগল আলাদা অ্যাকাউন্ট = বিশাল ব্যাচ কম্পিউট পুল<br>• **একমাত্র শর্ত:** রাউটারে অটো-ফেইলওভার থাকতে হবে যেন কোনো নোড অফলাইন হলে সিস্টেম নিজে নিজেই ব্যাকআপ অ্যাকাউন্টে ট্রাফিক পাঠায়। |
| **Upstash ৫০০K কমান্ড/মাস** | বর্তমান ফ্রি টিয়ার: **৫০০,০০০ কমান্ড/মাস**, ২৫৬MB ডেটা, ১০GB ব্যান্ডউইথ। | ✅ **আপডেট:** ব্যাকএন্ডে আরও অ্যাগ্রেসিভভাবে দ্রুতগতির রেডিস ব্যবহার করা যাবে। |
| **ফ্রন্টএন্ডে সরাসরি রেডিস কল** | `cache.manager.ts` ব্রাউজারেই `UPSTASH_REDIS_REST_TOKEN` এক্সপোজ করছে। | ❌ **P0 সিকিউরিটি ফিক্স:** ক্লায়েন্ট থেকে রেডিস ক্রেডেনশিয়াল বন্ধ করে ব্যাকএন্ড/এজ এপিআই প্রক্সি করা হবে। |
| **Durable Queue রিরাইট** | আমাদের `task_queue_enhanced.py`-তে অলরেডি বাউন্ডেড কিউ, রিট্রাই ও ট্র্যাকিং আছে। | ✅ **ইনক্রিমেন্টাল অ্যাডপশন:** সম্পূর্ণ রিরাইট না করে বর্তমান কিউয়ের ওপর শুধু একটি **Standard Job Envelope & DLQ** যোগ করব। |
| **Core Architecture-এ Wasm/Pyodide** | কোডবেসে এখনো কোনো প্রোডাকশন Wasm/Pyodide নেই। সরাসরি ইনজেক্ট করলে জটিলতা বাড়বে। | 🟡 **Phase 4-এ শিফট:** প্রথমে ব্যাকএন্ড প্রোফাইলিং হবে; যা CPU-heavy ও deterministic, কেবল সেগুলোতে ভবিষ্যতে Wasm আসবে। |

---

## ৪. পার্ট ৩: অনুমোদিত আর্কিটেকচার টপোলজি (The Clean Architecture)

```
                 ┌──────────────────────────────────────────────┐
                 │       SUPREMEAI UNIFIED CLIENT SHELL         │
                 │   (Web, VS Code Extension, Desktop Tauri)   │
                 └──────────────────────┬───────────────────────┘
                                        │
                                        ▼
           ┌────────────────────────────────────────────────────────────┐
           │                  CLOUDFLARE WORKERS EDGE                   │
           │ - Public GET Edge Caching (60s, Config, Metadata)         │
           │ - Strict Rate Limiting (100k req/day per account)          │
           │ - Circuit Breaker & Health-aware Routing                   │
           │   *(Never cache private/authenticated AI payloads)*        │
           └────────────────────────────┬───────────────────────────────┘
                                        │
                                        ▼
           ┌────────────────────────────────────────────────────────────┐
           │                      CORE API GATEWAY                      │
           │                 (FastAPI - Render / Koyeb)                 │
           │ - Service Isolation (Not Quota Abuse)                      │
           │ - Fast Read/Write Endpoints                                │
           │ - Standard Job Envelope Creation                           │
           └────────────────────────────┬───────────────────────────────┘
                                        │ (Job Enqueue)
                                        ▼
           ┌────────────────────────────────────────────────────────────┐
           │                     DURABLE TASK QUEUE                     │
           │           (Upstash Redis / Fallback In-Memory Queue)       │
           │ - Free Tier: 500K cmd/month, 256MB Data, 10GB Bandwidth    │
           │ - Backend Access ONLY (No Browser-Side Direct Redis)       │
           │ - Standard Envelope: job_id, tenant_id, retries, checkpoint│
           │ - Terminal DLQ on Failure                                  │
           └─────────────┬──────────────────────────────┬───────────────┘
                         │                              │
         ┌───────────────┴───────────────┐              │
         ▼                               ▼              ▼
┌─────────────────┐             ┌─────────────────────┐ ┌───────────────────────┐
│ ISOLATED WORKER │             │ AI MODEL ROUTER     │ │ OPTIONAL BATCH RUNNER │
│ - Web Scraper   │             │ - Intent Classifier │ │ (Research / Offline)  │
│ - Playwright    │             │ - Small Model First │ │ - Scheduled Batches   │
│ - Rate-limited  │             │ - TokenJuice Engine │ │ - GitHub Actions Pool │
└─────────────────┘             └─────────────────────┘ └───────────────────────┘
         │                               │                      │
         └───────────────┬───────────────┴──────────────────────┘
                         ▼
           ┌────────────────────────────────────────────────────────────┐
           │                    PERSISTENT STORAGE                      │
           │ - Supabase PostgreSQL (500MB, connection pool)             │
           │ - pgvector (ai_memory)                                     │
           │ - 30-Day DB Partitioning & Auto-Retention Cleaning         │
           └────────────────────────────────────────────────────────────┘
                         │
                         ▼ (Optional Optimization Later)
           ┌────────────────────────────────────────────────────────────┐
           │         PHASE 4: OPTIONAL CLIENT COMPUTE (Wasm)            │
           │ - Only after profiling CPU-heavy deterministic bottlenecks │
           └────────────────────────────────────────────────────────────┘
```

---

## ৫. ফেইলওভার ও রিকভারি ফ্লো (Failure Matrix)

```plaintext
Primary Worker Request
         ↓
Healthy? ───► Yes ───► Execute Task ───► Complete
         │
         └───► No (Crash / Timeout)
                 ↓
         Secondary Standby Path (Koyeb / Fallback Worker)
                 ↓
         Task Retry (Max 3 attempts with Exponential Backoff)
                 ↓
         Still Failing? ───► Push to Dead-Letter Queue (DLQ)
                                   ↓
                             Log Audit & Notify User with Clear Status
```

---

## ৬. বাস্তবায়ন রোডম্যাপ (Phased Execution)

### Phase 3.1 — Security Hardening & Job Envelope (P0/P1 - Immediate)
- [ ] **P0 Security:** `frontend/src/services/cache.manager.ts` থেকে সরাসরি Upstash REST URL/Token অ্যাক্সেস সম্পূর্ণ বাদ দিয়ে ব্যাকএন্ড এপিআই প্রক্সি তৈরি করা।
- [ ] **P1 CI Status:** Vercel-এর ফেইলিং বিল্ড কনফ্লিক্ট (`supremeai` vs `supremeai-frontend`) ফিক্স করা।
- [ ] **P1 Queue Standard:** `task_queue_enhanced.py`-তে Standard Envelope স্কিমা এনফোর্স করা এবং টার্মিনাল ফেইলিওরে Dead-Letter Queue (DLQ) যুক্ত করা।

### Phase 3.2 — Cost Optimization & Retention
- [ ] Cloudflare Edge-এ পাবলিক GET ও মেটাডেটা ক্যাশিং দৃঢ় করা (প্রাইভেট AI কল ক্যাশ হবে না)।
- [ ] Supabase ডেটাবেজে ৩০-দিনের পুরনো এক্সিকিউশন লগের অটো-পার্টিশন ও পিউরিফিকেশন স্ক্রিপ্ট সক্রিয় করা।
- [ ] Intent Classifier ও TokenJuice দিয়ে ছোট মডেলগুলোকে অগ্রাধিকার দেওয়া।

### Phase 4 — Optional Performance Optimization
- [ ] সার্ভার-সাইড প্রোফাইলিং শেষে ব্রাউজারে Wasm/Pyodide নিয়ে পরীক্ষা-নিরীক্ষা।
