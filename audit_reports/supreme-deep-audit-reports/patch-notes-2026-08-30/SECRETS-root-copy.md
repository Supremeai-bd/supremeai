# SupremeAI Secrets Management & Infisical Vault Strategy

## ১) GitHub Actions Secrets (bootstrap keys)
**Path:** GitHub Repository -> Settings -> Secrets and variables -> Actions
এগুলো Infisical-এ রাখা যাবে না, কারণ vault-এ ঢোকার চাবিই এগুলো।

| Key | Criticality |
| :--- | :--- |
| `INFISICAL_CLIENT_ID` | important |
| `INFISICAL_CLIENT_SECRET` | important |
| `INFISICAL_PROJECT_ID` | important |
| `GITHUB_TOKEN` | auto-provided by GH, লাগবে না manually |

*(ঐচ্ছিক legacy fallback: `INFISICAL_TOKEN` — client-id/secret থাকলে এটা লাগে না)*

---

## ২) Infisical Vault-এ `/github-actions` path, `prod` env-এ (CI/CD deploy-time secrets)

| Key | Criticality | ব্যবহার |
| :--- | :--- | :--- |
| `RENDER_API_KEY` | important | Render deploy trigger |
| `RENDER_PRIMARY_SVC_ID` | important | কোন Render service deploy হবে |
| `RENDER_API_KEY_BACKUP`, `RENDER_BACKUP_SVC_ID` | important | ব্যাকআপ instance থাকলে |
| `RENDER_DEPLOY_HOOK_URL` (+ backup) | important | webhook-based deploy fallback |
| `CLOUDFLARE_API_TOKEN` | optional | Worker deploy |
| `CLOUDFLARE_ACCOUNT_ID` | important | Worker deploy (wrangler-এর জন্য দরকারই) |
| `CLOUDFLARE_ZONE_ID`, `CLOUDFLARE_WORKERS_API_TOKEN` | optional | domain routing হলে |
| `SLACK_WEBHOOK_URL` (বা `SLACK_BOT_TOKEN`) | optional | failure notify |
| `DISCORD_WEBHOOK_URL` | optional | maintenance pipeline alert |
| `GCP_SA_KEY`, `FIREBASE_PROJECT_ID` | important | Firebase frontend deploy |
| `SENTRY_AUTH_TOKEN` | important | release/sourcemap upload |
| `NETLIFY_AUTH_TOKEN` | optional | ব্যবহার হলে |
| `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | important | Vercel deploy থাকলে |
| `MIRROR_REPO_TOKEN`, `STAGING_REPO_TOKEN` | important | repo mirror sync |
| `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`, `ANDROID_STORE_PASSWORD` | important | mobile app build |
| `APP_STORE_CONNECT_API_KEY_*` | important | iOS build |

---

## ৩) Render Backend/Admin instance-এ
**Path:** Infisical Vault-এ `/backend` বা `/render-backend` path-এ `prod` env-এ (app runtime, ভিন্ন path হওয়া উচিত)

| Key | Criticality |
| :--- | :--- |
| `SUPREMEAI_JWT_SECRET` | critical |
| `ENCRYPTION_KEY` | critical |
| `SUPREMEAI_ADMIN_PASSWORD_HASH` | critical |
| `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_DATABASE_URL` (+ pooler) | important |
| `REDIS_URL` | important |
| `QDRANT_URL`, `QDRANT_API_KEY` | important |
| `NATS_TOKEN` | important |
| `API_KEY_SIGNING_SECRET` | important |
| বাকি সব AI provider key (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, ইত্যাদি) | optional — feature-wise skip হয় |

---

## 💡 Practical Security Advice (Least Privilege Principle)
Infisical vault-এ একটা path সব environment-এর জন্য শেয়ার করা যাবে না।
যেমন: 
- `/github-actions` আলাদা path ব্যবহার করা হয়েছে deploy secrets-এর জন্য।
- আর app runtime secrets থাকবে `/backend` বা `/render-backend` path-এ `prod` env-এ। 

এতে GitHub Actions runner শুধু deploy-related secret-গুলোই access করবে, পুরো app-এর critical secret (`SUPREMEAI_JWT_SECRET` ইত্যাদি) না — নাহলে একটা compromised CI runner পুরো production vault-এ access পেয়ে যাবে।
