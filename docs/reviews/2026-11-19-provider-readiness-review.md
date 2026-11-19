# SupremeAI Provider Stack — Production Readiness Review

**Date:** 2026-11-19
**Revision reviewed:** `b5d47ba` (`main`)
**Scope:** the chat / provider / agent-execution path (`gateway/`, `core/`, `infrastructure/mcp-control-plane/`, CI + docs)
**Method:** static read of the hot paths, four live service handshakes, two runnable reproductions, and the existing pytest suites executed locally.

---

## 1. Verdict in one page

The project has an unusually strong *operational shell* (work-order pipeline, contract guards, deployment attestation) wrapped around a **provider core that is currently fragile in exactly the places users notice**: rate-limit fairness, upstream URL construction, parameter passthrough, and the operator brain that is supposed to fix all of it — which is currently **suspended**.

| Area | Grade | One-line reason |
|---|---|---|
| Live API (`supremeai-api`) | **B−** | Serving `2.0.0`, healthy, but per-IP fairness and provider fan-out are broken |
| MCP Tower (operator/self-fix brain) | **F** | Public `/health` returns *“This service has been suspended by its owner.”* |
| Provider transport | **D** | Double `/v1` in every fallback URL; sampling params and `tools` dropped |
| Rate limiting | **D** | One global bucket for all anonymous traffic; Redis path is racy |
| Resilience wiring | **D** | Circuit breaker is dead code — accepted, never consulted |
| Test signal | **C−** | 628 test modules exist; PR CI runs 20 of them; `main` is already red |
| Docs / DX | **C** | Good intent, bad entry points: broken links, no local install path, contract file is unreadable |

**Highest-value sequence:** ① restore the Tower → ② fix the four P0 provider defects (three are already fixed on this branch) → ③ collapse the two competing gateways into one → ④ widen PR CI so drift like today's red test cannot land.

---

## 2. Live handshake results (evidence)

Probed directly, since the Tower itself could not be used as the handshake point.

| Service (from `config/service_registry.yaml`) | URL | Result |
|---|---|---|
| API Gateway | `supremeai-api-ulw0.onrender.com/healthz` | ✅ `{"status":"healthy","version":"2.0.0","chat_ready":true}` |
| Scraper node | `supremeai-scraper-node.onrender.com/health` | ✅ healthy, `playwright_available:false`, `lightweight_http_mode:true` |
| Primary node | `supremeai-primary-node-5xso.onrender.com/health` | ✅ healthy, DB check 149 ms |
| Tiny brain | `supremeai-tiny-brain.onrender.com/health` | ⚠️ returns `{"cache_size":0,"uptime":1795079891}` — `uptime` is an epoch timestamp, not uptime |
| **MCP Tower** | `supremeai-mcp-tower.onrender.com/health` | ❌ **“This service has been suspended by its owner.”** |

---

## 3. P0 — fix before anything else

### P0-1 · The self-fix / self-update brain is offline
**File:** `render.yaml:64` (`supremeai-mcp-tower`, `plan: free`), `.github/workflows/keepwarm.yml:24`
**Evidence:** `/health` on the Tower returns *“This service has been suspended by its owner.”* The keep-warm workflow only pings the **API** (`curl ... || echo "Gateway ping returned non-200"`), so it can never notice, and never fails, when the Tower dies.
**Why it matters:** every capability the brief asks for — *do work for others, fix himself, update himself* — is mediated by the Tower (bridge queue, work orders, landing watchdog, GitHub adapters). Suspension silently disables autonomy while every other dashboard still shows green. This is the single most damaging fact in the review.
**Fix:** move the Tower off the free plan (or onto the Cloudflare keep-warm mesh it already owns); make `keepwarm.yml` ping **all** registered services and **fail** on non-200; add an out-of-band monitor (GitHub Action every 15 min → open a P0 issue with service name + status) so suspension is loud instead of silent.

### P0-2 · Rate limiter applies one global bucket to all anonymous traffic
**File:** `gateway/main.py:177` (`check_rate_limit`) — fixed on this branch
**Evidence (reproduced):** with `max_requests=2`, two different clients (`X-Forwarded-For` last hops `…10` and `…11`) → `200, 200, 429`. Behind Render the socket peer is the proxy, so `request.client.host` is identical for every caller: one abuser spends everyone's budget, and rotating IPs buys nothing.
**Fix landed:** bucket on `_client_ip(request)` (the trusted last XFF hop, already used by the guest-daily limiter) and hash key-scoped buckets with SHA-256 so raw keys never become limiter keys. Regression test: `gateway/tests/test_provider_transport_and_limits.py::test_anonymous_rate_limit_is_per_proxy_resolved_ip`.
**Still to do:** `gateway/rate_limit.py:126` — the Redis limiter does `ZREMRANGEBYSCORE → ZCARD → ZADD` as three round-trips, so N concurrent requests can all pass the check and overshoot the limit N-fold. Replace with a single Lua script. Also `gateway/rate_limit.py:63` evicts the *insertion-oldest* key, so an attacker cycling keys evicts honest clients' counters; use LRU-by-last-seen.

### P0-3 · Every fallback-configured provider is called at `…/v1/v1/chat/completions`
**File:** `gateway/provider_chain.py:80` (`_completions_url`, replacing the `+ "/v1/chat/completions"` join) — fixed on this branch
**Evidence (reproduced with a fake transport):**
`Endpoint(provider="groq")` → `https://api.groq.com/openai/v1/v1/chat/completions`.
All entries in `_FALLBACKS` already end in `/v1`; the Gemini OpenAI-compat base ends in `/openai`. So the “just set `GROQ_API_KEY` and it works” path — the one the docstring advertises — has never worked.
**Fix landed:** explicit `_completions_url()` join handling `/v1`, `/openai`, bare-host and full-path bases, covered by a 6-case parametrized test.

### P0-4 · Sampling knobs and tool calling are silently dropped
**Files:** `gateway/main.py:809` (payload build), `gateway/provider_chain.py:256` (provider body) — fixed on this branch
**Evidence:** the payload was `{"messages", "stream"}` and the provider body was `{"model", "messages", "stream": False}`. `temperature`, `max_tokens`, `stop`, `response_format` and **`tools`** never reached any provider.
**Why it matters:** an agent platform that drops `tools` cannot “do work for others” at all — it can only chat. It also means every client that sets `temperature` sees it ignored, which looks like a model problem, not a gateway problem.
**Fix landed:** a 13-key allowlist (`_FORWARDED_KEYS`) forwarded from gateway payload → provider body, `model` always owned by the routed endpoint, plus tests asserting `tools`/`temperature`/`max_tokens` arrive.
**Follow-up:** `stream: False` is still hardcoded in the transport, so streaming is emulated; see P1-4.

### P0-5 · The circuit breaker is dead code, so a dead provider costs a full timeout on every request
**Files:** `gateway/circuit_breaker.py` (128 lines, `default_breaker` has **zero** callers), `gateway/provider_chain.py:305`, `gateway/main.py:394` + `:865`
**Evidence:** `execute_chain(..., circuit_breaker=...)` accepts the argument and never reads it; `create_app(circuit_breaker=...)` threads it through to the same no-op. `grep -rn circuit_breaker gateway/` outside that module only shows the parameter and an unrelated chaos worker.
**Why it matters:** when a provider is down, every user request pays the full 30 s transport timeout before failing over — a 5-endpoint chain can stall a request for ~2.5 minutes. It also means `/health` has no truth to report about provider state.
**Fix:** in `execute_chain`, `if not breaker.allow(provider): ledger.record(outcome="breaker_open"); continue`, `record_success` on 2xx, `record_failure` on transport errors/5xx/429; expose `breaker.snapshot()` on `/health/ready`. Or delete the module — an unused breaker is worse than none, because reviewers believe the system is protected.

### P0-6 · Admin authentication does blocking network I/O inside async handlers
**File:** `gateway/service/admin_auth.py:100` (`get_vault_secret`), used by `get_jwt_secret()` on every token issue/verify
**Evidence:** `urllib.request.urlopen(login_req, timeout=10)` and a second `urlopen(..., timeout=10)` run synchronously. Called from `async def` routes, so one cold/misconfigured Infisical lookup **blocks the event loop for up to 20 s** — all concurrent chat requests stall. Side effects: fetched secrets are written into `os.environ` and cached forever (`_vault_cache`), so a rotated secret is never picked up without a redeploy.
**Fix:** `httpx.AsyncClient` + `asyncio.gather` prefetch at lifespan startup; TTL cache (e.g. 5 min) with a single-flight lock; never mutate `os.environ`.

### P0-7 · Admin cookies are non-`Secure` in production
**Files:** `gateway/service/admin_auth.py:155` (`_get_cookie_secure_settings`), `render.yaml`
**Evidence:** the flag is derived from `ENV`, defaulting to `local` → `(secure=False, samesite="lax")`. `render.yaml` sets `NODE_ENV: production` for the Tower but **never sets `ENV` for the API service** (verified by grep). So admin session cookies are issued over plain HTTP-semantics on the deployed API. The *same* variable also gates whether the hardcoded dev JWT secret is used (`:184`) — fail-closed there, but one missing env var silently changes two security behaviours in opposite directions.
**Fix:** set `ENV: production` in `render.yaml` for `supremeai-api`; prefer deriving from `RENDER`/`RENDER_SERVICE_ID`; always set `Secure` + `SameSite=None` when the request is HTTPS.

---

## 4. P1 — architecture and correctness

### P1-1 · There are two gateways and production runs the *other* one
**Files:** `gateway/Dockerfile:36` and `config/service_registry.yaml:42` deploy `gateway.service.app:app`; `gateway/main.py` (`create_app`) is the documented OpenAPI implementation and the one the pytest fleet drives.
**Evidence:** the deployed app has 96 `@app.*` routes and **no** `/metrics`; `main.py` has `/metrics`, `/v1/consensus`, the provider chain and the injectable test seams. The live service reports `version: 2.0.0`, which only `service/app.py` defines.
**Why it matters:** every fix in `main.py` (including mine) is invisible to users; every divergence is a silent contract break. This is also why `api-schemas/gateway.openapi.yaml` and the running service can disagree without any test failing.
**Fix (highest structural ROI):** pick `service/app.py` as the runtime, then port into it — and delete from `main.py` — the provider chain, the ledger, the test seams. Or invert: make `main:create_app` the runtime and move `service/app.py`'s route bodies behind routers. Either way, end with **one** app module and add a test that asserts the deployed ASGI app exposes every path in the OpenAPI document.

### P1-2 · Schema/SSOT drift, plus a red test on `main`
**Files:** `gateway/config.py:53` (`perplexity`, `manus`), `api-schemas/task-router.schema.json` (`provider` enum has 7, no `web`, no `perplexity`, no `manus`), failing test `gateway/tests/test_streaming_gateway.py::test_config_provider_enum_matches_task_router_ssot`
**Evidence:** local run → `1 failed, 20 passed`. `perplexity`/`manus` pass gateway validation but have **no adapter** in `_default_attempt` and no `_FALLBACKS` entry, so a chain using them boots fine and fails at runtime.
**Fix:** make the schema the generated source (the repo already has `scripts/ci/contract_codegen_guard.py`); fail closed in `_default_attempt` for providers with no transport; delete or implement `perplexity`/`manus`.

### P1-3 · PR CI runs ~3 % of the suite, which is how P1-2 landed
**Files:** `config/ci/pr-battery.args` (20 test modules), `.github/workflows/full-test-suite.yml` (nightly + dispatch only), `pytest.ini` (testpaths = 628 modules)
**Why it matters:** the guards that would have caught the enum drift and both P0 bugs run *after* merge, or never. Red-on-main is now normal, which destroys the main signal an autonomous loop depends on.
**Fix:** add `gateway/tests` to the PR battery with `-n auto` sharding (it runs in ~2 s locally for the provider suites); add `--fail-on-empty` style guard so a renamed test path can't silently shrink the battery; keep the nightly for `core/tests`.

### P1-4 · Streaming is emulated, and its error frames can break the SSE contract
**Files:** `gateway/main.py:823` (`default_stream`), `:245` (`relay_stream`), `gateway/provider_chain.py:256` (`stream: False`)
**Problems:**
1. Without an injected `stream_fn`, the “stream” is one non-stream completion replayed as one chunk — no first-token win, no cancellation, 30 s hard timeout.
2. `X-RateLimit-*` / `Retry-After` are attached only to `JSONResponse`; `StreamingResponse` returns none, so clients cannot see budget.
3. `sanitize_error_message` (`gateway/sanitization.py:123`) only redacts secrets — it does **not** strip `\n`. A provider error containing a newline is interpolated into `data: {json}` and can split the frame, which OpenAI-compatible clients parse as a second event.
**Fix:** real SSE pass-through with per-read timeout (`asyncio.timeout` around `__anext__`), `json.dumps` only (already done) **plus** `payload.replace("\n","\\n")` / `json.dumps` of a full envelope, and rate headers on the streaming response.

### P1-5 · No request-size or conversation-size limits anywhere
**Files:** `gateway/main.py:751`, `gateway/service/app.py:2329` (both call `await request.json()` directly)
**Evidence:** zero `content-length` checks in `gateway/`; no cap on `len(messages)` or per-message size.
**Why it matters:** on a 512 MB free Render instance, one 50 MB POST or a 10k-message array is an OOM/cost kill switch, and it burns provider tokens before any auth check on the guest path.
**Fix:** ASGI middleware capping body at ~1 MB, `len(messages) <= 200`, per-message ≤ 32 KB, `max_tokens` default; return the existing structured error contract.

### P1-6 · `/health` and `/readyz` are decorative
**Files:** `gateway/main.py:584` (hardcoded `"modules": {... "healthy"}`), `:593` (`/health/ready` only checks memory)
**Evidence:** live `tiny-brain` returns `uptime: 1795079891` (an epoch, not an uptime) and `cache_size: 0`; the gateway reports `command/agents/skills/mcp: healthy` without probing any of them.
**Why it matters:** Render, keep-warm, and the self-healer all key off these endpoints. A lying `/health` is why the Tower suspension was invisible.
**Fix:** each module probe returns `{state, latency_ms, last_error}`; `/health` = liveness only; `/readyz` fails when `chains` is empty **or** every provider's breaker is open; never emit constant “healthy”.

### P1-7 · `/metrics` is unauthenticated (and absent from the deployed app)
**File:** `gateway/main.py:637`
**Why it matters:** route-level counters double as a recon surface (traffic shape, admin path probes) and as a cardinality bomb (`/v1/.../<id>` labels). Meanwhile the deployed app exports **no** metrics at all, so there is no observability to fall back on.
**Fix:** mount behind operator key or bind to an internal-only port; normalise path labels; add `/metrics` to `service/app.py` behind the same guard.

### P1-8 · Silent third-party default endpoint
**File:** `gateway/provider_chain.py:98`
```python
if not relay_url:
    relay_url = "https://supremeai-worker.paykaribazaronline.workers.dev"
```
If the three env vars are missing, user prompts are sent to a hardcoded external worker — no error, no log, no consent. **Fix:** fail closed with a configuration error naming the env var; keep test doubles in tests only.

### P1-9 · All limiter/health state is per-process and dies on deploy
**Files:** `gateway/service/app.py:679` (`_guest_hits`), `gateway/service/pool.py` (key cooldowns), `gateway/service/admin_auth.py:96` (`_pending_totp_setups`), `gateway/rate_limit.py` fallbacks
**Why it matters:** free-plan services restart often and scale by instance count, so budget = N × limit, cooldowns evaporate exactly when providers are flapping, and TOTP setup fails if the verify request lands on another instance. **Fix:** one Redis-backed budget/cooldown store with an in-process cache, and make TOTP setup stateless (signed short-lived setup token).

---

## 5. P2 — developer experience and docs

| # | File(s) | Issue | Why it matters |
|---|---|---|---|
| P2-1 | `infrastructure/mcp-control-plane/src/index.fixed.ts` (528 lines) | A byte-identical duplicate of `src/index.ts` that `tsconfig` compiles into `dist/`, kept alive by `test_entry_governance.ts` asserting equality | Two files to patch, one of which is dead; doubles dist; teaches contributors the wrong pattern. Delete it and point the governance test at `src/index.ts` (or at a single canonical path). |
| P2-2 | `gateway/service/app.py` 2 960 L, `scripts/agents/continuous_agent_loop.py` 4 966 L, `core/config_classification.py` 2 467 L, 141 files > 800 L, 762 k LOC | God files and 10 sibling `core/config*.py` modules (`config`, `config_cache`, `config_fields`, `config_parsers`, `config_proxy`, `config_registry`, `config_validation`, `config_validator`, `config_control_plane`, `config_classification`) | Impossible to review safely; agents “fixing” one file cannot see the others. Split by route/responsibility and collapse the config family behind one facade. |
| P2-3 | `AGENTS.md` (whole file) | The agent-facing contract is three lines of broken Banglish run-ons plus a stray `,,,` | This is *the* file every external agent is told to read first (`CONTRIBUTING.md` §1). Rules are unenforceable if unparseable — rewrite in plain English as numbered, testable invariants. |
| P2-4 | `CONTRIBUTING.md:36,192,193` | Links to `.github/workflows/landing.yml`, `ISSUE_TEMPLATE/bridge-work-order.yml`, `ISSUE_TEMPLATE/agent-task.yml` — none exist (real names: `agent_task.yml`, `bug_report.yml`, …) | Broken onboarding links at the exact moment a contributor decides whether to trust the repo. Add a link-check step to the docs guard. |
| P2-5 | repo root (no `pyproject.toml` / `requirements.txt` / `Makefile`), `CONTRIBUTING.md` §4 | A fresh clone cannot run `pytest`: it fails at `ModuleNotFoundError: pydantic_settings` until you reverse-engineer `core/requirements.lock -r gateway/requirements.lock` out of a workflow YAML (I hit this during the review) | The claimed “zero credentials, clone and go” path stops at step one. Add `make dev` / `make test` + a root `pyproject.toml` (or `requirements-dev.txt` that actually installs the runtime). |
| P2-6 | `pytest.ini` | No `asyncio_default_fixture_loop_scope`, so pytest-asyncio emits a deprecation warning on every run and will change behaviour on upgrade | One line now vs a surprise async-fixture break later. |
| P2-7 | `.env.example` (11 KB), `gateway/provider_chain.py:210-260` | Five accepted key conventions (`GROQ_API_KEY`, `GROQ_API_KEYS`, `GROQ_API_KEY_2..11`, `SUPREMEAI_PROVIDER_KEY_GROQ`, numbered regex scan of *all* env vars) with no documentation of precedence | Operators cannot predict which key is used first; the per-request `os.environ` regex scan is also latency and a leak surface (it will pick up a key meant for another service). Parse the pool once at startup into a typed registry. |
| P2-8 | `gateway/dynamic_llm_router.py:47-130` | Hardcoded model IDs that do not exist upstream (`qwen/qwen3.8-27b`, `nvidia/nemotron-3.5-lightning:free`, `grok-beta`), plus the whole module duplicates `provider_chain` with **no** importers outside itself | Guaranteed 404s on first use, and a second routing brain to keep in sync. Validate model IDs against a probe or delete the module. |
| P2-9 | `render.yaml` (3 services) vs `config/service_registry.yaml` (7 entries) | Registry declares scraper/primary/worker/tiny-brain that the blueprint does not deploy; docs do not say where they live | “All services healthy” is unverifiable from the repo; new operators cannot reproduce the fleet. |
| P2-10 | repo root | No `docker-compose.yml` / local run path for the multi-service stack | Contributors can only test the gateway in isolation, so integration bugs (P0-3, P0-7) stay invisible until deploy. |

---

## 6. Missing tests (concrete, ordered by blast radius)

1. **Provider transport** — there were **zero** references to `_default_attempt` in any test module, which is exactly why the double-`/v1` bug shipped. Now covered by `gateway/tests/test_provider_transport_and_limits.py`.
2. **Rate-limit keying / fairness** — no test asserted that two clients get separate budgets. Now covered.
3. **Circuit breaker integration** — `execute_chain` + breaker has no test at all (the argument is unused, so it *cannot* have one). Add: 5 failures → provider skipped → cooldown → half-open probe.
4. **Redis limiter concurrency** — `test_redis_rate_limit.py` covers fail-open, not the check-then-add race. Add a concurrency test with `fakeredis` + 50 parallel `check()` calls asserting `allowed <= max_requests`.
5. **Admin auth under vault failure/timeout** — no test proves a hung Infisical does not stall the loop, and none asserts `Secure` cookie attributes under `ENV=production`.
6. **Request limits** — no test that a 10 MB body or 10 000 messages is rejected.
7. **SSE framing with hostile content** — no test that a provider error containing `\n` cannot break `data:` framing.
8. **Deployed-app/OpenAPI parity** — no test compares `service/app.py` routes to `api-schemas/gateway.openapi.yaml`; add it after P1-1 and drift becomes impossible.
9. **Health honesty** — `test_health.py` asserts shape, not truth; add a test that `/readyz` flips to 503 when every breaker is open.
10. **Tower availability** — nothing in CI fails when the Tower is suspended (P0-1). Add a scheduled probe.

---

## 7. Roadmap to the stated goal (“production-ready, lightweight, intelligent, self-fixing provider”)

**Milestone 0 — make it honest (hours).**
Tower un-suspended + fleet-wide keep-warm that fails loudly; `ENV=production`; per-IP limits; URL join; parameter passthrough (all but the first two are on this branch); widen the PR battery to `gateway/tests`.

**Milestone 1 — one core (days).**
One gateway module, one provider transport, one limiter, one key registry. Contract test: deployed app ⊇ OpenAPI. Acceptance: `pytest tests gateway/tests` green on a fresh clone via `make test`.

**Milestone 2 — a provider that can *do* work (days).**
Real SSE pass-through with first-token timeout; `tools`/`tool_choice`/`response_format` end-to-end; per-key budget accounting (tokens, not requests); structured-output validation; cancellation propagation; cost ledger per request.

**Milestone 3 — a provider that can *fix itself* (weeks).**
Close the loop that already half-exists (`core/health/self_healer.py`, `core/evolution/*`, Tower bridge): structured error → dedup issue → agent patch → the repo's own verify tiers → PR → canary → auto-rollback. Guardrails: protected paths, blast-radius limit, mandatory evidence block, human gate for auth/data boundaries. Right now the self-healing modules exist but the *trigger* (Tower) is dead — that is the wiring gap, not a missing algorithm.

**Milestone 4 — a provider that can *update itself* (weeks).**
Model/route inventory refreshed from live probes instead of hardcoded IDs (P2-8); shadow scoring of new models against a golden set (`evals/` exists); promote by measured quality/latency/cost, never by edit.

**Metrics that prove it:** p95 TTFB, provider success rate, failover rate and chain position histogram, 429 rate per IP, cost per 1 k tokens, Tower uptime, MTTR of the self-heal loop, and “% of merged PRs whose tests ran in CI”.

---

## 8. Changes already landed on this branch

| File | Change | Verification |
|---|---|---|
| `gateway/main.py:177` | Per-client-IP rate-limit bucketing (hash of key when authenticated) | `test_anonymous_rate_limit_is_per_proxy_resolved_ip`, `test_rate_limit_does_not_key_on_raw_api_key` |
| `gateway/main.py:809` | Forward `temperature`/`max_tokens`/`tools`/`response_format`/… to providers | `test_default_attempt_forwards_sampling_and_tools` |
| `gateway/provider_chain.py` | `_completions_url()` — correct join for `/v1`, `/openai`, bare-host bases; `_forwarded_body()` | `test_completions_url_is_joined_exactly_once` (6 cases), `test_default_attempt_uses_fallback_base_without_doubling_v1` |
| `gateway/tests/test_provider_transport_and_limits.py` | New regression suite for the four defects above | `10 passed`; `tests/test_gateway_foundation.py` + `test_streaming_gateway.py` + `test_guest_daily_limit.py` → `36 passed, 1 failed` (the pre-existing P1-2 enum drift only) |

Deliberately **not** changed (needs review, not a drive-by): circuit-breaker wiring (P0-5), admin vault async (P0-6), body limits (P1-5), gateway consolidation (P1-1).

---

## Appendix — commands used

```bash
# live handshakes
curl -s https://supremeai-api-ulw0.onrender.com/healthz
curl -s https://supremeai-mcp-tower.onrender.com/health     # -> service suspended
curl -s https://supremeai-scraper-node.onrender.com/health
curl -s https://supremeai-primary-node-5xso.onrender.com/health
curl -s https://supremeai-tiny-brain.onrender.com/health

# existing suites (fresh venv: fastapi httpx pytest pytest-asyncio)
python -m pytest tests/test_gateway_foundation.py -q                  # 14 passed
python -m pytest gateway/tests/test_streaming_gateway.py -q           # 1 failed (enum drift), 20 passed

# new regression suite
python -m pytest gateway/tests/test_provider_transport_and_limits.py -q   # 10 passed
ruff check gateway/main.py gateway/provider_chain.py                      # only pre-existing findings
```
