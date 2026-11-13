# SupremeAI — Static Codebase Checking Checklist

> **Purpose:** Everything an auditor can verify by **reading code, diffs, configs, and CI logs** — no live services required. Complements the runtime checklist in `prompt2.md`. Each item includes **how to verify** so results are reproducible.
>
> **Format:** `[ ]` = Not checked yet | `[x]` = Passed | `[!]` = Failed + reason in Note column | `[~]` = N/A

---

## 0. How to Use This Checklist

```bash
# Clone both repos at the exact SHA you are auditing
git clone https://github.com/Supremeai-bd/supremeai.git && cd supremeai && git rev-parse HEAD
git clone https://github.com/Supremeai-bd/supremeai-frontend.git
```

Record the SHA at the top of your report. **Never audit a moving branch.** All checks below assume a pinned SHA.

**Audit Metadata:**
- **Auditor:** ____________________
- **Pinned Git SHA:** ____________________
- **Audit Date:** ____________________
- **Target Repository:** `Supremeai-bd/supremeai` & `Supremeai-bd/supremeai-frontend`

---

## 1. Repository & Branch Hygiene

| # | Check Item | How to verify | Status | Note |
|---|---|---|---|---|
| 1.1 | `main` is protected (no direct pushes, required reviews) | GitHub → Settings → Branches | `[ ]` | |
| 1.2 | No long‑lived feature branches >30 days | `git branch -r --sort=-committerdate` | `[ ]` | |
| 1.3 | No merge commits on `main` (squash‑only policy enforced) | `git log --merges main` → expect empty | `[ ]` | |
| 1.4 | Commit messages follow convention (Conventional Commits / project standard) | `git log --oneline -50` | `[ ]` | |
| 1.5 | No committed binaries, build artifacts, or `node_modules`/`__pycache__` | `git ls-files \| grep -E '\.(pyc\|zip\|whl\|so\|dll)$'` | `[ ]` | |
| 1.6 | `.gitignore` covers `.env*`, `*.pem`, `*.key`, `dist/`, `.venv/` | Read `.gitignore` | `[ ]` | |
| 1.7 | Satellite repos are **archived** (read‑only) per SSOT policy | GitHub repo → Settings → Archive | `[ ]` | |
| 1.8 | No stale open PRs against retired satellite repos | GitHub PR list per repo | `[ ]` | |
| 1.9 | `CODEOWNERS` present and accurate | Read `.github/CODEOWNERS` | `[ ]` | |
| 1.10 | Issue/PR templates present | `.github/ISSUE_TEMPLATE/`, `PULL_REQUEST_TEMPLATE.md` | `[ ]` | |

---

## 2. Structure & Module Boundaries

| # | Check Item | How to verify | Status | Note |
|---|---|---|---|---|
| 2.1 | Directory layout matches documented architecture (Gateway / Core / Brain / Worker / Scraper) | Compare tree to README | `[ ]` | |
| 2.2 | No circular imports between top‑level modules | `pydeps .` or `python -c "import gateway"` + `import-linter` | `[ ]` | |
| 2.3 | Gateway routes do not import service internals directly (must go through service layer) | `grep -r "from services\." gateway/routes/` | `[ ]` | |
| 2.4 | Shared utilities live in one place (no duplicated helpers) | Search for repeated function names | `[ ]` | |
| 2.5 | Route files are registered in a single router aggregator (no orphan routes) | Inspect `gateway/main.py` include_router calls vs. `ls gateway/routes/` | `[ ]` | |
| 2.6 | No dead/duplicate route files (e.g., two `admin_*.py` doing the same) | Compare `ls gateway/routes/` against router registration | `[ ]` | |
| 2.7 | Import depth ≤ project convention (no `../../../../`) | `grep -r "\.\./\.\./\.\./"` | `[ ]` | |
| 2.8 | Frontend: no absolute imports escaping `src/`; path aliases used | Read `tsconfig.json` `paths` | `[ ]` | |

---

## 3. Dependencies & Supply Chain

| # | Check Item | How to verify | Status | Note |
|---|---|---|---|---|
| 3.1 | Lockfiles committed (`bun.lock`, `poetry.lock`/`requirements.txt` with hashes) | `ls` repo root | `[ ]` | |
| 3.2 | No unpinned `>=`/`*` versions in production requirements | `grep -E ">=|\*" requirements*.txt` | `[ ]` | |
| 3.3 | Dependency versions consistent across services (no two Redis client versions) | Compare each service's requirements | `[ ]` | |
| 3.4 | No known‑vulnerable packages | `pip-audit`, `npm audit --production`, Dependabot alerts | `[ ]` | |
| 3.5 | No duplicate/conflicting libraries (e.g., `requests` **and** `httpx` **and** `aiohttp` for the same job) | `grep -rE "import (requests\|httpx\|aiohttp)"` | `[ ]` | |
| 3.6 | Dev dependencies separated from runtime | `requirements-dev.txt` / `devDependencies` | `[ ]` | |
| 3.7 | License compatibility reviewed (GPL in a proprietary product?) | `pip-licenses`, `license-checker` | `[ ]` | |
| 3.8 | No `git+https://` or path‑based deps in production lockfile | Inspect lockfile | `[ ]` | |
| 3.9 | Frontend bundle: no accidental heavy deps (moment, lodash full, etc.) | `bun pm ls` / bundle analyzer | `[ ]` | |

---

## 4. Configuration & Secrets

| # | Check Item | How to verify | Status | Note |
|---|---|---|---|---|
| 4.1 | Zero hardcoded secrets, API keys, tokens, passwords | `gitleaks detect`, `trufflehog`, `grep -rE "(sk-\|AKIA\|ghp_\|eyJ)"` | `[ ]` | |
| 4.2 | No secrets in git history (even if removed from HEAD) | `gitleaks detect --log-opts="--all"` | `[ ]` | |
| 4.3 | All config read from env / Infisical — no fallback literals for sensitive values | `grep -rE "os.getenv\(.*, *['\"]"` → inspect defaults | `[ ]` | |
| 4.4 | `.env.example` lists every required var with safe placeholders | Diff `.env.example` against `grep -rhoE "os.getenv\(['\"][A-Z_]+"` | `[ ]` | |
| 4.5 | Startup fails fast if required env missing (no silent `None`) | Read config loader | `[ ]` | |
| 4.6 | Feature flags have safe defaults (off in prod unless intended) | `grep -r "FEATURE_\|flag"` | `[ ]` | |
| 4.7 | Public config endpoint exposes **no** secrets | Read `public_config.py` | `[ ]` | |
| 4.8 | No debug/verbose flags hardcoded `True` | `grep -rE "DEBUG\s*=\s*True\|debug=True"` | `[ ]` | |
| 4.9 | CORS origins are an explicit allowlist, not `["*"]` | `grep -r "allow_origins"` | `[ ]` | |
| 4.10 | Internal‑only routes guarded (not exposed via public router) | Read `internal.py`, router registration | `[ ]` | |

---

## 5. Authentication & Authorization

| # | Check Item | How to verify | Status | Note |
|---|---|---|---|---|
| 5.1 | Every private route has an auth dependency | `grep -L "Depends(get_current_user)\|require_auth" gateway/routes/*.py` | `[ ]` | |
| 5.2 | Auth middleware applied globally, not per‑route‑by‑accident | Read `main.py` middleware stack | `[ ]` | |
| 5.3 | Token validation checks signature, expiry, issuer, audience | Read JWT verification | `[ ]` | |
| 5.4 | Session refresh invalidates old token (rotation) | Read refresh handler | `[ ]` | |
| 5.5 | Logout revokes server‑side session, not just client cookie | Read logout handler | `[ ]` | |
| 5.6 | Admin routes require `admin_god` / role guard **and** JIT OTP | Read `admin_god` dependency + OTP flow | `[ ]` | |
| 5.7 | OTP: rate‑limited, single‑use, time‑bounded, channel fallback logged | Read `approval_manager` / OTP module | `[ ]` | |
| 5.8 | API keys: hashed at rest, scoped, revocable, last‑used tracked | Read API key model + service | `[ ]` | |
| 5.9 | Tenant isolation: every query scoped by `tenant_id`/`user_id` | `grep -r "select(" ` → confirm filters | `[ ]` | |
| 5.10 | No IDOR: path params validated against caller's ownership | Spot‑check `/{id}` routes | `[ ]` | |
| 5.11 | Role checks on **every** mutating admin endpoint, not just UI | `grep -rn "def .*admin" gateway/routes/` → inspect each | `[ ]` | |
| 5.12 | SSO callback validates `state` and nonce | Read SSO handler | `[ ]` | |

---

## 6. API Surface & Contracts

| # | Check Item | How to verify | Status | Note |
|---|---|---|---|---|
| 6.1 | OpenAPI schema generates without errors | `python -c "from gateway.main import app; app.openapi()"` | `[ ]` | |
| 6.2 | Every route has a response model (no bare `dict`) | `grep -rn "response_model=None\|-> dict"` | `[ ]` | |
| 6.3 | Consistent versioning (`/v1/...`) | `grep -r "APIRouter(" gateway/routes/` | `[ ]` | |
| 6.4 | Consistent error envelope `{code, message, detail?}` | Read exception handlers | `[ ]` | |
| 6.5 | Pagination on all list endpoints (no unbounded `SELECT *`) | `grep -rn "def list_\|\.all()"` | `[ ]` | |
| 6.6 | HTTP verbs semantically correct (no `GET` that mutates) | Scan route decorators | `[ ]` | |
| 6.7 | Deprecated routes marked and documented | `grep -rn "deprecated=True"` | `[ ]` | |
| 6.8 | No debug/dev‑only routes exposed in prod build | `grep -rn "/debug\|/test"` | `[ ]` | |
| 6.9 | Webhooks validate HMAC signature before processing | Read `repos.py`, `webhooks_*.py` | `[ ]` | |
| 6.10 | SSE/stream endpoints handle client disconnect | Read streaming generators for `finally`/`CancelledError` | `[ ]` | |

---

## 7. Input Validation & Sanitization

| # | Check Item | How to verify | Status | Note |
|---|---|---|---|---|
| 7.1 | All request bodies use Pydantic models (no raw `Request.json()` unchecked) | `grep -rn "await request.json()"` | `[ ]` | |
| 7.2 | File uploads validated: size, MIME, extension, magic bytes | Read `upload_validator` | `[ ]` | |
| 7.3 | File paths sanitized (no `../` traversal) | `grep -rn "os.path.join\|Path("` → inspect user input | `[ ]` | |
| 7.4 | SQL: parameterized only — zero f‑string SQL | `grep -rnE "f['\"].*(SELECT\|INSERT\|UPDATE\|DELETE)"` | `[ ]` | |
| 7.5 | Shell: no `shell=True` with user input | `grep -rn "shell=True\|subprocess"` | `[ ]` | |
| 7.6 | SSRF: outbound URLs validated (allowlist / block private IPs) | Read `stealth_webhook`, scraper URL fetch | `[ ]` | |
| 7.7 | Prompt injection defense active on user input into LLM | Read gateway prompt‑injection filter | `[ ]` | |
| 7.8 | HTML/JS output escaped (XSS) in frontend and any HTML response | `grep -rn "dangerouslySetInnerHTML"` | `[ ]` | |
| 7.9 | JSON depth/size limits set | Read body size middleware | `[ ]` | |

---

## 8. Data Layer & Migrations

| # | Check Item | How to verify | Status | Note |
|---|---|---|---|---|
| 8.1 | Alembic `head` matches ORM models (no pending autogenerate diff) | `alembic check` | `[ ]` | |
| 8.2 | Every migration has working `downgrade()` | `grep -L "def downgrade" migrations/versions/*.py` | `[ ]` | |
| 8.3 | Migrations are immutable post‑merge (no edits to applied ones) | Git history of `migrations/versions/` | `[ ]` | |
| 8.4 | RLS enabled on every user‑facing table | Supabase SQL: `select tablename from pg_tables where rowsecurity=false` | `[ ]` | |
| 8.5 | RLS policies cover SELECT/INSERT/UPDATE/DELETE, not just SELECT | Query `pg_policies` | `[ ]` | |
| 8.6 | DB sessions always closed (context managers / `finally`) | `grep -rn "SessionLocal()\|create_engine"` → inspect usage | `[ ]` | |
| 8.7 | No `SELECT *` on wide tables in hot paths | `grep -rn "select(\*)\|SELECT \*"` | `[ ]` | |
| 8.8 | Indexes exist for columns used in WHERE/JOIN on large tables | Compare query patterns to indexes | `[ ]` | |
| 8.9 | N+1 queries absent (use `selectinload`/`joinedload`) | Read ORM relationship access in loops | `[ ]` | |
| 8.10 | Transactions used for multi‑write operations | `grep -rn "commit()"` in multi‑step flows | `[ ]` | |
| 8.11 | Redis: keys namespaced, TTLs set (no unbounded growth) | `grep -rn "\.set(\|\.setex("` | `[ ]` | |
| 8.12 | Redis client uses pooled connections | Read cache init | `[ ]` | |

---

## 9. Error Handling & Logging

| # | Check Item | How to verify | Status | Note |
|---|---|---|---|---|
| 9.1 | No bare `except:` / `except Exception: pass` swallowing errors | `grep -rn "except:" \| grep -rn "except Exception:.*pass"` | `[ ]` | |
| 9.2 | Exceptions mapped to sanitized HTTP responses (no stack traces) | Read global exception handler | `[ ]` | |
| 9.3 | Structured logging (JSON) with request‑id / trace‑id | `grep -rn "logger\.\|structlog"` | `[ ]` | |
| 9.4 | No secrets/PII/tokens in log lines | `grep -rnE "logger\.(info\|debug).*(token\|password\|key\|otp)"` | `[ ]` | |
| 9.5 | Log levels correct (`debug` not used in hot path in prod) | Scan `logger.debug` | `[ ]` | |
| 9.6 | Failed webhook/external calls retried with backoff, then dead‑lettered | Read retry wrappers | `[ ]` | |
| 9.7 | 4xx vs 5xx correct (validation ≠ server error) | Read `HTTPException` usage | `[ ]` | |
| 9.8 | User‑facing errors do not leak internals | Read error envelope builder | `[ ]` | |

---

## 10. Async, Concurrency & Resources

| # | Check Item | How to verify | Status | Note |
|---|---|---|---|---|
| 10.1 | No blocking I/O in `async def` (sync DB/HTTP/file calls) | `grep -rn "requests\.\|time\.sleep\|open("` inside async | `[ ]` | |
| 10.2 | All `httpx`/`aiohttp` clients reused, not created per request | `grep -rn "AsyncClient("` | `[ ]` | |
| 10.3 | Background tasks have timeouts and error handling | Read `BackgroundTasks`/Celery/worker usage | `[ ]` | |
| 10.4 | Semaphores/rate‑limits on outbound calls (no thundering herd) | Read circuit‑breaker/limiter | `[ ]` | |
| 10.5 | Websocket handlers clean up on disconnect | Read `ws` routes for `finally`/`WebSocketDisconnect` | `[ ]` | |
| 10.6 | Thread/process pools bounded | `grep -rn "ThreadPoolExecutor\|ProcessPoolExecutor"` | `[ ]` | |
| 10.7 | No unbounded in‑memory caches / dicts | `grep -rn "= {}\|lru_cache"` → assess | `[ ]` | |
| 10.8 | Graceful shutdown handler flushes in‑flight work | Read `lifespan`/`shutdown` events | `[ ]` | |

---

## 11. External Integrations & Webhooks

| # | Check Item | How to verify | Status | Note |
|---|---|---|---|---|
| 11.1 | Every integration has timeout + retry + circuit breaker | Read integration client wrappers | `[ ]` | |
| 11.2 | Webhooks idempotent (replay safe) | Read `webhooks_*.py`, `n8n`, `ci_webhooks` | `[ ]` | |
| 11.3 | Payment webhook signature verified before state change | Read billing webhook | `[ ]` | |
| 11.4 | GitHub webhook HMAC validated (`X‑Hub‑Signature‑256`) | Read `repos.py` | `[ ]` | |
| 11.5 | MCP tool names match contract (dotted vs snake_case) | Compare README spec to `mcp_tower` route + tool registry | `[ ]` | |
| 11.6 | Third‑party failures degrade gracefully (no 500 to user) | Read fallback paths | `[ ]` | |
| 11.7 | OAuth tokens stored encrypted at rest | Read token store | `[ ]` | |
| 11.8 | Egress allowlist / IP blocklist honored by scraper | Read `ip_blocklist`, browser `session_manager` | `[ ]` | |

---

## 12. LLM / AI‑Specific Checks

| # | Check Item | How to verify | Status | Note |
|---|---|---|---|---|
| 12.1 | System prompts not leakable via user input | Read prompt assembly | `[ ]` | |
| 12.2 | Token/cost budgets enforced per request (`cost_guard`) | Read guard middleware | `[ ]` | |
| 12.3 | Model routing configurable without deploy (`admin_llm`) | Read routing layer | `[ ]` | |
| 12.4 | Streaming cancellation stops upstream LLM call | Read SSE generator `finally` | `[ ]` | |
| 12.5 | Tool‑calling validated against allowlist (`tool_pruner`, MCP policy) | Read tool dispatch | `[ ]` | |
| 12.6 | RAG context sanitized (no prompt‑injected instructions from docs) | Read retrieval → prompt path | `[ ]` | |
| 12.7 | Memory writes scoped per user/tenant (no cross‑contamination) | Read memory layer | `[ ]` | |
| 12.8 | Eval harness covers prompt regression | `ls evals/` | `[ ]` | |
| 12.9 | Adversarial prompt suite present and green in CI | Read CI workflow | `[ ]` | |

---

## 13. Frontend Codebase

| # | Check Item | How to verify | Status | Note |
|---|---|---|---|---|
| 13.1 | `tsc --noEmit` clean | `bun run typecheck` (or `npx tsc --noEmit`) | `[ ]` | |
| 13.2 | ESLint clean, no `any` escapes in core paths | `bun run lint`; `grep -rn ": any"` | `[ ]` | |
| 13.3 | No secrets in `NEXT_PUBLIC_*` beyond truly public values | `grep -rn "NEXT_PUBLIC_"` | `[ ]` | |
| 13.4 | Auth guard on all protected pages (middleware + layout) | Read `middleware.ts`, layout files | `[ ]` | |
| 13.5 | API calls go through one client with error handling | `grep -rn "fetch("` — inspect | `[ ]` | |
| 13.6 | No `localStorage` for tokens/sensitive data | `grep -rn "localStorage"` | `[ ]` | |
| 13.7 | i18n keys complete for `en` and `bn` | Diff locale key sets | `[ ]` | |
| 13.8 | Accessibility: semantic HTML, labels, focus states | Read key components; `axe` in CI | `[ ]` | |
| 13.9 | No unused deps / dead pages | `ts-prune`, `bun pm ls` | `[ ]` | |
| 13.10 | Bundle budget enforced in CI | Read workflow for size check | `[ ]` | |

---

## 14. Testing

| # | Check Item | How to verify | Status | Note |
|---|---|---|---|---|
| 14.1 | Unit + integration tests exist for each route module | `ls tests/` vs `ls gateway/routes/` | `[ ]` | |
| 14.2 | Coverage threshold enforced in CI | Read `pytest.ini`/`pyproject.toml` + workflow | `[ ]` | |
| 14.3 | No skipped/xfail tests without ticket reference | `grep -rn "skip\|xfail"` | `[ ]` | |
| 14.4 | Tests do not hit real external services (mocked) | `grep -rn "requests\.\|http" tests/` | `[ ]` | |
| 14.5 | Security tests for auth bypass / IDOR present | `ls tests/security/` | `[ ]` | |
| 14.6 | Webhook signature tests exist | `grep -rn "signature\|hmac" tests/` | `[ ]` | |
| 14.7 | Frontend E2E exists (Playwright/Cypress) covering login→chat→agent | `ls e2e/` | `[ ]` | |
| 14.8 | Flaky tests quarantined, not disabled | CI history | `[ ]` | |

---

## 15. CI/CD & Release Gates

| # | Check Item | How to verify | Status | Note |
|---|---|---|---|---|
| 15.1 | `unified-pipeline.yml` runs on PR and `main` | Read workflow | `[ ]` | |
| 15.2 | All 7 PR guards defined and required (branch protection) | Compare workflow jobs to required checks | `[ ]` | |
| 15.3 | Python matrix versions match prod runtime | Read matrix vs Render runtime | `[ ]` | |
| 15.4 | Lint + typecheck + tests + security scan all gating | Read job dependencies | `[ ]` | |
| 15.5 | Deploy job pinned to a SHA, not `latest` | Read deploy step | `[ ]` | |
| 15.6 | Rollback step defined and tested (manual or auto) | Read deploy workflow | `[ ]` | |
| 15.7 | No `continue-on-error: true` on security gates | `grep -rn "continue-on-error"` | `[ ]` | |
| 15.8 | Secrets in CI come from GitHub Secrets/Vault, not repo | Read workflow `env:` | `[ ]` | |
| 15.9 | Satellite dispatch is read‑only (no push back) | Read dispatch job | `[ ]` | |

---

## 16. Documentation & Operability

| # | Check Item | How to verify | Status | Note |
|---|---|---|---|---|
| 16.1 | README has runnable setup (no missing steps) | Follow it in a clean clone | `[ ]` | |
| 16.2 | `CONSUMERS.md` matches actual route/webhook consumers | Cross‑check | `[ ]` | |
| 16.3 | `OpenAPI` schema committed or generated in CI | `ls docs/` / workflow | `[ ]` | |
| 16.4 | Runbooks for: rollback, DB restore, key rotation, incident | `ls docs/runbooks/` | `[ ]` | |
| 16.5 | Env var reference complete (every var documented) | Diff `grep os.getenv` vs docs | `[ ]` | |
| 16.6 | Architecture diagram current | Compare to `ls gateway/routes` | `[ ]` | |
| 16.7 | Onboarding doc < 1 hour to first running test | Time yourself | `[ ]` | |
| 16.8 | Changelog / release notes maintained | `CHANGELOG.md` | `[ ]` | |

---

## 17. Performance & Scalability Smells

| # | Check Item | How to verify | Status | Note |
|---|---|---|---|---|
| 17.1 | No synchronous full‑table loads in request path | `grep -rn "\.all()"` in routes | `[ ]` | |
| 17.2 | No regex compiled per request | `grep -rn "re.compile"` outside module scope | `[ ]` | |
| 17.3 | Caching used for expensive deterministic calls | Read cache decorators | `[ ]` | |
| 17.4 | Payload sizes bounded (list endpoints paginated) | Read response models | `[ ]` | |
| 17.5 | Cold‑start‑sensitive init (heavy imports) lazy‑loaded | Read module‑level code | `[ ]` | |
| 17.6 | Connection pools sized to Render instance limits | Read engine/pool config | `[ ]` | |
| 17.7 | No per‑request model/client instantiation | `grep -rn "= Client(\|= OpenAI("` in handlers | `[ ]` | |

---

## 18. Maintainability & Code Quality

| # | Check Item | How to verify | Status | Note |
|---|---|---|---|---|
| 18.1 | Function length reasonable (no 500‑line handlers) | `ruff check` / radon | `[ ]` | |
| 18.2 | No duplicated logic across services (copy‑paste detection) | `jscpd` / `pylint duplicate-code` | `[ ]` | |
| 18.3 | Type hints on public functions (Python) | `mypy` (if configured) | `[ ]` | |
| 18.4 | No commented‑out code blocks >10 lines | `grep -rn "^#.*def \|^#.*class "` | `[ ]` | |
| 18.5 | TODO/FIXME tracked in issues, not buried | `grep -rn "TODO\|FIXME\|HACK"` | `[ ]` | |
| 18.6 | Naming consistent (one term per concept) | Spot‑check | `[ ]` | |
| 18.7 | No magic numbers without constants | `grep -rnE "[^a-zA-Z_][0-9]{3,}"` | `[ ]` | |

---

## 19. Top Red Flags — Auto‑Fail if Any Present

| # | Red Flag | How to verify | Status | Note |
|---|---|---|---|---|
| 19.1 | Secret in repo or git history | `gitleaks detect --all` | `[ ]` | |
| 19.2 | `SELECT *` concatenated with user input (SQLi) | manual grep | `[ ]` | |
| 19.3 | Auth dependency missing on a mutating route | route‑by‑route scan | `[ ]` | |
| 19.4 | `allow_origins=["*"]` in prod config | grep | `[ ]` | |
| 19.5 | `except Exception: pass` around a security check | grep | `[ ]` | |
| 19.6 | Deployed SHA ≠ audited SHA | compare | `[ ]` | |
| 19.7 | RLS disabled on a user‑facing table | Supabase query | `[ ]` | |
| 19.8 | Payment/webhook handler without signature check | read | `[ ]` | |
| 19.9 | `shell=True` with request data | grep | `[ ]` | |
| 19.10 | Admin route reachable without `admin_god` | route scan | `[ ]` | |

---

## 20. Scoring & Sign‑off

| Section | Passed | Failed | N/A | Notes |
|---|---|---|---|---|
| 1. Repo Hygiene | /10 | | | |
| 2. Structure | /8 | | | |
| 3. Dependencies | /9 | | | |
| 4. Config & Secrets | /10 | | | |
| 5. Auth & RBAC | /12 | | | |
| 6. API Surface | /10 | | | |
| 7. Input Validation | /9 | | | |
| 8. Data Layer | /12 | | | |
| 9. Error & Logging | /8 | | | |
| 10. Async & Resources | /8 | | | |
| 11. Integrations | /8 | | | |
| 12. LLM / AI | /9 | | | |
| 13. Frontend | /10 | | | |
| 14. Testing | /8 | | | |
| 15. CI/CD | /9 | | | |
| 16. Docs & Runbooks | /8 | | | |
| 17. Performance | /7 | | | |
| 18. Maintainability | /7 | | | |
| 19. Red Flags | /10 | | | |
| **Total** | **/172** | | | |

- **Final Verdict:** `[ ] PASS` / `[ ] PASS WITH FIXES` / `[ ] BLOCK`
- **Blocking Items Identified:** ____________________
- **Auditor Name & Signature:** ____________________
- **Audit Date:** ____________________
- **Audit Commit SHA:** ____________________

