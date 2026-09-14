# Live Environment & Secrets Evidence Matrix (P0)

> Owner sign-off requirement: *"exists in code" ≠ "correctly exists in live
> environment"*. This matrix tracks each mandatory production variable:
> **Variable → Source → Required? → Service → Verified? → Date**.
>
> Verification levels:
> - ✅ **verified-live** — probed/observed against the running service from a
>   real session on the date shown.
> - 🟡 **present-in-vault** — secret name exists in the Infisical `prod`
>   environment (138 secrets enumerated 2026-09-14); value correctness not
>   independently re-validated from this session.
> - ⬜ **pending** — owner/operator must fill in evidence (Render dashboard /
>   Supabase console / Vercel team).

Last full pass: **2026-09-14** (sandbox session; probes via agent-browser +
GitHub Actions API + Infisical SDK enumeration).

---

## 1. Core backend (Render: supremeai-primary-node)

| Variable | Source | Required? | Service | Verified? | Date |
| --- | --- | --- | --- | --- | --- |
| `DATABASE_URL` / `SUPABASE_DATABASE_URL_POOLER` | Infisical `prod` → Render env | YES (critical) | core | 🟡 present-in-vault (`SUPABASE_DATABASE_URL_POOLER`, `NEON_DATABASE_URL` also present) | 2026-09-14 |
| `REDIS_URL` | Infisical `prod` (Upstash) → Render | YES (rate-limit/auth windows) | core | 🟡 present-in-vault (`UPSTASH_REDIS_REST_URL/TOKEN` present) | 2026-09-14 |
| `SUPREMEAI_JWT_SECRET` / `JWT_SECRET` | Infisical `prod` → Render | YES (auth) | core | 🟡 present-in-vault | 2026-09-14 |
| `ENCRYPTION_KEY` | Infisical `prod` → Render | YES (secret vault at rest) | core | 🟡 present-in-vault | 2026-09-14 |
| `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` | Infisical `prod` → Render | YES | core | 🟡 present-in-vault; API reachable: `https://supremeai-primary-node.onrender.com/health/ready` → `ready` ✅ | 2026-09-14 |
| `USER_CORS_ORIGINS` / `ADMIN_CORS_ORIGINS` | Infisical `prod` → Render | YES (auth+CORS chain) | core | 🟡 present-in-vault; deployed app served at `https://supremeai-a.web.app` loads ✅ | 2026-09-14 |
| `ALLOWED_HOSTS` | Infisical `prod` → Render | YES | core | 🟡 present-in-vault | 2026-09-14 |
| `BACKEND_URL` (canonical self URL) | Infisical `prod` → Render | YES | core | ✅ live: `/health/live` → `alive`, `/health/ready` → `ready` | 2026-09-14 |
| LLM provider keys (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY`) | Infisical `prod` → Render | YES (boot alerts if zero) | core | 🟡 present-in-vault (names confirmed; CI logs show "Mocking missing secret LLM_PROVIDER_KEYS" only in LOCAL env, not prod) | 2026-09-14 |
| `SUPREMEAI_DOCS_ENABLED` / `SUPREMEAI_DOCS_PASSWORD` | NEW (this PR's docs policy) → Render | Optional: only set `SUPREMEAI_DOCS_ENABLED=true` if docs must be on; password then mandatory (≥12 chars) | core | ⬜ pending — decide: default (docs OFF in production) is the recommended state | 2026-09-14 |

## 2. Worker / Scraper / MCP nodes (Render)

| Variable | Source | Required? | Service | Verified? | Date |
| --- | --- | --- | --- | --- | --- |
| `DATABASE_URL` (role-scoped) | Infisical `prod` → each service | YES (degradation allowed per policy) | worker/scraper/mcp | 🟡 present-in-vault | 2026-09-14 |
| `REDIS_URL` | Infisical `prod` → each service | YES | worker/scraper/mcp | 🟡 present-in-vault | 2026-09-14 |
| `BACKEND_URL` of core | derived | YES (callback) | worker/scraper/mcp | 🟡 present-in-vault (`USER_BACKEND_URL`/`ADMIN_BACKEND_URL` names present) | 2026-09-14 |

## 3. Frontend (Firebase web.app build + Vercel preview)

| Variable | Source | Required? | Service | Verified? | Date |
| --- | --- | --- | --- | --- | --- |
| `VITE_API_URL` (= canonical backend) | Infisical `prod` `BACKEND_URL`/`USER_BACKEND_URL` → CI build env | YES (baked at build time) | frontend build | ✅ **automated check now enforced in CI** (`scripts/ci/verify_frontend_build_contract.py`, evidence: `ci-reports/frontend-build-contract.json`); local PASS build with `https://supremeai-primary-node.onrender.com` | 2026-09-14 |
| `VITE_USER_BACKEND` / `VITE_ADMIN_BACKEND` | same as above | YES (baked) | frontend build | ✅ same automated check | 2026-09-14 |
| `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` | Infisical `prod` | YES (client auth) | frontend build | 🟡 present-in-vault | 2026-09-14 |

## 4. Platform evidence (deployments & CI)

| Item | Source | Required? | Verified? | Date |
| --- | --- | --- | --- | --- |
| Render core deploy `live` | Render API / status page | YES | ✅ `/health/ready` returns `ready` (17:07+ deploy per earlier session, re-probed today) | 2026-09-14 |
| Firebase frontend `web.app` serving | https://supremeai-a.web.app | YES | ✅ UI renders (chat, sign-in, workspace) | 2026-09-14 |
| CI Pipeline (PR #292) | GitHub Actions | YES | ✅ 17 checks green; Backend Aggregate Gate coverage-merge bug found & fixed this round | 2026-09-14 |
| Vercel `supremeai` project preview | vercel.com (paykaribazaronline acct) | Optional preview | ✅ READY | 2026-09-14 |
| Vercel `supremeai-frontend` + `browser` projects | vercel.com/supremeai1 team (NO token access from automation) | Optional | ⬜ **Error state since PR #287** — pre-existing; requires login to the `supremeai1` Vercel team to read build logs; not a blocker for Firebase production path | 2026-09-14 |

## 5. Owner pending actions (fill the ⬜ and 🟡 columns)

1. Render dashboard → core service → Environment: confirm the 🟡 rows above
   (values match Infisical `prod`); export a screenshot or use
   `render env-vars list --output json` with a Render API key.
2. Decide docs exposure policy rows in §1 (recommended: leave
   `SUPREMEAI_DOCS_ENABLED` unset → docs stay OFF in production).
3. Vercel team `supremeai1`: open the two failing projects
   (`supremeai-frontend`, `browser`), read build logs, or remove the projects
   if the Firebase path is the production contract (they have been Error since
   PR #287 and are not part of the Firebase+Render production chain).
4. After verification, update the Verified?/Date columns in this file — that
   is the "live evidence" the production sign-off requires.
