# SupremeAI Third-Party Services Ecosystem & Architecture Master Catalog

**Document:** docs/THIRD_PARTY_SERVICES_ECOSYSTEM.md  
**Phase:** Self-Evolution & Production-Ready Operations  
**Single Source of Truth:** STATUS.md  
**Philosophy:** 100% Zero-Cost (-Cost Muscle), Fault-Tolerant, Multi-Cloud Hybrid Mesh with Brand Exclusivity (Thin Client).

---

## Executive Summary
SupremeAI কোনো একক ক্লাউড বা ভেন্ডরের ওপর নির্ভরশীল নয়। এর নিজস্ব বুদ্ধিমত্তা হলো **The Eternal Brain (i_memory / pgvector)**। বিশ্বের সেরা ওপেন ও ফ্রি-টিয়ার থার্ড-পার্টি সার্ভিসসমূহকে সুপ্রিমএআই এমনভাবে সংযুক্ত ও অরকেস্ট্রেট করেছে যাতে কোনো একটি সার্ভিস ডাউন বা রেট-লিমিটেড হলেও সিস্টেম মুহূর্তের মধ্যে অন্য সার্ভিসে ট্রাফিক রুট করে ২৪/৭ জীবিত থাকে।

---

## 1. Cloud Hosting, Compute & Edge Mesh

| সার্ভিস | ভূমিকা / উদ্দেশ্য | কনফিগারেশন / লাইভ নোড | ফ্রি-টিয়ার অপ্টিমাইজেশন |
|---|---|---|---|
| **Render** | • **Node 1 (Core):** মূল FastAPI ব্যাকএন্ড (https://supremeai-primary-node.onrender.com)<br>• **Node 2 (Worker):** ব্যাকগ্রাউন্ড টাস্ক ও সেলফ-হিলিং (https://supremeai-worker-node.onrender.com)<br>• **Node 3 (Scraper):** ব্রাউজার ও ওয়েব ইন্টেলিজেন্স (https://supremeai-scraper-node.onrender.com)<br>• **Node 4 (MCP Tower):** মডেল কনটেক্সট প্রোটোকল গেটওয়ে (https://supremeai-mcp-tower.onrender.com) | ৪টি স্বাধীন ফ্রি অ্যাকাউন্ট (৪৫০ মিনিট বাজেট গার্ড সহ) | 
ender_build_budget_guard.py দিয়ে বিল্ড মিনিট মনিটর করা হয় এবং অটো-ডিপ্লয় সীমা রক্ষা করা হয়। |
| **Cloudflare** | • **Edge Gateway & Proxy:** https://supremeai-worker.paykaribazaronline.workers.dev<br>• **Keepalive Cron:** প্রতি ৮ মিনিটে (*/8 * * * *) ৪টি রেন্ডার নোডকে পিং করে ঘুম ভাঙিয়ে রাখে (Anti-Cold Start)<br>• **Workers AI:** @cf/meta/llama-3.1-8b-instruct ফ্রি এজ ইনফারেন্স<br>• **Cloudflare R2:** এস৩-কম্প্যাটিবল জিরো-ইগ্রেস অবজেক্ট স্টোরেজ | Global API Key & Workers Token | ১০০,০০০ রিকোয়েস্ট/দিন ফ্রি কোটা। |
| **Kaggle** | • **Distributed GPU Workers & Batch Synthesis:** হেভি ট্রেইনিং, বড় মডেল ইভালুয়েশন ও ডাটা সিন্থেসিস<br>• **Headless Kernel Execution:** ব্যাকগ্রাউন্ড ব্যাচ কম্পিউট | ৬টি অ্যাকাউন্টের পুল (KAGGLE_API_TOKEN_1 ... 6) | সপ্তাহে ৩০ ঘণ্টা করে প্রতি অ্যাকাউন্টে মোট ১৮০ ঘণ্টা ফ্রি GPU কম্পিউট। |
| **Google Colab** | • অন-ডিমান্ড ইন্টারেক্টিভ মডেল এক্সপেরিমেন্টেশন ও ইমার্জেন্সি স্ক্র্যাচপ্যাড এক্সিকিউশন | রিসার্চ সারফেস | অন-ডিমান্ড ফ্রি T4 GPU। |
| **Firebase Hosting** | • React SPA সিঙ্গেল ফ্রন্টএন্ড হোস্টিং (https://supremeai-a.web.app ও https://supremeai-admin.web.app) | Spark Free Tier | গুগল গ্লোবাল এজ সিডিএন ক্যাশিং। |
| **Vercel** | • প্রোডাকশন ফ্রন্টএন্ডের অল্টারনেট মিরর (https://supremeai-lac.vercel.app) | Hobby Free | হাই-স্পিড এজ হোস্টিং। |
| **GitHub Actions / GHCR** | • CI/CD টেস্ট পাইপলাইন, ডকার কন্টেইনার বিল্ড ও GHCR কন্টেইনার রেজিস্ট্রি | GitHub Hosted Ubuntu Runners | ২০০০ ফ্রি মিনিট/মাস ও ফ্রি কন্টেইনার হোস্টিং। |

---

## 2. Multi-Model AI Inference Fleet (-Cost Muscle)

| AI প্রোভাইডার | মডেলসমূহ | মূল ভূমিকা |
|---|---|---|
| **Google Gemini API** | gemini-2.0-flash, gemini-1.5-flash, gemini-1.5-pro | দ্রুত চ্যাট, লং-কনটেক্সট এবং মাল্টিমোডাল/ইমেজ প্রসেসিং। |
| **Groq Cloud** | llama-3.3-70b-versatile, llama-3.1-8b-instant, mixtral-8x7b-32768 | আল্ট্রা-ফাস্ট (৮০০+ টোকেন/সেকেন্ড) সাব-সেকেন্ড রেসপন্স ও কোড জেনারেশন। |
| **Mistral AI** | mistral-small-latest, codestral-latest | ডিফেন্সিভ কোডিং, সিনট্যাক্স ভেরিফিকেশন ও লজিক্যাল রিজনিং। |
| **GitHub Models** | gpt-4o, claude-3.5-sonnet, o1-mini | ক্রিটিক্যাল আর্কিটেকচারাল রিজনাল ডিসিশন ও ডিপ কোড রিভিউ। |
| **OpenRouter** | deepseek-v3, qwen-2.5-coder, meta-llama | মাল্টি-মডেল গ্লোবাল ফলব্যাক হাব। |
| **Cloudflare Workers AI** | @cf/meta/llama-3.1-8b-instruct | সার্ভারলেস এজ ইনফারেন্স। |
| **Ollama (Local/Node)** | llama3, deepseek-r1, qwen | লোকাল অফলাইন ইনফারেন্স ব্যাকআপ। |

---

## 3. Databases, Vector Memory & Cache Mesh

| সার্ভিস | টেকনোলজি | সুপ্রিমএআই-এ ভূমিকা |
|---|---|---|
| **Supabase (Singapore)** | Managed PostgreSQL + pgvector | মূল রিলেশনাল স্টেট, ইউজার অথেন্টিকেশন এবং i_memory (চিরন্তন ভেক্টর মেমোরি)। |
| **Qdrant Cloud** | Cloud Native Vector Search | ডকুমেন্ট সার্চ, নলেজ এমবেডিংস এবং সেমান্টিক ডকুমেন্ট ক্যাশ। |
| **Upstash Redis** | Serverless REST Redis | গ্লোবাল রেট-লিমিটিং, সেশন স্টেট, এবং রিয়েলটাইম পাব-সাব ইভেন্ট বাস। |
| **Firebase Firestore** | NoSQL Document DB | ব্যাকআপ স্টেট এবং রিয়েলটাইম কনফিগারেশন স্টোর। |

---

## 4. Security, Secrets & Vulnerability Gates

| সার্ভিস | ভূমিকা |
|---|---|
| **Infisical Cloud** | সেন্ট্রালাইজড মেশিন আইডেন্টিটি সিক্রেট ম্যানেজার (Primary Vault) — রানটাইমে সব কী অটো-সিন্ক হয়। |
| **Google Cloud KMS** | কী-ম্যানেজমেন্ট ও সিমেট্রিক এনক্রিপশন রিং (supremeai-a-prod-ring)। |
| **TruffleHog** | সিআই পাইপলাইনে কমিট হিস্ট্রি থেকে সিক্রেট লিক শনাক্তকারী। |
| **Trivy (Aqua Security)** | ডকার ইমেজ ও ওএস প্যাকেজের CRITICAL/HIGH ভালনারেবিলিটি ব্লকার। |

---

## 5. Web Intelligence, Automation & Scraping

| সার্ভিস | ভূমিকা |
|---|---|
| **Firecrawl API** | জটিল ওয়েব পেজ ও ডকসকে ক্লিন LLM-ফ্রেন্ডলি মার্কডাউনে কনভার্ট করে। |
| **OpenHands / Browserless** | হেডলেস ক্রোম ব্রাউজার অটোমেশন, ইন্টারেকশন ও এন্ড-টু-এন্ড রেন্ডারিং। |
| **RouteMe API** | ট্রাফিক ডায়নামিক অপটিমাইজেশন ও গ্লোবাল রাউটিং মেজারমেন্ট। |

---

## 6. Observability, Monitoring & Alerts

| সার্ভিস | ভূমিকা |
|---|---|
| **Sentry** | সেন্ট্রালাইজড রিয়েলটাইম এরর ট্র্যাকিং ও পারফরম্যান্স ট্রেসিং (APM)। |
| **LaunchDarkly** | ডায়নামিক ফিচার ফ্ল্যাগিং ও রিয়েলটাইম কিল-সুইচ। |
| **Telegram Bot API** | অ্যাডমিন ক্র্যাশ অ্যালার্ট, সিকিউরিটি ওটিপি (OTP) ও রিমোট কনসোল কমান্ড। |
| **Discord Webhook** | সিআই/সিডি পাইপলাইন স্ট্যাটাস ও সিস্টেম ইভেন্ট লগিং। |
| **Resend** | ট্রানজেকশনাল ইমেইল নোটিফিকেশন (ইউজার রেজিস্ট্রেশন, পাসওয়ার্ড রিসেট)। |

---

## 7. Monetization & Payment Gateways

| সার্ভিস | ভূমিকা |
|---|---|
| **Stripe** | ইউজার সাবস্ক্রিপশন, ক্রেডিট টপ-আপ ও বিলিং ওয়েবহুক হ্যান্ডলিং। |

---

## 8. Resilience & Fallback Hierarchy (Zero Downtime Guarantee)

`	ext
               ┌───────────────────────────────┐
               │    USER / CLIENT REQUEST      │
               └──────────────┬────────────────┘
                              ▼
               ┌───────────────────────────────┐
               │ Cloudflare Edge (Worker / AI) │
               └──────────────┬────────────────┘
                              ▼
               ┌───────────────────────────────┐
               │ Render Node 1 (Core Backend)  │
               └───────┬───────────────┬───────┘
                       │               │
      [Fast Inference] ▼               ▼ [Heavy / Batch / Research]
       ┌────────────────────────┐     ┌────────────────────────┐
       │ Primary: Groq / Gemini │     │ Render Worker (Node 2) │
       │ Fallback 1: Mistral    │     │ Kaggle GPU Pool (x6)   │
       │ Fallback 2: GH Models  │     │ Colab Batch Surface    │
       │ Fallback 3: OpenRouter │     └────────────────────────┘
       └──────────────┬─────────┘
                      ▼
       ┌────────────────────────┐
       │ Supabase (pgvector)    │
       │ Persistent Memory Save │
       └────────────────────────┘
`
- **কোনো একক সার্ভিসের বিলুপ্তিতে সুপ্রিমএআই কখনো বিকল হবে না।**
- সমস্ত এনভায়রনমেন্ট ভেরিয়েবল Infisical ও রুট .env-এ কনফিগার করা এবং সিআই টেস্টের মাধ্যমে সার্বক্ষণিক ভ্যালিডেট করা হয়।
