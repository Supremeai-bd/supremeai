# 📝 SupremeAI 2.0 Setup & Installation Guide

সুপ্রিম এআই ২.০ সচল এবং ইনস্টল করার সম্পূর্ণ গাইডলাইন নিচে দেওয়া হলো:

---

## 1️⃣ পূর্বশর্ত ও প্রয়োজনীয় সফটওয়্যার (Prerequisites)
1. **Docker Desktop:** উইন্ডোজের জন্য [Docker Desktop](https://www.docker.com/products/docker-desktop/) ডাউনলোড করে ইনস্টল করুন। ব্যাকগ্রাউন্ডে এটি সচল রাখুন।
2. **Ollama (Local LLM):** অফলাইন ব্যাকআপ বা লোকাল কাজের জন্য [Ollama](https://ollama.com/) ডাউনলোড করে উইন্ডোজ টার্মিনালে `ollama pull qwen:0.5b` বা `ollama pull llama3` দিয়ে প্রয়োজনীয় মডেল ডাউনলোড করুন।

---

## 2️⃣ অ্যাকাউন্ট তৈরি ও API Key সংগ্রহ
নিচের প্ল্যাটফর্মগুলোতে অ্যাকাউন্ট তৈরি করে এপিআই কীগুলো সংগ্রহ করুন:
* **OpenRouter** (openrouter.ai) - ক্লাউড মডেল গেটওয়ে
* **Google AI Studio** (aistudio.google.com) - Gemini API key
* **DeepSeek** (platform.deepseek.com)
* **HuggingFace** (huggingface.co/settings/tokens) - Access Token
* **GitHub** (github.com/settings/tokens) - Classic Token (with repo access)

---

## 3️⃣ এনভায়রনমেন্ট ফাইল (.env) কনফিগারেশন
প্রজেক্টের রুট ডিরেক্টরিতে [.env](file:///c:/Users/n/supremeai/supremeai_2.0/.env) ফাইলে আপনার সংগৃহীত কীগুলো বসান:
```env
ENV=local  # ক্লাউডের জন্য production
OPENROUTER_API_KEY=আপনার_ওপেনরাউটার_কী
GEMINI_API_KEY=আপনার_জেমিনি_কী
DEEPSEEK_API_KEY=আপনার_দীপসিক_কী
HF_API_KEY=আপনার_হাগিংফেস_টোকেন
GITHUB_TOKEN=আপনার_গিথাব_টোকেন

GCP integration-এর জন্য optional variables:
GCP_PROJECT_ID=supremeai-gcp
GCP_REGION=us-central1
GCP_CLOUD_RUN_URL=https://your-cloud-run-url.run.app
GCP_FIRESTORE_COLLECTION=verification_queue
GCP_PUBSUB_TOPIC=supremeai-tasks
GCP_CLOUD_FUNCTION_NAME=processOCR
```

---

## 4️⃣ অ্যাপ্লিকেশন রান করা (Running the App)
প্রজেক্ট ফোল্ডারে টার্মিনাল ওপেন করে নিচের কমান্ডটি রান করুন:
```bash
docker-compose up -d
```
এটি ব্যাকগ্রাউন্ডে আপনার n8n, Flowise এবং মাস্টার সার্ভার চালু করে দেবে।

### 5️⃣ পরীক্ষা ও ভেরিফিকেশন (Testing & Verification)
ভ্যালিডেশন মডিউল ঠিকভাবে কাজ করছে কিনা তা নিশ্চিত করতে নিচের কমান্ডটি রান করুন:
```bash
.venv\Scripts\python -m pytest
```

---

## 6️⃣ ম্যানুয়াল কনফিগারেশন গাইড (Manual Setup Guide)

নিচের প্ল্যাটফর্মগুলো সেটআপ করে ম্যানুয়াল কী-সমূহ [.env](file:///c:/Users/n/supremeai/supremeai_2.0/.env) ফাইলে যুক্ত করুন:

### ১. Multi-Cloud Setup (Railway, Render, GCP Cloud Run)
1. **Render Deployment:**
   - Render ড্যাশবোর্ডে গিয়ে `New Web Service` তৈরি করুন এবং GitHub রিপোজিটরি কানেক্ট করুন।
   - `render.yaml` অনুযায়ী Health check path `/health` সেট করুন এবং `PORT` হিসেবে Render-এর ডাইনামিক পোর্ট ব্যবহার হতে দিন।
2. **Railway Setup:**
   - [Railway.app](https://railway.app) এ `New Project` -> `Deploy from GitHub repo` সিলেক্ট করে ডিপ্লয় করুন এবং ভ্যারিয়েবল সেট করুন।
3. **GCP Cloud Run Setup:**
   - **Step 1: Create GCP Project (Free)**
     ```bash
     gcloud auth login
     gcloud projects create supremeai-gcp --name="SupremeAI GCP"
     gcloud config set project supremeai-gcp
     gcloud services enable run.googleapis.com firestore.googleapis.com cloudfunctions.googleapis.com pubsub.googleapis.com storage.googleapis.com logging.googleapis.com
     ```
   - **Step 2: Deploy to Cloud Run**
     ```bash
     gcloud builds submit --tag gcr.io/supremeai-gcp/supremeai-api
     gcloud run deploy supremeai-api --image gcr.io/supremeai-gcp/supremeai-api --platform managed --region us-central1 --allow-unauthenticated --set-env-vars="ENV=production,GCP_PROJECT_ID=supremeai-gcp"
     ```
4. **Load Balancer Setup (Cloudflare Workers):**
   - Cloudflare Workers ব্যবহার করে একটি ফ্রি লোড ব্যালেন্সার স্ক্রিপ্ট সেটআপ করুন যা ট্রাফিক GCP, Railway, এবং Render এ ডিস্ট্রিবিউট করবে।
5. **Shared State Setup (Supabase & Upstash):**
   - **Supabase (PostgreSQL):** Supabase-এ একটি ফ্রি অ্যাকাউন্ট খুলে কানেকশন ইউআরএল সংগ্রহ করুন।
   - **Upstash (Redis):** Upstash-এ ফ্রি Redis ক্লাস্টার তৈরি করে কুয়েরি কিউ এর জন্য কানেকশন ডিটেইলস সংগ্রহ করুন।

### ২. Telegram Bot (বট কনফিগারেশন)
1. টেলিগ্রামে [@BotFather](https://t.me/BotFather) সার্চ করে স্টার্ট করুন।
2. `/newbot` লিখে আপনার বটের নাম এবং ইউজারনেম দিন।
3. BotFather আপনাকে একটি `HTTP API Token` (যেমন: `123456:ABC-DEF...`) প্রদান করবে।
4. এই টোকেনটি `.env` ফাইলের `TELEGRAM_BOT_TOKEN` ভ্যারিয়েবলে বসান।

### ৩. Discord Bot (ডিসকর্ড বট)
1. [Discord Developer Portal](https://discord.com/developers/applications) এ যান এবং `New Application` তৈরি করুন।
2. বাম পাশের মেনু থেকে `Bot` ট্যাবে ক্লিক করে `Add Bot` সিলেক্ট করুন।
3. **Privileged Gateway Intents** সেকশনে `Presence Intent`, `Server Members Intent`, এবং `Message Content Intent` সচল (ON) করুন।
4. `Reset Token` এ ক্লিক করে বটের টোকেন কপি করুন এবং তা `.env` ফাইলের `DISCORD_BOT_TOKEN` এ বসান।

### ৪. Sentry (এরর মনিটরিং)
1. [Sentry.io](https://sentry.io) এ সাইন-আপ বা লগইন করুন।
2. `Create Project` এ গিয়ে `Python / FastAPI` সিলেক্ট করে নতুন প্রজেক্ট তৈরি করুন।
3. প্রজেক্টের Settings -> `Client Keys (DSN)` সেকশন থেকে আপনার **DSN URL** কপি করুন।
4. এই DSN টি `.env` ফাইলের `SENTRY_DSN` ভ্যারিয়েবলে বসান।

---
*Last Synced with supremeai_1.0 Reusable Options Analysis: 2026-06-20 (Firebase Deployed)*



<!-- Synced with Rule Update: 2026-06-20 (Bangla Pro Tips Rule added) -->

<!-- Synced with Project Status Update: 2026-06-20 (React Studio Client Modularized) -->

<!-- Synced with Backend Optimization Update: 2026-06-20 (Backend production-ready optimized) -->
