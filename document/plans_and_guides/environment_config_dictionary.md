# 🔑 Environment Configuration Dictionary

সুপ্রিম এআই ২.০ (SupremeAI 2.0) প্রজেক্টের কনফিগারেশনের জন্য ব্যবহৃত প্রতিটি এনভায়রনমেন্ট ভ্যারিয়েবল এবং `.env` ফাইলের কী-গুলোর বিস্তারিত বিবরণ নিচে দেওয়া হলো:

## ১. কোর সিস্টেম ভ্যারিয়েবল (Core Configuration)

| Variable Name | Default Value | Options | Description |
| :--- | :--- | :--- | :--- |
| `ENV` | `local` | `local`, `production` | প্রজেক্টটি লোকাল কম্পিউটারে রান হচ্ছে নাকি লাইভ সার্ভারে তা নির্ধারণ করে। |
| `PROJECT_NAME` | `SupremeAI` | Any String | গেটওয়ে এবং এপিআই প্রজেক্টের নাম। |
| `API_V1_STR` | `/api/v1` | URL Path | এপিআই রুট রাউটিং প্রিফিক্স। |

---

## ২. ক্লাউড এআই গেটওয়ে ও এপিআই কী (AI Providers API Keys)

এই কী-গুলো প্রজেক্টের বুদ্ধিমত্তা এবং রিমোট মডেল অ্যাক্সেস করার জন্য ব্যবহৃত হয়:

* **`OPENROUTER_API_KEY`**: OpenRouter গেটওয়ের মাধ্যমে ১০০+ মডেল (যেমন Claude, Llama 3) অ্যাক্সেস করার টোকেন।
* **`GEMINI_API_KEY`**: গুগল এআই স্টুডিওর জেমিনি মডেল ব্যবহারের ডিরেক্ট কী।
* **`DEEPSEEK_API_KEY`**: ডিপসিক প্ল্যাটফর্মের এপিআই টোকেন।
* **`HF_API_KEY`**: HuggingFace ওপেন সোর্স মডেলসমূহ ফ্রিতে ব্যবহারের সিকিউরিটি এক্সেস টোকেন।
* **`OLLAMA_URL`**: লোকাল ওলামা সার্ভারের এড্রেস (ডিফল্ট: `http://localhost:11434`)।

---

## ৩. ইন্টিগ্রেশন ও ডেভেলপমেন্ট ভ্যারিয়েবল (Integration Tokens)

* **`GITHUB_TOKEN`**: কোডবেজ রিড/রাইট করা ও গিট নলেজ এক্সট্র্যাক্টরের জন্য ক্লাসিক গিটহাব টোকেন।
* **`SENTRY_DSN`**: লাইভ প্রোডাকশনে বাফারিং ও সিস্টেম এরর মনিটর ও সেন্ড করার লিংক।
* **`TELEGRAM_BOT_TOKEN`**: মেসেজিং ইন্টারফেস এবং নোটিফিকেশন এলার্ট পাঠানোর জন্য বটের এপিআই কী।
* **`HALLUCINATION_DB_PATH`**: SQLite DB path for logging AI mistakes (default: `hallucination_patterns.db`)।

## ৪. মাল্টি-ক্লাউড ডিস্ট্রিবিউশন ভ্যারিয়েবল (Multi-Cloud Distribution Config)

* **`GCP_REGION`**: গুগল ক্লাউড ডেপ্লয়মেন্ট রিজিয়ন (যেমন: `us-central1`)।
* **`GCP_PROJECT_ID` / `GOOGLE_CLOUD_PROJECT`**: GCP project ID; Firestore, Pub/Sub এবং Cloud Functions path তৈরি করতে ব্যবহৃত হয়।
* **`GCP_REGION`**: GCP deployment region (default: `us-central1`)।
* **`GCP_SERVICE_NAME`**: Cloud Run service name (default: `supremeai-api`)।
* **`GCP_CLOUD_RUN_URL`**: গুগল ক্লাউড রানের হোস্ট URL যা ট্রাফিকের ৪০% প্রসেস করে।
* **`GCP_FIRESTORE_COLLECTION`**: Firestore verification queue collection name (default: `verification_queue`)।
* **`GCP_FIRESTORE_SQLITE_PATH`**: Firestore unavailable হলে local SQLite fallback DB path।
* **`GCP_PUBSUB_TOPIC`**: Pub/Sub topic name (default: `supremeai-tasks`)।
* **`GCP_PUBSUB_SUBSCRIPTION`**: Pub/Sub subscription name (default: `<topic>-sub`)।
* **`GCP_PUBSUB_SQLITE_PATH`**: Pub/Sub unavailable হলে local SQLite fallback DB path।
* **`GCP_CLOUD_FUNCTION_NAME`**: Cloud Functions function name, example `processOCR`।
* **`GCP_CLOUD_FUNCTION_URL`**: Optional full Cloud Functions trigger URL override।
* **`GCP_CLOUD_FUNCTION_BEARER_TOKEN`**: Optional IAM bearer token for protected Cloud Functions।
* **`RAILWAY_URL`**: রেলওয়ে সার্ভারের হোস্ট URL যা ট্রাফিকের ৩৫% প্রসেস করে।
* **`RENDER_URL`**: রেন্ডার ফ্রি সার্ভারের হোস্ট URL যা ট্রাফিকের ২৫% প্রসেস করে.
* **`SUPABASE_DATABASE_URL`**: শেয়ার্ড স্টেট ডাটাবেস হিসেবে ব্যবহৃত সুপাবেস পোস্টগ্রেস কানেকশন স্ট্রিং।
* **`UPSTASH_REDIS_URL`**: শেয়ার্ড মেসেজ ও কুয়েরি কিউ হিসেবে ব্যবহৃত আপস্ট্যাশ রেডিস কানেকশন ইউআরএল।

---
*Last Synced with supremeai_1.0 Reusable Options Analysis: 2026-06-20 (Firebase Deployed)*


<!-- Synced with Rule Update: 2026-06-20 (Bangla Pro Tips Rule added) -->

<!-- Synced with Project Status Update: 2026-06-20 (React Studio Client Modularized) -->

<!-- Synced with Backend Optimization Update: 2026-06-20 (Backend production-ready optimized) -->
