# 🔧 Admin Tasks — SupremeAI Production Setup

> **Audience:** DevOps / system administrator
> **Purpose:** Tasks that CANNOT be done by code changes alone — require admin access to deploy configs, env vars, or external services.
> **Source:** Found during v3 production readiness analysis (4 parallel agents).

---

## 📋 Quick Reference — All Required Env Vars

| Variable | Default | Purpose | Priority |
| --- | --- | --- | --- |
| `ENABLE_AUTO_HEALER` | `true` | Start AutoHealer background service | HIGH |
| `ENABLE_EVOLUTION` | `false` | Start SelfEvolutionAgent 5-min loop | MEDIUM |
| `ENABLE_DAILY_LEARNER` | `false` | Start 24h research scan | LOW |
| `ENABLE_TIER8` | `false` | Start self-improvement (requires paid OpenAI gpt-4o-mini) | LOW |
| `ENABLE_EVOLUTION_LEARNING` | `false` | Wire EvolutionEngine into LLM success path | MEDIUM |
| `USE_SUPABASE_VECTOR` | `true` | Use Supabase pgvector (no Render disk needed) — set false to use ChromaDB/Qdrant (requires disk) | HIGH |
| `EXPERIENCE_DB_PATH` | `data/experience.db` | Local SQLite path (not used for vectors on Render free-tier) | LOW |
| `QDRANT_PATH` | `/tmp/qdrant` | Qdrant local file path (only used if USE_SUPABASE_VECTOR=false) | LOW |
| `WS_MAX_CONNECTIONS` | `50` | Max concurrent WS connections | HIGH |
| `WS_MAX_PER_USER` | `3` | Max WS connections per user | HIGH |
| `INTENT_ROUTER_MODE` | `llm` | LLM gatekeeper (regex = fallback only) | LOW |
| `TOKEN_JUICE_ENABLED` | `true` | Token compression on LLM inputs | LOW |
| `SUPREMEAI_ENABLE_HEAVY_ROUTES` | `false` | digital_twin/economics/swarm (removed upstream) | N/A |

---

## ✅ Code-Owned Wiring Completed

The application now has a canonical control-plane registry, dynamic service URL resolution, worker task lifecycle routes, scraper execution through the worker, and authenticated MCP discovery. Do not manually edit frontend source URLs or add Render service URLs to code.

### MCP Control Tower readiness contract

- `/health` is liveness-only and must remain cheap.
- `/health/ready` runs a dependency sweep and returns `503` when any configured dependency is not healthy; use this for deployment/readiness checks, not liveness probes.
- Production HTTP MCP, approval, and autonomy-kill routes fail closed unless `MCP_API_KEY` is configured and supplied as a Bearer token.
- Production GitHub and Cloudflare webhooks require HMAC signatures via `GITHUB_WEBHOOK_SECRET` and `CLOUDFLARE_WEBHOOK_SECRET`.
- A green readiness result proves configured checks passed at that instant; it is not proof of every business workflow. Synthetic workflow checks remain required.

## 🔐 Audit Remediation — 2026-09-04

- [x] Deploy the CSRF and health/readiness changes; verify `/live`, `/ready`, and `/health` on every production service. (COMPLETED & VERIFIED on Core, Worker, Scraper, MCP Tower)
- [x] Confirm `SUPABASE_DATABASE_URL_WRITER` is configured and run `alembic upgrade head` / required Supabase migrations through the approved deployment process. (Migrations 15, 16, 18, 19 applied and verified)
- [x] Run deployed-origin CORS preflight and cookie-auth CSRF tests, including allowed and unknown origins. (VERIFIED: allowed origins return 200, unknown origin rejected with 400, CSRF double-submit contract 100% verified)
- [ ] Review production logs and secret-manager access history; rotate any exposed credentials.
- [x] Complete the durable learning/HITL audit-storage migration and decide the remaining SQLite-backed learning stores. (COMPLETED & VERIFIED: Learning/telemetry pipeline migrated to durable Supabase tables `learning_events`, `task_outcomes`, `provider_metrics`, `skill_metrics`, and `feedback_events` via PostgREST with in-process fail-safe ring buffers; vector experiences migrated via `match_experiences` pgvector RPC; ephemeral SQLite fallback is strictly locked down via `require_sqlite_allowed` and degraded in-memory mode in production).
- [ ] Run release-candidate E2E flows and attach redacted evidence.

## 👤 Manual Work Status & Progress

### Current release gate — backend CI evidence captured

- [x] Run the repository CI workflow on the latest `main` baseline and confirm the backend job completes with the pinned Poetry environment.
- [x] Record the successful CI run: `https://github.com/SaifulHaqueNiloy/supremeai/actions/runs/33808294106` (SHA `90845ec6bb2448ea64f7c5e4f71f1ad2cb1bd55b`). Backend Tests, Security Scan, Advanced Pre-Merge Checks, Integration Tests, DB Schema Contract Check, and deployment gates completed successfully.
- [x] Review the latest CI job summary: the skipped Build/Frontend/Deploy jobs were conditional path-filter skips on the `main` baseline, not masked failures. Backend Tests, Security Scan, Advanced Pre-Merge Checks, Integration Tests, DB Schema Contract Check, and deployment gates passed.
- [x] Run a full release-candidate workflow with `force_backend=true`, `force_frontend=true`, and `force_infra=true`; record the run URL and confirm the frontend/build/deploy jobs pass. (COMPLETED & VERIFIED: `https://github.com/SaifulHaqueNiloy/supremeai/actions/runs/33890394228` — Security Scan, Canonical Configuration Registry, Frontend Tests, Backend Tests, Build Verification, MCP Build & Verify, Integration Tests, Advanced Pre-Merge Checks, Frontend Deploy, Scraper Image Publish, Core Image Publish, Cloudflare Worker Deploy, Worker Image Publish, MCP Tower Deploy, Core Deploy, Worker Deploy, DB Schema Contract Check, Scraper Deploy, and Smart Pipeline Summary all passed with conclusion=success in 7m 57s)
- [x] Run deployed-origin CORS preflight checks for every configured user/admin origin, including `Authorization`, `Content-Type`, `X-CSRF-Token`, and `X-Device-Fingerprint`; confirm unknown origins are rejected.
- [x] Review secret-manager access history and rotate any credential exposed in logs, reports, screenshots, or old deployment configuration; record rotation date and owner.
- [x] Verify `/health` remains liveness-only and `/ready`/`/health/ready` fail closed when the required database is unavailable; record responses from every production service.
- [ ] Execute release-candidate E2E flows: login/session refresh, tenant-scoped read/write, approval-required action, worker task completion, scraper handoff, and MCP dependency sweep; attach redacted evidence artifacts.
- [ ] Reject unverified zero-cost capacity claims; measure real quotas, concurrency, cold starts, latency, and provider terms in a controlled staging load test.
- [ ] Do not implement browser stealth, auto-click, CAPTCHA/detection bypass, multi-account quota rotation, or secret-bearing public worker polling; obtain provider approval or replace with compliant job runners.
- [ ] Design a compliant high-compute queue with signed short-lived worker credentials, idempotent jobs, leases, retries, cancellation, result-size limits, and tenant-scoped artifacts.
- [ ] Validate Cloudflare Worker CPU/request limits and Render/Koyeb free-tier availability against current provider documentation before committing to capacity or uptime guarantees.
- [ ] Document provider outage behavior, data residency, notebook/session loss, GPU availability variance, abuse controls, and an explicit paid-capacity fallback.
- [ ] Never ship example secrets such as `X-Worker-Key: supreme-secret`; use secret-manager references and rotation evidence only.

**Rollback:** revert to the last green release commit; do not bypass the backend gate with `continue-on-error` or `|| true`.

1. [x] **Run migrations 15, 16, and 19** — **COMPLETED & VERIFIED:** `match_experiences` RPC deployed and `19_harden_knowledge_base.sql` applied on Supabase. `knowledge_base` schema hardened with `knowledge_key`, `content_hash`, and `knowledge_import_audits`.
2. [x] **Set service URLs in the Core/Worker environments** — **COMPLETED & VERIFIED:** Render API script injected `BACKEND_URL`, `WORKER_URL`, `SCRAPER_URL`, and `MCP_URL` into all 4 Render services (`Primary Node`, `Worker Node`, `Scraper Node`, `MCP Tower`).
3. [x] **Set frontend public variables before build** — **COMPLETED & VERIFIED:** Configured in `frontend/.env` (`VITE_API_URL` and `VITE_BACKEND_URL` pointing to `https://supremeai-primary-node.onrender.com`).
4. [x] **Deploy all service revisions together** — **COMPLETED & VERIFIED:** Triggered latest deploys across all Render services: Core (`dep-dad12udg1s2s73ejfgog`), Worker (`dep-dad12umk1f9s73anmni0`), Scraper (`dep-dad12uv10e5c73cs7i50`), and MCP Tower (`dep-dad12vf10e5c73cs7jdg`).
5. [x] **Verify each service endpoint** — **COMPLETED & VERIFIED:**
   - Core API: `https://supremeai-primary-node.onrender.com/api/v1/health/live` -> **`200 {"status":"alive"}`**
   - Async Worker: `https://supremeai-worker-node.onrender.com/health` -> **`200 {"status":"ok"}`**
   - Scraper: `https://supremeai-scraper-node.onrender.com/api/v1/health/live` -> **`200 {"status":"alive"}`**
   - MCP Tower: `https://supremeai-mcp-tower.onrender.com/health` -> **`200 {"status":"ok"}`**
6. [ ] **Enable evolution features only after observing logs:** keep `ENABLE_EVOLUTION=false` until startup, memory, and approval behavior are verified.
7. [x] **Configure secrets through the provider secret manager** — **COMPLETED & VERIFIED:** Infisical Vault integration is active (`124 secrets loaded in single call`). No raw secrets in code.

## 🚨 CRITICAL — Do These First

### 1. Run the Vector DB Migration (replaces "Mount /data/ Volume")

**⚠️ IMPORTANT:** Render free-tier does NOT support persistent disks/volumes.
The previous ADMIN_TASKS instructed to "Mount /data/ Volume on Render" — that
is IMPOSSIBLE on the free tier. Instead, use Supabase pgvector which is
remote + persistent + already provisioned (free-tier 500MB Postgres).

**File:** `backend/database/migrations/16_add_match_experiences_rpc.sql`

**Why:** Without this RPC function, the new `SupabaseVectorBackend` cannot do
similarity search. ChromaDB/Qdrant (which require local disk) will silently
fall back, but data is LOST on every Render container restart.

**How (Supabase dashboard):**

1. Open Supabase project → **SQL Editor**
2. Paste the contents of `16_add_match_experiences_rpc.sql`
3. Click **Run**
4. Verify:

   ```sql
   SELECT proname FROM pg_proc WHERE proname = 'match_experiences';
   -- Should return 1 row
   ```

**Then set env vars on Render (NO disk mount needed):**

```
USE_SUPABASE_VECTOR=true     # default — uses Supabase pgvector
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
```

**Verify after deploy:**

```bash
# Check Render logs for this success line:
# ✅ ExperienceDatabase using Supabase pgvector (persistent, no Render disk needed)

# Test: make a chat request, then make a similar request 5 min later
# Logs should show "⚡ [SEMANTIC CACHE HIT]" — proving persistence works
```

**Rollback:**

```sql
DROP FUNCTION IF EXISTS match_experiences;
-- And set env USE_SUPABASE_VECTOR=false to force ChromaDB/Qdrant (data NOT persistent)
```

---

### 2. Run the User Indexes Migration

**File:** `backend/database/migrations/15_add_user_indexes.sql`

**Why:** Without indexes, list endpoints (`GET /api/conversations`, `GET /api/messages`, etc.) do full table scans. As data grows, this exhausts Supabase free-tier DB CPU.

**How (Supabase dashboard):**

1. Open Supabase project → **SQL Editor**
2. Paste the contents of `15_add_user_indexes.sql`
3. Click **Run**
4. Verify in **Table Editor** → indexes tab that 10 new indexes exist

**Verify:**

```sql
SELECT indexname FROM pg_indexes
WHERE indexname LIKE 'idx_%'
ORDER BY indexname;
-- Should return 10+ rows
```

**Rollback:**

```sql
DROP INDEX IF EXISTS idx_conversations_user_id;
DROP INDEX IF EXISTS idx_conversations_updated_at;
DROP INDEX IF EXISTS idx_messages_conversation_id;
-- ... etc (10 indexes total)
```

---

## 🟡 RECOMMENDED — Enable Self-Healing / Self-Evolving

These capabilities EXIST in code but are OFF by default because they need verification in your environment.

### 3. Enable Auto-Healer (default ON, just verify it starts)

**Status:** Already ON by default. Just verify the success log appears.

**Verify:**

```bash
# Check Render logs after deploy
grep "AutoHealerService started" /var/log/render.log
# Should print on every startup
```

**If it fails:**

```bash
# Set to false to disable
ENABLE_AUTO_HEALER=false
```

### 4. Enable Self-Evolution Loop

**Why:** Makes the system actually self-improving — runs every 5 min, analyzes skill fitness, refactors underperforming skills.

**How (Render env vars):**

```
ENABLE_EVOLUTION=true
ENABLE_EVOLUTION_LEARNING=true
```

**Caveat:** Requires `FitnessEngine` to be importable. If you see this in logs:

```
SelfEvolutionAgent init failed (FitnessEngine missing?)
```

Then either:

- Install missing deps: `poetry install --with ml`
- OR keep `ENABLE_EVOLUTION=false` (default)

### 5. Enable Daily Learner (optional)

**Why:** Scans for new techniques every 24h, proposes skill improvements.

**How:**

```
ENABLE_DAILY_LEARNER=true
```

### 6. Enable Tier-8 Self-Improvement (PAID — skip if zero-cost)

**Why:** Uses OpenAI `gpt-4o-mini` to improve prompts. Adds ~$0.15/day cost.

**How:**

```
ENABLE_TIER8=true
OPENAI_API_KEY=sk-...
```

**Skip this if you want true zero-cost.**

---

## 🟢 OPTIONAL — Performance Tuning

### 7. Tune WebSocket Limits

If you have many concurrent users, adjust these:

```
WS_MAX_CONNECTIONS=100      # default 50 (Render free-tier safe)
WS_MAX_PER_USER=5          # default 3
```

**Watch out:** Each WS connection uses ~50KB RAM. 100 connections = 5MB.
Render free-tier has 512MB — don't set above 200.

### 8. Tune Maintenance Interval

Default is 120s (2 min). For free-tier with cold-starts, consider:

```
MAINTENANCE_INTERVAL=300   # 5 min (less aggressive)
```

### 9. Enable Low-Memory Mode (if you see OOM crashes)

```
LOW_MEMORY_MODE=true
```

This disables vector DBs entirely (falls back to plain SQLite). Trade-off:

- ✅ No OOM crashes
- ❌ No semantic cache hits
- ❌ No auto-learning from vector similarity

---

## BROWSER FOUNDATION — ADMIN TASKS AND INTEGRATION AUDIT

The browser foundation is now code-wired for authenticated, owner-scoped sessions and basic actions. The following checks require a deployed Playwright runtime or admin/provider access and must be completed before enabling browser automation for real users:

- [ ] Confirm the deployed Core service includes the browser route module and OpenAPI exposes `/api/browser/automation/sessions` and `/api/browser/automation/actions`.
- [ ] Confirm the Playwright browser binary is installed in the deployed image; create, navigate, screenshot, fill, click, extract, and close one test session.
- [ ] Confirm an authenticated user cannot list, inspect, execute actions on, or close another user’s browser session.
- [ ] Confirm the session cap and idle cleanup in Render logs; begin with the safe default of 3 concurrent sessions and 15-minute idle expiry.
- [ ] Confirm Core service shutdown logs show browser contexts closing cleanly; repeat after a redeploy.
- [ ] Confirm SSRF checks reject localhost, private-network, link-local, and metadata-service URLs while allowing approved public HTTPS targets.
- [ ] Keep browser credentials disabled until encrypted storage, rotation, audit logging, and per-user ownership are verified in the deployed environment.
- [ ] Do not enable vision grounding, semantic DOM, screencast, HITL takeover, swarm execution, or stealth/bot-bypass features yet; these remain later implementation milestones and are not currently fully connected to the canonical session API.

**Integration audit result:** frontend browser-related state/events and admin panels exist, but no verified frontend client currently consumes the canonical automation session/action endpoints. The legacy surf state endpoints and the new session endpoints therefore remain two separate surfaces. A frontend adapter and end-to-end flow are required before claiming the browser feature is fully interconnected.

**Evidence to record:** deployment URL, OpenAPI route list, Playwright smoke-test output, authorization test result, session cleanup log lines, and rollback revision.

## 🟠 KNOWN LIMITATIONS (Code-Level — Track in Issues)

These are documented in `docs/PRODUCTION_READINESS_PLAN_V3.md` but CANNOT be fixed by admin alone — require code changes in a future PR:

1. **Sync Supabase calls in async routes** — `db.client.table(...).execute()` is sync but called from async handlers without `asyncio.to_thread()`. ~10 routes affected. Fix: migrate to `supabase.create_async_client()` OR wrap all calls in `asyncio.to_thread()`.

2. **Firebase SDK in frontend bundle** — `firebase: ^12.18.0` adds ~500KB to initial JS bundle. Fix: code-split auth behind `/login` route, OR replace Firebase Auth entirely with the JWT auth already implemented in `core/security/verify_token`.

3. **Duplicate React Flow libraries** — both `reactflow` (v11, deprecated) and `@xyflow/react` (v12) installed = ~250KB duplicate. Fix: migrate 5 files from `reactflow` to `@xyflow/react`, then remove `reactflow` dep.

4. **Heavy torch dependency** — `torch: ^2.5.0` (~2GB on disk, ~700MB RSS). Fix: move to `[tool.poetry.extras]` optional group; convert eager `import torch` to lazy local imports.

---

## 📊 Post-Deploy Verification Checklist

After applying env vars + running migration, verify each capability works:

```bash
# 1. App boots cleanly
curl https://your-app.onrender.com/health
# Expected: {"status":"healthy"}

# 2. Auto-healer started
# Check Render logs for: "✅ AutoHealerService started"

# 3. SSE endpoints work (new in this iteration)
curl -N "https://your-app.onrender.com/api/v1/stream/chat?prompt=hi&token=YOUR_JWT"
# Expected: "event: connected" then "event: token" chunks

# 4. WebSocket limits enforced
# Try opening 100 WS connections — 51st should be rejected with code 1013

# 5. DB indexes exist
# In Supabase SQL editor:
# SELECT count(*) FROM pg_indexes WHERE indexname LIKE 'idx_%';
# Expected: >= 10

# 6. Vector DB persists across restarts (Supabase pgvector, no Render disk needed)
# Make a chat request, restart container, make similar request
# Check logs for "⚡ [SEMANTIC CACHE HIT]" — should appear if persistence works
# Verify env USE_SUPABASE_VECTOR=true (default) is set in Render dashboard
```

---

## 🆘 Emergency Rollback

If something breaks after deploy:

```bash
# 1. Disable all new env vars (restore defaults):
ENABLE_AUTO_HEALER=true      # keep
ENABLE_EVOLUTION=false        # was false
ENABLE_EVOLUTION_LEARNING=false  # was false
ENABLE_DAILY_LEARNER=false   # was false

# 2. Revert to previous commit on Render (manual):
# Settings → Deploy → Manual Deploy → Deploy a specific commit → choose last known good

# 3. Drop new indexes if they cause issues:
# In Supabase SQL editor, run DROP statements from migration 15

# 4. Disable SSE routes (set WS_FALLBACK=true, stop using /api/v1/stream/*):
WS_FALLBACK=true
```

---

## 📞 Contact

For questions about this document, refer to:

- `docs/PRODUCTION_READINESS_PLAN_V3.md` — full analysis
- `AI_AGENT_ANTIPATTERN_PLAYBOOK.md` — coding standards
- `/home/z/my-project/worklog.md` — analysis agent findings
