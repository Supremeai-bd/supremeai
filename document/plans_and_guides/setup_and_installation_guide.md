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

