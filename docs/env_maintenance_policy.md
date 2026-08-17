# SupremeAI 2.0 - Environment & Secret Maintenance Policy (আর্কিটেকচার ডকুমেন্টেশন)

> ⚠️ **এই ফাইলটি আর CI-তে machine-parse করা হয় না।** আগে `scripts/parse_env_policy.py`
> এই ফাইল থেকে key-list scrape করত এবং `secrets_registry.yaml`-এর সাথে সমান্তরাল
> ভাবে চলত — দুটো ফাইল একই environment-এর জন্য ভিন্ন সংখ্যক key বলছিল, কারণ কেউ একটায়
> key যোগ করলে অন্যটা জানত না। এখন **`secrets_registry.yaml`-ই একমাত্র enforced
> single source of truth** (`scripts/audit_env_usage.py`, `scripts/verify_render_env.py`,
> `scripts/verify_infisical_env.py` — সবগুলো CI check এখন শুধু ওই ফাইল পড়ে)। এই
> ডকুমেন্ট এখন শুধু architecture ও rationale বোঝানোর জন্য মানুষের পড়ার প্রবন্ধ —
> নতুন key যোগ করতে `secrets_registry.yaml` (বা `scripts/generate_registry.py`) এডিট করুন।

এই ডকুমেন্টটি SupremeAI 2.0-এর "Hybrid Secret Architecture"-এর নির্দেশিকা — কোন কি (key) কোথায় থাকে তার প্রেক্ষাপট এখানে ব্যাখ্যা করা হলো।

## 🏗️ মূল আর্কিটেকচার (Hybrid Approach)
সিকিউরিটি, স্কেলাবিলিটি এবং মেইনটেইনবিলিটির কথা মাথায় রেখে প্রোজেক্টের সিক্রেটগুলোকে এখন **চারটি স্তরে (Four Tiers)** ভাগ করা হয়েছে:

1. **Firebase Primary Vault (Admin Truth):** অ্যাডমিন প্যানেল এবং ফুল এক্সেসের জন্য সমস্ত সিক্রেট Firebase Firestore (`primary_vault/secrets`) এ এনক্রিপ্টেড অবস্থায় রাখা হয়। এটি সেন্ট্রাল ব্যাকআপ হিসেবেও কাজ করে।
2. **Infisical Vault (App Truth):** সমস্ত API Keys, Database URLs, Tokens, Webhook Secrets ইত্যাদি যা এনভায়রনমেন্ট ভেদে পরিবর্তন হয় না। (Dual DB-এর জন্য Supabase এবং Neon উভয়ের ক্রেডেনশিয়াল এখানে থাকে)।
3. **Environment-Specific `.env` (Local to Service):** শুধুমাত্র সেই সব ভ্যালু যেগুলো সার্ভিস-স্পেসিফিক বা বুটস্ট্র্যাপ করার জন্য অপরিহার্য।
4. **GitHub Actions Repo Secrets Sync:** CI/CD পাইপলাইনের জন্য প্রয়োজনীয় বুটস্ট্র্যাপ ও ডিপ্লয়মেন্ট সিক্রেট (Infisical Token, Render API Key, Vercel Configs) প্রাইমারি এবং মীরর রেপোতে সিঙ্ক্রোনাইজ করা থাকে।

### 🛡️ Dual-Database Architecture (Active-Passive)
সিস্টেমটি এখন ১০০% ফল্ট-টলারেন্ট। **Primary DB** হিসেবে `Supabase (Singapore)` ব্যবহৃত হয় এবং ফেইলওভারের জন্য **Secondary DB** হিসেবে `Neon.tech (Singapore)` কনফিগার করা আছে। Infisical বা `.env`-এ `SUPABASE_DATABASE_URL` এবং `NEON_DATABASE_URL` উভয়ই থাকতে হবে।

---

## 🔒 Category 1: Infisical Vault (Shared Secrets)

যেসব সিক্রেট সব এনভায়রনমেন্টে (বা একাধিক এনভায়রনমেন্টে) **একই ভ্যালু** শেয়ার করে, সেগুলো শুধু Infisical-এ থাকবে। 

**✅ Infisical-এ আপলোড ও যাচাইকৃত সিক্রেটগুলোর পূর্ণাঙ্গ তালিকা (Total: 72 Verified):**
- `ADMIN_AUTHORIZED`
- `ADMIN_EMAILS`
- `ADMIN_NOTIFICATION_EMAIL`
- `ALLOWED_HOSTS`
- `ALLOW_TEST_AUTH_BYPASS`
- `ALLOW_TEST_ORIGIN_BYPASS`
- `API_KEY_SIGNING_SECRET`
- `API_V1_STR`
- `AUTOFIX_AUTHORIZED`
- `CI_WEBHOOK_SECRET`
- `CLOUDFLARE_API_KEY`
- `CLOUDFLARE_EMAIL`
- `CORS_ORIGINS`
- `DISCORD_OTP_WEBHOOK_URL`
- `DISCORD_WEBHOOK_URL`
- `DOCS_PASSWORD`
- `ENCRYPTION_KEY`
- `EXPERIENCE_DB_PATH`
- `FIREBASE_SERVICE_ACCOUNT_JSON`
- `FIRECRAWL_API_KEY`
- `GCP_KMS_KEY_RING`
- `GEMINI_API_KEY`
- `GITHUB_API_TOKEN`
- `GITHUB_CLIENT_ID`
- `GITHUB_PAT_AUTO_FIX`
- `GITHUB_PAT_MODELS`
- `GITHUB_PAT_NILOYJOY7`
- `GITHUB_TOKEN`
- `GROQ_API_KEY`
- `JIT_OTP_SECRET`
- `LAUNCHDARKLY_API_KEY`
- `LOW_MEMORY_MODE`
- `MISTRAL_API_KEY`
- `OPENHANDS_API_KEY`
- `OPENROUTER_API_KEY`
- `PROJECT_NAME`
- `QDRANT_API_KEY`
- `QDRANT_URL`
- `REDIS_URL`
- `RENDER_API_KEY`
- `RENDER_BACKUP_SVC_ID`
- `RENDER_DEPLOY_HOOK_URL`
- `RENDER_PRIMARY_SVC_ID`
- `RESEND_API_KEY`
- `STRIPE_API_KEY`
- `STRIPE_PUBLISHABLE_KEY`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `SUPABASE_ACCESS_TOKEN`
- `SUPABASE_DATABASE_URL`
- `SUPABASE_DATABASE_URL_POOLER`
- `SUPABASE_JWKS_URL`
- `SUPABASE_KEY`
- `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_URL`
- `SUPREMEAI_ADMIN_PASSWORD_HASH`
- `SUPREMEAI_ADMIN_TOTP_SECRET`
- `SUPREMEAI_API_KEY`
- `SUPREMEAI_GITHUB_TOKEN`
- `SUPREMEAI_JWT_SECRET`
- `UPSTASH_REDIS_REST_TOKEN`
- `UPSTASH_REDIS_REST_URL`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`
- `VERCEL_TOKEN`
- `VITE_FIREBASE_API_KEY`
- `VITE_FIREBASE_PROJECT_ID`
- `routeme_api_key`

> [!TIP]
> **কেন?** যদি কোনো API Key রোটেট (পরিবর্তন) করতে হয়, তাহলে শুধু Infisical-এ একবার আপডেট করলেই হবে। কোনো সার্ভিস রি-ডিপ্লয় করার দরকার নেই, Infisical SDK/Agent অটোমেটিক নতুন কি (key) ফেচ করে নেবে।

---

**❓ Missing / Pending Keys in Infisical (ভ্যালু পাওয়া মাত্রই Infisical-এ অ্যাড করতে হবে - Total: 88):**
- `AIDER_API_KEY`
- `ALLOWED_TAKEOVER_TOKENS`
- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`
- `ANDROID_STORE_PASSWORD`
- `ANTHROPIC_API_KEY`
- `APP_STORE_CONNECT_API_KEY_CONTENT`
- `APP_STORE_CONNECT_API_KEY_ID`
- `AUTHORIZED_ADMINS`
- `BHASHA_BATCH_CONCURRENCY`
- `BHASHA_CACHE_TTL_HOURS`
- `BHASHA_MAX_CACHE`
- `BHASHA_MIN_QUALITY`
- `CLINE_API_KEY`
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_WORKERS_API_TOKEN`
- `CLOUDFLARE_ZONE_ID`
- `CODEIUM_API_KEY`
- `CONTINUE_API_KEY`
- `DB_PASSWORD`
- `DEEPSEEK_API_KEY`
- `DISCORD_ALERT_WEBHOOK`
- `DISCORD_BOT_TOKEN`
- `ENCRYPTION_KEYS`
- `GCP_ACCESS_TOKEN`
- `GCP_PROJECT_ID`
- `GCP_PUBSUB_SUBSCRIPTION`
- `GCP_PUBSUB_TOPIC`
- `GCP_SA_KEY`
- `GITHUB_CLIENT_SECRET`
- `GOOGLE_API_KEY`
- `GOOGLE_APPLICATION_CREDENTIALS`
- `GOOGLE_CLOUD_PROJECT`
- `GROQ_API_KEY_DEPLOYMENT_MONITOR`
- `HF_API_KEY`
- `JWT_SECRET`
- `KMS_KEY_NAME`
- `LANGSMITH_API_KEY`
- `LAUNCHDARKLY_AI_CONFIG_KEY`
- `LAUNCHDARKLY_SDK_KEY`
- `LOAD_TEST_TOKEN`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MOONSHOT_API_KEY`
- `NATS_TOKEN`
- `NEO4J_PASSWORD`
- `NEO4J_URI`
- `NEO4J_USER`
- `NETLIFY_AUTH_TOKEN`
- `NVIDIA_API_KEY`
- `OPENAI_API_KEY`
- `ORACLE_CLOUD_API_KEY`
- `PINECONE_API_KEY`
- `PLANDEX_API_KEY`
- `POSTHOG_API_KEY`
- `PYTHAGORA_API_KEY`
- `R2_ACCESS_KEY`
- `R2_SECRET_KEY`
- `RAILWAY_TOKEN`
- `SECRET`
- `SECRET_BACKEND`
- `SECRET_CACHE_TTL`
- `SENDGRID_API_KEY`
- `SENTRY_AUTH_TOKEN`
- `SLACK_BOT_TOKEN`
- `SMTP_PASSWORD`
- `SUPREMEAI_CREDENTIAL_ENC_KEY`
- `SUPREMEAI_EMAIL_PASSWORD`
- `TELEGRAM_BOT_TOKEN`
- `TEST_VAULT_KEY`
- `TOGETHER_API_KEY`
- `TWILIO_AUTH_TOKEN`
- `VERCEL_OIDC_TOKEN`
- `VITE_ADMIN_BACKEND`
- `VITE_API_BASE`
- `VITE_API_BASE_URL`
- `VITE_API_URL`
- `VITE_FIREBASE_APP_ID`
- `VITE_FIREBASE_AUTH_DOMAIN`
- `VITE_FIREBASE_MESSAGING_SENDER_ID`
- `VITE_FIREBASE_STORAGE_BUCKET`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_SUPABASE_URL`
- `VITE_USER_BACKEND`

---

## ⚠️ Category 2: Environment-Specific Keys (Local `.env`)

যেসব সিক্রেট Infisical-এ রাখলে অ্যাপ **ব্রেক** করবে বা যেগুলো এনভায়রনমেন্টের ওপর ভিত্তি করে ডাইনামিক, সেগুলো সার্ভিসের নিজস্ব প্ল্যাটফর্মে বা লোকাল ফাইলে থাকতে হবে।

**✅ এনভায়রনমেন্ট অনুযায়ী আলাদা থাকা সিক্রেটগুলোর পূর্ণাঙ্গ তালিকা:**

### ১. Render Unified Backend (`render.env`)
- `PORT`
- `ENV`
- `NODE_ENV`
- `SERVICE_ROLE` = `unified` (বা `user,admin` ডুয়াল রোল)
- `ALLOWED_HOSTS`
- `CORS_ORIGINS`
- `USER_CORS_ORIGINS`
- `ADMIN_CORS_ORIGINS`
- `SUPREMEAI_USER_BACKEND_URL`
- `SUPREMEAI_ADMIN_BACKEND_URL`
- `CHECKOUT_BASE_URL`
- `CHROMADB_PATH`
- `EXPERIENCE_DB_PATH`
- `OLLAMA_URL`
- `RENDER_DEPLOY_HOOK_URL`
- `INFISICAL_CLIENT_ID`
- `INFISICAL_CLIENT_SECRET`
- `INFISICAL_PROJECT_ID`
- `INFISICAL_TOKEN`
- `SUPREMEAI_ADMIN_PASSWORD_HASH`
- `SUPREMEAI_JWT_SECRET`

### ৩. Render Studio Client (`render-studio-client.env`)
- `PORT`
- `ENV`
- `NODE_ENV`
- `VITE_PRIMARY_BACKEND`
- `VITE_SECONDARY_BACKEND`

### ৪. Vercel Frontend (`vercel.env`)
<!-- বাংলা মন্তব্য: Vercel ক্লাউড বিল্ড প্রসেসের সময় ইনফিসিক্যাল এবং ব্যাকএন্ড কনফিগারের জন্য এই কিগুলো আবশ্যক -->
- `NODE_ENV`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`
- `VITE_PRIMARY_BACKEND`
- `VITE_SECONDARY_BACKEND`
- `INFISICAL_CLIENT_ID`
- `INFISICAL_CLIENT_SECRET`
- `INFISICAL_PROJECT_ID`
- `INFISICAL_ENV`

### ৫. GitHub Actions
- `INFISICAL_PROJECT_ID` — Infisical Project ID *(⚠️ Bootstrap Key: Infisical-এ নয়, GitHub Secrets-এ থাকবে)*
- `INFISICAL_TOKEN` — Infisical Service Access Token *(⚠️ Bootstrap Key: Infisical-এ নয়, GitHub Secrets-এ থাকবে)*
- `INFISICAL_CLIENT_ID` — Infisical Machine Identity Client ID *(⚠️ Bootstrap Key: Infisical-এ নয়, GitHub Secrets-এ থাকবে)*
- `INFISICAL_CLIENT_SECRET` — Infisical Machine Identity Client Secret *(⚠️ Bootstrap Key: Infisical-এ নয়, GitHub Secrets-এ থাকবে)*
- `GITHUB_PAT_AUTO_FIX` — অটোমেটেড স্ক্রিপ্ট বা এআই এজেন্টের মাধ্যমে সিক্রেট আপডেট করার PAT *(⚠️ এটি Infisical-এ নয়, GitHub Secrets-এ থাকবে)*
- `RENDER_API_KEY` — Render Account API Token *(CI-তে live env verifier & deploy validation-এর জন্য GitHub Repo Secrets-এ সেট করতে হবে)*
- `FIREBASE_SERVICE_ACCOUNT_SUPREMEAI_A` — Firebase Hosting CI Deploy Service Account JSON
- `GCP_SA_KEY` — Google Cloud Platform Service Account Key
- `GCP_PROJECT_ID` — GCP প্রজেক্ট ID
- `SENTRY_AUTH_TOKEN` — Sentry Error Monitoring Upload Token


---

## 🚀 নতুন সিক্রেট অ্যাড করার নিয়ম (Workflow)

যখনই প্রোজেক্টে নতুন কোনো API Key বা Secret অ্যাড করার প্রয়োজন হবে, তখন নিচের ফ্লো অনুসরণ করতে হবে:

1. **যাচাই করুন:** সিক্রেটটি কি সব জায়গায় একই? (যেমন: `NEW_AI_API_KEY`)
   - **হ্যাঁ:** সরাসরি Infisical ড্যাশবোর্ডে গিয়ে `prod` এবং `dev` এনভায়রনমেন্টে অ্যাড করে দিন। লোকাল `.env`-এ অ্যাড করার দরকার নেই।
   - **না:** এটি কি সার্ভার-স্পেসিফিক? (যেমন: `NEW_SERVER_PORT`) তাহলে এটি Infisical-এ অ্যাড করবেন না। যে যে সার্ভিসের জন্য প্রযোজ্য, শুধু তাদের `envs/` ফাইলে আপডেট করুন এবং ঐ নির্দিষ্ট ক্লাউড প্ল্যাটফর্মের (Render/Vercel) সেটিংসে গিয়ে ভ্যালু অ্যাড করুন।

2. **Group 2 Prevention Rule:** কখনোই লোকাল রুট `.env` ফাইলটি সরাসরি কপি-পেস্ট করে Infisical-এ ইমপোর্ট করবেন না। এতে লোকাল `PORT` বা `NODE_ENV=development` প্রোডাকশনে চলে যেতে পারে।

> [!WARNING]
> **Strict Restriction:** 
> `PORT`, `NODE_ENV`, `INFISICAL_*` — এই প্রিফিক্স/নামের কোনো ভেরিয়েবল কখনোই Infisical Vault-এর ভেতরে সেভ করা যাবে না (কারণ এগুলো সার্ভিস বুটস্ট্র্যাপ করার জন্য ব্যবহার হয়)।

---

## 🤖 AI Agent Auto-Propagation Rule (Rule #1)

অ্যাডমিন বা AI Agent দ্বারা যখনই লোকাল `.env` ফাইলে নতুন কোনো Key অ্যাড করা হবে বা আপডেট করা হবে, তখন AI Agent-কে অবশ্যই স্বয়ংক্রিয়ভাবে (Auto-propagate) তা নিচের এনভায়রনমেন্টগুলোতে সিঙ্ক করে দিতে হবে:

1. **Render Services:** Render API ব্যবহার করে `supremeai-backend-docker` এবং `supremeai-backend-6nwi` সার্ভিসে সিক্রেট আপডেট করা।
2. **Infisical Vault:** `infisical secrets set` ব্যবহার করে `SupremeAI` প্রোজেক্টে পুশ করা।
3. **GitHub Actions:** `GITHUB_PAT_AUTO_FIX` ব্যবহার করে GitHub Secrets-এ (pynacl এনক্রিপশন সহ) পুশ করা।
4. **Firebase Vault:** ফায়ারবেস সার্ভিস অ্যাকাউন্ট ব্যবহার করে Firestore এর `primary_vault/secrets`-এ আপডেট করা।

**পাসওয়ার্ড জেনারেশন রুল:** অ্যাডমিন কর্তৃক জেনারেট করা বা সিস্টেম ইন্টারনাল যেকোনো পাসওয়ার্ড/কি (যেমন: JWT_SECRET, DB_PASSWORD) অবশ্যই `"njel.com.bd"` বা এর হ্যাশ বেস করে তৈরি হতে হবে (যেমন: `NjelComBd_2026_Prod!`)।
