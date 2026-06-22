# SupremeAI 2.0 — Getting Started

## English

Welcome to **SupremeAI 2.0** — a multi-cloud AI orchestration platform that aggregates 8+ AI providers, routes tasks intelligently, and maximizes free-tier utilization to achieve zero operating cost.

### Prerequisites

- **Python 3.11+** and **Poetry** (backend)
- **Node.js 18+** and **pnpm** (frontend)
- **PostgreSQL** with Supabase (or managed equivalent)
- **Redis** (Upstash or self-hosted)
- **Git** (for cloning and hooks)

### Quick Start

```bash
# 1. Clone repository
git clone https://github.com/paykaribazaronline/supremeai.git
cd supremeai

# 2. Bootstrap environment
python scripts/bootstrap_env.py

# 3. Configure backend
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys

# 4. Install dependencies
cd backend && poetry install && cd ../apps/studio-client && pnpm install

# 5. Run migrations
cd ../../backend
poetry run python scripts/run_migrations.py

# 6. Start development servers
# Backend (terminal 1):
cd backend && poetry run uvicorn main:app --reload

# Frontend (terminal 2):
cd apps/studio-client && pnpm dev
```

### API Key Setup

1. Obtain keys from: OpenRouter, Gemini, DeepSeek, Groq, NVIDIA, Firecrawl
2. Add to `backend/.env`:
   ```
   OPENROUTER_API_KEY=sk-or-...
   GEMINI_API_KEY=AIza...
   ```
3. Verify via `/health` endpoint:
   ```bash
   curl http://127.0.0.1:8000/health
   ```

### Git Hooks (Pre-commit AI Gate)

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

---

## Bengali (বাংলা)

**সুপ্রেম AI 2.0** -এ স্বাগতম। এটি একটি মাল্টি-ক্লাউড AI অ্যারেস্ট্রেশন প্ল্যাটফর্ম যা ৮+ AI প্রদানকারীর একটি একক ইন্টারফেস প্রদান করে।

### প্রয়োজনীয়তা

- **Python 3.11+** এবং **Poetry** (ব্যাকেন্ড)
- **Node.js 18+** এবং **pnpm** (ফ্রন্টএন্ড)
- **PostgreSQL** (Supabase বা কোনো প্রম্যানেজড পরিবর্তন)
- **Redis** (Upstash বা স্ব-হোস্টেড)
- **Git**

### দ্রুত শুরু

```bash
# ১. রিপোজিটরি ক্লোন করুন
git clone https://github.com/paykaribazaronline/supremeai.git
cd supremeai

# ২. এনভায়রনমেন্ট বুটস্ট্র্যাপ
python scripts/bootstrap_env.py

# ৩. ব্যাকেন্ড কনফিগার করুন
cp backend/.env.example backend/.env
# আপনার API কী斋ের সাথে backend/.env এডিট করুন

# ৪. ডিপেন্ডেন্সি ইন্সটল
cd backend && poetry install && cd ../apps/studio-client && pnpm install

# ৫. মাইগ্রেশন চালান
cd ../../backend
poetry run python scripts/run_migrations.py

# ৬. ডেভসার্ভার চালু করুন
# ব্যাকেন্ড (টার্মিনাল ১):
cd backend && poetry run uvicorn main:app --reload

# ফ্রন্টএন্ড (টার্মিনাল ২):
cd apps/studio-client && pnpm dev
```

### API Key সেটআপ

1. OpenRouter, Gemini, DeepSeek, Groq, NVIDIA, Firecrawl থেকে Key নিন
2. `backend/.env` ফাইলে যোগ করুন:
   ```
   OPENROUTER_API_KEY=sk-or-...
   GEMINI_API_KEY=AIza...
   ```
3. `/health` এন্ডপয়েন্ট দিয়ে যাচাই:
   ```bash
   curl http://127.0.0.1:8000/health
   ```

### প্রি-কমিট গিট হুক

```bash
# হুক ইন্সটল
pip install pre-commit
pre-commit install

#ony  
pre-commit run --all-files
```
