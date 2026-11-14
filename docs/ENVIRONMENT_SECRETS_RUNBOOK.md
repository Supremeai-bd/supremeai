# SupremeAI Master Environment Variables & Secrets Runbook

> **Version:** 2.5.0-SSOT  
> **Target Platforms:** Render (`supremeai-api`), Cloudflare Pages (`supremeai-studio`), Supabase, Upstash Redis, GitHub Actions  
> **Security Classification:** Confidential / DevOps Runbook  

---

## 1. Executive Summary & Security Doctrine

SupremeAI operates on a **Local-First, Cloud-Optional** and **Zero-Trust Federation** architecture:
1. **Never Expose Admin Secrets in Client Bundles:** Variables prefixed with `VITE_` or deployed to static CDNs (like Cloudflare Pages) are compiled directly into public JavaScript bundles. Secrets such as `ADMIN_PASSKEY`, `GITHUB_TOKEN`, `RENDER_API_TOKEN`, and `DATABASE_URL` **must strictly reside on the Render Backend (`supremeai-api`) or Infisical Vault**.
2. **Same-Origin Reverse Proxy:** Cloudflare Pages proxies all `/api/*` traffic to the upstream Render backend via Cloudflare Pages Functions (`functions/api/[[path]].ts`). This prevents cross-origin CORS issues and ad-blocker false positives while masking internal backend topology.
3. **Graceful Multi-Tier Fallback:** If cloud provider keys (Gemini, Kaggle, Upstash) fail, the system falls back gracefully without crashing or corrupting state.

---

## 2. Platform-by-Platform Configuration Matrix

### 2.1 Render Dashboard — Web Service: `supremeai-api`
Navigate to: **Render Dashboard ➔ `supremeai-api` ➔ Environment**

| Environment Variable | Recommended Value / Format | Purpose | Mandatory? |
|---|---|---|---|
| `GITHUB_TOKEN` | `ghp_xxxxxxxxxxxxxxxxxxxx` | Accesses GitHub REST API for pipeline runs, reruns, PR review approvals, and auto-merge. | **YES (Critical for GitOps)** |
| `GITHUB_REPO` | `Supremeai-bd/supremeai` | Monorepo target for GitHub workflow and PR operations. | **YES** |
| `RENDER_API_TOKEN` | `rnd_xxxxxxxxxxxxxxxxxxxx` | Render account API key used to trigger service reboots and query deployment status. | **YES (For Node Reboots)** |
| `ADMIN_PASSKEY` | `<your-secure-admin-passkey>` | Master passkey verified by backend `/api/admin/auth/verify` for admin dashboard login. | **YES (Security)** |
| `DATABASE_URL` | `postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres` | Primary Supabase PostgreSQL connection with pgvector and RLS support. | **YES (Persistence)** |
| `SUPABASE_URL` | `https://[ref].supabase.co` | Supabase API endpoint for Auth and Storage. | **YES** |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJhbGciOi...` | High-privilege service key bypassing RLS for administrative operations. | **YES** |
| `UPSTASH_REDIS_REST_URL` | `https://[instance].upstash.io` | Upstash Redis REST URL for distributed caching, token bucket rate limits, and task queues. | **YES (Rate Limits & Queues)** |
| `UPSTASH_REDIS_REST_TOKEN` | `Axxxxxxxxxxxxxxxxxxxx...` | Upstash Redis authentication token. | **YES** |
| `GEMINI_API_KEY` | `AIzaSyxxxxxxxxxxxxxxxxx` | Google GenAI SDK key for chat reasoning, multimodal analysis, and neural TTS. | **YES (Primary AI)** |
| `GROQ_API_KEY` | `gsk_xxxxxxxxxxxxxxxxxxx` | Ultra-low latency inference engine (Llama-3 / Mixtral fallback). | **Recommended** |
| `OPENAI_API_KEY` | `sk-proj-xxxxxxxxxxxxxx` | Fallback LLM provider for GPT-4o / O3 tasks. | **Optional** |
| `ANTHROPIC_API_KEY` | `sk-ant-xxxxxxxxxxxxxxx` | Claude 3.7 Sonnet provider key for deep code analysis. | **Optional** |
| `TELEGRAM_BOT_TOKEN` | `123456789:ABCdef...` | Telegram bot token for real-time mobile incident alerts and HITL verification. | **Optional** |
| `ADMIN_TELEGRAM_CHAT_ID` | `987654321` | Telegram chat ID receiving server alerts. | **Optional** |
| `KAGGLE_USERNAME` | `<kaggle-user-handle>` | Account handle for 180 hrs/wk remote GPU offloading (batch jobs, LoRA fine-tuning). | **Optional** |
| `KAGGLE_KEY` | `<kaggle-api-key>` | Kaggle API key. | **Optional** |
| `INFISICAL_PROJECT_ID` | `<uuid>` | Infisical project ID for automated dynamic secret hydration. | **Optional** |
| `INFISICAL_CLIENT_ID` | `<client-id>` | Infisical machine identity client ID. | **Optional** |
| `INFISICAL_CLIENT_SECRET` | `<secret>` | Infisical machine identity client secret. | **Optional** |
| `INFISICAL_ENV` | `prod` | Infisical environment scope. | **Optional** |

---

### 2.2 Cloudflare Pages — Project: `supremeai-studio`
Navigate to: **Cloudflare Pages Dashboard ➔ `supremeai-studio` ➔ Settings ➔ Environment variables**

> [!IMPORTANT]
> Do **NOT** set secret keys (`ADMIN_PASSKEY`, `DATABASE_URL`, or `GITHUB_TOKEN`) in Cloudflare Pages. These are client-facing and will be visible in web browsers.

| Variable Name | Value | Purpose | Notes |
|---|---|---|---|
| `SUPREMEAI_BACKEND_URL` | `https://supremeai-api-ulw0.onrender.com` | Target upstream origin for Cloudflare Pages edge proxy (`/api/*`). | Recommended to set explicitly. |
| `VITE_USE_MOCK` | `false` | Explicitly disables mock data in all production builds. | Code already auto-disables mock in PROD. |
| `VITE_API_BASE_URL` | *(Leave Empty)* | Same-origin API routing. | **Must remain empty** to avoid cross-domain CORS issues. |
| `VITE_GATEWAY_URL` | `/v1` | Prefix for AI completions gateway. | Default exists in `src/config/env.ts`. |
| `VITE_MCP_TOWER_URL` | `/api/mcp-tower` | Reverse proxy path to MCP Control Tower. | Default exists in `src/config/env.ts`. |
| `VITE_SUPABASE_URL` | `https://auth.supremeai.bd` | Custom auth domain for Supabase Client. | Default exists in `src/config/env.ts`. |

---

### 2.3 Backend Local Development (`f:\supremeai\.env`)
Create or update your local `f:\supremeai\.env` for local testing:

```ini
# Core Server Configuration
PORT=8000
HOST=0.0.0.0
ENVIRONMENT=development
LOG_LEVEL=INFO

# Security & Passkey Authentication
ADMIN_PASSKEY=admin_local_secret_2026
JWT_SECRET=super_secret_jwt_key_local_only

# GitHub GitOps Control Plane
GITHUB_TOKEN=ghp_yourPersonalAccessTokenHere
GITHUB_REPO=Supremeai-bd/supremeai

# Render Cloud API
RENDER_API_TOKEN=rnd_yourRenderApiTokenHere

# Storage & Persistence (Supabase)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/supremeai_local
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key

# Distributed Cache & Queues (Upstash Redis)
UPSTASH_REDIS_REST_URL=https://your-redis-instance.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-upstash-token

# AI Model Squad
GEMINI_API_KEY=AIzaSyYourGeminiKey
GROQ_API_KEY=gsk_YourGroqKey
OPENAI_API_KEY=sk-proj-YourOpenAIKey

# Omnichannel Alerts
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
ADMIN_TELEGRAM_CHAT_ID=your-telegram-chat-id
```

---

## 3. How to Obtain the Critical API Keys

### 3.1 GitHub Personal Access Token (PAT)
1. Go to: **GitHub Settings ➔ Developer Settings ➔ Personal access tokens ➔ Fine-grained tokens** (or Tokens Classic).
2. Click **Generate new token**.
3. Set Token Name: `SupremeAI Control Plane`.
4. Select Repository: `Supremeai-bd/supremeai`.
5. Permissions required:
   - **Actions:** Read and write (to trigger reruns and cancel workflow runs).
   - **Pull requests:** Read and write (to approve and merge PRs).
   - **Contents:** Read and write.
6. Copy the token and paste it into Render Environment as `GITHUB_TOKEN`.

### 3.2 Render API Token
1. Log in to **Render Dashboard** (`dashboard.render.com`).
2. Click your profile avatar (top right) ➔ **Account Settings**.
3. Scroll down to **API Keys**.
4. Click **Create API Key**, label it `SupremeAI-Admin-Automation`, and copy the token.
5. Paste it into Render Environment as `RENDER_API_TOKEN`.

### 3.3 Upstash Redis REST Token
1. Log in to **Upstash Console** (`console.upstash.io`).
2. Open your Redis database cluster.
3. Scroll to **REST API** section.
4. Copy `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN`.
5. Paste them into Render Environment.

### 3.4 Supabase Service Role Key & Connection String
1. Log in to **Supabase Dashboard** (`app.supabase.com`).
2. Go to **Project Settings ➔ API**.
3. Copy **Project URL** (`SUPABASE_URL`) and **`service_role` secret** (`SUPABASE_SERVICE_ROLE_KEY`).
4. Go to **Project Settings ➔ Database ➔ Connection string (URI)**.
5. Copy the Postgres URI (Port 5432) as `DATABASE_URL`.

---

## 4. Verification & Validation Protocol

After updating environment variables:

1. **Trigger Redeployment on Render:**
   In Render Dashboard ➔ `supremeai-api`, click **Manual Deploy ➔ Deploy latest commit** to ensure new environment variables are loaded into the running container.

2. **Run Smoke Verification from Frontend Repo:**
   ```bash
   cd f:\supremeai-frontend
   node scripts/smoke-live.mjs
   ```
   **Expected Output:**
   ```text
   200 /api/health
   200 /api/platform/config
   200 /api/mcp-tower/services
   200 /api/v1/hitl/pending
   200 /api/v1/stream/hitl
   ```

3. **Verify GitOps & PR Control:**
   Open `https://supremeai-studio.pages.dev/?tab=github-pipeline`.
   - Ensure the red `⚠ GITHUB_TOKEN not configured` badge disappears.
   - Verify that workflow runs load with status badges.
   - Test the `Rerun Failed` or `Approve PR` buttons.

4. **Verify Dynamic Architecture Mesh:**
   Open `https://supremeai-studio.pages.dev/?tab=architecture-map`.
   - Confirm that all 15 nodes (Render Services, Supabase, Redis, Kaggle, Infisical, AI Squad) display **🟢 Healthy**.
   - If any service is broken, confirm that it glows **🔴 Red** with the animated pulse badge.

---

*Authored by Antigravity Agentic Assistant on 2026-11-15 for SupremeAI Operations.*
