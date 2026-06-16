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

---
*Last Synced with Missing Skills, Dependencies & Tools Analysis: 2026-06-17*

