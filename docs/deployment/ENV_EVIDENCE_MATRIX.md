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

Incremental pass: **2026-09-15** (public-probe re-verification from an
automation session: docs trio `404`, `/health/full` per-check evidence incl.
database `healthy`/critical, frontend zero-console-error QA; REQUIRED-registry
coverage completed — every `required` and condition-bearing `conditional`
spec in `backend/core/config_classification.py` now has a row below;
drift-guard test `backend/tests/test_env_evidence_matrix.py` added).

---

## 1. Core backend (Render: supremeai-primary-node)

| Variable | Source | Required? | Service | Verified? | Date |
| --- | --- | --- | --- | --- | --- |
| `DATABASE_URL` / `SUPABASE_DATABASE_URL_POOLER` | Infisical `prod` → Render env | YES (critical) | core | ✅ verified-live: `/health/full` per-check `database` → `healthy` (critical, ~13.5 ms latency) on prod core (2026-09-15); vault presence previously 🟡 (`SUPABASE_DATABASE_URL_POOLER`, `NEON_DATABASE_URL` names confirmed 2026-09-14) | 2026-09-15 |
| `REDIS_URL` | Infisical `prod` (Upstash) → Render | YES (rate-limit/auth windows) | core | 🟡 present-in-vault (`UPSTASH_REDIS_REST_URL/TOKEN` present) | 2026-09-14 |
| `SUPREMEAI_JWT_SECRET` / `JWT_SECRET` | Infisical `prod` → Render | YES (auth) | core | ✅ verified-live (boot-level): production boot fail-fast requires it and the service is continuously up (uptime ~3729 s at probe) (2026-09-15); value rotation freshness remains owner-dashboard | 2026-09-15 |
| `ENCRYPTION_KEY` | Infisical `prod` → Render | YES (secret vault at rest) | core | ✅ verified-live (boot-level): production boot fail-fast requires it; service continuously up (2026-09-15) | 2026-09-15 |
| `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` | Infisical `prod` → Render | YES | core | 🟡 present-in-vault; API reachable: `https://supremeai-primary-node.onrender.com/health/ready` → `ready` ✅ | 2026-09-14 |
| `CORS_ORIGINS` / `ADMIN_CORS_ORIGINS` | Infisical `prod` → Render | YES (auth+CORS chain) | core | 🟡 present-in-vault; functional chain observed: deployed app at `https://supremeai-a.web.app` loads and user-portal cross-origin calls succeed with zero console errors (2026-09-15); value equality still needs dashboard confirm. NOTE: `USER_CORS_ORIGINS` (used by earlier revisions of this row) is a registry-documented legacy alias (see ALIAS_TO_CANONICAL in the registry) — canonical names are `CORS_ORIGINS` / `ADMIN_CORS_ORIGINS` | 2026-09-15 |
| `ALLOWED_HOSTS` | Infisical `prod` → Render | YES | core | 🟡 present-in-vault | 2026-09-14 |
| `BACKEND_URL` (canonical self URL) | Infisical `prod` → Render | YES | core | ✅ live: `/health/live` → `alive`, `/health/ready` → `ready` (re-probed 2026-09-15) | 2026-09-15 |
| LLM provider keys (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY`) | Infisical `prod` → Render | YES (boot alerts if zero) | core | 🟡 present-in-vault (names confirmed; CI logs show "Mocking missing secret LLM_PROVIDER_KEYS" only in LOCAL env, not prod) | 2026-09-14 |
| `SUPREMEAI_DOCS_ENABLED` / `SUPREMEAI_DOCS_PASSWORD` | docs exposure policy → Render | Optional: only set `SUPREMEAI_DOCS_ENABLED=true` if docs must be on; password then mandatory (≥12 chars, fail-fast) | core | ✅ verified-live: `/docs`, `/redoc`, `/openapi.json` all → `404` on prod core (2026-09-15) — default-OFF policy is ACTIVE; no action needed unless docs must be turned on | 2026-09-15 |
| `ENV` / `PORT` / `HOST` | Render env (host-direct) | YES | core | ✅ verified-live: `/health/full` payload shows `"environment": "production"`, `"platform": "render"`; service bound and serving (2026-09-15) | 2026-09-15 |
| `FRONTEND_URL` / `APP_BASE_URL` | Render env | YES | core | ✅ functional: `https://supremeai-a.web.app` serving; user-portal cross-origin calls succeed, zero console/page errors (agent-browser QA 2026-09-15) | 2026-09-15 |
| `SUPREMEAI_USER_BACKEND_URL` | Render env (canonical user backend location) | YES | core, deploy | ✅ functional: user portal reaches core (composer renders; backend serving) (2026-09-15) | 2026-09-15 |
| `SUPREMEAI_ADMIN_BACKEND_URL` | Render env (canonical admin backend location) | YES | core, deploy | ⬜ pending — admin-portal authenticated flow needs operator creds to verify end-to-end | — |
| `ALLOWED_ORIGINS` | Render env (legacy-compat input; canonical resolver owns interpretation) | YES | core | 🟡 present-in-vault; functional CORS chain for user portal observed (2026-09-15); value equality needs dashboard confirm | 2026-09-15 |
| `SUPABASE_KEY` | Infisical `prod` → Render | YES (secret) | core | 🟡 present-in-vault (paired with `SUPABASE_URL`) | 2026-09-14 |
| `SUPREMEAI_ADMIN_PASSWORD_HASH` | Infisical `prod` → Render | YES (secret) | core | ⬜ pending — admin login flow verification requires operator creds | — |
| `ADMIN_URL` — when admin aggregation enabled | Render env | Conditional | core | ⬜ pending — feature-flag state unverified | — |
| `CHECKOUT_BASE_URL` — when billing enabled | Render env | Conditional | core | ⬜ pending — billing-flag state unverified | — |
| `SUPABASE_DB_CA_CERT` — when explicit PostgreSQL CA verification enabled | Infisical `prod` | Conditional | core | ⬜ pending — CA-verification mode unverified | — |

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
| `VITE_PORTAL_TYPE` + `VITE_FIREBASE_API_KEY` / `VITE_FIREBASE_AUTH_DOMAIN` / `VITE_FIREBASE_PROJECT_ID` / `VITE_FIREBASE_STORAGE_BUCKET` / `VITE_FIREBASE_MESSAGING_SENDER_ID` / `VITE_FIREBASE_APP_ID` | Firebase build env (baked at build time) | YES (baked) | frontend build | ✅ verified-live: deployed build initializes Firebase auth UI and portal mode, zero console/page errors (agent-browser QA) (2026-09-15) | 2026-09-15 |

## 4. Platform evidence (deployments & CI)

| Item | Source | Required? | Verified? | Date |
| --- | --- | --- | --- | --- |
| Render core deploy `live` | Render API / status page | YES | ✅ `/health/ready` returns `ready` (17:07+ deploy per earlier session, re-probed today) | 2026-09-14 |
| Firebase frontend `web.app` serving | https://supremeai-a.web.app | YES | ✅ UI renders (chat, sign-in, workspace) | 2026-09-14 |
| CI Pipeline (PR CI) | GitHub Actions | YES | ✅ PR CI green across the queued hardening stack (e.g. #353 @ ecfe38a5: 19✓/0✗/7 skipped, 2026-09-15); `main` RED trio is known #352 fallout with heal #355 queued green | 2026-09-15 |
| Vercel `supremeai` project preview | vercel.com (paykaribazaronline acct) | Optional preview | ✅ READY | 2026-09-14 |
| Vercel `supremeai-frontend` + `browser` projects | vercel.com/supremeai1 team (NO token access from automation) | Optional | ⬜ **Error state since PR #287** — pre-existing; re-observed 2026-09-15 as permanent failure statuses riding on PR heads (non-required checks); requires login to the `supremeai1` Vercel team to read build logs; not a blocker for Firebase production path | 2026-09-15 |
| `INFISICAL_CLIENT_ID` / `INFISICAL_CLIENT_SECRET` / `INFISICAL_PROJECT_ID` | Render env (Universal Auth connector) → CI | YES (secret) | ci + core bootstrap | ✅ CI-level: green pipeline runs bootstrap secrets via Infisical Universal Auth (2026-09-15); rotation freshness = owner dashboard | 2026-09-15 |
| `RENDER_API_KEY` — when automated Render deployment enabled | CI secret | Conditional | ci | ⬜ pending — deployment-automation scope unverified | — |
| `RENDER_PRIMARY_SVC_ID` — when primary Render service automation enabled | CI secret / dashboard | Conditional | ci | 🟡 cross-referenced: Node-1 service ID recorded in `SUPREMEAI_CLUSTER_MASTER_ENV_SPEC.md` (owner-verified checklist) | 2026-09-14 |
| `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` — when Cloudflare deployment enabled | CI secret | Conditional | ci | ⬜ pending — Cloudflare path optional; not part of the Firebase production chain | — |

## 5. Owner pending actions (fill the ⬜ and 🟡 columns)

1. Render dashboard → core service → Environment: confirm the 🟡 rows above
   (values match Infisical `prod`); export a screenshot or use
   `render env-vars list --output json` with a Render API key.
2. ~~Decide docs exposure policy rows in §1~~ **RESOLVED 2026-09-15:**
   default-OFF verified live (docs trio `404`); keep `SUPREMEAI_DOCS_ENABLED`
   unset unless docs must be turned on (strong password then mandatory).
3. Vercel team `supremeai1`: open the two failing projects
   (`supremeai-frontend`, `browser`), read build logs, or remove the projects
   if the Firebase path is the production contract (they have been Error since
   PR #287 and are not part of the Firebase+Render production chain).
4. After verification, update the Verified?/Date columns in this file — that
   is the "live evidence" the production sign-off requires.

## 6. Registry alignment (drift guard)

`backend/core/config_classification.py` is the canonical variable registry
(277 specs as of 2026-09-15). This matrix MUST mention every spec classified
`required` and every condition-bearing `conditional` spec (a `required_when`
condition). Enforcement: `backend/tests/test_env_evidence_matrix.py` fails
when —

- the registry grows a new required/condition-bearing variable without a
  matrix row here (or a row is deleted);
- a matrix row drops the ✅/🟡/⬜ verification vocabulary;
- a verified (✅) row loses its `YYYY-MM-DD` date; or
- the registry itself shrinks below its current size (silent guard-voiding).

The long tail of optional / conditional-secret variables stays
registry-authoritative and is intentionally not duplicated row-by-row here;
§1–§4 track the variables whose live correctness production sign-off depends
on. Re-run the probes in §1–§4 (curl + browser QA) after any dashboard or
registry change and update the Verified?/Date columns.
