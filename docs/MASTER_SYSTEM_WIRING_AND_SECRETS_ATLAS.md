# SupremeAI Master System Wiring & Canonical Secrets Atlas

> **Repository:** `Supremeai-bd/supremeai`  
> **Topology:** Pure 2-Repository SSOT (`supremeai` + `supremeai-studio`)  
> **SSOT References:** `config/service_registry.yaml`, `scripts/ci/canonical_name_registry.json`, `INFISICAL_VAULT_SECRETS_INVENTORY.md`  
> **Vault Platform:** Infisical Cloud (https://app.infisical.com)  
> **Status:** Live & Production Ready  

---

## ১. এন্ড-টু-এন্ড রিকোয়েস্ট আর্কিটেকচার (End-to-End Request Wiring)

```text
User / External AI Agents
    │
    ├── Cloudflare Edge Proxy & Keep-Warm Mesh (https://supremeai.live)
    │       └── infrastructure/cloudflare-studio-proxy/src/index.js
    │
    ├── Mission Control Cockpit (Studio UI)
    │       └── studio/ → Vercel Origin (https://supremeai-studio.vercel.app)
    │
    ├── MCP Control Tower (Single Door Governed Hub)
    │       └── infrastructure/mcp-control-plane (https://supremeai-mcp-tower.onrender.com)
    │
    └── Direct API Gateway
            └── gateway.service.app:app (https://supremeai-api-ulw0.onrender.com)
                    │
                    ├── Multi-LLM Provider Router (Gemini, Groq, OpenRouter, Anthropic, OpenAI)
                    ├── Redis Cache / Upstash REST Chain
                    ├── Core Decision & Runtime (supremeai-primary)
                    ├── Ephemeral CI Runner (supremeai-ci-runner)
                    └── Persistent Data:
                            ├── Supabase (Postgres & Native Auth)
                            ├── Qdrant (Vector Layer & Long-Term Memory)
                            └── Infisical Vault (Universal Secret Store)
```

---

## ২. মাস্টার সার্ভিস ওয়্যারিং ও ক্যানোনিকাল কি-ম্যাপিং টেবিল (Master Key Map)

নিচে সুপ্রিমএআই-এর প্রতিটি সার্ভিসের রানটাইম পাথ, পোর্ট, ক্যানোনিকাল এনভায়রনমেন্ট ভেরিয়েবল, কোডবেসে থাকা লেগেসি অ্যালিয়াস এবং সংশ্লিষ্ট ওনার ইমেইল অ্যাকাউন্টের সমন্বিত ম্যাপিং দেওয়া হলো:

| Service ID | Render / Platform Name | Runtime Path & Port | Health Check | Canonical Env / Secret Name | Supported Legacy Aliases | Associated Owner Account / Email |
|---|---|---|---|---|---|---|
| **`ci-runner`** | `supremeai-ci-runner` | `scripts/ci/**` | `/health` | `RENDER_CI_RUNNER_SERVICE_ID`<br>`RENDER_CI_RUNNER_API_KEY` | `RENDER_CI_RUNNER_SVC_ID`<br>`RENDER_API_KEY_PAYKARI`, `RENDER_API_KEY_7` | `paykaribazaronline@gmail.com` |
| **`core`** | `supremeai-primary` | `core/` (Port 8080) | `/health`<br>`/health/ready` | `RENDER_CORE_SERVICE_ID`<br>`RENDER_API_KEY_1` | `RENDER_PRIMARY_SVC_ID`, `RENDER_CORE_SVC_ID`<br>`RENDER_API_KEY` | `paykaribazaronline@gmail.com` |
| **`mcp`** | `supremeai-mcp-tower` | `infrastructure/mcp-control-plane/` (Port 3771) | `/health` | `RENDER_MCP_SERVICE_ID`<br>`RENDER_API_KEY_4` | `RENDER_MCP_SVC_ID`<br>`RENDER_API_KEY` | `paykaribazaronline@gmail.com` |
| **`api`** | `supremeai-api` | `gateway/` (Port 8787) | `/healthz`<br>`/readyz` | `RENDER_API_SERVICE_ID`<br>`RENDER_API_KEY_5` | `RENDER_API_SVC_ID`, `RENDER_SVC_ID`<br>`RENDER_API_KEY_API` | `paykaribazaronline@gmail.com` |
| **`brain`** | `supremeai-brain` | `core/services/brain/` (Port 8080) | `/health` | `RENDER_BRAIN_SERVICE_ID`<br>`RENDER_API_KEY_6` | `RENDER_BRAIN_SVC_ID`<br>`RENDER_API_KEY` | `paykaribazaronline@gmail.com` |
| **`scraper`** | `supremeai-browser` | `browser/` (Port 8080) | `/health` | `RENDER_SCRAPER_SERVICE_ID`<br>`RENDER_API_KEY_3` | `RENDER_SCRAPER_SVC_ID`, `RENDER_BROWSER_SERVICE_ID`<br>`RENDER_API_KEY` | `paykaribazaronline@gmail.com` |
| **`worker`** | `supremeai-worker` | `core/services/worker/` (Port 8080) | `/health` | `RENDER_WORKER_SERVICE_ID`<br>`RENDER_API_KEY_2` | `RENDER_WORKER_SVC_ID`<br>`RENDER_API_KEY` | `paykaribazaronline@gmail.com` |
| **`supabase`** | Supabase Cloud | Postgres & Auth | `/auth/v1/health` | `SUPABASE_URL`<br>`SUPABASE_ANON_KEY`<br>`SUPABASE_SERVICE_ROLE_KEY` | `SUPABASE_KEY`<br>`SUPABASE_SERVICE_KEY`<br>`SUPABASE_SECRET_KEY` | `paykaribazaronline@gmail.com`<br>(Project `xtvkltzmberxekoamala`) |
| **`redis`** | Upstash Redis | Upstash REST API | PING / REST | `UPSTASH_REDIS_REST_URL`<br>`UPSTASH_REDIS_REST_TOKEN` | `REDIS_URL`<br>`REDIS_PASSWORD`, `REDIS_TOKEN` | `paykaribazaronline@gmail.com` |
| **`cloudflare`**| Cloudflare Workers | Edge Mesh | `/cf-health`<br>`/cf-keepwarm` | `CLOUDFLARE_WORKERS_API_TOKEN`<br>`CLOUDFLARE_ZONE_ID` | `CLOUDFLARE_API_KEY`<br>`CLOUDFLARE_API_TOKEN` | `paykaribazaronline@gmail.com` |
| **`vault`** | Infisical Cloud | Universal Auth API | `/api/v3/secrets` | `INFISICAL_CLIENT_ID`<br>`INFISICAL_CLIENT_SECRET`<br>`INFISICAL_PROJECT_ID` | `INFISICAL_TOKEN` | `paykaribazaronline@gmail.com` |

---

## ৩. স্ট্যান্ডার্ড অপরিবর্তিত থার্ড-পার্টি কি-সমূহ (External SaaS Keys)

যেসব কি আন্তর্জাতিক স্ট্যান্ডার্ড SDK এবং ফ্রেমওয়ার্ক ডিফল্ট অনুসরণ করে (যেমন OpenAI, Anthropic, Stripe, Sentry), সেগুলোতে কোনো নাম পরিবর্তন করার প্রয়োজন নেই:

| ডোমেন / সার্ভিস | স্ট্যান্ডার্ড সিক্রেট নেম (অপরিবর্তিত থাকবে) | Associated Owner Account | ভূমিকা ও ক্রিটিক্যালিটি |
|---|---|---|---|
| **AI LLM Providers** | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `DEEPSEEK_API_KEY`, `TOGETHER_API_KEY`, `OPENROUTER_API_KEY` | `paykaribazaronline@gmail.com` | মাল্টি-মডেল এলএলএম ফ্যালব্যাক পুল |
| **Vector Database** | `QDRANT_URL`, `QDRANT_API_KEY` | `paykaribazaronline@gmail.com` | লং-টার্ম ভেক্টর মেমোরি ও RAG সার্চ |
| **Payments & Billing** | `STRIPE_API_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` | `paykaribazaronline@gmail.com` | স্ট্রাইপ পেমেন্ট ও সাবস্ক্রিপশন গেটওয়ে |
| **Observability** | `SENTRY_AUTH_TOKEN`, `TELEGRAM_BOT_TOKEN`, `DISCORD_WEBHOOK_URL` | `paykaribazaronline@gmail.com` | অ্যালার্টিং, এরর ট্র্যাকিং ও আউটবাউন্ড নোটিফিকেশন |
| **Core Auth & Security**| `JWT_SECRET`, `ENCRYPTION_KEY`, `SUPREMEAI_ADMIN_PASSWORD_HASH`, `SUPREMEAI_ADMIN_TOTP_SECRET` | System Master Vault | সুপ্রিমএআই প্ল্যাটফর্ম মাস্টার অথ ও সেশন সিকিউরিটি |

---

## ৪. ফায়ারবেস কি-সমূহ: ডিপ্রিকেটেড / ডিঅ্যাক্টিভেটেড সেকশন (Archived for Future Use)

> **পলিসি নোট:** সুপ্রিমএআই বর্তমানে সম্পূর্ণ **Native Auth ও Supabase SSOT**-এ স্থানান্তরিত হয়েছে। তাই ফায়ারবেস এখন সম্পূর্ণ নিষ্ক্রিয়। তবে ভবিষ্যতে কখনো প্রয়োজনে যাতে ব্যবহার করা যায়, সেজন্য ভল্ট বা কনফিগে এগুলো ডিলিট না করে **`ARCHIVED / DISABLED` (কমেন্টেড)** অবস্থায় সংরক্ষণ করা হলো।

| # | Deprecated Key Name | পূর্বের ভূমিকা | Associated Account | বর্তমান স্ট্যাটাস ও আর্কিভ নোট |
|---|---|---|---|---|
| 1 | `VITE_FIREBASE_API_KEY` | Firebase Client Web API Key | `paykaribazaronline@gmail.com` | ⏸️ **ARCHIVED (Disabled)** — Supabase Auth দ্বারা প্রতিস্থাপিত |
| 2 | `VITE_FIREBASE_APP_ID` | Firebase App Identifier | `paykaribazaronline@gmail.com` | ⏸️ **ARCHIVED (Disabled)** — বর্তমানে কোনো ক্লায়েন্ট ব্যবহার করে না |
| 3 | `VITE_FIREBASE_AUTH_DOMAIN` | Firebase Auth Domain | `paykaribazaronline@gmail.com` | ⏸️ **ARCHIVED (Disabled)** — Native JWT/OTP সক্রিয় |
| 4 | `VITE_FIREBASE_MESSAGING_SENDER_ID` | Cloud Messaging Sender ID | `paykaribazaronline@gmail.com` | ⏸️ **ARCHIVED (Disabled)** — পুশ নোটিফিকেশন আপাতত বন্ধ |
| 5 | `VITE_FIREBASE_PROJECT_ID` | Firebase Project Name | `paykaribazaronline@gmail.com` | ⏸️ **ARCHIVED (Disabled)** — Supabase Project SSOT |
| 6 | `VITE_FIREBASE_STORAGE_BUCKET`| Firebase Cloud Storage Bucket | `paykaribazaronline@gmail.com` | ⏸️ **ARCHIVED (Disabled)** — Supabase Storage / R2 প্রস্তুত |
| 7 | `FIREBASE_SERVICE_ACCOUNT_JSON`| Admin SDK Service Account JSON | `paykaribazaronline@gmail.com` | ⏸️ **ARCHIVED (Disabled)** — MCP Tower ও Docker থেকে অপসারিত |
| 8 | `FIREBASE_TOKEN` | CI/CD CLI Deployment Token | `paykaribazaronline@gmail.com` | ⏸️ **ARCHIVED (Disabled)** — ফায়ারবেস হোস্টিং ডিপ্লয় বন্ধ |

---

## ৫. ব্লাস্ট রেডিয়াস ও ডিপ্লয়মেন্ট ইমপ্যাক্ট রুলস (Blast-Radius Rules)

| পরিবর্তন সিনারিও | কোথায় আপডেট করতে হবে | ভেরিফিকেশন টেস্ট |
|---|---|---|
| **Gateway API বদল** | `RENDER_API_SERVICE_ID`, `gateway/Dockerfile`, Cloudflare Worker `API_ORIGIN` | `/healthz`, Edge `/v1` proxy, CORS preflight |
| **CI Runner বদল** | `RENDER_CI_RUNNER_SERVICE_ID`, `RENDER_CI_RUNNER_API_KEY`, `.github/workflows/unified-pipeline.yml` | Tier 2 remote CI execution, attestation log |
| **MCP Control Tower বদল** | `RENDER_MCP_SERVICE_ID`, `infrastructure/mcp-control-plane/render.yaml` | `/health`, SSE/MCP streamable-http handshake |
| **Core API বদল** | `RENDER_CORE_SERVICE_ID`, `core/Dockerfile` | `/health`, `/health/ready`, Supabase DB query |
| **Supabase Secret রোটেশন** | `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY` (Infisical + GitHub Secrets) | RLS query, Token verification |
| **Upstash Redis রোটেশন** | `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` | `redis_ping` REST check |
