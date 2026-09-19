# SupremeAI Cluster & Infrastructure: Master Environment Variables & Deployment Checklist

> **Security & Privacy Notice:** All real secrets, private keys, and live tokens have been masked with safe placeholders (e.g., `<INFISICAL_CLIENT_SECRET>`, `<RENDER_API_KEY_1>`). Actual active credentials reside solely in your protected, git-ignored `.env.clean`, `.env`, and the Infisical Cloud Vault.
>
> **Incident note (#696):** the two `CI_WEBHOOK_SECRET` entries and the Cloudflare `account_id`/`CLOUDFLARE_ACCOUNT_ID` entries below previously carried live values; they are now redacted. Do not re-enter real values in this file — record them in the Infisical vault and, if a value needs documenting, use a placeholder plus a pointer to `docs/security/CREDENTIAL_ROTATION_CHECKLIST.md`. Until the git history is purged (see `docs/security/HS-01-REMEDIATION.md`), old commits still expose pre-rotation values.

---

## 📑 Operational Master Checklist

This document is your **deployment & configuration checklist**. Check off items as they are configured and verified across each platform dashboard.

---

### Phase 1: Core Principles & Safety Gates
- [x] **Single Source of Truth Gate**: 130+ application secrets are verified active inside Infisical Cloud Vault (`prod` environment).
- [x] **Zero Secret Leakage Gate**: No database passwords, AI API keys, private JWT secrets, or Firebase service account JSONs are entered directly into Render or Vercel environment variables.
- [x] **Conflict Prevention Gate**: Node roles (`SUPREMEAI_SERVICE_ROLE`), local ports (`PORT`), and client build-time variables (`VITE_*`) are never placed in Infisical (to prevent cluster role collisions).

---

### Phase 2: Render 4-Node Cluster Checklist

#### 🔲 Node 1: Primary Backend Core Hub
* **Account:** `paykaribazaronline@gmail.com`
* **Service ID:** `srv-dabm7dfqj5pc738jkbmg`
* **Public URL:** `https://<render-primary-url>`
* **Dashboard Path:** Render Dashboard ➔ Node 1 Service ➔ Environment

- [x] **Infisical Universal Auth Connector (Mandatory Bootstrap)**
  - [x] `INFISICAL_PROJECT_ID="<INFISICAL_PROJECT_ID>"`
  - [x] `INFISICAL_CLIENT_ID="<INFISICAL_CLIENT_ID>"`
  - [x] `INFISICAL_CLIENT_SECRET="<INFISICAL_CLIENT_SECRET>"` *(Live updated to active secret)*
  - [x] `INFISICAL_ENV="prod"`
- [x] **Service Role & Networking (Host Direct)**
  - [x] `SUPREMEAI_SERVICE_ROLE="core"` *(Mandatory: Activates FastAPI Core Router)*
  - [x] `PORT="8000"`
  - [x] `WEB_CONCURRENCY="1"`
  - [x] `LOW_MEMORY_MODE="true"`
  - [x] `ENABLE_LEARNING_LOOP="true"`
  - [x] `WORKER_URL="https://<render-worker-url>"`
  - [x] `SCRAPER_URL="https://<render-scraper-url>"`
  - [x] `MCP_URL="https://<render-mcp-url>"`
- [x] **Security & Allowed Origins**
  - [x] `CORS_ORIGINS="https://supremeai-a.web.app,https://supremeai-admin.web.app,https://supremeai-lac.vercel.app,https://supremeai-studio.vercel.app,https://<render-primary-url>,https://<render-worker-url>,https://<render-scraper-url>,https://<render-mcp-url>,https://supremeai-worker.paykaribazaronline.workers.dev"`
  - [x] `ALLOWED_HOSTS="<render-primary-host>,<render-worker-host>,<render-scraper-host>,<render-mcp-host>,supremeai-admin.web.app,supremeai-a.web.app,supremeai-lac.vercel.app"`
  - [x] `ADMIN_CORS_ORIGINS="https://supremeai-admin.web.app"`
  - [x] `USER_CORS_ORIGINS="https://supremeai-a.web.app,https://supremeai-lac.vercel.app,https://supremeai-studio.vercel.app"`
  - [x] `CI_WEBHOOK_SECRET="<REDACTED — rotated value lives in Infisical; see docs/security/CREDENTIAL_ROTATION_CHECKLIST.md>"`
- [x] **Verification**: Core node updated & syncing with Render API (`200 OK`).

---

#### 🔲 Node 2: Worker Processing & Background Task Engine
* **Account:** `niloyjoy7@gmail.com`
* **Service ID:** `srv-dabm7evqj5pc738jkf30`
* **Public URL:** `https://<render-worker-url>`
* **Dashboard Path:** Render Dashboard ➔ Node 2 Service ➔ Environment

- [x] **Infisical Universal Auth Connector (Mandatory Bootstrap)**
  - [x] `INFISICAL_PROJECT_ID="<INFISICAL_PROJECT_ID>"`
  - [x] `INFISICAL_CLIENT_ID="<INFISICAL_CLIENT_ID>"`
  - [x] `INFISICAL_CLIENT_SECRET="<INFISICAL_CLIENT_SECRET>"`
  - [x] `INFISICAL_ENV="prod"`
- [x] **Service Role & Worker Execution Limits**
  - [x] `SUPREMEAI_SERVICE_ROLE="worker"` *(Mandatory: Prevents FastAPI Core Router; activates Task Worker Engine)*
  - [x] `PORT="8000"`
  - [x] `LOW_MEMORY_MODE="true"`
  - [x] `PRIMARY_BACKEND_URL="https://<render-primary-url>"`
  - [x] `TASK_QUEUE_PROVIDER="upstash"`
  - [x] `TASK_QUEUE_CONCURRENCY="5"`
  - [x] `WS_MAX_CONNECTIONS="50"`
  - [x] `WS_MAX_PER_USER="3"`
  - [x] `ZERO_COST_MAX_CONCURRENT="3"`
  - [x] `ZERO_COST_TASK_TIMEOUT="300.0"`
- [x] **Verification**: Worker node synced via Render API (`200 OK`).

---

#### 🔲 Node 3: Dedicated Web Scraper & Headless Browser Node
* **Account:** `ziaulhaquezia01@gmail.com`
* **Service ID:** `srv-dabm7gfqj5pc738jkicg`
* **Public URL:** `https://<render-scraper-url>`
* **Dashboard Path:** Render Dashboard ➔ Node 3 Service ➔ Environment

- [x] **Infisical Universal Auth Connector (Mandatory Bootstrap)**
  - [x] `INFISICAL_PROJECT_ID="<INFISICAL_PROJECT_ID>"`
  - [x] `INFISICAL_CLIENT_ID="<INFISICAL_CLIENT_ID>"`
  - [x] `INFISICAL_CLIENT_SECRET="<INFISICAL_CLIENT_SECRET>"`
  - [x] `INFISICAL_ENV="prod"`
- [x] **Service Role & Browser Specs**
  - [x] `SUPREMEAI_SERVICE_ROLE="scraper"` *(Mandatory: Activates Scraper Router only)*
  - [x] `PORT="8000"`
  - [x] `LOW_MEMORY_MODE="true"`
  - [x] `PRIMARY_BACKEND_URL="https://<render-primary-url>"`
  - [x] `BROWSER_VIEWPORT_WIDTH="1280"`
  - [x] `BROWSER_VIEWPORT_HEIGHT="800"`
  - [x] `ZERO_COST_MAX_CONCURRENT="3"`
  - [x] `ZERO_COST_TASK_TIMEOUT="300.0"`
- [x] **Verification**: Scraper node synced via Render API (`200 OK`).

---

#### 🔲 Node 4: MCP Control Tower & Swarm Gateway
* **Account:** `njelmedia@gmail.com`
* **Service ID:** `srv-dabm7inqj5pc738jkrt0`
* **Public URL:** `https://<render-mcp-url>`
* **Dashboard Path:** Render Dashboard ➔ Node 4 Service ➔ Environment

- [x] **Infisical Universal Auth Connector (Mandatory Bootstrap)**
  - [x] `INFISICAL_PROJECT_ID="<INFISICAL_PROJECT_ID>"`
  - [x] `INFISICAL_CLIENT_ID="<INFISICAL_CLIENT_ID>"`
  - [x] `INFISICAL_CLIENT_SECRET="<INFISICAL_CLIENT_SECRET>"`
  - [x] `INFISICAL_ENV="prod"`
- [x] **Tower Environment & Port Binding**
  - [x] `NODE_ENV="production"`
  - [x] `PORT="8000"`
  - [x] `MCP_PORT="8000"`
- [x] **MCP Security Tokens**
  - [x] `MCP_ADMIN_KEY="<MCP_ADMIN_KEY>"`
  - [x] `MCP_API_KEY="<MCP_ADMIN_KEY>"`
  - [x] `MCP_AGENT_KEY="<MCP_AGENT_KEY>"`
  - [x] `MCP_VIEWER_KEY="<MCP_VIEWER_KEY>"`
  - [x] `GITHUB_PAT_ADMIN="<GITHUB_PAT_ADMIN>"`
- [x] **Distributed Remote GPU / Kaggle Swarm Keys (Mandatory for MCP Cluster Engine)**
  - [x] `KAGGLE_API_TOKEN="<KAGGLE_API_TOKEN>"` *(Primary Rotational Token)*
  - [x] `KAGGLE_API_TOKENS="<KAGGLE_API_TOKEN_1>,...,<KAGGLE_API_TOKEN_6>"` *(6-Account Distributed Pool)*
- [x] **Cross-Cluster Render Orchestration API Keys**
  - [x] `RENDER_API_KEY_1="<RENDER_API_KEY_1>"` | `RENDER_PRIMARY_SVC_ID="srv-dabm7dfqj5pc738jkbmg"`
  - [x] `RENDER_API_KEY_2="<RENDER_API_KEY_2>"` | `RENDER_WORKER_SVC_ID="srv-dabm7evqj5pc738jkf30"`
  - [x] `RENDER_API_KEY_3="<RENDER_API_KEY_3>"` | `RENDER_SCRAPER_SVC_ID="srv-dabm7gfqj5pc738jkicg"`
  - [x] `RENDER_API_KEY_4="<RENDER_API_KEY_4>"` | `RENDER_MCP_SVC_ID="srv-dabm7inqj5pc738jkrt0"`
- [x] **Verification**: MCP Control Tower synced via Render API (`200 OK`) with active Kaggle GPU pool adapters.

---

### Phase 3: External Platforms Checklist

#### 🔲 GitHub Actions (Repository Secrets & Variables)
* **Path:** GitHub Repository ➔ Settings ➔ Secrets and variables ➔ Actions

- [x] **Infisical Deployment Secrets (For CI Secret Pulling)**
  - [x] `INFISICAL_PROJECT_ID`
  - [x] `INFISICAL_CLIENT_ID`
  - [x] `INFISICAL_CLIENT_SECRET`
  - [x] `INFISICAL_ENV="prod"`
- [x] **Render Multi-Account Deployment Triggers**
  - [x] `RENDER_API_KEY_1` & `RENDER_PRIMARY_SVC_ID`
  - [x] `RENDER_API_KEY_2` & `RENDER_WORKER_SVC_ID`
  - [x] `RENDER_API_KEY_3` & `RENDER_SCRAPER_SVC_ID`
  - [x] `RENDER_API_KEY_4` & `RENDER_MCP_SVC_ID`
- [x] **Security & CI Fallbacks**
  - [x] `CI_WEBHOOK_SECRET="<REDACTED — rotated value lives in Infisical; see docs/security/CREDENTIAL_ROTATION_CHECKLIST.md>"`
  - [x] `CLOUDFLARE_API_TOKEN`
  - [x] `CLOUDFLARE_ACCOUNT_ID="<REDACTED — live value in Infisical vault / Cloudflare dashboard; tracked by #703>"`
- [x] **Verification**: Sodium encrypted secrets synced via GitHub API (`Status 204`).

---

#### 🔲 Cloudflare Edge Workers (`wrangler.toml` & Secrets)
* **Path:** Cloudflare Dashboard ➔ Workers & Pages ➔ `supremeai-worker`

- [x] **Account & Target Cluster Configuration**
  - [x] `account_id="<REDACTED — live value in Infisical vault / Cloudflare dashboard; tracked by #703>"`
  - [x] `PRIMARY_URL="https://supremeai-primary-node.onrender.com"`
  - [x] `WORKER_URL="https://supremeai-worker-node.onrender.com"`
  - [x] `SCRAPER_URL="https://supremeai-scraper-node.onrender.com"`
  - [x] `MCP_URL="https://<render-mcp-url>"`
- [x] **Failover & Inter-routing Bindings**
  - [x] `USER_BACKEND_URL="https://<render-primary-url>"`
  - [x] `GCP_CLOUD_RUN_URL="https://<render-primary-url>"`
  - [x] `GCP_REGION="us-central1"` | `GCP_WEIGHT="25"`
- [x] **Verification**: All 8 active environment bindings verified live on `supremeai-worker` script via Cloudflare API (`200 OK`).

---

#### 🔲 Vercel Frontend Dashboard (Static Build Environment Variables)
* **Path:** Vercel Dashboard ➔ SupremeAI Project (`prj_xyOf1RFtY7S5fexghk86DnvfDIxo`) ➔ Settings ➔ Environment Variables

- [x] `VITE_BACKEND_URL="https://<render-primary-url>"`
- [x] `VITE_API_URL="https://<render-primary-url>"`
- [x] `VITE_API_BASE="https://supremeai-worker.paykaribazaronline.workers.dev"`
- [x] `VITE_SUPABASE_URL="https://<project-ref>.supabase.co"`
- [x] `VITE_SUPABASE_ANON_KEY="<SUPABASE_ANON_JWT>"`
- [x] `VITE_FIREBASE_API_KEY="<FIREBASE_WEB_API_KEY>"`
- [x] `VITE_FIREBASE_PROJECT_ID="supremeai-a"`
- [x] `VITE_FIREBASE_AUTH_DOMAIN="supremeai-a.firebaseapp.com"`
- [x] `VITE_FIREBASE_STORAGE_BUCKET="supremeai-a.appspot.com"`
- [x] `VITE_FIREBASE_MESSAGING_SENDER_ID="110488671645256111793"`
- [x] `VITE_FIREBASE_APP_ID="1:110488671645256111793:web:abcd1234efgh5678"`
- [x] **Verification**: All 11 public frontend build variables injected via Vercel API.

---

#### 🔲 Remote GPU / Kaggle Engine (Optional Free-Compute Tier)
- [x] `KAGGLE_API_TOKEN="<KAGGLE_API_TOKEN>"` *(Primary rotational token)*
- [x] `KAGGLE_API_TOKENS="<KAGGLE_API_TOKEN_1>,...,<KAGGLE_API_TOKEN_6>"` *(6-account distributed swarm pool)*
- [x] **Verification**: Injected into Infisical Cloud Vault (`prod`) and synced to Node 4 MCP Control Tower (`200 OK`).

---

## 4. Master Conflict & Resolution Reference Table

| Configuration Item | In Infisical Vault? | Directly in Render? | Directly in GitHub? | Directly in Cloudflare? | Directly in Vercel? | Operational Rationale |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Infisical Auth (4 keys)** | ❌ N/A | **✅ YES (Mandatory)** | **✅ YES (Mandatory)** | ❌ NO | ❌ NO | **Bootstrap Gate:** Host requires credentials to connect to Infisical. |
| **Service Role (`SUPREMEAI_SERVICE_ROLE`)** | ❌ **NEVER** | **✅ YES (Unique per node)** | ❌ NO | ❌ NO | ❌ NO | **Conflict Isolation:** Prevents worker/scraper from running core router. |
| **Container Port (`PORT`, `MCP_PORT`)** | ❌ **NEVER** | **✅ YES (8000)** | ❌ NO | ❌ NO | ❌ NO | **Host Binding:** Render requires container binding to `$PORT`. |
| **Frontend Public (`VITE_*`)** | Optional | ❌ NO | Optional (CI) | ❌ NO | **✅ YES (Mandatory)** | **Build-Time Baking:** Injected into client JavaScript assets during build. |
| **Cluster Ping URLs** | Optional | ✅ In Inter-routing | ❌ NO | **✅ YES (Mandatory)** | ❌ NO | **Edge Worker Execution:** V8 isolates run outside Python Infisical SDK. |
| **Render Deploy Keys (`RENDER_API_*`)** | ✅ Vault | Node 4 Only | **✅ YES (Mandatory)** | ❌ NO | ❌ NO | **CI Deployment:** GitHub Actions needs API tokens to trigger re-deploys. |
| **Kaggle GPU Tokens (`KAGGLE_API_*`)** | **✅ YES (Vault)** | **Node 4 Only (Mandatory)** | ❌ NO (Via Vault) | ❌ NO | ❌ NO | **Remote Compute:** Node 4 MCP Control Tower routes tasks to 6 Kaggle GPU accounts. |
| **130+ App Secrets (DB, JWT, AI, Redis)** | **✅ YES (Single Source)** | ❌ **NEVER** | Optional (CI) | ❌ **NEVER** | ❌ **NEVER** | **Dynamic Injection:** Loaded securely into memory in ~1s at container startup. |

