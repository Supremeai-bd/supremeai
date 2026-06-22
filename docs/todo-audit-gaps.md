# .kilo Agent Todo Audit — Missing Items

**Date:** 2026-06-22  
**Source audit:** `backend/api/routes/admin_dashboard.py`, `backend/brain/model_router.py`, `backend/api/routes/auth.py`  
**Working dir:** `C:\Users\n\supremeai\supremeai_2.0`

---

## Gaps Not Covered in .kilo Todo List

### H1 — Entry Point / Foundation

- **`backend/main.py`** — inspect lifespan/startup/shutdown; add graceful error handling
- **`backend/api/routes/internal.py`** — audit and secure internal-only routes

### H2 — Core Router Dependencies

- **`core/agent_orchestrator.py`** — audit routing gaps (referenced from `model_router.py:16`)
- **`core/semantic_cache.py`** — validate/upgrade for production 5-level cache strategy

### H3 — Auth & Security

- **`core/config.py` merge risk** — `backend/main.py` likely imports both configs; merge must preserve all env vars
- **JWT blacklist Redis fallback/migration** — `admin_dashboard.py:29` references `app_mod.redis_queue`; incomplete if Redis unconfigured

### H4 — Circuit Breaker State

- **`model_router.py` — in-memory `_breakers`** needs Redis-backed state for multi-worker deployments

### H5 — Admin Tooling

- **`tools/cost_auditor.py`** — replace hardcoded fallback report with real DB-backed cost tracking
- **`tools/codebase_exporter.py`** — add chunking/streaming for large repos

### H6 — Voice / Tools Polish

- **`backend/tools/voice.py`** — complete implementation and integrate with `model_router` streaming pipeline

### H7 — Registry / Deprecation

- **`brain/model_registry.py`** — audit for deprecated models noted in `model_router.py` comments (gemini-1.5-flash, llama3-8b-8192, etc.)

### H8 — Config Concurrency

- **`.env` ETag race condition** — `admin_dashboard.py /config` uses file-based ETag; multi-instance deployments need locking
