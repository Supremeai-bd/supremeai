# 🔧 Admin Tasks — SupremeAI Production Setup

> **Audience:** DevOps / system administrator
> **Purpose:** Tasks that CANNOT be done by code changes alone — require admin access to deploy configs, env vars, or external services.
> **Source:** Found during v3 production readiness analysis (4 parallel agents).

---

## 📋 Quick Reference — All Required Env Vars

| Variable | Default | Purpose | Priority |
|---|---|---|---|
| `ENABLE_AUTO_HEALER` | `true` | Start AutoHealer background service | HIGH |
| `ENABLE_EVOLUTION` | `false` | Start SelfEvolutionAgent 5-min loop | MEDIUM |
| `ENABLE_DAILY_LEARNER` | `false` | Start 24h research scan | LOW |
| `ENABLE_TIER8` | `false` | Start self-improvement (requires paid OpenAI gpt-4o-mini) | LOW |
| `ENABLE_EVOLUTION_LEARNING` | `false` | Wire EvolutionEngine into LLM success path | MEDIUM |
| `EXPERIENCE_DB_PATH` | `/tmp/chroma` | ChromaDB persistence path (mount /data/) | HIGH |
| `QDRANT_PATH` | `/tmp/qdrant` | Qdrant local file storage path | HIGH |
| `WS_MAX_CONNECTIONS` | `50` | Max concurrent WS connections | HIGH |
| `WS_MAX_PER_USER` | `3` | Max WS connections per user | HIGH |
| `INTENT_ROUTER_MODE` | `llm` | LLM gatekeeper (regex = fallback only) | LOW |
| `TOKEN_JUICE_ENABLED` | `true` | Token compression on LLM inputs | LOW |
| `SUPREMEAI_ENABLE_HEAVY_ROUTES` | `false` |digital_twin/economics/swarm (removed upstream) | N/A |

---

## 🚨 CRITICAL — Do These First

### 1. Mount Persistent `/data/` Volume on Render

**Why:** Without this, all learning (ChromaDB + Qdrant + EvolutionEngine) is lost every time the container cold-starts (Render free-tier sleeps after 15 min idle).

**How:**
1. Open Render dashboard → your service → **Disks** tab
2. Click **Add Disk**
3. Set:
   - **Name:** `supremeai-data`
   - **Mount Path:** `/data`
   - **Size:** 1 GB (free-tier max)
4. Save and redeploy
5. Set these env vars on Render:
   ```
   EXPERIENCE_DB_PATH=/data/chroma
   QDRANT_PATH=/data/qdrant
   ```

**Verify after deploy:**
```bash
# SSH into Render shell (or use 'console' tab)
ls -la /data/
# Should see chroma/ and qdrant/ after first request
```

---

### 2. Run the New Database Migration

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

# 6. ChromaDB persists (after enabling /data/ volume)
# Make a chat request, restart container, make similar request
# Check logs for "⚡ [SEMANTIC CACHE HIT]" — should appear if persistence works
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
