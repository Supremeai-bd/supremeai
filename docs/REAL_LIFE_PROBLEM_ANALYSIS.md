# SupremeAI — Real-Life Problem Analysis & Smart Solutions

> **Purpose:** This is the "what will actually break in production" layer on top of the
> implementation plans. Plans describe intent; this document describes **reality**:
> what fails in week 1 of real traffic, and the smallest free-tier-friendly fix for each.
>
> **Method:** Every finding below was verified against the current code (branch
> `regression-fixes-v4-evidence`, Sept 2026). No speculative problems are listed.
>
> **Companion plan governance:** per `docs/plans/PLAN_RECONCILIATION_2026-09-03.md`,
> plans are historical inputs. Several claims in older plans were verified as
> **already fixed** in code — do not re-implement them (see Appendix A).

---

## 1. Render Free Tier — the physics of the platform

### RLP-1: Cold starts kill the first user experience (P0)
**Reality:** Render free services spin down after ~15 min idle. Next request waits
30–60s while the app boots. FastAPI app with ~581 routes + lifespan init (DB pool,
routers, evolution agents) is on the slow end. A real user's first chat shows a
frozen screen.

**Smart tricks (already partially in place):**
1. Frontend must show a **"waking up the AI"** state for 60s on first request
   instead of a generic spinner — verified: `useServerStream.ts` and
   `websocketManager.ts` already implement exponential backoff (cap 30s, max attempts).
   Keep the copy human: "First request after idle takes up to a minute. Free tier 🙂"
2. **Self-wake trick:** the frontend pings `GET /api/v1/health/live` (registered at
   both `/api/v1/health` and `/health`) on page load, in parallel with user login.
   By the time the user types, the app is warm.
3. **Boot-time budget:** `check_app_boots.sh` exists — run it in CI and track boot
   time as a metric. If boot exceeds ~45s, lazy-load heavy routers (browser,
   evolution dashboards) behind `include_router` on first use.

### RLP-2: Ephemeral disk silently deletes "persistent" data (P0)
**Reality:** Render free tier wipes the filesystem on every deploy/restart.
`backend/adaptive_engine/experience_db.py` now defaults to
`USE_SUPABASE_VECTOR=true` (Supabase = durable) — verified — but `EXPERIENCE_DB_PATH`
falls back to `/tmp/chroma` (wiped) if Supabase is disabled.

**Smart tricks:**
1. **Treat local disk as cache-only, never source-of-truth.** Add a startup log
   warning when `USE_SUPABASE_VECTOR=false` in production:
   `"⚠️ learning data will be lost on restart"`.
2. **Learning-dump trick:** before Render's periodic restart (or on shutdown
   signal), flush in-memory experience rows to Supabase via the existing
   `save_memory()` service call in a lifespan shutdown handler. Cheap, idempotent.
3. Never "fix" this by mounting a paid disk — the free-tier contract is
   stateless compute + durable external state.

### RLP-3: 512MB RAM + single worker = one bad request OOMs everyone (P1)
**Reality:** Voice WebSocket buffers raw audio in a `bytearray` per connection
(`websocket_voice.py`), Playwright Chromium instances are ~200-400MB, and
`resource.getrusage`-based memory checks exist only in `websocket_agent.py`.

**Smart tricks:**
1. **Cap the audio buffer** (e.g. 10MB) in `websocket_voice.py` — drop oldest
   chunks; a real voice command rarely exceeds a few hundred KB.
2. **Playwright is a luxury:** keep `get_global_browser()` lazy (already lazy) and
   add a semaphore (max 1 concurrent page) so a screenshot burst can't spawn N pages.
3. **OOM guard pattern:** reuse `websocket_agent.py`'s `MAX_MEMORY_MB` idea —
   before accepting new work (WS connect, heavy task), check RSS; if > 80% of
   budget, reject with 1013/503 and let the client back off. Graceful, free.

---

## 2. Real-time connections in real life

### RLP-4: SSE streams die mid-answer after inactivity proxy timeouts (P1)
**Reality:** Render's proxy terminates idle connections (~100s); long LLM
generation with no bytes looks "idle" to the proxy even though the model is working.

**Smart tricks:**
1. **Heartbeat comments:** every 15s during generation, emit `: ping\n\n` (SSE
   comment line — ignored by EventSource parsers, resets the proxy idle timer).
   Verified pattern already used by some generators; make it universal in
   `stream_chat_sse.py`.
2. Client already reconnects with backoff — on reconnect, include
   `Last-Event-ID` and re-emit the last partial token buffer from server-side
   session memory to avoid restarting the answer from zero.

### RLP-5: WebSocket reconnect storms after a deploy (P2)
**Reality:** On redeploy all WS clients drop simultaneously and reconnect with
jitter — verified `websocketManager.ts` has backoff. But the server-side caps
added this iteration (`WS_MAX_CONNECTIONS=50`) can reject legitimate users if
stale sockets haven't been swept.

**Smart trick:** server sweeper — a background task every 60s pings each
connection and removes dead ones (pattern already exists in
`websocket_agent.py::_cleanup_stale_connections`). Reuse it for the three
managers capped this iteration. **Do not** raise the cap to "fix" this.

---

## 3. Supabase free tier in real life

### RLP-6: Connection exhaustion / project pause (P1)
**Reality:** Supabase free pauses after ~7 days of inactivity and limits direct
connections. A burst of requests each opening a connection (or a long-lived
async pool that grows on spike) hits `too many connections`.

**Smart tricks (already architecturally present, enforce them):**
1. Always connect through the **PgBouncer pool URL** (`backend/database/pgbouncer_pool.py`
   exists — verify all paths route through it, not direct Postgres).
2. **Keep-warm (legitimate):** the existing health cron pings the API; add a
   single lightweight `SELECT 1` per day so the DB never idles into pause.
   One query/day is well inside policy — unlike quota-multiplying schemes.
3. **Circuit breaker on DB errors:** when connection fails, serve cached/semantic
   cache responses and queue writes (the existing `intelligent_cache` + retry
   wrappers) instead of retrying synchronously — retry storms are what actually
   exhaust the pool.

### RLP-7: Migrations exist but nothing runs them (P1)
**Reality:** verified — `15_add_user_indexes.sql` is idempotent and correct, but
no runner references it. On a fresh Supabase project the indexes silently don't
exist → full table scans as data grows.

**Smart trick:** DEPLOYMENT_CHECKLIST.md (added this iteration) makes migration
application an explicit human step with a one-liner (`supabase db execute` per
file, in numeric order — all files are IF NOT EXISTS/DO $$ idempotent). Optionally
add `scripts/db/apply_migrations.sh` that loops `database/migrations/*.sql` in
order with psql. **Never** auto-run migrations on boot in production (partial
apply during traffic is worse than explicit step).

---

## 4. Silent failure modes (the verified collection)

This is the most important category — features that *look* deployed but no-op.

### RLP-8: Wrong-prefix lazy imports (`backend.core.*`) (P0 — fixed this iteration)
**Reality:** 10 lazy imports in `browser_routes.py` + 2 elsewhere used a
`backend.` prefix that only resolves if the process starts from the *repo root*
— but `CMD ["python", "main.py"]` runs from `backend/`. Every browser endpoint,
the auto-healer's cache fix, knowledge sync, and the self-improving agent were
dead on arrival, each wrapped in `try/except ImportError` so nothing ever
logged loudly.

**Smart tricks:**
1. **Fixed** this iteration (see commit `2028cb054f`).
2. **Guardrail:** `scripts/ci/validate_router_imports.py --strict` catches route
   modules; extend the same idea with a lint rule — **forbid `from backend.` /
   `import backend.` inside `backend/**`** (grep-level CI check, 5 lines).
   This bug class has recurred 3+ times in this repo's history.
3. **Anti-pattern:** `except ImportError: return False` capability checks should
   `logger.warning` once at startup listing *which* import failed, so ops sees
   "browser capability disabled: no module named X" instead of silent off.

### RLP-9: Advertised-but-never-existing APIs (P1 — fixed this iteration)
**Reality:** `browser_routes.py` called `PlaywrightManager.capture_screenshot()`,
`UnifiedMemory.store()/query()`, `OriginValidator` — classes that never existed
anywhere in the codebase (stale code written against an imagined API). The
browser health endpoint reported degraded forever; nobody noticed because the
endpoints 503'd "gracefully."

**Smart tricks:**
1. **Fixed** this iteration by rewriting against the real APIs
   (`get_global_browser()`, `unified_memory` facade, `SSRFProtection` at
   `core.security.protection`).
2. **Guardrail:** the boot test (`check_app_boots.sh`) should exercise one
   capability-check endpoint (`/api/browser/health`) and fail if the *status
   is degraded for reasons other than missing optional deps* — i.e., fail on
   `ImportError`-shaped errors, pass on `playwright not installed`.

### RLP-10: Dead-broken modules accumulate (P2 — one deleted this iteration)
**Reality:** `core/middleware/db_optimization_middleware.py` had 4 imports of
nonexistent modules and 0 importers — pure liability.

**Smart trick:** quarterly `git grep`-based dead-module sweep; the
`SUPREMEAI_CONSOLIDATION_AND_CLEANUP_PLAN.md` Phase 1 pattern (0 callers →
`git rm`) is correct — keep applying it.

---

## 5. Self-evolution: what "learning" can really mean on free tier

### RLP-11: Learning loops that write but nobody reads (P1)
**Reality:** verified in code comments and analysis docs — some improvement
engines write Redis keys that no component reads (write-only memory). Evolution
learning is now correctly wired & gated (`ENABLE_EVOLUTION_LEARNING`, default
off) in `llm_gateway.py`.

**Smart tricks:**
1. **Keep the gate OFF until a consumer exists.** A "learning" signal with no
   reader is cost with zero value — the reconciled master plan's
   "work avoided" principle applies to learning itself.
2. **Lesson promotion budget:** `rotate_lessons.py` exists — schedule it to
   prune/compact `ai_memory` so the Eternal Brain stays within the free 500MB.
   Prefer "validated, reused lessons" over raw artifacts (per
   `docs/plans/implementation_plan.md` §5).

### RLP-12: Background "self-healing" workers vs single-process reality (P2)
**Reality:** `MaintenancePipeline` now correctly uses `app.state.evo_agent`
(fixed earlier). But multiple background loops (health monitor, swarm streamer,
cleanup tasks) all share the one event loop — a stuck synchronous call in any
of them stalls heartbeats everywhere.

**Smart trick:** any loop that does blocking I/O must use
`asyncio.to_thread` (the `supabase_client.py` retry wrapper already models
this correctly). Add a CI grep for bare `time.sleep(` inside `async def` —
a 3-line script, catches the #1 event-loop killer class.

---

## 6. Security in real life

### RLP-13: "48 unguarded routes" claim is stale — the real defense-in-depth (verified)
**Reality:** every admin route file has router-level or route-level admin guards
(`get_current_admin` / `require_admin_token` / `_verify_admin`), and a global
`AuthMiddleware` rejects every non-public path without a JWT, attaching
`role`/`tenant_id` to the scope. Test-env bypass is production-guarded
(`is_bypass_allowed` false in production).

**Smart tricks:**
1. **Keep the middleware as the primary guard** (one place, no gaps) and
   route-level `Depends` as the role check — this is exactly the current
   design; document it rather than "fixing" 581 routes by hand.
2. **Drift guard:** the existing `tests/api/test_route_rbac_matrix.py` +
   periodic `grep -L "Depends(get_current_admin)" api/routes/*admin*.py`
   (all 9 admin files must match ≥1 guard) — 2-line CI assertion, prevents
   future admin files from shipping unguarded.
3. **Real residual risk:** the OPTIONS-bypass in AuthMiddleware is correct for
   CORS, but make sure `TrustedOriginMiddleware` (exists) is registered *after*
   it so preflights still get origin-checked.

### RLP-14: Secrets in logs (P1)
**Reality:** several modules log settings-derived values at DEBUG; logfox like
`sync_render_secrets.py` handles secrets properly, but one bad `logger.info(f"{settings}")`
in a dependency prints everything.

**Smart trick:** a startup log-filter that redacts known secret-shaped keys
(`api_key`, `token`, `secret`, `password`) — Python `logging.Filter`, ~20 lines,
one registration in `app_builder.py`. Free, permanent.

---

## 7. Quota exhaustion & graceful degradation

### RLP-15: Free LLM provider quota outages (P0 for UX)
**Reality:** multi-provider routing exists (model_router / economic optimizer /
circuit breakers). Real-life failure: ALL free providers rate-limited at once
(Groq daily cap + Gemini RPM + OpenRouter free models down).

**Smart tricks:**
1. **Honest degradation UI:** when all providers fail, return a structured
   "capacity" message with retry-after, not a raw 500. Users tolerate honest
   limits; they don't tolerate mystery errors.
2. **Semantic cache as capacity:** `intelligent_cache` + `semantic_cache`
   already exist — on total-provider outage, serve cached similar answers with
   a `"cached": true` flag. Free "uptime" for repeat traffic.
3. **Quota ledger:** `provider_rate_limiter` exists — persist per-provider
   429 events to `ai_memory` metadata so the router learns weekly patterns
   (Sunday evening Groq cap) and pre-routes. This is the *legitimate* version
   of the old "federation" idea: policy-compliant, no account multiplication.

### RLP-16: GitHub Actions minutes & Render build minutes (P2)
**Reality:** free tier build limits are consumed by the 1400+ file test matrix.

**Smart tricks:**
1. Tiered CI already exists (`test-ci-tiers` branch naming, coverage tiers).
   Keep PR CI to tier-1 (fast unit) and run the full matrix nightly + pre-release.
2. `paths-ignore: ["docs/**", "*.md"]` on workflow triggers — docs commits
   (frequent in this repo) shouldn't burn build minutes.

---

## 8. Frontend ↔ backend in real life

### RLP-17: Hardcoded/deploy-specific backend URL drift (P0 once, verified fixed)
**Reality:** commit history shows `fix(frontend): resolve Render backend URL
explicitly on Vercel` — this class of bug shipped before. The base URL must
come from env only.

**Smart trick:** CI check `check_hardcoded_deployment_config.py` exists — add
the frontend to its scope (grep for `https://*.onrender.com` literals in
`frontend/src` → fail build).

### RLP-18: Stale OpenAPI contract between FE/BE (P2)
**Reality:** `openapi.json` + `generate_types.py` exist; hand-written types drift.

**Smart trick:** CI step: regenerate types → `git diff --exit-code` on generated
files. Drift fails CI with a one-command fix (`python scripts/generate_types.py`).

---

## 9. Plan-vs-code drift (meta-problem)

### RLP-19: Plans claim bugs that were already fixed (verified — see Appendix A)
**Reality:** of 13 claimed fixes in PRODUCTION_READINESS_PLAN_V3, 10 were already
fixed in code; only remnants remained (now fixed). Implementing plans literally
would have re-broken working code (e.g. reverting the `StrEnum` fix, re-adding
`time.sleep` paths).

**Smart tricks:**
1. **This document + Appendix A** is the drift record; the reconciliation doc's
   evidence-first rule works — enforce it.
2. **Drift check automation (the plan's own suggestion):** a CI job that greps
   each plan's cited `file:line` evidence, checks whether the pattern still
   exists, and comments "STALE: Fix #N already applied" on the plan file
   (or a generated `PLAN_STATUS.md`). ~100 lines of Python, saves whole
   agent-days per iteration.

---

## TOP 5 — do-not-miss list for the next operator

1. **Never trust `try/except ImportError` features as "done."** They ship broken
   silently (RLP-8/9 cost this repo a whole browser pillar).
2. **The disk is a lie.** State lives in Supabase or it doesn't exist (RLP-2).
3. **Boot time is UX.** Measure it in CI; lazy-load heavy routers (RLP-1).
4. **Heartbeat every long-running stream** (SSE comments / WS pings) or Render's
   proxy eats it (RLP-4).
5. **Wire the gate before the learner:** `ENABLE_EVOLUTION_LEARNING` stays off
   until something reads what it writes (RLP-11).

---

## Appendix A — Evidence-based status of PRODUCTION_READINESS_PLAN_V3 (verified Sept 2026)

| Fix | Plan claim | Verified reality |
|-----|-----------|------------------|
| #1 ArtifactType(str,str) | boot crash | ✅ already fixed — `class ArtifactType(StrEnum)` (artifacts.py:38) |
| #2 stream_chat_sse garbage | SSE broken | ✅ already fixed — real `async for` streaming (lines ~169-257) |
| #3 missing awaits ×7 | no-op calls | ✅ already fixed (incl. `asyncio.run` wrapper for sync caller) |
| #4 broken imports ×9 | silent no-ops | ⚠️ 3 + 10 remained → **fixed this iteration** (`2028cb054f`) |
| #5 time.sleep in async | loop blocking | ✅ already fixed (event-loop-aware retry wrapper) |
| #6 WS unbounded ×4 | DoS/memory | ⚠️ 3 remained → **capped this iteration** (`WS_MAX_CONNECTIONS`, 1013) |
| #7 `_pref_locks` leak | memory growth | ✅ already fixed (`LRUCache(maxsize=1000)`) |
| #8 per-request httpx | conn churn | ✅ already fixed (global client + closed fallback) |
| #9 DB indexes | table scans | ✅ migration file exists & idempotent; **apply step documented** (RLP-7) |
| #10 dead files | clutter | ✅ already deleted; 1 more removed this iteration |
| #11 `__new__` skip init | silent crash | ✅ already fixed (`app.state.evo_agent`) |
| #12 evolution not wired | no learning | ✅ already wired + env-gated |
| #13 ephemeral ChromaDB | data loss | ✅ already handled (`USE_SUPABASE_VECTOR=true` default, env path, tmp fallback) |
