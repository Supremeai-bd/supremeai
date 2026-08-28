# SupremeAI — Secrets Audit Report

_Generated: _audit.py run · repo: SaifulHaqueNiloy/supremeai_

## Methodology

- **Source of truth (keys):** `.env` (runtime) unioned with `secrets_registry.yaml` (canonical key→service map).
- **Live verification:** Infisical vault (`prod`) via Universal Auth; GitHub Actions secret *names* via REST; Render backend + scraper env-var *names* via REST.
- **Real/Fake:** provider key-format validation (prefix/JWT/numeric) + placeholder-pattern scan (`njel.com.bd`, `example`, `changeme`, etc.). Opaque secrets (hashes, encryption keys) are marked `UNVERIFIABLE` — they cannot be confirmed real without a live API test against the provider.
- **Not auto-verified:** Cloudflare, Neon, Supabase, Vercel, Firebase external dashboards (no name-listing API used here; targets still listed from registry).

## Summary

- **Total tracked keys:** 257
- **Present in `.env` (with value):** 147
- **Empty in `.env`:** 64  |  **Absent from `.env`:** 46
- **In Infisical vault (`prod`):** 96  |  **Missing from Infisical:** 161
- **In GitHub Actions secrets:** 0  _(GitHub error: token in .env is invalid/expired — 401 Bad credentials)_
- **In Render env vars:** 16  _(verified against service `srv-da666f8u01pc739bm3t0` = supremeai-backend-v2)_
- **Value looks FAKE/PLACEHOLDER:** 8  |  **EMPTY value:** 110

## Action Items — Keys Missing from Infisical Vault (by criticality)

- `[important]` ANDROID_KEY_ALIAS
- `[important]` ANDROID_KEY_PASSWORD
- `[important]` ANDROID_KEYSTORE_BASE64
- `[important]` ANDROID_STORE_PASSWORD
- `[important]` APP_STORE_CONNECT_API_KEY_CONTENT
- `[important]` APP_STORE_CONNECT_API_KEY_ID
- `[important]` GCP_SA_KEY
- `[important]` GITHUB_CLIENT_SECRET
- `[important]` INFISICAL_CLIENT_ID
- `[important]` INFISICAL_PROJECT_ID
- `[important]` JWT_SECRET_KEY
- `[important]` NATS_TOKEN
- `[important]` REDIS_PASSWORD
- `[important]` RENDER_DEPLOY_HOOK_URL_BACKUP
- `[important]` SECRET_IDS
- `[important]` SECRET_KEY
- `[important]` SENTRY_AUTH_TOKEN
- `[important]` STAGING_REPO_TOKEN
- `[important]` SUPABASE_SERVICE_KEY
- `[important]` VERCEL_OIDC_TOKEN
- `[optional]` AIDER_API_KEY
- `[optional]` ALLOWED_TAKEOVER_TOKENS
- `[optional]` ANTHROPIC_API_KEY
- `[optional]` API_KEY
- `[optional]` API_KEYS
- `[optional]` AUTHORIZED_ADMINS
- `[optional]` AUTO_TEST_MAX_TOKENS
- `[optional]` BHASHA_BATCH_CONCURRENCY
- `[optional]` BHASHA_CACHE_TTL_HOURS
- `[optional]` BHASHA_MAX_CACHE
- `[optional]` BHASHA_MIN_QUALITY
- `[optional]` CLINE_API_KEY
- `[optional]` CLOUDFLARE_API_TOKEN
- `[optional]` CLOUDFLARE_WORKERS_API_TOKEN
- `[optional]` CLOUDFLARE_ZONE_ID
- `[optional]` CODEIUM_API_KEY
- `[optional]` CONTINUE_API_KEY
- `[optional]` DASHBOARD_API_KEY
- `[optional]` DEEPSEEK_API_KEY
- `[optional]` DISCORD_ALERT_WEBHOOK
- `[optional]` DISCORD_BOT_TOKEN
- `[optional]` DOTENV_KEY
- `[optional]` ENCRYPTION_KEYS
- `[optional]` GCP_ACCESS_TOKEN
- `[optional]` GCP_PROJECT_ID
- `[optional]` GCP_PUBSUB_SUBSCRIPTION
- `[optional]` GCP_PUBSUB_TOPIC
- `[optional]` GIT_HTTP_PROXY_AUTHMETHOD
- `[optional]` GOOGLE_API_KEY
- `[optional]` GOOGLE_APPLICATION_CREDENTIALS
- `[optional]` GOOGLE_CLOUD_PROJECT
- `[optional]` GROQ_API_KEY_DEPLOYMENT_MONITOR
- `[optional]` HF_API_KEY
- `[optional]` KEYCHAIN_PATH
- `[optional]` KMS_KEY_NAME
- `[optional]` LANGSMITH_API_KEY
- `[optional]` LAUNCHDARKLY_AI_CONFIG_KEY
- `[optional]` LAUNCHDARKLY_SDK_KEY
- `[optional]` LITELLM_API_KEY
- `[optional]` LOAD_TEST_TOKEN
- `[optional]` LOG_TOKENS
- `[optional]` MAX_TOTAL_TOKENS
- `[optional]` MINIO_ACCESS_KEY
- `[optional]` MINIO_SECRET_KEY
- `[optional]` MOONSHOT_API_KEY
- `[optional]` NEO4J_PASSWORD
- `[optional]` NEO4J_URI
- `[optional]` NEO4J_USER
- `[optional]` NETLIFY_AUTH_TOKEN
- `[optional]` NEXT_PUBLIC_SUPABASE_ANON_KEY
- `[optional]` NEXTAUTH_URL
- `[optional]` NVIDIA_API_KEY
- `[optional]` ORACLE_CLOUD_API_KEY
- `[optional]` PINECONE_API_KEY
- `[optional]` PLANDEX_API_KEY
- `[optional]` PLAYWRIGHT_MCP_EXTENSION_TOKEN
- `[optional]` POSTHOG_API_KEY
- `[optional]` PYDANTIC_PRIVATE_ALLOW_UNHANDLED_SCHEMA_TYPES
- `[optional]` PYTHAGORA_API_KEY
- `[optional]` PYTHON_KEYRING_BACKEND
- `[optional]` R2_ACCESS_KEY
- `[optional]` R2_SECRET_KEY
- `[optional]` RAILWAY_TOKEN
- `[optional]` RATE_LIMIT_FALLBACK_MAX_KEYS
- `[optional]` REDIS_KEY_PREFIX
- `[optional]` REDIS_TOKEN
- `[optional]` RETRY_BUDGET_MAX_TOKENS
- `[optional]` SECONDARY_SERVICE_ACCOUNT_KEY
- `[optional]` SECRET_CACHE_TTL
- `[optional]` SENDGRID_API_KEY
- `[optional]` SLACK_BOT_TOKEN
- `[optional]` SMTP_PASSWORD
- `[optional]` SSLKEYLOGFILE
- `[optional]` SUPABASE_ANON_KEY
- `[optional]` SUPREMEAI_EMAIL_PASSWORD
- `[optional]` SUPREMEAI_SOLVER_API_KEY
- `[optional]` TOGETHER_API_KEY
- `[optional]` TOKEN_JUICE_ENABLED
- `[optional]` TWILIO_AUTH_TOKEN
- `[optional]` UPSTASH_REDIS_TOKEN
- `[optional]` VITE_ADMIN_BACKEND
- `[optional]` VITE_API_BASE
- `[optional]` VITE_API_BASE_URL
- `[optional]` VITE_API_URL
- `[optional]` VITE_FIREBASE_APP_ID
- `[optional]` VITE_FIREBASE_AUTH_DOMAIN
- `[optional]` VITE_FIREBASE_MESSAGING_SENDER_ID
- `[optional]` VITE_FIREBASE_STORAGE_BUCKET
- `[optional]` VITE_SUPABASE_ANON_KEY
- `[optional]` VITE_SUPABASE_URL
- `[optional]` VITE_USER_BACKEND
- `[optional]` WS_AUTH_WINDOW_SECONDS
- `[optional]` WS_MAX_AUTH_ATTEMPTS
- `[?]` ADMIN_CORS_ORIGINS
- `[?]` APP_STORE_CONNECT_API_ISSUER_ID
- `[?]` CHECKOUT_BASE_URL
- `[?]` CHROMADB_PATH
- `[?]` CLOUDFLARE_ACCOUNT_ID
- `[?]` DB_MAX_OVERFLOW
- `[?]` DB_POOL_RECYCLE
- `[?]` DB_POOL_SIZE
- `[?]` ENABLE_AUTO_HEALER
- `[?]` ENABLE_DAILY_LEARNER
- `[?]` ENABLE_EVOLUTION
- `[?]` ENABLE_EVOLUTION_LEARNING
- `[?]` ENABLE_TIER8
- `[?]` ENV
- `[?]` FIREBASE_SERVICE_ACCOUNT
- `[?]` FIREBASE_TOKEN
- `[?]` GH_TOKEN
- `[?]` GITHUB_MODELS_API_KEY
- `[?]` GITLAB_TOKEN
- `[?]` HF_TOKEN
- `[?]` HUGGINGFACE_TOKEN
- `[?]` INTENT_ROUTER_MODE
- `[?]` KAGGLE_API_TOKEN
- `[?]` MAIN_REPO_TOKEN
- `[?]` NETLIFY_API_KEY
- `[?]` NETLIFY_SITE_ID
- `[?]` OLLAMA_URL
- `[?]` PAGERDUTY_ROUTING_KEY
- `[?]` PLAY_STORE_CONFIG_JSON
- `[?]` QDRANT_PATH
- `[?]` RENDER_SCRAPER_SVC_ID
- `[?]` SAFETY_API_KEY
- `[?]` sav#
- `[?]` SUPREMEAI_ADMIN_BACKEND_URL
- `[?]` SUPREMEAI_ADMIN_LOGIN_EMAIL
- `[?]` SUPREMEAI_ADMIN_LOGIN_PASSWORD
- `[?]` SUPREMEAI_CF_WORKER_URL
- `[?]` SUPREMEAI_USER_BACKEND_URL
- `[?]` TELEGRAM_ADMIN_USERNAME
- `[?]` TELEGRAM_API_HASH
- `[?]` TELEGRAM_API_ID
- `[?]` TELEGRAM_CHAT_ID
- `[?]` TEST_ADMIN_PASSWORD
- `[?]` USER_CORS_ORIGINS
- `[?]` VITE_PRIMARY_BACKEND
- `[?]` VITE_SECONDARY_BACKEND
- `[?]` WS_MAX_CONNECTIONS
- `[?]` WS_MAX_PER_USER

## Suspicious / Placeholder / Fake / Weak Values

- **DOCS_PASSWORD** → `PLACEHOLDER` (weak/default-style password) — value: `supr…(23)`
- **CI_WEBHOOK_SECRET** → `PLACEHOLDER` (literal placeholder value 'njel.com.bd') — value: `njel…(11)`
- **STRIPE_API_KEY** → `FAKE` (expected one of ['sk_live_', 'sk_test_', 'rk_']) — value: `mk_1…(27)`
- **STRIPE_PUBLISHABLE_KEY** → `FAKE` (expected one of ['pk_']) — value: `mk_1…(27)`
- **STRIPE_SECRET_KEY** → `FAKE` (expected one of ['sk_live_', 'sk_test_', 'rk_']) — value: `mk_1…(27)`
- **SUPREMEAI_ADMIN_TOTP_SECRET** → `FAKE` () — value: `JBSW…(16)`
- **ADMIN_AUTHORIZED** → `PLACEHOLDER` (literal placeholder value 'njel.com.bd') — value: `admi…(52)`
- **SUPREMEAI_ADMIN_LOGIN_PASSWORD** → `PLACEHOLDER` (literal placeholder value 'njel.com.bd') — value: `njel…(11)`

## Full Key Inventory

| Key | .env | Val(len) | Real/Fake | Infisical | GitHub | Render | Target services | Notes |
|-----|------|-----------|-----------|-----------|--------|--------|---------------|-------|
| ADMIN_EMAILS | ✓ | ["ni…(69) | UNVERIFIABLE | ✓ | ? | ✓ | (untracked) | no provider-format rule |
| ADMIN_TELEGRAM_CHAT_ID | ✓ | 7804…(10) | REAL | ✓ | ? | ✗ | (untracked) | numeric |
| ALLOW_TEST_ORIGIN_BYPASS | ✓ | fa…(5) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | no provider-format rule |
| API_V1_STR | ✓ | /a…(7) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | no provider-format rule |
| CB_ADAPTIVE | ✓ | tr…(4) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | no provider-format rule |
| CLOUDFLARE_EMAIL | ✓ | payk…(28) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | no provider-format rule |
| DOCS_PASSWORD | ✓ | supr…(23) | PLACEHOLDER | ✓ | ? | ✗ | (untracked) | weak/default-style password |
| ENCRYPTION_KEY | ✓ | hBZC…(33) | UNVERIFIABLE | ✓ | ? | ✗ | github-actions,infisical-vault,render-admin,render-backend | opaque |
| FIREBASE_SERVICE_ACCOUNT_JSON | ✓ | {"ty…(2327) | REAL | ✓ | ? | ✗ | (untracked) | service-account JSON |
| FIREBASE_SERVICE_ACCOUNT_SUPREMEAI_A | ✓ | {"ty…(2327) | REAL | ✓ | ? | ✗ | (untracked) | service-account JSON |
| GCP_KMS_KEY_RING | ✓ | supr…(21) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | no provider-format rule |
| GITHUB_CLIENT_ID | ✓ | Ov23…(20) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) |  |
| GITHUB_PAT_AUTO_FIX | ✓ | ghp_…(40) | REAL | ✓ | ? | ✗ | (untracked) | GitHub token format |
| GITHUB_PAT_NILOYJOY7 | ✓ | gith…(93) | REAL | ✓ | ? | ✗ | (untracked) | GitHub token format |
| INFISICAL_CLIENT_SECRET | ✓ | 316a…(64) | UNVERIFIABLE | ✓ | ? | ✓ | github-actions,infisical-vault,render-admin,render-backend | hex |
| INFISICAL_TOKEN | ✓ | eyJh…(435) | REAL | ✓ | ? | ✗ | github-actions,infisical-vault,render-admin,render-backend | JWT-like |
| KAGGLE_API_TOKEN_1 | ✓ | KGAT…(37) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | custom KGAT_ prefix (not externally verifiable) |
| KAGGLE_API_TOKEN_2 | ✓ | KGAT…(37) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | custom KGAT_ prefix (not externally verifiable) |
| KAGGLE_API_TOKEN_3 | ✓ | KGAT…(37) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | custom KGAT_ prefix (not externally verifiable) |
| KAGGLE_API_TOKEN_4 | ✓ | KGAT…(37) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | custom KGAT_ prefix (not externally verifiable) |
| KAGGLE_API_TOKEN_5 | ✓ | KGAT…(37) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | custom KGAT_ prefix (not externally verifiable) |
| KAGGLE_API_TOKEN_6 | ✓ | KGAT…(37) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | custom KGAT_ prefix (not externally verifiable) |
| LAUNCHDARKLY_API_KEY | ✓ | api-…(40) | REAL | ✓ | ? | ✗ | (untracked) | starts api-… |
| LEARNING_ENABLED | ✓ | tr…(4) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | no provider-format rule |
| LOW_MEMORY_MODE | ✓ | tr…(4) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | no provider-format rule |
| MISTRAL_API_KEY | ✓ | S5bg…(32) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | no fixed prefix |
| NEON_API_KEY | ✓ | napi…(69) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | no provider-format rule |
| NEON_DATABASE_URL | ✓ | post…(122) | REAL | ✓ | ? | ✗ | (untracked) | starts postgr… |
| PROJECT_NAME | ✓ | Supr…(13) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | no provider-format rule |
| routeme_api_key | ✓ | rm-f…(51) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | no provider-format rule |
| SELF_HEALING | ✓ | tr…(4) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | no provider-format rule |
| SUPABASE_JWKS_URL | ✓ | http…(70) | REAL | ✓ | ? | ✗ | (untracked) | starts https:… |
| SUPABASE_PUBLISHABLE_KEY | ✓ | sb_p…(46) | REAL | ✓ | ? | ✗ | (untracked) | starts sb_pub… |
| SUPABASE_SECRET_KEY | ✓ | sb_s…(15) | REAL | ✓ | ? | ✗ | (untracked) | starts sb_sec… |
| SUPREMEAI_ADMIN_PASSWORD_HASH | ✓ | $2b$…(61) | REAL | ✓ | ? | ✗ | github-actions,infisical-vault,render-admin,render-backend |  |
| SUPREMEAI_JWT_SECRET | ✓ | 0eaf…(64) | UNVERIFIABLE | ✓ | ? | ✗ | github-actions,infisical-vault,render-admin,render-backend | opaque hex |
| ZERO_COST_MAX_CONCURRENT | ✓ | 3…(1) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | no provider-format rule |
| ZERO_COST_TASK_TIMEOUT | ✓ | 30…(5) | UNVERIFIABLE | ✓ | ? | ✗ | (untracked) | no provider-format rule |
| ADMIN_NOTIFICATION_EMAIL | ✓ | nilo…(19) | UNVERIFIABLE | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | no provider-format rule |
| API_KEY_SIGNING_SECRET | ✓ | e27d…(32) | UNVERIFIABLE | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | opaque |
| CI_WEBHOOK_SECRET | ✓ | njel…(11) | PLACEHOLDER | ✓ | ? | ✗ | github-actions,infisical-vault,render-admin,render-backend | literal placeholder value 'njel.com.bd' |
| GITHUB_API_TOKEN | ✓ | ghp_…(40) | REAL | ✓ | ? | ✗ | github-actions,infisical-vault | GitHub token format |
| GITHUB_TOKEN | ✓ | ghp_…(40) | REAL | ✓ | ? | ✗ | github-actions,infisical-vault,render-admin,render-backend | GitHub token format |
| JIT_OTP_SECRET | ✓ | NWZP…(32) | UNVERIFIABLE | ✓ | ? | ✗ | infisical-vault,vercel-frontend | no provider-format rule |
| JWT_SECRET | ✓ | JWT_…(32) | UNVERIFIABLE | ✓ | ? | ✓ | infisical-vault,render-admin,render-backend | opaque |
| MIRROR_REPO_TOKEN | — absent | - | EMPTY | ✓ | ? | ✗ | github-actions,infisical-vault | no value in .env |
| QDRANT_API_KEY | ✓ | eyJh…(176) | REAL | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | JWT-like |
| QDRANT_URL | ✓ | http…(76) | REAL | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | starts https:… |
| REDIS_URL | ✓ | redi…(118) | REAL | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend,vercel-frontend | starts redis:… |
| RENDER_API_KEY | ✓ | rnd_…(32) | UNVERIFIABLE | ✓ | ? | ✗ | firebase-gcp,github-actions,infisical-vault,render-admin,render-backend | no provider-format rule |
| RENDER_API_KEY_BACKUP | — absent | - | EMPTY | ✓ | ? | ✗ | firebase-gcp,github-actions,infisical-vault,render-admin,render-backend | no value in .env |
| RENDER_BACKUP_SVC_ID | ✗ empty | - | EMPTY | ✓ | ? | ✗ | github-actions,infisical-vault | no value in .env |
| RENDER_DEPLOY_HOOK_URL | ✓ | http…(70) | UNVERIFIABLE | ✓ | ? | ✗ | github-actions,infisical-vault | no provider-format rule |
| RENDER_PRIMARY_SVC_ID | ✓ | srv-…(24) | UNVERIFIABLE | ✓ | ? | ✗ | github-actions,infisical-vault | no provider-format rule |
| STRIPE_API_KEY | ✓ | mk_1…(27) | FAKE | ✓ | ? | ✗ | github-actions,infisical-vault,render-admin,render-backend | expected one of ['sk_live_', 'sk_test_', 'rk_'] |
| STRIPE_PUBLISHABLE_KEY | ✓ | mk_1…(27) | FAKE | ✓ | ? | ✗ | github-actions,infisical-vault | expected one of ['pk_'] |
| STRIPE_SECRET_KEY | ✓ | mk_1…(27) | FAKE | ✓ | ? | ✗ | github-actions,infisical-vault,render-admin,render-backend | expected one of ['sk_live_', 'sk_test_', 'rk_'] |
| STRIPE_WEBHOOK_SECRET | ✓ | whse…(38) | REAL | ✓ | ? | ✗ | github-actions,infisical-vault,render-admin,render-backend | starts whsec_… |
| SUPABASE_ACCESS_TOKEN | ✓ | sbp_…(44) | UNVERIFIABLE | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | no provider-format rule |
| SUPABASE_DATABASE_URL | ✓ | post…(118) | REAL | ✓ | ? | ✗ | github-actions,infisical-vault,render-admin,render-backend | starts postgr… |
| SUPABASE_DATABASE_URL_POOLER | ✓ | post…(118) | REAL | ✓ | ? | ✗ | github-actions,infisical-vault,render-admin,render-backend | starts postgr… |
| SUPABASE_KEY | ✓ | eyJh…(208) | REAL | ✓ | ? | ✓ | github-actions,infisical-vault,render-admin,render-backend | JWT-like |
| SUPABASE_SERVICE_ROLE_KEY | ✓ | eyJh…(219) | REAL | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | JWT-like |
| SUPABASE_URL | ✓ | http…(40) | REAL | ✓ | ? | ✓ | github-actions,infisical-vault,render-admin,render-backend | starts https:… |
| SUPREMEAI_ADMIN_TOTP_SECRET | ✓ | JBSW…(16) | FAKE | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend |  |
| SUPREMEAI_API_KEY | ✓ | sk-s…(43) | REAL | ✓ | ? | ✗ | github-actions,infisical-vault,render-admin,render-backend | starts sk-sup… |
| SUPREMEAI_CREDENTIAL_ENC_KEY | ✓ | KmVt…(44) | UNVERIFIABLE | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | opaque |
| SUPREMEAI_GITHUB_TOKEN | ✓ | ghp_…(40) | UNVERIFIABLE | ✓ | ? | ✗ | github-actions,infisical-vault | no provider-format rule |
| UPSTASH_REDIS_REST_TOKEN | ✓ | gQAA…(62) | REAL | ✓ | ? | ✗ | github-actions,infisical-vault |  |
| UPSTASH_REDIS_REST_URL | ✓ | http…(41) | REAL | ✓ | ? | ✗ | github-actions,infisical-vault | starts https:… |
| VERCEL_ORG_ID | ✓ | team…(29) | UNVERIFIABLE | ✓ | ? | ✗ | github-actions,infisical-vault |  |
| VERCEL_PROJECT_ID | ✓ | prj_…(32) | REAL | ✓ | ? | ✗ | github-actions,infisical-vault,render-admin,render-backend | starts prj_… |
| VERCEL_TOKEN | ✓ | vcp_…(60) | REAL | ✓ | ? | ✗ | firebase-gcp,github-actions,infisical-vault | starts vcp_… |
| ADMIN_AUTHORIZED | ✓ | admi…(52) | PLACEHOLDER | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | literal placeholder value 'njel.com.bd' |
| ALLOW_TEST_AUTH_BYPASS | ✓ | fa…(5) | UNVERIFIABLE | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | no provider-format rule |
| ALLOWED_HOSTS | ✓ | supr…(275) | UNVERIFIABLE | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | no provider-format rule |
| AUTOFIX_AUTHORIZED | ✓ | tr…(4) | UNVERIFIABLE | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | no provider-format rule |
| CLOUDFLARE_API_KEY | ✓ | cfk_…(52) | REAL | ✓ | ? | ✗ | github-actions,infisical-vault | starts cfk_… |
| CORS_ORIGINS | ✓ | http…(282) | UNVERIFIABLE | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | no provider-format rule |
| DB_PASSWORD | ✓ | DB_N…(31) | UNVERIFIABLE | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | opaque |
| DISCORD_OTP_WEBHOOK_URL | ✓ | http…(121) | REAL | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | Discord webhook URL |
| DISCORD_WEBHOOK_URL | ✓ | http…(121) | REAL | ✓ | ? | ✗ | firebase-gcp,github-actions,infisical-vault,render-admin,render-backend | Discord webhook URL |
| EXPERIENCE_DB_PATH | ✓ | ./da…(13) | UNVERIFIABLE | ✓ | ? | ✓ | infisical-vault,render-admin,render-backend | no provider-format rule |
| FIRECRAWL_API_KEY | ✓ | fc-5…(71) | REAL | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | starts fc-… |
| GEMINI_API_KEY | ✓ | AIza…(147) | REAL | ✓ | ? | ✗ | firebase-gcp,infisical-vault,render-admin,render-backend | starts AIza… |
| GROQ_API_KEY | ✓ | gsk_…(170) | REAL | ✓ | ? | ✗ | firebase-gcp,infisical-vault,render-admin,render-backend | starts gsk_… |
| OPENAI_API_KEY | ✓ | sk-p…(164) | REAL | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | starts sk-… |
| OPENHANDS_API_KEY | ✓ | sk-o…(38) | REAL | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | starts sk-oh-… |
| OPENROUTER_API_KEY | ✓ | sk-o…(147) | REAL | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | starts sk-or-… |
| RESEND_API_KEY | ✓ | re_t…(36) | REAL | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | starts re_… |
| SECRET | ✓ | SEC_…(32) | UNVERIFIABLE | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | opaque |
| SECRET_BACKEND | ✓ | SECB…(33) | UNVERIFIABLE | ✓ | ? | ✗ | firebase-gcp,infisical-vault | opaque |
| TELEGRAM_BOT_TOKEN | ✓ | 8858…(46) | REAL | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend |  |
| TEST_VAULT_KEY | ✓ | TEST…(33) | UNVERIFIABLE | ✓ | ? | ✗ | infisical-vault,render-admin,render-backend | opaque |
| VITE_FIREBASE_API_KEY | ✓ | AIza…(39) | UNVERIFIABLE | ✓ | ? | ✗ | github-actions,infisical-vault,vercel-frontend | no provider-format rule |
| VITE_FIREBASE_PROJECT_ID | ✓ | supr…(11) | UNVERIFIABLE | ✓ | ? | ✗ | infisical-vault,vercel-frontend | no provider-format rule |
| ADMIN_CORS_ORIGINS | ✓ | http…(282) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| APP_STORE_CONNECT_API_ISSUER_ID | ✗ empty | - | EMPTY | ✗ | ? | ✗ | (untracked) | no value in .env |
| CHECKOUT_BASE_URL | ✓ | http…(30) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| CHROMADB_PATH | ✓ | ./da…(15) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| CLOUDFLARE_ACCOUNT_ID | ✓ | 9d13…(32) | REAL | ✗ | ? | ✗ | (untracked) |  |
| DB_MAX_OVERFLOW | ✓ | 2…(1) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| DB_POOL_RECYCLE | ✓ | 18…(4) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| DB_POOL_SIZE | ✓ | 3…(1) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| ENABLE_AUTO_HEALER | ✓ | tr…(4) | UNVERIFIABLE | ✗ | ? | ✓ | (untracked) | no provider-format rule |
| ENABLE_DAILY_LEARNER | ✓ | fa…(5) | UNVERIFIABLE | ✗ | ? | ✓ | (untracked) | no provider-format rule |
| ENABLE_EVOLUTION | ✓ | fa…(5) | UNVERIFIABLE | ✗ | ? | ✓ | (untracked) | no provider-format rule |
| ENABLE_EVOLUTION_LEARNING | ✓ | fa…(5) | UNVERIFIABLE | ✗ | ? | ✓ | (untracked) | no provider-format rule |
| ENABLE_TIER8 | ✓ | fa…(5) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| ENV | ✓ | prod…(10) | UNVERIFIABLE | ✗ | ? | ✓ | (untracked) | no provider-format rule |
| FIREBASE_SERVICE_ACCOUNT | ✗ empty | - | EMPTY | ✗ | ? | ✗ | (untracked) | no value in .env |
| FIREBASE_TOKEN | ✓ | 1//0…(103) | REAL | ✗ | ? | ✗ | (untracked) |  |
| GH_TOKEN | — absent | - | EMPTY | ✗ | ? | ✗ | github-actions | no value in .env |
| GITHUB_MODELS_API_KEY | ✓ | gith…(657) | REAL | ✗ | ? | ✗ | (untracked) | GitHub token format |
| GITLAB_TOKEN | ✓ | glpa…(62) | REAL | ✗ | ? | ✗ | (untracked) | starts glpat-… |
| HF_TOKEN | — absent | - | EMPTY | ✗ | ? | ✗ | github-actions | no value in .env |
| HUGGINGFACE_TOKEN | — absent | - | EMPTY | ✗ | ? | ✗ | github-actions | no value in .env |
| INTENT_ROUTER_MODE | ✓ | ll…(3) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| KAGGLE_API_TOKEN | ✓ | KGAT…(37) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | custom KGAT_ prefix (not externally verifiable) |
| MAIN_REPO_TOKEN | ✓ | ghp_…(40) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| NETLIFY_API_KEY | — absent | - | EMPTY | ✗ | ? | ✗ | github-actions | no value in .env |
| NETLIFY_SITE_ID | ✗ empty | - | EMPTY | ✗ | ? | ✗ | (untracked) | no value in .env |
| OLLAMA_URL | ✓ | http…(22) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| PAGERDUTY_ROUTING_KEY | — absent | - | EMPTY | ✗ | ? | ✗ | github-actions | no value in .env |
| PLAY_STORE_CONFIG_JSON | ✗ empty | - | EMPTY | ✗ | ? | ✗ | (untracked) | no value in .env |
| QDRANT_PATH | ✓ | ./da…(13) | UNVERIFIABLE | ✗ | ? | ✓ | (untracked) | no provider-format rule |
| RENDER_SCRAPER_SVC_ID | ✓ | srv-…(24) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| SAFETY_API_KEY | — absent | - | EMPTY | ✗ | ? | ✗ | github-actions | no value in .env |
| sav# | ✓ | ====…(88) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| SUPREMEAI_ADMIN_BACKEND_URL | ✓ | http…(45) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| SUPREMEAI_ADMIN_LOGIN_EMAIL | ✓ | nilo…(19) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| SUPREMEAI_ADMIN_LOGIN_PASSWORD | ✓ | njel…(11) | PLACEHOLDER | ✗ | ? | ✗ | (untracked) | literal placeholder value 'njel.com.bd' |
| SUPREMEAI_CF_WORKER_URL | ✓ | http…(55) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| SUPREMEAI_USER_BACKEND_URL | ✓ | http…(45) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| TELEGRAM_ADMIN_USERNAME | ✓ | Saif…(10) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| TELEGRAM_API_HASH | ✓ | ea99…(32) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| TELEGRAM_API_ID | ✓ | 26…(8) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| TELEGRAM_CHAT_ID | ✓ | 7804…(10) | REAL | ✗ | ? | ✗ | (untracked) | numeric |
| TEST_ADMIN_PASSWORD | — absent | - | EMPTY | ✗ | ? | ✗ | github-actions | no value in .env |
| USER_CORS_ORIGINS | ✓ | http…(282) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| VITE_PRIMARY_BACKEND | ✓ | http…(45) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| VITE_SECONDARY_BACKEND | ✓ | http…(45) | UNVERIFIABLE | ✗ | ? | ✗ | (untracked) | no provider-format rule |
| WS_MAX_CONNECTIONS | ✓ | 50…(2) | UNVERIFIABLE | ✗ | ? | ✓ | (untracked) | no provider-format rule |
| WS_MAX_PER_USER | ✓ | 3…(1) | UNVERIFIABLE | ✗ | ? | ✓ | (untracked) | no provider-format rule |
| ANDROID_KEY_ALIAS | ✗ empty | - | EMPTY | ✗ | ? | ✗ | github-actions,infisical-vault | no value in .env |
| ANDROID_KEY_PASSWORD | ✗ empty | - | EMPTY | ✗ | ? | ✗ | github-actions,infisical-vault | no value in .env |
| ANDROID_KEYSTORE_BASE64 | ✗ empty | - | EMPTY | ✗ | ? | ✗ | github-actions,infisical-vault | no value in .env |
| ANDROID_STORE_PASSWORD | ✗ empty | - | EMPTY | ✗ | ? | ✗ | github-actions,infisical-vault | no value in .env |
| APP_STORE_CONNECT_API_KEY_CONTENT | ✗ empty | - | EMPTY | ✗ | ? | ✗ | github-actions,infisical-vault | no value in .env |
| APP_STORE_CONNECT_API_KEY_ID | ✗ empty | - | EMPTY | ✗ | ? | ✗ | github-actions,infisical-vault | no value in .env |
| GCP_SA_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | github-actions,infisical-vault | no value in .env |
| GITHUB_CLIENT_SECRET | ✗ empty | - | EMPTY | ✗ | ? | ✗ | github-actions,infisical-vault,render-admin,render-backend | no value in .env |
| INFISICAL_CLIENT_ID | ✓ | 9f23…(36) | UNVERIFIABLE | ✗ | ? | ✓ | github-actions,infisical-vault,render-admin,render-backend | uuid |
| INFISICAL_PROJECT_ID | ✓ | 92aa…(36) | UNVERIFIABLE | ✗ | ? | ✓ | github-actions,infisical-vault,render-admin,render-backend | uuid |
| JWT_SECRET_KEY | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| NATS_TOKEN | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend,render-scraper | no value in .env |
| REDIS_PASSWORD | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| RENDER_DEPLOY_HOOK_URL_BACKUP | — absent | - | EMPTY | ✗ | ? | ✗ | github-actions,infisical-vault | no value in .env |
| SECRET_IDS | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| SECRET_KEY | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| SENTRY_AUTH_TOKEN | ✗ empty | - | EMPTY | ✗ | ? | ✗ | github-actions,infisical-vault,render-admin,render-backend | no value in .env |
| STAGING_REPO_TOKEN | — absent | - | EMPTY | ✗ | ? | ✗ | github-actions,infisical-vault | no value in .env |
| SUPABASE_SERVICE_KEY | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| VERCEL_OIDC_TOKEN | ✗ empty | - | EMPTY | ✗ | ? | ✗ | github-actions,infisical-vault,render-admin,render-backend | no value in .env |
| AIDER_API_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| ALLOWED_TAKEOVER_TOKENS | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| ANTHROPIC_API_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| API_KEY | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| API_KEYS | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| AUTHORIZED_ADMINS | ✗ empty | - | EMPTY | ✗ | ? | ✗ | firebase-gcp,infisical-vault | no value in .env |
| AUTO_TEST_MAX_TOKENS | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| BHASHA_BATCH_CONCURRENCY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| BHASHA_CACHE_TTL_HOURS | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| BHASHA_MAX_CACHE | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| BHASHA_MIN_QUALITY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| CLINE_API_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| CLOUDFLARE_API_TOKEN | ✓ | cfut…(53) | REAL | ✗ | ? | ✗ | github-actions,infisical-vault | starts cfut_… |
| CLOUDFLARE_WORKERS_API_TOKEN | ✓ | cfut…(53) | REAL | ✗ | ? | ✗ | github-actions,infisical-vault | starts cfut_… |
| CLOUDFLARE_ZONE_ID | ✗ empty | - | EMPTY | ✗ | ? | ✗ | github-actions,infisical-vault | no value in .env |
| CODEIUM_API_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| CONTINUE_API_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| DASHBOARD_API_KEY | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| DEEPSEEK_API_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| DISCORD_ALERT_WEBHOOK | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| DISCORD_BOT_TOKEN | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| DOTENV_KEY | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| ENCRYPTION_KEYS | ✓ | X-mE…(44) | UNVERIFIABLE | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | opaque |
| GCP_ACCESS_TOKEN | ✗ empty | - | EMPTY | ✗ | ? | ✗ | firebase-gcp,infisical-vault | no value in .env |
| GCP_PROJECT_ID | ✗ empty | - | EMPTY | ✗ | ? | ✗ | firebase-gcp,github-actions,infisical-vault,render-admin,render-backend,render-scraper | no value in .env |
| GCP_PUBSUB_SUBSCRIPTION | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend,render-scraper | no value in .env |
| GCP_PUBSUB_TOPIC | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend,render-scraper | no value in .env |
| GIT_HTTP_PROXY_AUTHMETHOD | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| GOOGLE_API_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| GOOGLE_APPLICATION_CREDENTIALS | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend,render-scraper | no value in .env |
| GOOGLE_CLOUD_PROJECT | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend,render-scraper | no value in .env |
| GROQ_API_KEY_DEPLOYMENT_MONITOR | ✗ empty | - | EMPTY | ✗ | ? | ✗ | firebase-gcp,infisical-vault | no value in .env |
| HF_API_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| KEYCHAIN_PATH | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| KMS_KEY_NAME | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| LANGSMITH_API_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| LAUNCHDARKLY_AI_CONFIG_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| LAUNCHDARKLY_SDK_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| LITELLM_API_KEY | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| LOAD_TEST_TOKEN | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| LOG_TOKENS | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| MAX_TOTAL_TOKENS | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| MINIO_ACCESS_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| MINIO_SECRET_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| MOONSHOT_API_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| NEO4J_PASSWORD | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| NEO4J_URI | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| NEO4J_USER | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| NETLIFY_AUTH_TOKEN | ✗ empty | - | EMPTY | ✗ | ? | ✗ | github-actions,infisical-vault | no value in .env |
| NEXT_PUBLIC_SUPABASE_ANON_KEY | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| NEXTAUTH_URL | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| NVIDIA_API_KEY | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| ORACLE_CLOUD_API_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| PINECONE_API_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| PLANDEX_API_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| PLAYWRIGHT_MCP_EXTENSION_TOKEN | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| POSTHOG_API_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| PYDANTIC_PRIVATE_ALLOW_UNHANDLED_SCHEMA_TYPES | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| PYTHAGORA_API_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| PYTHON_KEYRING_BACKEND | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| R2_ACCESS_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| R2_SECRET_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| RAILWAY_TOKEN | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| RATE_LIMIT_FALLBACK_MAX_KEYS | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| REDIS_KEY_PREFIX | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| REDIS_TOKEN | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| RETRY_BUDGET_MAX_TOKENS | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| SECONDARY_SERVICE_ACCOUNT_KEY | — absent | - | EMPTY | ✗ | ? | ✗ | firebase-gcp,infisical-vault | no value in .env |
| SECRET_CACHE_TTL | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| SENDGRID_API_KEY | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| SLACK_BOT_TOKEN | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| SMTP_PASSWORD | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| SSLKEYLOGFILE | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| SUPABASE_ANON_KEY | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| SUPREMEAI_EMAIL_PASSWORD | ✗ empty | - | EMPTY | ✗ | ? | ✗ | firebase-gcp,infisical-vault | no value in .env |
| SUPREMEAI_SOLVER_API_KEY | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| TOGETHER_API_KEY | ✗ empty | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| TOKEN_JUICE_ENABLED | ✓ | tr…(4) | UNVERIFIABLE | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no provider-format rule |
| TWILIO_AUTH_TOKEN | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| UPSTASH_REDIS_TOKEN | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| VITE_ADMIN_BACKEND | ✓ | http…(36) | UNVERIFIABLE | ✗ | ? | ✗ | infisical-vault,vercel-frontend | no provider-format rule |
| VITE_API_BASE | ✓ | http…(55) | UNVERIFIABLE | ✗ | ? | ✗ | github-actions,infisical-vault,vercel-frontend | no provider-format rule |
| VITE_API_BASE_URL | ✓ | http…(55) | UNVERIFIABLE | ✗ | ? | ✗ | github-actions,infisical-vault | no provider-format rule |
| VITE_API_URL | ✓ | http…(55) | UNVERIFIABLE | ✗ | ? | ✗ | infisical-vault,vercel-frontend | no provider-format rule |
| VITE_FIREBASE_APP_ID | ✓ | 1:11…(44) | UNVERIFIABLE | ✗ | ? | ✗ | infisical-vault,vercel-frontend | no provider-format rule |
| VITE_FIREBASE_AUTH_DOMAIN | ✓ | supr…(27) | UNVERIFIABLE | ✗ | ? | ✗ | infisical-vault,vercel-frontend | no provider-format rule |
| VITE_FIREBASE_MESSAGING_SENDER_ID | ✓ | 1104…(21) | UNVERIFIABLE | ✗ | ? | ✗ | infisical-vault,vercel-frontend | no provider-format rule |
| VITE_FIREBASE_STORAGE_BUCKET | ✓ | supr…(23) | UNVERIFIABLE | ✗ | ? | ✗ | infisical-vault,vercel-frontend | no provider-format rule |
| VITE_SUPABASE_ANON_KEY | ✓ | eyJh…(208) | UNVERIFIABLE | ✗ | ? | ✗ | github-actions,infisical-vault | no provider-format rule |
| VITE_SUPABASE_URL | ✓ | http…(40) | UNVERIFIABLE | ✗ | ? | ✗ | github-actions,infisical-vault | no provider-format rule |
| VITE_USER_BACKEND | ✓ | http…(55) | UNVERIFIABLE | ✗ | ? | ✗ | infisical-vault,vercel-frontend | no provider-format rule |
| WS_AUTH_WINDOW_SECONDS | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
| WS_MAX_AUTH_ATTEMPTS | — absent | - | EMPTY | ✗ | ? | ✗ | infisical-vault,render-admin,render-backend | no value in .env |
