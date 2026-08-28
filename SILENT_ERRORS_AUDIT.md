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

---

### C5. Secret resolution silently returns empty string
**File:** `backend/core/config_secrets.py` — lines **312–315**

```python
@property
def discord_bot_token(self) -> str:
    try:
        return get_secret_vault().fetch_secret("DISCORD_BOT_TOKEN", default="")
    except Exception:
        return ""   # ← vault outage looks identical to "no token configured"
```

**Why it hurts production:** When the secret vault is down, every consumer sees `""` and typically fails with *"invalid token"* or *"not configured"* — the root cause (vault outage) is invisible, turning a 5-minute infrastructure incident into a confusing debugging session.

**Fix:** Log at `ERROR` level before returning `""`, or raise and let callers decide; distinguish "not configured" from "vault unreachable".

---

### C6. Frontend crash reporting itself is swallowed — telemetry black hole
**File:** `frontend/src/components/GlobalErrorBoundary.tsx` — lines **28–45**

```tsx
fetch(`${getApiBaseUrl()}/api/telemetry/frontend-error`, {...keepalive: true})
  .catch(() => {});      // ← report failure ignored
```

**Why it hurts production:** This is the *last line of defense* — the component that reports uncaught React crashes. If the telemetry endpoint is down/misconfigured/CORS-blocked, errors vanish **with no console warning even in dev** and no retry. You only find out users crashed when they complain.

**Fix:** `console.warn` the failure in dev; add a `navigator.sendBeacon` fallback; count failures to detect telemetry outage.

---

### C7. One corrupted cache entry breaks entire batch reads
**File:** `frontend/src/lib/cache.manager.ts` — line **193** (unguarded parse also at 162; silent prefetch skip at 214)

```ts
const results = await pipeline.exec();
return Promise.all(results.map(async result =>
  result ? JSON.parse(await decompress(result as string)) : null
));
```

**Why it hurts production:** `JSON.parse` of decompressed data is unguarded. A single corrupted/legacy-format cache value **rejects the whole `batchGet`** → every key in the batch fails, and unlike `getWithCache` (which has a fallback fetcher), there is no fallback here.

**Fix:** Per-entry try/catch returning `null` + `console.warn` + delete the bad key (self-healing cache).

---

### C8. Unguarded `JSON.parse` in WebSocket message handlers freezes live views
**Files:**
- `frontend/src/pages/user/CostDashboard.tsx` — line **69**
- `frontend/src/components/admin/ScreencastViewer.tsx` — line **38**
- `frontend/src/components/research/DeepResearchPanel.tsx` — line **223** (catch present but empty)
- `frontend/src/components/admin/LibrarianQueue.tsx`, `CrownJewelBrowser.tsx` — floating `fetch()` with no await/catch (lines 25, 243, 511)


---

## 🟠 High-Volume Medium Findings (systemic patterns)

### P1. Fire-and-forget `asyncio.create_task(...)` — 26 verified occurrences

The task reference is discarded, so exceptions are raised to nobody. **Verified instances:**

| Location | Risk if the task dies silently |
|---|---|
| `backend/api/routes/websocket_agent.py:199` | All WS broadcasts stop (see C2) |
| `backend/api/routes/session_stream.py:60` | Session memory lost (see C4) |
| `backend/core/queue/task_queue.py:69` | Jobs stuck in `processing` (see C3) |
| `backend/core/admin_god.py:85,87` | Audit-log writes to Redis silently dropped |
| `backend/services/dynamic_ai/orchestrator.py:149` | Background health-check loop stops |
| `backend/services/dynamic_ai/learning_engine.py:105` | Learning loop stops |
| `backend/core/zero_cost_architecture/swarm_orchestrator_integration.py:326,363` | Swarm orchestration tasks stop |
| `backend/agents/infrastructure/cost_optimization_agent.py:798` | Budget config never initialized |
| `backend/agents/infrastructure/disaster_recovery_agent.py:676` | Recovery plans never initialized |
| `backend/tools/social/telegram_bot.py:1361` | Telegram updates silently unhandled |
| `scripts/devops/bug_prophet.py:681` | Outage events never emitted |

**Note (false-positive filter):** occurrences wrapped in `track_task(...)` (e.g., `governance_agent.py:580`, `error_remediation.py:185`, `config_cache.py:139`) *do* keep a reference — but verify `track_task` also attaches an exception-logging callback, otherwise failures are still invisible.

**Recommended pattern:**

```python
def _spawn(self, coro, name: str) -> None:
    task = asyncio.create_task(coro, name=name)
    self._tasks.add(task)
    task.add_done_callback(lambda t: (
        self._tasks.discard(t),
        t.exception() and logger.error(f"Background task '{name}' died", exc_info=t.exception()),
    ))
```

---

### P2. `except Exception: pass` in production code — 32 occurrences

All verified instances (excluding tests & vendor code):

| File:Line | Context |
|---|---|
| `backend/alembic_migrations/versions/2f7b3c5f620e_add_missing_indexes.py:193,209,221` | Index creation skipped (see C1) |
| `backend/api/routes/websocket_agent.py:171` | `ws.close()` on stale connections — acceptable, but consider debug log |
| `backend/core/health/uptime_tracker.py:60` | Uptime writes skipped — has an explanatory comment but no log; DB corruption would be invisible |
| `backend/core/observability/observability_middleware.py:62` | `except ImportError: pass` — optional dependency, OK |
| `backend/core/providers/n8n/adapter.py:173` | `except ImportError: pass` — optional dependency, OK |
| `backend/core/zero_cost_architecture/zero_cost_patch_phase1_4.py:327,482,1534` | `except asyncio.CancelledError: pass` — **wrong idiom**: prefer `except CancelledError: raise` or at least `continue` semantics; swallowing cancellation breaks graceful shutdown |

---

### P3. `except Exception: return <default>` with no logging — 106 occurrences

Handlers that return `None/False/""/{}/0.0` without logging. The caller cannot distinguish "no data" from "it broke". Most impactful (backend core & API):

| File:Line | Returns | Hidden failure mode |
|---|---|---|
| `backend/api/routes/living_brain.py:409` | `{}` | Learning-pattern stats look empty when SQLite breaks |
| `backend/api/routes/living_brain.py:424` | `0.0` | Avg confidence metric lies |
| `backend/core/cache/redis_manager.py:168` | `None` | Corrupt cache value = cache miss; no counter/log to detect poisoning |
| `backend/core/config_secrets.py:314` | `""` | See C5 |
| `backend/core/health/uptime_tracker.py:81,105` | `None` / `[]` | Uptime dashboard can show blank during DB issues |
| `backend/core/messaging/event_bus.py:350` | `{}` | PSUtil metrics silently empty |

---

### P4. Empty / silent `catch` blocks in TypeScript — 30 occurrences

| Severity | Pattern | Count |
|---|---|---|
| High | `catch { }` fully empty | 19 |
| High | `catch { return null/false/[] }` no logging | 11 |

**Most impactful (production paths):**

| File:Line | What gets hidden |
|---|---|
| `frontend/src/services/apiClient.ts:44,102,130` | Central API client — localStorage removal, device-fingerprint, error-body parse. Lines 44/102 are documented-intentional (incognito/SSR, old browsers) but **no telemetry counter exists** to know how often fingerprints are skipped |
| `frontend/src/components/GlobalErrorBoundary.tsx:43` | Crash reporting (see C6) |
| `frontend/src/store/authStore.ts:45,65` | Malformed JWT / corrupted stored user → silent logout; users lose state with no diagnostic trail |
| `frontend/src/services/skillsService.ts:64`, `supremeShared.ts:43` | Skill/shared-service failures return empty results |
| `frontend/src/components/dashboard/sessionStore.ts:34` | Corrupted localStorage → all sessions vanish (write path *does* log, read path doesn't) |
| `frontend/src/services/costOptimizer.service.ts:106,118` | Rate-limit map silently reset (quota enforcement state lost) |
| `frontend/src/components/admin/InteractiveChatTab.tsx:106`, `CrownJewelBrowser.tsx:204,556`, `ActionCard.tsx:33`, `UnifiedChatBubble.tsx:44`, `SlashCommandMenu.tsx:151`, `customer/ChatPanel.tsx:22`, `dashboard/SandboxViewport.tsx:32`, `DeepResearchPanel.tsx:223`, `modelBranding.ts:112` | Admin & chat UI features degrade invisibly |
| `packages/shared-services/src/platform/electron.ts:53,124,140` | Electron platform detection failures |
| `tools/vscode-extension/src/ai/AIService.ts:65`, `services/apiBridge.ts:101,168`, `adapters/VsCodePlatformAdapter.ts:36` | VS Code extension: AI calls and API bridge failures swallowed |
| `scripts/monitoring/superai_console_capture.js:129` | Monitoring capture skips entries |

**Fix pattern:** never `catch {}` bare — either handle, or log: `catch (e) { console.warn('[ctx]', e); }` (dev) / forward to telemetry (prod).

---

### P5. Floating `fetch()` promises — 11 occurrences

`fetch()` called without `await` and without `.catch`: rejection becomes an unhandled promise rejection.

- `frontend/src/components/admin/LibrarianQueue.tsx:25` — admin librarian queue refresh
- `frontend/src/components/admin/data/CrownJewelBrowser.tsx:243,511` — browse-session & screenshots
- `frontend/src/components/GlobalErrorBoundary.tsx:29` — covered in C6 (has `.catch(()=>{})`, so no crash but no visibility)
- `tools/vscode-extension/test/*` — test mocks, no action needed

---

### P6. `contextlib.suppress(Exception)` — 11 occurrences

| File:Line | Assessment |
|---|---|
| `backend/core/llm/telemetry.py:94` | ✅ **Documented-intentional** (best-effort telemetry, rationale in comment) — but the suppressed emit isn't counted; add a metric |
| `backend/tools/knowledge/knowledge_base_indexer.py:228,409`, `local_search_rag.py:295`, `git_knowledge_extractor.py:110` | ⚠️ Indexing/search silently degrades — RAG quality drops with no signal |
| `backend/tools/code/cot_reasoner.py:83` | ⚠️ Reasoning step silently skipped |
| `backend/tools/social/telegram_bot.py:307`, `viral_referral_engine.py:216` | ⚠️ User-facing bot actions silently skipped |
| `backend/workers/chaos_worker.py:107` | ⚠️ Chaos experiment steps vanish |
| `scripts/backup/backup_telegram.py:29,854` | 🔴 **Backups** — a silent skip here means missing backup data discovered only during restore |

---

### P7. Bare `except:` — 1 occurrence

- `backend/examples/sample_buggy.py:104` — example file, but it's used as learning material and errors go to `print()`; replace with `except Exception as e: logger.exception(...)` so the pattern isn't copied.

---

## ✅ Reviewed and accepted as intentional (no action needed)

Flagged by the scan but verified as deliberate, documented decisions — listed so future audits don't re-flag them:

- `frontend/src/services/apiClient.ts:44` — localStorage absent in incognito/SSR (commented)

---

## 📊 Hotspots (files with most medium+high findings)

| # | Findings | File |
|---|---|---|
| 1 | 7 | `tools/vscode-extension/test/supremeai-service.test.ts` (test mocks — ignore) |
| 2 | 6 | `backend/core/code_validator.py` |
| 3 | 6 | `frontend/src/components/admin/data/CrownJewelBrowser.tsx` |
| 4 | 5 | `scripts/advanced_analysis/dependency_freshness_radar.py` |
| 5 | 4 | `backend/api/routes/browser_routes.py` |
| 6 | 4 | `backend/core/zero_cost_architecture/zero_cost_patch_phase1_4.py` |
| 7 | 4 | `backend/tools/code/code_smell_detector.py` |
| 8 | 4 | `scripts/advanced_analysis/agent_capability_registry_sync.py` |
| 9 | 3 | `backend/alembic_migrations/versions/2f7b3c5f620e_add_missing_indexes.py` |
| 10 | 3 | `backend/core/admin_god.py` |
| 11 | 3 | `backend/core/deployment/production_deploy.py` (false positives — see accepted list) |
| 12 | 3 | `backend/core/evolution/digital_twin/remediation_engine.py` |
| 13 | 3 | `backend/core/health/uptime_tracker.py` |
| 14 | 3 | `backend/core/queue/task_queue_enhanced.py` |
| 15 | 3 | `frontend/src/components/GlobalErrorBoundary.tsx` |
| 16 | 3 | `frontend/src/lib/cache.manager.ts` |
| 17 | 3 | `frontend/src/services/apiClient.ts` |
| 18 | 3 | `packages/shared-services/src/platform/electron.ts` |

---

## 🛠 Recommended Remediation Plan

**Phase 1 — this week (Critical C1–C8):**
1. Fix the Alembic migration (C1) — log + fail loudly; re-run against staging.
2. Add a `tracked_task()` helper (pattern in P1) and apply to the 11 riskiest call sites (websocket_agent, task_queue, session_stream, admin_god, orchestrators).
3. Guard all `JSON.parse` in WS handlers (C7, C8) with per-message try/catch.
4. Add error logging to `config_secrets.discord_bot_token` (C5) and `GlobalErrorBoundary` (C6).

**Phase 2 — this sprint:**
5. Sweep the 32 `except-pass` sites: replace `pass` with `logger.debug(...)` minimum; remove comment-only catches.
6. Add per-entry error handling to `batchGet` in cache.manager.ts.
7. Add CI lint rules: ruff `S110` (try-except-pass), `S112` (try-except-continue), `BLE001` (blind except), `RUF006` (asyncio task storage); eslint `no-empty` + custom rule banning `.catch(() => {})`.

**Phase 3 — next sprint:**
8. Triage the 106 `except-return-default` sites — add `logger.exception` where a false default can mislead callers (start with `core/`, `api/routes/`).
9. Centralize `safe_async(coro, name)` / `safe_json(text, fallback)` utilities so the *easy* path is the observable path.

- `frontend/src/services/apiClient.ts:102` — WebCrypto missing in old browsers; request proceeds without fingerprint (commented)
- `frontend/src/store/authStore.ts:45,65` — return-null on corrupt JWT/storage (falls back to fresh login)
- `backend/core/llm/telemetry.py:84–95` — best-effort telemetry with detailed rationale comment (prevents masking real LLM results)
- `backend/core/health/uptime_tracker.py:60` — uptime writes must never break health checks (add a metric though)
- `backend/core/admin_god.py:88` — audit path guarded with explicit "Anti-silent failure" comment (writes remain fire-and-forget — see P1)
- `backend/core/queue/task_queue_enhanced.py:129`, `backend/api/routes/browser_routes.py:738–769` — `except ImportError` feature-gates (optional deps)
- `backend/core/deployment/production_deploy.py:329,362,459` — flagged by scanner but **not silent**: they call `_update_deployment_status(..., FAILED, ...)` ✅
- `backend/agents/ephemeral_executor.py:145` — collects violation with message ✅
- `track_task(...)`-wrapped tasks (`governance_agent.py:580`, `error_remediation.py:185`, `config_cache.py:139`, `db_optimization_middleware.py:211,274`, `auto_scaling_agent.py:543`) — reference kept; verify `track_task` also logs exceptions on completion


**Fix:** `await` them (or `.catch` with logging); consider wrapping in the existing `requestQueue`.

| `backend/core/messaging/nats_messaging.py:119` | `None` | KV lookup failure indistinguishable from missing key |
| `backend/core/container_auditor.py:74` | `0.0` | Audit metrics read as zero |
| `backend/agents/infrastructure/auto_scaling_agent.py:441,485` | `0.0` / `None` | Autoscaler may compute on fake zeros |
| `backend/core/code_validator.py:55,62,78,93,128,146` | `False` | Validation outage reads as "code invalid" — 6 separate silent paths |
| `backend/core/admin_routes.py:487` | `False` | Admin op failure looks like "denied/not found" |
| `backend/core/app_builder.py:170` | `False` | Builder failure indistinguishable from validation failure |

Full list: `scratch/silent_errors_report.json` → `python_findings` where `type == "except-return-default"`.

**Fix pattern:** `except Exception: logger.exception("...context..."); return <default>` — one line restores observability while keeping behavior.

```ts
wsRef.current.onmessage = (event) => {
  const update = JSON.parse(event.data);   // ← throws on any malformed/partial frame
  ...
};
```

**Why it hurts production:** A malformed frame (proxy interruption, non-JSON ping, server format change) throws inside the handler. The browser logs an unhandled error (easy to miss), that message's state updates never run, and **the admin screencast silently freezes** while still showing "connected". Cost-dashboard realtime updates die the same way.

**Fix:** Wrap in try/catch, log the payload prefix at `warn`, keep the connection alive.


**Why it hurts production:** This is the only place session conversation history is persisted to vector memory. If the save fails (embedding API down, DB hiccup), the session memory is **silently lost forever** — no log, no retry, and the client believes the session completed cleanly.

**Fix:** Track the task + log failures; add a durable fallback queue for failed saves.

