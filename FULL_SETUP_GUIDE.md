# 🔱 SupremeAI 2.0 — সম্পূর্ণ সেটআপ গাইড (Full Setup Guide)

SupremeAI 2.0 সচল করতে নিচের ধাপগুলো সম্পন্ন করুন। এখানে লোকাল ও প্রোডাকশন উভয় এনভায়রনমেন্টের জন্য বিস্তারিত গাইড দেওয়া আছে।

---

## 1️⃣ সিস্টেমের পূর্বশর্ত (System Prerequisites)

১. **Python 3.11+** ইনস্টল থাকতে হবে।
২. **Docker Desktop** ইনস্টল ও চালু থাকতে হবে (n8n, Flowise ইত্যাদি ব্যাকগ্রাউন্ডে রান করতে)।
   - [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/) থেকে ডাউনলোড করে ইনস্টল করুন।
৩. **Ollama (শুধুমাত্র লোকাল ডেভেলপমেন্টের জন্য)**:
   - [Ollama for Windows](https://ollama.com/download/windows) ডাউনলোড করে রান করুন।
   - টার্মিনালে লোকাল মডেল নামাতে রান করুন:
     ```bash
     ollama pull llama3
     ```

---

## 2️⃣ এপিআই কী ও অ্যাকাউন্ট তালিকা (API Keys & Cloud Accounts)

নিম্নোক্ত সার্ভিসগুলোতে অ্যাকাউন্ট তৈরি করে এপিআই কী সংগ্রহ করুন:
- **OpenRouter**: [openrouter.ai](https://openrouter.ai/) (ক্লাউড মডেলসমূহের মূল গেটওয়ে)
- **Google AI Studio (Gemini)**: [aistudio.google.com](https://aistudio.google.com/) (ফ্রি টিয়ারের জন্য অত্যন্ত উপযোগী)
- **DeepSeek**: [platform.deepseek.com](https://platform.deepseek.com/)
- **Groq**: [console.groq.com](https://console.groq.com/)
- **Nvidia NIM**: [build.nvidia.com](https://build.nvidia.com/)
- **HuggingFace**: [huggingface.co](https://huggingface.co/)
- **GitHub Classic Token**: [github.com/settings/tokens](https://github.com/settings/tokens) (`repo` পারমিশন সহ)
- **Firecrawl**: [firecrawl.dev](https://www.firecrawl.dev/) (ওয়েব স্ক্র্যাপিং এপিআই)

---

## 3️⃣ এনভায়রনমেন্ট কনফিগারেশন (`.env`)

প্রজেক্টের রুট ডিরেক্টরিতে [.env](file:///c:/Users/n/supremeai/supremeai_2.0/.env) ফাইলটি ওপেন করুন এবং নিচের ভ্যালুগুলো বসিয়ে দিন। 
*(যদি কোনো প্রোভাইডারের একাধিক কী থাকে, তবে কমা `,` দিয়ে পরপর বসিয়ে দিন। সিস্টেম স্বয়ংক্রিয়ভাবে রোটেশন ও ফেইলওভার ম্যানেজ করবে।)*

```env
PORT=8000
HOST=0.0.0.0

# এনভায়রনমেন্ট মোড: 'local' (Ollama ব্যবহার করবে) অথবা 'production' (Ollama ছাড়া সরাসরি ক্লাউড মডেল)
ENV=local

# অ্যাডমিন পাসওয়ার্ড হ্যাশ (default: admin123)
SUPREMEAI_ADMIN_PASSWORD_HASH=8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918

# এপিআই কী-সমূহ (একাধিক কী কমা দিয়ে আলাদা করে দেওয়া যাবে)
OPENROUTER_API_KEY=কী_১,কী_২
GEMINI_API_KEY=কী_১,কী_২
DEEPSEEK_API_KEY=কী_১,কী_২,কী_৩
GROQ_API_KEY=কী_১,কী_২
NVIDIA_API_KEY=কী_১,কী_২
HF_API_KEY=কী_১
FIRECRAWL_API_KEY=কী_১
GITHUB_TOKEN=আপনার_গিথাব_টোকেন
```

---

## 4️⃣ ডিপেনডেন্সি ইনস্টলেশন (Dependencies Installation)

ভার্চুয়াল এনভায়রনমেন্ট সক্রিয় করে সমস্ত প্রয়োজনীয় প্যাকেজ ইনস্টল করুন:
```bash
pip install -r requirements.txt
```
অথবা একবারে সমস্ত মূল ডিপেনডেন্সি ম্যানুয়ালি ইনস্টল করতে:
```bash
pip install openrouter-py huggingface-hub langgraph crewai browser-use playwright chromadb pandas beautifulsoup4 httpx python-telegram-bot discord.py cryptography python-jose[cryptography] bcrypt python-dotenv pyyaml gitpython pygithub docker pytest pydantic-settings fastapi uvicorn loguru
```

---

## 5️⃣ অ্যাপ্লিকেশন রান করা (Running the App)

### ক. লোকাল ডকার সার্ভিসসমূহ চালু করা:
```bash
docker-compose up -d
```
এটি ব্যাকগ্রাউন্ডে **n8n**, **Flowise**, এবং **ChromaDB** রান করে দেবে।

### খ. মাস্টার সার্ভার রান করা:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 6️⃣ ড্যাশবোর্ড অ্যাক্সেস (Dashboard Access)

সার্ভার চালু হওয়ার পর ব্রাউজারে নিচের ইউআরএলগুলোতে ভিজিট করুন:

- 👤 **কাস্টমার পোর্টাল (Customer Portal)**: `http://localhost:8000/`
  - সাধারণ ব্যবহারকারীদের জন্য ক্লিন এবং প্রিমিয়াম চ্যাট উইন্ডো।
- 👑 **অ্যাডমিন কন্ট্রোল সেন্টার (Admin Control Center)**: `http://localhost:8000/admin/dashboard`
  - আপনার অ্যাডমিন পাসওয়ার্ড (`admin123`) দিয়ে লগইন করুন।
  - এখান থেকে সংবিধান রুলস (JSON Rules) রিয়েল-টাইমে আপডেট করা ও ইনস্টল করা স্কিলস দেখা যাবে।

---

## 🧪 সিস্টেমের কার্যকারিতা পরীক্ষা (Testing)

সিস্টেমের সবকিছু ঠিকঠাক কাজ করছে কিনা তা নিশ্চিত করতে টেস্ট স্যুট রান করুন:
```bash
pytest
```
অনুকূল ফলাফলে `23 passed` দেখাবে।
