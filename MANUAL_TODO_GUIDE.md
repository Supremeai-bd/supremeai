# 📝 Manual Setup TODO List & Guide

SupremeAI 2.0 সচল করতে নিচের কাজগুলো ধাপে ধাপে সম্পন্ন করুন:

---

## 1️⃣ Docker Desktop ইনস্টলেশন
- **লিংক:** [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
- **গাইড:** 
  1. লিংক থেকে ইনস্টলার ডাউনলোড করে ইনস্টল করুন।
  2. ইনস্টল শেষে পিসি রিস্টার্ট দিন।
  3. Docker Desktop চালু করে ব্যাকগ্রাউন্ডে রান রাখুন।

---

## 2️⃣ Ollama লোকাল মডেল সেটআপ (শুধুমাত্র Local Deployment-এর জন্য)
- **লিংক:** [Ollama for Windows](https://ollama.com/download/windows)
- **নোট:** প্রোডাকশন (Production) এনভায়রনমেন্টে Ollama-এর প্রয়োজন নেই, সেখানে সরাসরি ক্লাউড এপিআই (যেমন OpenRouter) ব্যবহার করা হবে।
- **গাইড:**
  1. Ollama ডাউনলোড করে ইনস্টল করুন।
  2. উইন্ডোজ টার্মিনাল/পাওয়ারশেল (PowerShell) ওপেন করুন।
  3. Llama 3 মডেলটি ডাউনলোড করতে এই কমান্ডটি রান করুন:
     ```bash
     ollama pull llama3
     ```

---

## 3️⃣ এপিআই কী ও অ্যাকাউন্ট তৈরি (API Keys Setup - Local & Production)
নিচের সাইটগুলোতে গিয়ে অ্যাকাউন্ট তৈরি করুন এবং API Key সংগ্রহ করুন (মাল্টিপল ব্যাকআপ অপশনের জন্য এগুলো সাহায্য করবে):

* **OpenRouter API Key**
  - **লিংক:** [openrouter.ai](https://openrouter.ai/)
  - **গাইড:** সাইনআপ করে Dashboard > Keys থেকে একটি নতুন কী জেনারেট করুন।
* **Google AI Studio (Gemini) API Key**
  - **লিংক:** [aistudio.google.com](https://aistudio.google.com/)
  - **গাইড:** Get API key তে ক্লিক করে একটি নতুন কী তৈরি করুন। (ফ্রি টিয়ারে চমৎকার স্পিড দেয়)।
* **DeepSeek API Key**
  - **লিংক:** [platform.deepseek.com](https://platform.deepseek.com/)
  - **গাইড:** API Keys সেকশন থেকে নতুন কী জেনারেট করুন।
* **HuggingFace Access Token**
  - **লিংক:** [huggingface.co](https://huggingface.co/)
  - **গাইড:** প্রোফাইল পিকচারে ক্লিক করে Settings > Access Tokens > New Token তৈরি করুন।
* **GitHub Classic Token**
  - **লিংক:** [github.com/settings/tokens](https://github.com/settings/tokens)
  - **গাইড:** Generate new token (classic) এ ক্লিক করে `repo` পারমিশন দিয়ে টোকেন তৈরি করুন।

---

## 4️⃣ এনভায়রনমেন্ট ফাইল (.env) কনফিগারেশন
- **ফাইল লিংক:** [.env](file:///c:/Users/n/supremeai/supremeai_2.0/.env)
- **গাইড:**
  1. [.env](file:///c:/Users/n/supremeai/supremeai_2.0/.env) ফাইলটি এডিটর দিয়ে ওপেন করুন।
  2. এনভায়রনমেন্ট অনুযায়ী `ENV` ভ্যালু সেট করুন (লোকালের জন্য `local`, প্রোডাকশনের জন্য `production`):
     ```env
     ENV=local  # অথবা production
     ```
  3. আপনার সংগৃহীত এপিআই কীগুলো নিচের ফিল্ডগুলোতে বসিয়ে সেভ করুন:
     ```env
     OPENROUTER_API_KEY=আপনার_আসল_ওপেনরাউটার_কী
     GEMINI_API_KEY=আপনার_আসল_জেমিনি_কী
     DEEPSEEK_API_KEY=আপনার_আসল_দীপসিক_কী
     HF_API_KEY=আপনার_আসল_হাগিংফেস_টোকেন
     GITHUB_TOKEN=আপনার_আসল_গিথাব_টোকেন
     ```

---

## 5️⃣ অ্যাপ্লিকেশন রান করা
সব সেটআপ শেষে প্রজেক্ট ফোল্ডারে টার্মিনাল ওপেন করে প্রজেক্ট রান করুন:
```bash
docker-compose up -d
```
এটি আপনার n8n, Flowise এবং Master Server একসাথে রান করে দেবে।
