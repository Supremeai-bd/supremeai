# SupremeAI 2.0 — সম্পূর্ণ গাইড (বাংলা)

> **দর্শন:** User দেখে জাদু। Admin হলো ঈশ্বর। System অদৃশ্য। Zero cost, Max performance.

---

## ১. SupremeAI কী?

SupremeAI 2.0 হলো একটি **মাল্টি-ক্লাউড AI অর্কেস্ট্রেশন প্ল্যাটফর্ম** যা:

- **৮+ AI প্রদানকারী** (OpenRouter, Gemini, DeepSeek, Groq, NVIDIA, Ollama) একত্রিত করে
- **স্বয়ংক্রিয় রাউটিং** — সবচেয়ে সস্তা ও দ্রুততম মডেল বেছে নেয়
- **Zero operating cost** — সব ফ্রি-টায়ার সর্বোচ্চ ব্যবহার করে
- **বাংলা ভাষা সাপোর্ট** — সম্পূর্ণ বাংলায় কথা বলা যায়

---

## ২. দ্রুত শুরু (Quick Start)

### প্রয়োজনীয়তা

| Software | সংস্করণ | কাজ |
|----------|---------|-----|
| Python | 3.11+ | Backend runtime |
| Poetry | Latest | Python package manager |
| Node.js | 18+ | Frontend runtime |
| pnpm | Latest | JavaScript package manager |
| Git | Latest | Version control |

### ইন্সটলেশন

```bash
# ১. রিপো ক্লোন করুন
git clone https://github.com/paykaribazaronline/supremeai.git
cd supremeai_2.0

# ২. পরিবেশ প্রস্তুত করুন
python scripts/bootstrap_env.py

# ৩. API key সেটআপ
cp backend/.env.example backend/.env
# backend/.env ফাইল খুলুন এবং আপনার key দিন

# ৪. Backend শুরু
cd backend
poetry install
poetry run uvicorn main:app --reload --port 8000

# ৫. Frontend শুরু (নতুন টার্মিনালে)
cd apps/studio-client
pnpm install
pnpm dev
```

### API Key কোথায় পাবেন?

| Provider | URL | ফ্রি টায়ার |
|----------|-----|-----------|
| OpenRouter | https://openrouter.ai | ✅ $5 ফ্রি |
| Gemini | https://aistudio.google.com | ✅ 15 req/min |
| DeepSeek | https://platform.deepseek.com | ✅ $2 ফ্রি |
| Groq | https://console.groq.com | ✅ 30 req/min |
| Supabase | https://supabase.com | ✅ 500MB DB |
| Upstash | https://upstash.com | ✅ 10k req/day |

---

## ৩. মূল ফিচারসমূহ

### ৩.১ — AI Chat (মূল চ্যাট)

```
ব্যবহার: http://localhost:5173
```

- যেকোনো প্রশ্ন বাংলা বা ইংরেজিতে জিজ্ঞেস করুন
- কোড লিখতে বলুন: "একটি Python ফাংশন লিখো যা ফাইবোনাচি সিরিজ দেয়"
- ব্যাখ্যা চাইতে পারেন: "এই কোডটি বুঝিয়ে দাও"

### ৩.২ — Voice Coder (কণ্ঠস্বর দিয়ে কোড)

```
Endpoint: POST /api/voice/process-audio
WebSocket: ws://localhost:8000/api/voice/ws
```

- মাইক্রোফোনে বলুন: "generate a login form in React"
- Whisper AI আপনার কণ্ঠ বুঝবে
- তাৎক্ষণিক কোড generate হবে

### ৩.৩ — Image to Code (ছবি থেকে কোড)

```
Endpoint: POST /api/tools/image-to-code
```

- UI design screenshot দিন
- GPT-4V বিশ্লেষণ করবে
- React/Tailwind কোড পাবেন

### ৩.৪ — PR Reviewer (কোড রিভিউ)

```
Webhook: POST /api/github/webhook
```

- GitHub PR তৈরি হলে auto-review
- Security scan, bug detection
- PR-এ comment দেয়

### ৩.৫ — Offline Mode

- Internet না থাকলেও কাজ করে
- Ollama দিয়ে local AI ব্যবহার
- Online হলে sync হয়

### ৩.৬ — Collaborative Editor

```
WebSocket: ws://localhost:8000/ws/collab/{doc_id}
```

- একই সময়ে একাধিক user কোড লিখতে পারে
- AI cursor suggestion দেয়

---

## ৪. Admin Panel

### অ্যাক্সেস

```
URL: http://localhost:5173 → Admin বোতামে ক্লিক করুন
Password: .env এ SUPREMEAI_ADMIN_PASSWORD সেট করুন
```

### Admin ট্যাবগুলো

| ট্যাব | কাজ |
|-------|-----|
| **Command Center** | সব কিছুর overview |
| **Cost Auditor** | API খরচ ট্র্যাক |
| **Health Map** | সব provider এর status |
| **User Manager** | User তৈরি/মুছে ফেলা |
| **Rate Limits** 🆕 | প্রতিটি tenant এর limit |
| **Model Router** | কোন মডেল কখন ব্যবহার হবে |
| **Threats** | Security monitoring |
| **CI/CD** | Deployment status |

### 🛡️ Rate Limit ম্যানেজার (নতুন)

Admin → Rate Limits ট্যাবে যান:

```
Billing Tiers:
├── Free       — 20 req/min,  50K tokens/day
├── Starter    — 60 req/min,  200K tokens/day  
├── Pro        — 200 req/min, 1M tokens/day
└── Enterprise — 999 req/min, Unlimited
```

---

## ৫. API Reference (বাংলা)

### Authentication

```bash
# JWT Token নিন
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"firebase_token": "YOUR_TOKEN"}'
```

### Chat API

```bash
# বাংলায় প্রশ্ন করুন
curl -X POST http://localhost:8000/api/generate \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Python দিয়ে একটি সহজ calculator বানাও",
    "task_type": "coding",
    "language": "bn"
  }'
```

### Voice Coder API

```bash
# Audio file দিয়ে কোড জেনারেট করুন
curl -X POST http://localhost:8000/api/voice/process-audio \
  -H "Authorization: Bearer YOUR_JWT" \
  -F "file=@recording.wav"
```

### Style Learner API

```bash
# আপনার repo থেকে coding style শিখুন
curl -X POST http://localhost:8000/api/style/learn \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/path/to/your/project", "language": "python"}'
```

### Diagram to Architecture

```bash
# Architecture diagram থেকে Terraform কোড
curl -X POST http://localhost:8000/api/diagram/generate \
  -H "Authorization: Bearer YOUR_JWT" \
  -F "file=@architecture.png" \
  -F "provider=aws" \
  -F "iac_tool=terraform"
```

### Onboarding API

```bash
# নতুন user setup complete করুন
curl -X POST http://localhost:8000/api/onboarding/complete \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "provider": "openrouter",
    "api_key": "sk-or-...",
    "default_model": "gpt-4o-mini",
    "theme": "dark",
    "language": "bn"
  }'
```

---

## ৬. Database Migration চালানো

```bash
# সব migration একসাথে
cd backend
poetry run python scripts/run_migrations.py

# নির্দিষ্ট migration
poetry run python -c "
from database.supabase_client import db
import pathlib
sql = pathlib.Path('database/migrations/06_referral_system.sql').read_text()
db.client.postgrest.schema('public')
# Supabase Dashboard এ SQL Editor-এ paste করুন
"
```

### Migration ফাইলগুলো

| File | কাজ |
|------|-----|
| `01_initial_schema.sql` | মূল টেবিল তৈরি |
| `02_skills_engine.sql` | Skills সিস্টেম |
| `03_memory_audit.sql` | Memory ও Audit log |
| `04_schema_upgrade.sql` | Full schema upgrade |
| `05_seed_github_repos.sql` | ১০০+ GitHub repo |
| `06_referral_system.sql` | 🆕 Referral ও credit |
| `07_tenant_sso_offline.sql` | 🆕 Multi-tenant + SSO |

---

## ৭. Deployment (Production)

### GCP Cloud Run

```bash
# Docker image build
docker build -t gcr.io/YOUR_PROJECT/supremeai-backend .

# Cloud Run deploy
gcloud run deploy supremeai-backend \
  --image gcr.io/YOUR_PROJECT/supremeai-backend \
  --region asia-south1 \
  --min-instances 0 \
  --max-instances 10 \
  --memory 2Gi \
  --cpu 2 \
  --allow-unauthenticated
```

### Firebase Hosting (Frontend)

```bash
cd apps/studio-client
pnpm build
firebase deploy --only hosting
```

---

## ৮. সমস্যা সমাধান (Troubleshooting)

### সাধারণ সমস্যা

| সমস্যা | সমাধান |
|--------|--------|
| `poetry not found` | `pip install poetry` চালান |
| `SUPABASE_URL not set` | `.env` ফাইল চেক করুন |
| `Connection refused :8000` | Backend চালু আছে কিনা দেখুন |
| `JWT validation failed` | `JWT_SECRET` সেট করুন |
| AI response না আসলে | Health endpoint চেক: `curl localhost:8000/health` |

### Debug Mode

```bash
# Verbose logging
LOG_LEVEL=DEBUG poetry run uvicorn main:app --reload

# Health check
curl http://localhost:8000/health | python -m json.tool
```

---

## ৯. Referral সিস্টেম ব্যবহার

```python
# Referral code তৈরি করুন
POST /api/referral/generate
{"user_id": "user123"}
# Response: {"code": "SUPREME-A1B2C3D4"}

# Share করুন
GET /api/referral/link/SUPREME-A1B2C3D4?platform=whatsapp
# WhatsApp/Telegram/Twitter link পাবেন

# নতুন user signup করলে
POST /api/referral/redeem
{"new_user_id": "newuser456", "code": "SUPREME-A1B2C3D4"}
```

### Reward টায়ার

| টায়ার | Referral | Reward |
|-------|---------|--------|
| Bronze | 1 | $5 credit |
| Silver | 5 | $10 credit |
| Gold | 20 | $25 credit |
| Platinum | 50 | $50 + Stripe payout |

---

_Last Updated: 2026-06-22_  
_Version: SupremeAI 2.0_  
_Language: বাংলা (Bengali)_
