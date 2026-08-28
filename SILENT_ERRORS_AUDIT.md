# 🔇 Silent Error Audit — SupremeAI Codebase

> **Date:** 2026-08-28
> **Scope:** `backend/` (Python), `frontend/src/`, `packages/`, `tools/vscode-extension`, `scripts/` (TypeScript/JavaScript)
> **Method:** AST-based analysis (Python) + pattern heuristics (JS/TS), followed by manual verification of every Critical/High finding.
> **Scanner:** `scratch/scan_silent_errors.py` · Raw results: `scratch/silent_errors_report.json`
> **Excluded (not project code):** `node_modules/`, `.venv*`, `site-packages`, `dist*/`, `build/`, generated docs, Playwright driver bundles.

---

## Executive Summary

| Severity | Count | Meaning |
|---|---|---|
| 🔴 **Critical / High** | **30** | Errors fully swallowed in production paths — data loss, dead features, or untraceable failures possible |
| 🟠 **Medium** | **203** | Silent degradation paths with no logging/observability |
| 🟡 **Low** | **828** | Mostly guarded/secondary paths; many are documented-intentional |
| **Total findings** | **1,061** | across 1,720 Python + 494 JS/TS files scanned |

**The three most dangerous patterns in this codebase:**

1. **Fire-and-forget `asyncio.create_task(...)`** — 26 occurrences. If the task crashes, *nobody ever finds out*; the feature (memory auto-save, Redis listener, queue processing, agent init) just silently dies.
2. **Silent index creation in Alembic migrations** — a DB migration swallows index-creation failures, so production can run for months with missing indexes and zero trace.
3. **Unguarded `JSON.parse` inside WebSocket `onmessage` handlers** — one malformed frame silently kills the update loop for cost dashboards and admin screencast.

---

## 🔴 Critical Findings (verified by code inspection)

### C1. Database migration silently skips creating critical indexes
**File:** `backend/alembic_migrations/versions/2f7b3c5f620e_add_missing_indexes.py` — lines **193, 209, 221**

```python
try:
    op.create_index("idx_knowledge_base_user_id", "knowledge_base", ["user_id"], if_not_exists=True)
    print("✅ Created index: idx_knowledge_base_user_id")
except Exception:
    pass   # ← failure completely invisible
```

**Why it hurts production:** Index creation on `knowledge_base`, `activity_logs`, and `telemetry` can fail (lock timeout, table drift, permission). The migration still prints *"🎉 Migration complete!"* — you get **no error, no retry, no record**. Full-table scans on hot tables degrade every query indefinitely. Line 183 (same file) *does* log its skip reason — proving the inconsistency.

**Fix:** Log the exception (like lines 182–183), emit `logger.error`, and fail loudly if any index creation failed.

---

### C2. WebSocket Redis listener runs as an untracked task — broadcast can die silently
**File:** `backend/api/routes/websocket_agent.py` — line **199**

```python
await self.pubsub.subscribe("ws_broadcast")
asyncio.create_task(self._listen_to_redis())   # ← reference discarded
```

**Why it hurts production:** `_listen_to_redis()` is the pump that delivers every real-time message to connected clients. The task reference is discarded: if the coroutine dies outside its inner `try` (e.g., during `await self.pubsub.get_message`) or is GC'd mid-flight (allowed by CPython for unreferenced tasks), **all WebSocket pushes stop working with no error anywhere** — clients just see stale UI.

**Fix:** Keep the reference (`self._listener_task = asyncio.create_task(...)`) and add a done-callback logging `task.exception()`; restart with backoff on failure.

---

### C3. Task-queue worker processes jobs as untracked tasks
**File:** `backend/core/queue/task_queue.py` — line **69**

```python
result = await redis.blpop(self.queue_name, timeout=5)
if result:
    task_data = json.loads(task_json)
    asyncio.create_task(self._process_task(task_data))   # ← fire & forget
```

**Why it hurts production:** If `_process_task` raises before its internal `try` (e.g., `task_data["task_id"]` KeyError at line 75, or Redis connection failure at line 77), the exception vanishes — **the job stays in `processing` status forever**, never retried, with no log.

**Fix:** Track inflight tasks in a set + done-callback that logs `task.exception()`.

---

### C4. Session vector-memory auto-save is fire-and-forget — memory loss is silent
**File:** `backend/api/routes/session_stream.py` — line **60**

```python
finally:
    batcher.unsubscribe(session_id, queue)
    asyncio.create_task(auto_save_session_memory(session_id))   # ← unref'd
```

**Why it hurts production:** This is the only place session conversation history is persisted to vector memory. If the save fails (embedding API down, DB hiccup), the session memory is **silently lost forever** — no log, no retry, and the client believes the session completed cleanly.

**Fix:** Track the task + log failures; add a durable fallback queue for failed saves.

