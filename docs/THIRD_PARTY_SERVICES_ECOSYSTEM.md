# SupremeAI Third-Party Services Ecosystem & Deep Architectural Audit
`
**Document:** docs/THIRD_PARTY_SERVICES_ECOSYSTEM.md  
**Phase:** Self-Evolution & Production-Ready Operations  
**Single Source of Truth:** STATUS.md  
**Audit Basis:** Repository code/AST parsing, active environment variables, service registries, and public free-tier constraints.  
**Critical Principle:** *Environment variable থাকা মানেই deployed runtime-এ service সফলভাবে ব্যবহৃত হচ্ছে—এটা প্রমাণ করে না।*
`
---
`
## 1. বর্তমানে ব্যবহৃত / সংযুক্ত সার্ভিসের পূর্ণাঙ্গ নিরীক্ষা (Current Audit)
`
| সার্ভিস | বর্তমান ব্যবহার | Free সুবিধা ও সীমাবদ্ধতা | সুপ্রিমএআই প্রোডাকশন অবস্থা | ভেরিফিকেশন প্রমাণ |
|---|---|---|---|---|
| **Render** | Core, Worker, Scraper, MCP Tower backend nodes | Free web service (৭৫০ ঘণ্টা/মাস pooled); idle হলে ১৫ মিনিটে sleep/cold-start | ৪টি live node সক্রিয়; ৪৫০m বাজেট গার্ড স্ক্রিপ্ট সংহত | 🟢 **Verified Live** (HTTP 200 on liveness) |
| **Cloudflare Workers** | Edge gateway, routing, keepalive (supremeai-worker) | Free plan-এ দৈনিক ১০০,০০০ রিকোয়েস্ট কোটা | Gateway live (*/8 * * * * keepalive cron চলছে) | 🟢 **Verified Live** (supremeai-worker.paykaribazaronline.workers.dev) |
| **Firebase Hosting** | User ও Admin ফ্রন্টএন্ড পরিবেশন | Spark plan: ৩৬০MB/দিন ব্যান্ডউইথ ও গ্লোবাল CDN | ২টি ডোমেইন লাইভ (supremeai-a ও supremeai-admin) | 🟢 **Verified Live** (Single SPA dist deployed) |
| **Vercel** | Alternate frontend mirror | Hobby plan: ১০০GB ব্যান্ডউইথ ও এজ ডিপ্লয় | Mirror live (supremeai-lac.vercel.app) | 🟢 **Verified Live** (HTTP 200) |
| **GitHub Actions / GHCR** | CI/CD, সিকিউরিটি স্ক্যান, ডকার বিল্ড ও ডিপ্লয় | ২০০০ মিনিট/মাস (private), আনলিমিটেড (public); ফ্রি কন্টেইনার রেজিস্ট্রি | সম্পূর্ণ অটোমেটেড টেস্ট, সাইন ও ডিপ্লয় পাইপলাইন | 🟢 **Strong Evidence** (.github/workflows/ci.yml) |
| **Supabase** | PostgreSQL, Auth, pgvector (i_memory) | ৫০০MB ডাটাবেস, ৫GB ইগ্রেস, ৫০,০০০ MAU; ৭ দিন inactive হলে pause | সিঙ্গাপুর ক্লাস্টারে লাইভ পুলার কানেকশন সক্রিয় | 🟢 **Strong Evidence** (Active DB pooler & vector tables) |
| **Qdrant Cloud** | Vector search, knowledge base, embeddings | Free ১GB ক্লাস্টার; প্রোটোটাইপ স্কেল | API Key ও ক্লাউড URL কনফিগার করা | 🟡 **Config-Only / Auxiliary** (Runtime fallback to pgvector) |
| **Upstash Redis** | Cache, rate limit, pub/sub, heartbeat bus | দৈনিক ১০,০০০ কমান্ড ফ্রি; REST API ভিত্তিক | রেট-লিমিটার ও সার্কিট ব্রেকারে কানেক্টেড | 🟢 **Strong Evidence** (Active Upstash REST client) |
| **Firebase Firestore** | Client metadata, config, backup | Spark: ৫০,০০০ read, ২০,০০০ write/দিন, ১GB storage | Firebase admin SDK ইনিশিয়ালাইজড | 🟡 **Auxiliary** (Client config / audit state) |
| **Infisical Cloud** | সেন্ট্রালাইজড মেশিন আইডেন্টিটি ও সিক্রেট ভল্ট | Free tier: আনলিমিটেড সিক্রেটস, মেশিন আইডেন্টিটি | CI ও ব্যাকএন্ড রানটাইমে ডাইনামিক সিঙ্ক | 🟢 **Strong Evidence** (Universal Auth integrated) |
| **Google Cloud KMS** | সিমেট্রিক এনক্রিপশন ও কী রিং | সীমিত ফ্রি অপারেশন; প্রতি ২০,০০০ অপারেশনে .০৩ | supremeai-a-prod-ring কনফিগার করা | 🟡 **Config / Enterprise Guard** |
| **Google Gemini API** | AI ইনফারেন্স, লং কনটেক্সট, ভিশন প্রসেসিং | Free tier: ১৫ RPM / ১ মিলিয়ান TPM (Gemini 2.0/1.5 Flash) | মাল্টি-মডেল রাউটারের প্রাইমারি ওয়ার্কার | 🟢 **Strong Evidence** (Router priority tier) |
| **Groq Cloud** | সাব-সেকেন্ড লো-লেটেন্সি চ্যাট ও কোডিং | Free developer tier: ৩০ RPM / ১৪,৪০০ RPD (Llama 3.3 70B) | আল্ট্রা-ফাস্ট স্ট্রিমিং ও চ্যাট জেনারেশন | 🟢 **Strong Evidence** (Fastest inference route) |
| **Mistral AI** | কোডিং ও লজিক্যাল রিজনিং ফলব্যাক | Free mode: ১ RPS / ৫০০,০০০ টোকেন/মিনিট | কোডস্টেস্ট্রাল ও মিস্ট্রাল স্মল ফলব্যাক | 🟢 **Strong Evidence** (IDE Trio & Router fallback) |
| **GitHub Models** | GPT-4o, Claude 3.5 Sonnet এক্সপেরিমেন্টেশন | সীমিত রেট লিমিট (১৫ RPM / ১৫০ RPD); ট্রায়াল | ডিপ কোড রিভিউ ও আর্কিটেকচার অডিট | 🟢 **Strong Evidence** (7 rotated PAT tokens) |
| **OpenRouter** | মাল্টি-মডেল গ্লোবাল ফলব্যাক হাব | ফ্রি মডেলসমূহে ২০ RPM / ৫০ রিকোয়েস্ট/দিন | ডিপসিক V3 ও কিউয়েন 2.5 ফলব্যাক | 🟢 **Strong Evidence** (Circuit-breaker catchall) |
| **Cloudflare Workers AI** | সার্ভারলেস এজ ইনফারেন্স (@cf/meta/llama-3.1-8b) | ফ্রি নিউরাল নেটওয়ার্ক কোটা (১০,০০০ নিউরন/দিন) | ব্যাকএন্ড ফেল করলে এজ-লেভেল ফলব্যাক | 🟡 **Edge Fallback** (Configured in worker) |
| **Kaggle** | হেভি ব্যাচ কম্পিউট, GPU ট্রেইনিং ও ডাটা সিন্থেসিস | ৬টি অ্যাকাউন্টে ১৮০ ঘণ্টা/সপ্তাহ ফ্রি T4/P100 GPU | হেডলেস কার্নেল ও ব্যাচ সিন্থেসিস স্ক্রিপ্ট | 🟡 **Batch / Auxiliary** (Non-production worker) |
| **Firecrawl** | ওয়েব-টু-মার্কডাউন এলএলএম স্ক্র্যাপিং | ৫০০ ফ্রি ক্রেডিট | স্ক্র্যাপার সার্ভিসে ইন্টিগ্রেটেড | 🟡 **Tooling** (Triggered on web-research) |
| **OpenHands / Browserless** | হেডলেস ব্রাউজার অটোমেশন ও ইভ্যালুয়েশন | সেলফ-হোস্টেড / ট্রায়াল কোটা | প্লে-রাইট ব্রাউজার টেস্ট ও অটোমেশন | 🟡 **Development / Testing Tool** |
| **Telegram Bot API** | অ্যাডমিন ক্র্যাশ অ্যালার্ট, OTP, রিমোট কমান্ড | আনলিমিটেড ফ্রি বট মেসেজিং | সরাসরি অ্যাডমিন টেলিগ্রাম আইডিতে অ্যালার্ট পুশ | 🟢 **Strong Evidence** (Realtime admin notifier) |
| **Discord Webhooks** | CI/CD বিল্ড নোটিফিকেশন ও ডিপ্লয় অ্যালার্ট | আনলিমিটেড ফ্রি ওয়েবহুক কল | সিআই পাইপলাইন ও ডিপ্লয়মেন্ট মনিটরিং | 🟢 **Strong Evidence** (Dispatched on every deploy) |
| **Resend** | ট্রানজেকশনাল ইমেইল (Auth, OTP, Billing) | ৩,০০০ ইমেইল/মাস (১০০/দিন) ফ্রি | ইউজার রেজিস্ট্রেশন ও সিকিউরিটি ভেরিফিকেশন | 🟢 **Strong Evidence** (Auth email dispatcher) |
| **Stripe** | সাবস্ক্রিপশন, ক্রেডিট পারচেজ, পেমেন্ট ওয়েবহুক | নো মান্থলি ফি; ট্রানজেকশনে ২.৯% + ৩০¢ | বিলিং সার্ভিস, পোর্টাল ও ওয়েবহুক ইন্টিগ্রেটেড | 🟢 **Strong Evidence** (Full webhook & checkout logic) |
| **RouteMe API** | ট্রাফিক ডায়নামিক রাউটিং অপটিমাইজেশন | সীমিত ফ্রি কোটা | রাউটার মেজারমেন্ট টুলস | 🟡 **Auxiliary** (Low footprint) |
`
---
`
## 2. বর্তমান কোডবেসে প্রমাণের শ্রেণিবিন্যাস (Evidence Classification)
`
### 🟢 Strong Evidence (প্রোডাকশনে সরাসরি সক্রিয় ও পরীক্ষিত)
- **Supabase:** PostgreSQL কানেকশন পুলার, ইউজার সেশন, i_memory (pgvector)।
- **Render:** ৪টি নোডের লাইভ রানটাইম, হেলথচেক পাথ /api/v1/health/live, বিল্ড বাজেট গার্ড।
- **Cloudflare Workers:** এজ রাউটার গেটওয়ে ও ২৪/৭ কীপ-অ্যালাইভ ক্রন।
- **Firebase Hosting:** ইউনিফাইড সিঙ্গেল SPA ফ্রন্টএন্ড (supremeai-a ও supremeai-admin)।
- **Upstash Redis:** ডিস্ট্রিবিউটেড রেট-লিমিটিং, সার্কিট ব্রেকার স্টেট ও ক্যাশ।
- **AI Core Fleet:** Groq, Gemini, Mistral, OpenRouter ও GitHub Models-এর লাইভ ফলব্যাক চেইন।
- **Telegram & Discord:** লাইভ অ্যালার্ট এবং পাইপলাইন ইভেন্ট রিপোর্টিং।
- **GitHub Actions:** এন্ড-টু-এন্ড টেস্ট, ডকার ইমেজ পুশ (GHCR) ও ডিপ্লয় গেটওয়ে।
`
### 🟡 Config-Only / Auxiliary (টুলিং বা ব্যাকআপ হিসেবে সংরক্ষিত)
- **Qdrant Cloud:** কনফিগ ও ক্লায়েন্ট তৈরি আছে, কিন্তু প্রাথমিক ভেক্টর স্টোর হিসেবে Supabase pgvector অগ্রাধিকার পায়।
- **Google Cloud KMS:** কি-রিং ও রিং আইডি কনফিগার করা, তবে ফাইল সিস্টেম এনক্রিপশনে সিমেট্রিক ENCRYPTION_KEY ব্যবহৃত হয়।
- **Kaggle:** ব্যাচ ডাটা সিন্থেসিসের জন্য তৈরি, তবে কোর এপিআই রানটাইমে যুক্ত নয় (পলিসি সেফ)।
- **Firecrawl & Browserless:** অন-ডিমান্ড এক্সটার্নাল রিসার্চ স্ক্রিপ্টে ব্যবহৃত হয়।
- **RouteMe:** অল্টারনেট রাউটিং ট্র্যাকিং।
`
---
`
## 3. প্রতিটি সার্ভিসের অব্যবহৃত Free সুবিধা ও সর্বোচ্চ ব্যবহারের গাইডলাইন
`
### A. Firebase (Frontend & Client Platform)
- **Firebase AI Logic / Vertex AI (Backend Muscle হিসেবে):**  
  সরাসরি ফ্রন্টএন্ড থেকে কল করা **নিষিদ্ধ** (ব্র্যান্ড এক্সক্লুসিভিটি ও থিন ক্লায়েন্ট বজায় রাখতে)। তবে Core Backend-এর ভেতরে সার্ভিস অ্যাকাউন্ট দিয়ে Gemini 2.0 Flash কোটা ব্যাকআপ ইঞ্জিন হিসেবে ব্যবহার করা যাবে।
- **Firebase App Check:**  
  Play Integrity / reCAPTCHA Enterprise দিয়ে অবৈধ API স্ক্র্যাপিং ও স্প্যাম ক্লায়েন্ট ব্লক করা।
- **Remote Config:**  
  ফ্রন্টএন্ড বা ব্যাকএন্ড রি-ডিপ্লয় না করেই রানটাইমে এআই মডেল রাউটিং পলিসি বা ফিচার ফ্ল্যাগ পরিবর্তন।
- **Firestore Offline Persistence:**  
  ইউজারের ড্রাফট প্রম্পট, থিম প্রিফারেন্স বা সাময়িক স্টেট অফলাইনে ক্যাশ রাখা।
`
### B. Cloudflare (Edge & Security Layer)
- **Health-Based Failover:**  
  Core নোড ডাউন হলে Worker স্বয়ংক্রিয়ভাবে ব্যাকআপ Worker নোডে ট্রাফিক ডাইভার্ট করবে।
- **Cloudflare Turnstile:**  
  লগইন, রেজিস্ট্রেশন এবং এআই এন্ডপয়েন্টে রোবট/বট অ্যাটাক ঠেকাতে -কস্ট ক্যাপচা সুরক্ষা।
- **Cloudflare R2:**  
  ইউজারের আপলোড করা বড় ফাইল, কোড আর্টিক্ট ও ব্যাকআপ জিরো-ইগ্রেস কস্টে সংরক্ষণ।
- **Cloudflare KV & Rate Limiting:**  
  আইপি-ভিত্তিক ব্রুট-ফোর্স অ্যাটাক এজ লেভেলেই আটকে দেওয়া।
`
### C. Supabase (Data, State & Memory)
- **Row Level Security (RLS):**  
  প্রতিটি ইউজারের প্রজেক্ট ও চ্যাট ডেটা ডেটাবেস কার্নেল লেভেলে সম্পূর্ণ আইসোলেটেড রাখা।
- **Realtime Pub/Sub:**  
  WebSocket ছাড়াই ফ্রন্টএন্ড ড্যাশবোর্ডে এজেন্টের লাইভ স্টেট আপডেট পুশ করা।
- **Automated Partitioning & Cleanup:**  
  পুরনো সাময়িক লগ স্বয়ংক্রিয়ভাবে পার্জ করে ৫০০MB ফ্রি কোটার মধ্যে ডাটাবেসকে অপটিমাইজ রাখা।
`
### D. Upstash Redis (High-Speed State)
- **Idempotency Locks:**  
  ডুপ্লিকেট পেমেন্ট বা একই প্রম্পটের জোড়া এক্সিকিউশন আটকানো।
- **Semantic Prompt Caching:**  
  একই প্রশ্নের পুনরাবৃত্তি হলে এআই প্রোভাইডারের কাছে না গিয়ে রেডিস থেকে ইনস্ট্যান্ট রেসপন্স দেওয়া (Save Tokens & Latency)।
- **Circuit Breaker Registry:**  
  কোনো প্রোভাইডার ডাউন হলে তার স্টেট গ্লোবালি রেডিসে রাখা যাতে অন্য নোডগুলো অপ্রয়োজনীয় কল না করে।
`
### E. AI Inference Fleet (Cost & Capacity Optimization)
- **Automated Downgrade Hierarchy:**  
  Groq (Fast) ➔ Gemini Flash (Free) ➔ Mistral (Logic) ➔ GitHub Models ➔ OpenRouter।
- **Token Budget Guard:**  
  ইউজার প্রতি মাসিক বা দৈনিক ফেয়ার-ইউজ টোকেন সীমা বজায় রাখা।
- **Streaming by Default:**  
  প্রতিটি চ্যাট SSE স্ট্রিম আকারে পাঠানো যাতে ইউজার শূন্য লেটেন্সি অনুভব করে।
`
### F. Resend (Email Communication)
- **Strict Budgeting:**  
  মাসে ৩,০০০ ইমেইল কোটা সুরক্ষিত রাখতে শুধুমাত্র ক্রিটিক্যাল ইমেইল (Password Reset, Signup OTP, Billing Receipt) পাঠানো।
- **Idempotency Keys:**  
  নেটওয়ার্ক গ্লিচের কারণে একই ইউজার যেন একাধিক ভেরিফিকেশন ইমেইল না পায়।
### G. GitHub (DevSecOps & Supply Chain)
- **CodeQL & Dependabot:**  
  অটোমেটেড কোড স্ক্যানিং ও আউটডেটেড লাইব্রেরি প্যাচিং।
- **Container Signing (Cosign) & SBOM:**  
  ডকার ইমেজের ক্রিপ্টোগ্রাফিক ভেরিফিকেশন নিশ্চিত করা।

---

## 4. প্রস্তাবিত নতুন ফ্রি টুলস (Missing / Recommended Additions)
| টুল / সার্ভিস | প্রস্তাবিত ব্যবহার | সুবিধা |
|---|---|---|
| **Sentry** | সেন্ট্রাল এরর ট্র্যাকিং ও এপিএম ট্রেসিং | ব্যাকএন্ড ও ফ্রন্টএন্ডের যেকোনো আনহ্যান্ডেলড ক্র্যাশ রিয়েলটাইমে ডিটেক্ট করে। |
| **Cloudflare Turnstile** | বট ও স্ক্র্যাপার প্রটেকশন | গুগল রি-ক্যাপচার চেয়ে হালকা এবং ইউজারের বিরক্তি ছাড়াই ব্যাকগ্রাউন্ডে বট ভ্যালিডেট করে। |
| **PostHog** | প্রোডাক্ট অ্যানালিটিক্স ও ইউজার জার্নি ট্র্যাকিং | ফ্রি টিয়ারে প্রতি মাসে ১ মিলিয়ান ইভেন্ট সম্পূর্ণ বিনামূল্যে ট্র্যাক করা যায়। |
| **Better Uptime / UptimeRobot** | এক্সটার্নাল ব্ল্যাকবক্স আপটাইম মনিটর | প্রতি ৫ মিনিটে বাইরে থেকে সার্ভিস ডাউন কিনা স্বাধীনভাবে চেক করে টেলিগ্রামে অ্যালার্ট পাঠায়। |
| **Lighthouse CI** | ফ্রন্টএন্ড ওয়েব পারফরম্যান্স অডিট | সিআই পাইপলাইনে Core Web Vitals (LCP, FID, CLS) স্কোর বজায় রাখে। |

---
## 5. অ্যাকশন প্রায়োরিটি ম্যাট্রিক্স (Execution Roadmap)

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ PRIORITY 0: CORE CONNECTIVITY & AUDIT (🟡 PARTIALLY VERIFIED)           │
│ • [x] Unified Single Frontend deployed to Firebase (User & Admin).      │
│ • [x] 4 Render Backend Nodes running with /api/v1/health/live probe.    │
│ • [x] Cloudflare Gateway keepalive cron active (*/8 * * * *).           │
│ • [ ] End-to-End browser authentication & chat session verification.    │
│ • [ ] Deprecate risky PAT rotation in GitHub Models to official scope.  │
│ • [ ] Audit Supabase RLS policies and eliminate client secret exposure. │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PRIORITY 1: PRODUCTION RELIABILITY & OBSERVABILITY                      │
│ • Integrate Sentry for real-time frontend and FastAPI error tracking.   │
│ • Integrate Langfuse for LLM token, latency, and cost telemetry.        │
│ • Deploy Cloudflare Turnstile bot protection on auth & chat endpoints.  │
│ • Implement Upstash Redis semantic prompt caching to cut token waste.   │
│ • Implement Cloudflare health-based automatic edge failover.            │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PRIORITY 2: ADVANCED ASYNC & STORAGE SCALE                              │
│ • Cloudflare R2 object storage for generated artifacts and exports.     │
│ • Cloudflare Queues for heavy scraping and asynchronous self-healing.   │
│ • Better Stack external uptime heartbeat monitoring.                    │
│ • Firebase Vertex AI integration inside Core Backend as backup muscle.  │
│ • Stripe self-service Customer Portal for billing management.           │
└─────────────────────────────────────────────────────────────────────────┘
```
