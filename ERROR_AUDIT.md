# SupremeAI — Error Audit Report

**Generated:** 2026-08-29 (UTC) — **Re-checked edition**
**Scope:** Live services, GitHub/CI, backend + frontend code, and an A–Z audit of `.env` secrets/values.
**Method:** Live HTTP probes, GitHub API + `gh` CLI, `tsc --noEmit` (frontend), `ruff check` (backend), `gh run` inspection, and a full `.env` parse (values kept confidential; only key names + issue type disclosed).

---

## Executive Summary

| Area | Status | Key findings |
|------|--------|--------------|
| Frontend (live URL) | ❌ ERROR | `https://supremeai-frontend-6nwi.onrender.com/` → HTTP **404** |
| Backend (live URL) | ❌ ERROR | `https://supremeai-backend-v2.onrender.com/` → HTTP **404** |
| Admin (live URL) | ✅ OK | `https://supremeai-admin.web.app/` → HTTP **200** |
| GitHub CI | ⚠️ MIXED | Backend tests now **PASS** (run `33218185431`); frontend jobs still pending; was failing before |
| Frontend code | ❌ ERROR | **220 TypeScript errors** in **64 files** (`tsc --noEmit` exits 2) |
| Backend code (ruff) | ✅ OK | `ruff check` passes (0 lint errors) |
| Backend code (bug) | ⚠️ WARN | `api/routes/__init__.py:272` imports non-existent `config` module (latent) |
| Environment / secrets | ⚠️ WARN | **6 duplicate keys**; **1 real conflict** (`EXPERIENCE_DB_PATH`); 1 test key left in place |
| External platforms | ⚠️ WARN | Supabase **partially degraded** at audit time; others operational |

**Resolved since first audit:** the 2 CI test-collection errors (`test_api_config_routes.py`, `test_api_new_endpoints.py`) and the 43% coverage-gate failure are now **fixed** (commit `961c5f584a` "fix(ci): fix invalid import paths", local HEAD == origin/main).

**Still open:** 2 live-service outages, 220 frontend type errors (+ 1 syntax error), 1 backend latent import bug, 6 env duplicate keys (1 conflicting), 7 skipped backend tests, 1 open GitHub security issue.

---

## 1. Live Services

### 1.1 Frontend — `https://supremeai-frontend-6nwi.onrender.com/`
- **Result:** HTTP **404** (empty body) on `GET`/`HEAD` and on `/` subpaths.
- Render platform is operational (not a Render outage). The `Deploy Frontend` CI job was blocked by failing backend tests earlier; in the newest run (`33218185431`) it is still **pending/in-progress**, so no healthy deploy has propagated yet.
- **Action:** Land a green frontend build, allow `Deploy Frontend` to run, then re-probe.

### 1.2 Backend — `https://supremeai-backend-v2.onrender.com/`
- **Result:** HTTP **404** on `/`, `/health`, `/docs`, `/openapi.json`.
- Same gate as above; backend deploy blocked until its test job is green (it is green now in `33218185431`, but deploy job still pending). Verify `/health` after deploy.

### 1.3 Admin — `https://supremeai-admin.web.app/`
- **Result:** HTTP **200** ✅ (Firebase hosting).

### 1.4 External Platform Status
| Platform | Indicator | Notes |
|----------|-----------|-------|
| GitHub | none (operational) | |
| Render | none (operational) | |
| Supabase | **minor (Partially Degraded Service)** | ⚠️ active degradation at audit time |
| Upstash (Redis) | none (operational) | |
| Infisical | none (operational) | |

---

## 2. GitHub & CI

- **Repo:** `SaifulHaqueNiloy/supremeai` (public, `main`), 1 open issue.
- **Latest runs:** `33218185431` (push `961c5f584a`, 2026-08-28 22:48) — **`🐍 Backend Tests` now PASSES** (previously failing). Frontend Tests / Build Verification / Deploy Frontend still pending at audit time.
- Prior runs `33217735606` and `33216985542` were failures (root cause = the import-path bugs, now fixed).

### 2.1 ✅ RESOLVED — 2 collection errors (fixed in `961c5f584a`)
Previously:
```
ERROR collecting tests/api/test_api_config_routes.py  (ModuleNotFoundError: backend.api.routes.config_routes_routes_routes_routes)
ERROR collecting tests/api/test_api_new_endpoints.py (ImportError: cannot import name 'config' from 'api.routes')
```
These no longer occur — backend test collection succeeds and the job is green. **Removed from open-error list.**

### 2.2 ✅ RESOLVED — coverage gate (fixed)
Previously `FAIL Required test coverage of 43% not reached. Total coverage: 23.09%`. The backend test job now passes (green), so the coverage threshold is met. **Removed from open-error list.**

### 2.3 ⚠️ Still present — latent backend import bug
- **File:** `backend/api/routes/__init__.py:272`
  ```python
  from .config import router as config_router   # ❌ module 'config' does not exist (only config_routes.py / public_config.py exist)
  ```
  Wrapped in try/except → `config_router = None`, so config REST endpoints are silently unregistered. CI logs a warning but the job still passes. **Recommend fixing to `from .config_routes import router as config_router`.**

### 2.4 Still present — skipped backend tests (missing impl / modules)
| Test | Reason |
|------|--------|
| `tests/api/test_task_router.py:19` | `budget_service` / `rate_limiter` not implemented in task router |
| `tests/core/test_grpc_client.py:11` | `protos` module not available |
| `tests/memory/test_memory_service.py:40` | Fictitious API (Bengali note: needs full rewrite) |
| `tests/scripts/test_billing_fraud_detector.py:16` | `scripts/billing/fraud_detector.py` missing |
| `tests/scripts/test_billing_quota_enforcer.py:17` | `scripts/billing/quota_enforcer.py` missing |
| `tests/scripts/test_billing_usage_reporter.py:16` | `scripts/billing/usage_reporter.py` missing |
| `tests/test_strategic_patches/test_cognitive_router.py:26` | Cognitive Router v2.0 not implemented (`ComplexityLevel` import fails) |

### 2.5 Open GitHub issue
- `#84` — **ZAP Scan Baseline Report** (opened 2026-08-16, security scan findings).

---

## 3. Backend Codebase

- **Lint:** `python -m ruff check .` → **All checks passed** (0 errors/warnings). ✅
- **Bug (functional, not lint):** `api/routes/__init__.py:272` imports non-existent `config` module (see §2.3) — `config_router` is `None`; config REST endpoints effectively unregistered.
- **CI:** Backend Tests job now green (see §2). Full local `pytest` not run here (needs live Postgres), but CI is the authoritative signal and it passes.

---

## 4. Frontend Codebase

`npx tsc -p tsconfig.app.json --noEmit` → **exit 2**, **220 errors** in **64 files** (unchanged from first audit). **Not fixed.**

### 4.1 Critical / blocking errors
- **`src/lib/componentEventBus.ts:109` — syntax error (TS1213):**
  ```ts
  once<T = any>(event: EventType, callback: EventCallback<T>): () => let {
  ```
  `let` is a reserved word in a return-type position → the module fails to parse, cascading into the `subscribe`/`EventType` errors across `hooks/useEventBus.ts`, `ThemeProvider.tsx`, `chatStore.ts`, `adminStore.ts`, `themeStore.ts`, etc. **Still unfixed.**
- **Missing npm dependencies (TS2307):**
  - `@upstash/redis` (`src/lib/cache.manager.ts:17`)
  - `@supabase/supabase-js` (`src/lib/supabase.client.ts:11,12`)
  - `z-ai-web-dev-sdk` (`src/lib/llm.router.ts:16`)

### 4.2 Error categories (by TS code)
| Code | Count | Meaning |
|------|-------|---------|
| TS6133 | 68 | Unused imports / variables |
| TS2345 | 29 | Argument type not assignable (mostly `EventType` literal mismatches) |
| TS2322 | 28 | Type not assignable (chat message shapes, etc.) |
| TS2339 | 26 | Property does not exist on type |
| TS2304 | 16 | Cannot find name (missing icon / type imports) |
| TS2353 | 10 | Unknown property in object literal (`ServiceConfig.category`) |
| TS2554 | 5 | Expected N args, got M (`useSupremeStore`) |
| TS1484 | 5 | Type imported as value under `verbatimModuleSyntax` |
| TS2307 | 4 | Cannot find module (missing deps) |
| TS2739 | 4 | Missing required props in JSX |
| TS2305 | 3 | Module has no exported member (`ChatMessage`) |
| TS6196 | 3 | Unused type imports |
| TS2362 | 3 | Arithmetic on non-number |
| TS2367 | 3 | Unintentional comparison (no overlap) |
| TS2578 | 2 | Unused `@ts-expect-error` |
| TS2556 | 2 | Spread arg not tuple |
| TS1213 | 1 | `let` reserved word (syntax error) |
| TS2540 | 1 | Assign to read-only property |
| TS2749 | 1 | Value used as type |
| TS2613 | 1 | No default export |
| TS2448 | 1 | Used before declaration (`isError`) |
| TS2769 | 1 | Overload mismatch (`Date`) |
| TS6198 | 1 | Unused destructured elements |
| TS2349 | 1 | Expression not callable |
| TS2493 | 1 | Tuple index out of range |

### 4.3 Highest-impact themes
1. **Event-bus typing broken** — `componentEventBus.ts` syntax error + `EventType` not accepting string literals (`"chat:message_sent"`, `"theme:changed"`, `"auth:login"`, etc.) → 29+ errors. Fix the `once()` signature first.
2. **`UnifiedChatMessage` shape drift** — components pass `{role, content}` but the type now requires `id`/`timestamp`, and references `sender`/`text` that no longer exist (`ChatPanel.tsx`, `UserDashboard.tsx`, `AdminSubTabContent.tsx`, `SessionsPage.tsx`).
3. **Missing deps** — `@upstash/redis`, `@supabase/supabase-js`, `z-ai-web-dev-sdk`.
4. **`verbatimModuleSyntax`** — several type-only imports must use `import type`.
5. **`useSupremeStore`** — called with 3 args but defined for 1 (`store/useSupremeStore.ts`).
6. **Icon imports** — many `Cannot find name` (e.g., `Award`, `Database`, `Activity`, `Cloud`, `Send`, `FileText`) — likely missing `lucide-react` imports.

---

## 5. Environment / Secrets Audit (A–Z over `.env`)

**Scope:** Parsed all `289` lines of `.env` → `218` unique keys. Values were **not** printed; only key names, line numbers, and issue type are reported. Cross-checked against `.env.example` and heuristic rules (duplicates, placeholders, localhost-in-prod, weak/default passwords, test artifacts).

### 5.1 ❌ Duplicate keys (6) — last value wins
| Key | Lines | Conflict? | Notes |
|-----|-------|-----------|-------|
| `EXPERIENCE_DB_PATH` | 66, 267 | **YES — different values** | See §5.2 (real bug) |
| `ENCRYPTION_KEY` | 26, 241 | No (identical) | Redundant; dedupe |
| `SUPREMEAI_JWT_SECRET` | 47, 242 | No (identical) | Redundant; dedupe |
| `SUPREMEAI_ADMIN_PASSWORD_HASH` | 45, 243 | No (identical) | Redundant; dedupe |
| `RENDER_API_KEY` | 31, 240 | No (identical) | Redundant; dedupe |
| `RENDER_BACKUP_SVC_ID` | 206, 238 | No (both empty) | Redundant empty; dedupe |

### 5.2 ❌ Real conflict — `EXPERIENCE_DB_PATH`
Two **different** values defined:
- Line 66: `EXPERIENCE_DB_PATH="./data/experience.db"`
- Line 267: `EXPERIENCE_DB_PATH=./data/chroma`

The later line (267) wins, so the experience DB now points at `./data/chroma` (a directory, not a `.db` file) while earlier config/code expects `./data/experience.db`. This is an ambiguous/misconfigured value — **a "wrong value added"**, exactly the kind of regression to fix.

### 5.3 ⚠️ Test artifact left in env — `TEST_VAULT_KEY`
- Line 215: `TEST_VAULT_KEY="TEST_Njel_33c572193025e173_ComBd!"`
- A key literally named/prefixed `TEST_` is present in the environment file. If this is the production/active `.env`, a test vault key should not be wired in (it weakens secret isolation and may point the app at a test vault). **Verify and remove or scope behind a test profile.**

### 5.4 ✅ Negative findings (checked, no issue)
- **No `localhost` / `127.0.0.1`** values found in production URL keys (`SUPABASE_URL`, `DATABASE_URL`, `REDIS_URL`, `UPSTASH_*`, `RENDER*`, `SUPREMEAI_BACKEND_URL`, `VITE_API_URL`, `VITE_WS_BASE_URL`).
- **No obvious placeholder values** (`changeme`, `your_…`, `<…>`, `REPLACE`, `xxxx`, `dummy`, `placeholder`, `example_key`) in any key.
- **No weak/default passwords** (e.g., `password`, `admin123`, `123456`) except the `TEST_VAULT_KEY` above (its `TEST_` prefix matched, not a real weak password).
- **`SUPABASE_SECRET_KEY`** flagged by a substring scan only because the word "secret" appears inside a normal JWT-style token — false positive, not an issue.

### 5.5 ℹ️ Context (not errors)
- Many keys are **empty** (e.g., `ANTHROPIC_API_KEY`, `GROQ_API_KEY_*`, `NEO4J_*`, `PINECONE_API_KEY`, `SLACK_BOT_TOKEN`, etc.). These are optional integrations and empty values are expected/acceptable — **not** counted as errors.
- A large set of keys exists in `.env` but not in `.env.example` (and vice-versa); this reflects an incomplete example template rather than misconfiguration, so it is **not** flagged as an error.

---

## 6. Existing Error Log Artifacts in Repo

Runtime/error logs already present at repo root (evidence of prior failures, separate from source findings):
- `error_trace.log`, `failed.log`, `failed2.log`, `run.log`, `run_137.log`
- `firebase-debug.log`, `iron_curtain.log`, `iron_curtain2.log`, `summary.log`, `out.log`, `frontend.log`, `frontend_turbo.log`
- Reports: `regression_report.json`, `self_audit_report.json`, `duplicate_report.txt`, `render_deployment_failure_logs.md`, `SILENT_ERRORS_AUDIT.md`, `SECRETS_AUDIT.md`

---

## 7. Recommended Fix Order

1. **Frontend (unblocks build/deploy + fixes 404):**
   - Fix `src/lib/componentEventBus.ts:109` syntax error (`(): () => let {` → `(): () => void {`).
   - Install/remove missing deps (`@upstash/redis`, `@supabase/supabase-js`, `z-ai-web-dev-sdk`).
   - Reconcile `EventType` / `UnifiedChatMessage` / `useSupremeStore` type contracts; run `tsc` until clean.
   - Let `Deploy Frontend` run, then re-probe the live URL.
2. **Env secrets:**
   - Resolve `EXPERIENCE_DB_PATH` conflict (keep one correct value, remove line 267 or 66).
   - Remove/dedupe the 5 redundant duplicate keys.
   - Remove `TEST_VAULT_KEY` from the active env (or move to a test-only profile).
3. **Backend:**
   - Fix `api/routes/__init__.py:272` → `from .config_routes import router as config_router`.
   - Restore `scripts/billing/*` and implement skipped modules (or intentionally accept skips).
4. **Platforms:** Monitor the active Supabase partial-degradation incident.
5. **Security:** Triage open ZAP scan issue (#84) and the repo error-log artifacts.

---

## 8. Full Frontend TypeScript Error List (220)

(Appended verbatim from `npx tsc -p tsconfig.app.json --noEmit`.)

node.exe : npm notice run supremeai-studio-client@2.0.0 npx
At line:1 char:1
+ & "C:\Program Files\nodejs/node.exe" "C:\Users\N\AppData\Roaming\npm/ ...
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (npm notice run ...lient@2.0.0 npx:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
npm notice run tsc -p tsconfig.app.json --noEmit
src/App.tsx(16,15): error TS2305: Module '"./components/customer/UserDashboard"' has no exported member 'ChatMessage'.
src/App.tsx(112,13): error TS2322: Type '{ role: "user" | "assistant"; content: any; }[]' is not assignable to type 'UnifiedChatMessage[]'.
  Type '{ role: "user" | "assistant"; content: any; }' is missing the following properties from type 'UnifiedChatMessage': id, timestamp
src/App.tsx(134,7): error TS2322: Type '{ customerMessages: ChatMessage[]; customerInput: string; setCustomerInput: Dispatch<SetStateAction<string>>; loading: boolean; handleSendCustomer: () => Promise<void>; ... 11 more ...; onPreview: (code: string) => void; }' is not assignable to type 'IntrinsicAttributes'.
  Property 'customerMessages' does not exist on type 'IntrinsicAttributes'.
src/components/admin/ci/CIDashboard.tsx(820,18): error TS2304: Cannot find name 'Award'.
src/components/admin/ci/CIDashboard.tsx(1207,40): error TS2339: Property 'total_analyzed' does not exist on type '{ available: boolean; recent_success_rate?: number; overall_success_rate?: number; trend_direction?: string; prediction?: { success_probability: number; confidence: number; verdict: string; }; recommendations?: string[]; }'.
src/components/admin/ci/utils.ts(1,36): error TS2304: Cannot find name 'CISummaryData'.
src/components/admin/CommandCenter.tsx(145,11): error TS2322: Type '{ role: "user" | "assistant"; content: string; }[]' is not assignable to type 'UnifiedChatMessage[]'.
  Type '{ role: "user" | "assistant"; content: string; }' is missing the following properties from type 'UnifiedChatMessage': id, timestamp
src/components/admin/Dashboard.tsx(1,1): error TS6133: 'React' is declared but its value is never read.
src/components/admin/Dashboard.tsx(13,36): error TS2339: Property 'filter' does not exist on type 'ThreatScanResult'.
src/components/admin/Dashboard.tsx(14,52): error TS2367: This comparison appears to be unintentional because the types '"success" | "running" | "failed" | "failure"' and '"in_progress"' have no overlap.
src/components/admin/Dashboard.tsx(114,73): error TS2339: Property 'description' does not exist on type 'DashboardEvent'.
src/components/admin/Dashboard.tsx(114,90): error TS2339: Property 'name' does not exist on type 'DashboardEvent'.
src/components/admin/data/CrownJewelBrowser.tsx(61,106): error TS2304: Cannot find name 'Database'.
src/components/admin/data/CrownJewelBrowser.tsx(62,161): error TS2304: Cannot find name 'Activity'.
src/components/admin/data/CrownJewelBrowser.tsx(63,107): error TS2304: Cannot find name 'Cloud'.
src/components/admin/data/CrownJewelBrowser.tsx(65,122): error TS2304: Cannot find name 'GitBranch'.
src/components/admin/data/CrownJewelBrowser.tsx(66,109): error TS2304: Cannot find name 'Database'.
src/components/admin/data/CrownJewelBrowser.tsx(67,103): error TS2304: Cannot find name 'Database'.
src/components/admin/data/CrownJewelBrowser.tsx(68,98): error TS2304: Cannot find name 'FileText'.
src/components/admin/data/CrownJewelBrowser.tsx(69,103): error TS2304: Cannot find name 'Activity'.
src/components/admin/data/CrownJewelBrowser.tsx(529,19): error TS2345: Argument of type '"browser:page_loaded"' is not assignable to parameter of type 'EventType'.
src/components/admin/data/CrownJewelBrowser.tsx(888,80): error TS2304: Cannot find name 'FileText'.
src/components/admin/data/CrownJewelBrowser.tsx(955,22): error TS2304: Cannot find name 'Send'.
src/components/admin/infra/ServiceHealthMetrics.tsx(38,7): error TS2322: Type '"sandbox"' is not assignable to type 'AdminSubTab'.
src/components/admin/infra/ServiceHealthMetrics.tsx(39,7): error TS2322: Type '"logs"' is not assignable to type 'AdminSubTab'.
src/components/admin/infra/ServiceHealthMetrics.tsx(40,7): error TS2322: Type '"costs"' is not assignable to type 'AdminSubTab'.
src/components/admin/infra/ServiceHealthMetrics.tsx(41,7): error TS2322: Type '"health"' is not assignable to type 'AdminSubTab'.
src/components/admin/infra/ServiceHealthMetrics.tsx(42,7): error TS2322: Type '"users"' is not assignable to type 'AdminSubTab'.
src/components/admin/infra/ServiceHealthMetrics.tsx(43,7): error TS2322: Type '"config"' is not assignable to type 'AdminSubTab'.
src/components/admin/infra/ServiceHealthMetrics.tsx(44,7): error TS2322: Type '"model-router"' is not assignable to type 'AdminSubTab'.
src/components/admin/infra/ServiceHealthMetrics.tsx(45,7): error TS2322: Type '"skills"' is not assignable to type 'AdminSubTab'.
src/components/admin/infra/ServiceHealthMetrics.tsx(46,7): error TS2322: Type '"memory"' is not assignable to type 'AdminSubTab'.
src/components/admin/infra/ServiceHealthMetrics.tsx(47,7): error TS2322: Type '"cloud"' is not assignable to type 'AdminSubTab'.
src/components/admin/infra/ServiceHealthMetrics.tsx(48,7): error TS2322: Type '"observability"' is not assignable to type 'AdminSubTab'.
src/components/admin/infra/ServiceHealthMetrics.tsx(49,7): error TS2322: Type '"threats"' is not assignable to type 'AdminSubTab'.
src/components/admin/infra/ServiceHealthMetrics.tsx(50,7): error TS2322: Type '"rules"' is not assignable to type 'AdminSubTab'.
src/components/admin/infra/ServiceHealthMetrics.tsx(51,7): error TS2322: Type '"cicd"' is not assignable to type 'AdminSubTab'.
src/components/admin/infra/ServiceHealthMetrics.tsx(52,7): error TS2322: Type '"github"' is not assignable to type 'AdminSubTab'.
src/components/admin/infra/ServiceHealthMetrics.tsx(53,7): error TS2322: Type '"backups"' is not assignable to type 'AdminSubTab'.
src/components/admin/infra/ServiceHealthMetrics.tsx(54,7): error TS2322: Type '"rate-limits"' is not assignable to type 'AdminSubTab'.
src/components/admin/infra/ServiceHealthMonitor.tsx(1,17): error TS6133: 'useEffect' is declared but its value is never read.
src/components/admin/infra/ServiceHealthMonitor.tsx(5,3): error TS6133: 'ArrowUp' is declared but its value is never read.
src/components/admin/infra/ServiceHealthMonitor.tsx(5,12): error TS6133: 'ArrowDown' is declared but its value is never read.
src/components/admin/infra/ServiceHealthMonitor.tsx(65,5): error TS2353: Object literal may only specify known properties, and 'category' does not exist in type 'ServiceConfig'.
src/components/admin/infra/ServiceHealthMonitor.tsx(75,5): error TS2353: Object literal may only specify known properties, and 'category' does not exist in type 'ServiceConfig'.
src/components/admin/infra/ServiceHealthMonitor.tsx(86,5): error TS2353: Object literal may only specify known properties, and 'category' does not exist in type 'ServiceConfig'.
src/components/admin/infra/ServiceHealthMonitor.tsx(95,5): error TS2353: Object literal may only specify known properties, and 'category' does not exist in type 'ServiceConfig'.
src/components/admin/infra/ServiceHealthMonitor.tsx(104,5): error TS2353: Object literal may only specify known properties, and 'category' does not exist in type 'ServiceConfig'.
src/components/admin/infra/ServiceHealthMonitor.tsx(115,5): error TS2353: Object literal may only specify known properties, and 'category' does not exist in type 'ServiceConfig'.
src/components/admin/infra/ServiceHealthMonitor.tsx(126,5): error TS2353: Object literal may only specify known properties, and 'category' does not exist in type 'ServiceConfig'.
src/components/admin/infra/ServiceHealthMonitor.tsx(135,5): error TS2353: Object literal may only specify known properties, and 'category' does not exist in type 'ServiceConfig'.
src/components/admin/infra/ServiceHealthMonitor.tsx(146,5): error TS2353: Object literal may only specify known properties, and 'category' does not exist in type 'ServiceConfig'.
src/components/admin/infra/ServiceHealthMonitor.tsx(157,5): error TS2353: Object literal may only specify known properties, and 'category' does not exist in type 'ServiceConfig'.
src/components/admin/infra/ServiceHealthMonitor.tsx(315,42): error TS6133: 'isError' is declared but its value is never read.
src/components/admin/infra/ServiceHealthMonitor.tsx(318,22): error TS2362: The left-hand side of an arithmetic operation must be of type 'any', 'number', 'bigint' or an enum type.
src/components/admin/infra/ServiceHealthMonitor.tsx(326,22): error TS2362: The left-hand side of an arithmetic operation must be of type 'any', 'number', 'bigint' or an enum type.
src/components/admin/infra/ServiceHealthMonitor.tsx(335,22): error TS2362: The left-hand side of an arithmetic operation must be of type 'any', 'number', 'bigint' or an enum type.
src/components/admin/RealTimeMetricsPanel.tsx(178,26): error TS2769: No overload matches this call.
  Overload 1 of 4, '(value: string | number | Date): Date', gave the following error.
    Argument of type 'ReactNode' is not assignable to parameter of type 'string | number | Date'.
      Type 'bigint' is not assignable to type 'string | number | Date'.
  Overload 2 of 4, '(value: string | number): Date', gave the following error.
    Argument of type 'ReactNode' is not assignable to parameter of type 'string | number'.
      Type 'bigint' is not assignable to type 'string | number'.
src/components/admin/ScreencastViewer.tsx(3,10): error TS2305: Module '"../../utils/api"' has no exported member 'getWsBaseUrl'.
src/components/admin/security/SecurityDashboard.tsx(3,79): error TS6133: 'Activity' is declared but its value is never read.
src/components/admin/security/SecurityDashboard.tsx(174,86): error TS2367: This comparison appears to be unintentional because the types '"info" | "medium" | "high" | "low"' and '"warning"' have no overlap.
src/components/admin/shared/AdminSubTabContent.tsx(130,31): error TS2367: This comparison appears to be unintentional because the types 'AdminSubTab' and '"dashboard"' have no overlap.
src/components/admin/shared/AdminSubTabContent.tsx(196,77): error TS2339: Property 'sender' does not exist on type 'UnifiedChatMessage'.
src/components/admin/shared/AdminSubTabContent.tsx(198,17): error TS2339: Property 'sender' does not exist on type 'UnifiedChatMessage'.
src/components/admin/shared/AdminSubTabContent.tsx(202,18): error TS2339: Property 'text' does not exist on type 'UnifiedChatMessage'.
src/components/artifacts/ArtifactsPanel.tsx(10,3): error TS6133: 'Check' is declared but its value is never read.
src/components/auth/ServiceHealthBar.tsx(136,22): error TS2448: Block-scoped variable 'isError' used before its declaration.
src/components/chat/ChatInterface.tsx(14,1): error TS6133: 'ThinkingPanel' is declared but its value is never read.
src/components/chat/ChatInterface.tsx(15,1): error TS6133: 'ArtifactsPanel' is declared but its value is never read.
src/components/chat/ChatInterface.tsx(26,5): error TS6133: 'shareDialogOpen' is declared but its value is never read.
src/components/chat/ChatInterface.tsx(26,22): error TS6133: 'shareConversationId' is declared but its value is never read.
src/components/chat/ChatInterface.tsx(26,43): error TS6133: 'closeShareDialog' is declared but its value is never read.
src/components/chat/ChatInterface.tsx(27,5): error TS6133: 'showReasoning' is declared but its value is never read.
src/components/chat/ChatInterface.tsx(27,20): error TS6133: 'reasoningSteps' is declared but its value is never read.
src/components/chat/ChatInterface.tsx(27,36): error TS6133: 'isThinking' is declared but its value is never read.
src/components/chat/ChatInterface.tsx(28,5): error TS6133: 'artifactsPanelOpen' is declared but its value is never read.
src/components/chat/ChatInterface.tsx(28,25): error TS6133: 'activeArtifactId' is declared but its value is never read.
src/components/chat/ChatInterface.tsx(28,43): error TS6133: 'artifacts' is declared but its value is never read.
src/components/chat/ChatInterface.tsx(28,54): error TS6133: 'selectArtifact' is declared but its value is never read.
src/components/chat/ChatInterface.tsx(28,70): error TS6133: 'setArtifactsPanelOpen' is declared but its value is never read.
src/components/chat/ChatInterface.tsx(29,5): error TS6133: 'slashMenuOpen' is declared but its value is never read.
src/components/chat/ChatInterface.tsx(29,36): error TS6133: 'slashFilter' is declared but its value is never read.
src/components/chat/ChatInterface.tsx(29,49): error TS6133: 'slashPosition' is declared but its value is never read.
src/components/chat/ChatInterface.tsx(36,10): error TS6133: 'audioQueue' is declared but its value is never read.
src/components/chat/ChatInterface.tsx(106,19): error TS2345: Argument of type '"chat:message_sent"' is not assignable to parameter of type 'EventType'.
src/components/chat/ChatInterface.tsx(132,23): error TS2345: Argument of type '"tts:generated"' is not assignable to parameter of type 'EventType'.
src/components/chat/ChatInterface.tsx(173,27): error TS2345: Argument of type '"voice:toggled"' is not assignable to parameter of type 'EventType'.
src/components/chat/ChatInterface.tsx(222,13): error TS2322: Type '{ conversationId: string; onUploadComplete: (attachment: any) => void; }' is not assignable to type 'IntrinsicAttributes & ImageUploadButtonProps'.
  Property 'conversationId' does not exist on type 'IntrinsicAttributes & ImageUploadButtonProps'.
src/components/chat/ChatInterface.tsx(246,8): error TS2739: Type '{}' is missing the following properties from type 'ShareDialogProps': conversationId, isOpen, onClose
src/components/chat/ChatInterface.tsx(247,8): error TS2739: Type '{}' is missing the following properties from type 'ChatSearchDialogProps': isOpen, onClose
src/components/chat/ChatInterface.tsx(248,8): error TS2739: Type '{ onSelect: (cmd: string) => void; }' is missing the following properties from type 'SlashCommandMenuProps': isOpen, position, onClose
src/components/chat/ChatInterface.tsx(250,66): error TS2339: Property 'trigger' does not exist on type 'string'.
src/components/commands/SlashCommandMenu.tsx(1,31): error TS6133: 'useCallback' is declared but its value is never read.
src/components/customer/BrowserPreview.tsx(7,50): error TS6133: 'Maximize' is declared but its value is never read.
src/components/customer/BrowserPreview.tsx(61,21): error TS6133: 'setReloadKey' is declared but its value is never read.
src/components/customer/BrowserPreview.tsx(105,25): error TS2304: Cannot find name 'handleSubmit'.
src/components/customer/BrowserPreview.tsx(107,14): error TS2304: Cannot find name 'ExternalLink'.
src/components/customer/BrowserPreview.tsx(159,10): error TS6133: 'Globe' is declared but its value is never read.
src/components/customer/BrowserPreview.tsx(159,16): error TS6133: 'props' is declared but its value is never read.
src/components/customer/BrowserPreview.tsx(160,10): error TS6133: 'ArrowRight' is declared but its value is never read.
src/components/customer/BrowserPreview.tsx(160,21): error TS6133: 'props' is declared but its value is never read.
src/components/customer/BrowserPreview.tsx(161,20): error TS6133: 'props' is declared but its value is never read.
src/components/customer/BrowserPreview.tsx(162,10): error TS6133: 'Loader2' is declared but its value is never read.
src/components/customer/BrowserPreview.tsx(162,18): error TS6133: 'props' is declared but its value is never read.
src/components/customer/BrowserPreview.tsx(163,10): error TS6133: 'Wifi' is declared but its value is never read.
src/components/customer/BrowserPreview.tsx(163,15): error TS6133: 'props' is declared but its value is never read.
src/components/customer/ChatPanel.test.tsx(7,48): error TS2322: Type 'string' is not assignable to type 'number'.
src/components/customer/ChatPanel.test.tsx(8,46): error TS2322: Type 'string' is not assignable to type 'number'.
src/components/customer/ChatPanel.tsx(37,30): error TS2339: Property 'sender' does not exist on type 'UnifiedChatMessage'.
src/components/customer/ChatPanel.tsx(41,27): error TS2339: Property 'text' does not exist on type 'UnifiedChatMessage'.
src/components/customer/ChatPanel.tsx(43,17): error TS2322: Type 'number' is not assignable to type 'string'.
src/components/customer/ChatPanel.tsx(44,29): error TS2339: Property 'action' does not exist on type 'UnifiedChatMessage'.
src/components/customer/ChatPanel.tsx(50,49): error TS2339: Property 'text' does not exist on type 'UnifiedChatMessage'.
src/components/customer/UserDashboard.test.tsx(42,21): error TS2345: Argument of type '{}' is not assignable to parameter of type '{ username: string; }'.
  Property 'username' is missing in type '{}' but required in type '{ username: string; }'.
src/components/customer/UserDashboard.tsx(3,15): error TS6133: 'Play' is declared but its value is never read.
src/components/customer/UserDashboard.tsx(18,34): error TS2339: Property 'username' does not exist on type 'UserProfile'.
src/components/customer/UserDashboard.tsx(18,55): error TS2339: Property 'username' does not exist on type 'UserProfile'.
src/components/dashboard/HumanInTheLoopProtocol.tsx(2,8): error TS2613: Module '"F:/supremeai/frontend/src/store/useSupremeStore"' has no default export. Did you mean to use 'import { useSupremeStore } from "F:/supremeai/frontend/src/store/useSupremeStore"' instead?
src/components/dashboard/LivingDashboardShell.tsx(8,14): error TS2304: Cannot find name 'ReactNode'.
src/components/dashboard/LivingDashboardShell.tsx(12,7): error TS6133: 'UNSUPPORTED_PLATFORMS' is declared but its value is never read.
src/components/dashboard/LivingDashboardShell.tsx(14,7): error TS6133: 'SIDEBAR_SPRING' is declared but its value is never read.
src/components/dashboard/SessionsPage.tsx(48,9): error TS2739: Type '{ role: "user"; content: string; }' is missing the following properties from type 'UnifiedChatMessage': id, timestamp
src/components/ErrorBoundary.tsx(12,28): error TS1484: 'ErrorInfo' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.
src/components/ErrorBoundary.tsx(12,39): error TS1484: 'ReactNode' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.
src/components/export/ExportMenu.tsx(86,13): error TS6133: 'response' is declared but its value is never read.
src/components/research/DeepResearchPanel.tsx(78,10): error TS6133: 'getStepLineClass' is declared but its value is never read.
src/components/ui/Button.test.tsx(4,1): error TS6133: 'React' is declared but its value is never read.
src/components/ui/Card.test.tsx(4,1): error TS6133: 'React' is declared but its value is never read.
src/components/ui/Input.test.tsx(4,1): error TS6133: 'React' is declared but its value is never read.
src/contexts/ThemeProvider.tsx(3,1): error TS6133: 'getApiBaseUrl' is declared but its value is never read.
src/contexts/ThemeProvider.tsx(47,28): error TS2339: Property 'subscribe' does not exist on type 'ComponentEventBus'.
src/contexts/ThemeProvider.tsx(79,19): error TS2345: Argument of type '"theme:changed"' is not assignable to parameter of type 'EventType'.
src/hooks/useChat.ts(49,7): error TS2322: Type 'string' is not assignable to type 'number'.
src/hooks/useChat.ts(96,15): error TS2322: Type 'string' is not assignable to type 'number'.
src/hooks/useChat.ts(116,11): error TS2322: Type 'string' is not assignable to type 'number'.
src/hooks/useChat.ts(151,11): error TS2322: Type 'string' is not assignable to type 'number'.
src/hooks/useEventBus.test.ts(13,54): error TS2556: A spread argument must either have a tuple type or be passed to a rest parameter.
src/hooks/useEventBus.test.ts(14,68): error TS2556: A spread argument must either have a tuple type or be passed to a rest parameter.
src/hooks/useEventBus.test.ts(30,49): error TS2493: Tuple type '[]' of length '0' has no element at index '1'.
src/hooks/useEventBus.test.ts(41,27): error TS2345: Argument of type '"E"' is not assignable to parameter of type 'EventType'.
src/hooks/useEventBus.test.ts(50,39): error TS2345: Argument of type '"E"' is not assignable to parameter of type 'EventType'.
src/hooks/useEventBus.ts(11,30): error TS2339: Property 'subscribe' does not exist on type 'ComponentEventBus'.
src/hooks/useEventBus.ts(32,34): error TS2339: Property 'subscribe' does not exist on type 'ComponentEventBus'.
src/hooks/useEventBus.ts(41,65): error TS2339: Property 'subscribe' does not exist on type 'ComponentEventBus'.
src/hooks/useEventBus.ts(41,89): error TS2339: Property 'subscribe' does not exist on type 'ComponentEventBus'.
src/hooks/useEventBus.ts(51,19): error TS2345: Argument of type 'string' is not assignable to parameter of type 'EventType'.
src/hooks/useEventBus.ts(68,16): error TS2339: Property 'subscribe' does not exist on type 'ComponentEventBus'.
src/hooks/useIframeConsole.ts(47,23): error TS2345: Argument of type '"iframe:console_error"' is not assignable to parameter of type 'EventType'.
src/lib/cache.manager.ts(17,23): error TS2307: Cannot find module '@upstash/redis' or its corresponding type declarations.
src/lib/cache.manager.ts(18,1): error TS6133: 'cache' is declared but its value is never read.
src/lib/cache.manager.ts(21,16): error TS6133: 'compress' is declared but its value is never read.
src/lib/cache.manager.ts(80,29): error TS2345: Argument of type 'string' is not assignable to parameter of type 'AllowSharedBufferSource'.
src/lib/cache.manager.ts(80,44): error TS2345: Argument of type 'Uint8Array<ArrayBufferLike>[]' is not assignable to parameter of type 'BlobPart[]'.
  Type 'Uint8Array<ArrayBufferLike>' is not assignable to type 'BlobPart'.
    Type 'Uint8Array<ArrayBufferLike>' is not assignable to type 'ArrayBufferView<ArrayBuffer>'.
      Types of property 'buffer' are incompatible.
        Type 'ArrayBufferLike' is not assignable to type 'ArrayBuffer'.
          Type 'SharedArrayBuffer' is not assignable to type 'ArrayBuffer'.
            Types of property '[Symbol.toStringTag]' are incompatible.
              Type '"SharedArrayBuffer"' is not assignable to type '"ArrayBuffer"'.
src/lib/cache.manager.ts(171,30): error TS2349: This expression is not callable.
  Type 'Boolean' has no call signatures.
src/lib/cache.manager.ts(229,14): error TS6198: All destructured elements are unused.
src/lib/componentEventBus.ts(109,70): error TS1213: Identifier expected. 'let' is a reserved word in strict mode. Class definitions are automatically in strict mode.
src/lib/componentEventBus.ts(109,70): error TS2304: Cannot find name 'let'.
src/lib/llm.router.ts(16,17): error TS2307: Cannot find module 'z-ai-web-dev-sdk' or its corresponding type declarations.
src/lib/supabase.client.ts(11,30): error TS2307: Cannot find module '@supabase/supabase-js' or its corresponding type declarations.
src/lib/supabase.client.ts(12,37): error TS2307: Cannot find module '@supabase/supabase-js' or its corresponding type declarations.
src/pages/admin/AdminShell.tsx(6,28): error TS6196: 'Skill' is declared but never used.
src/pages/admin/AdminShell.tsx(6,35): error TS6196: 'Checkpoint' is declared but never used.
src/pages/admin/AdminShell.tsx(6,60): error TS6196: 'HealthMap' is declared but never used.
src/pages/PromptTemplatePage.tsx(2,20): error TS6133: 'ChevronRight' is declared but its value is never read.
src/pages/SharedConversationPage.tsx(7,3): error TS6133: 'MessageSquare' is declared but its value is never read.
src/pages/SharedConversationPage.tsx(11,3): error TS6133: 'Loader2' is declared but its value is never read.
src/pages/SharedConversationPage.tsx(16,1): error TS6133: 'UnifiedChatMessage' is declared but its value is never read.
src/pages/user/AIStudio.tsx(5,15): error TS2305: Module '"../../components/customer/UserDashboard"' has no exported member 'ChatMessage'.
src/pages/user/CostDashboard.tsx(3,10): error TS6133: 'getApiBaseUrl' is declared but its value is never read.
src/pages/user/CostDashboard.tsx(74,27): error TS2345: Argument of type '"cost:threshold_reached"' is not assignable to parameter of type 'EventType'.
src/pages/user/EvolutionForge/EvolutionForge.tsx(114,17): error TS2345: Argument of type '"evolution:skill_auto_created"' is not assignable to parameter of type 'EventType'.
src/pages/user/EvolutionForge/EvolutionForge.tsx(116,20): error TS2345: Argument of type '"evolution:skill_auto_created"' is not assignable to parameter of type 'EventType'.
src/pages/user/EvolutionForge/EvolutionForge.tsx(202,23): error TS2345: Argument of type '"evolution:skill_auto_created"' is not assignable to parameter of type 'EventType'.
src/pages/user/EvolutionForge/EvolutionForge.tsx(264,21): error TS2345: Argument of type '"evolution:skill_approval_needed"' is not assignable to parameter of type 'EventType'.
src/pages/user/EvolutionForge/EvolutionForge.tsx(271,44): error TS2749: 'Events' refers to a value, but is being used as a type here. Did you mean 'typeof Events'?
src/services/aiActions.test.ts(52,11): error TS6133: 'onLoading' is declared but its value is never read.
src/services/aiActions.test.ts(54,53): error TS2345: Argument of type '() => void' is not assignable to parameter of type '(ctx: FileContext) => Promise<void>'.
  Type 'void' is not assignable to type 'Promise<void>'.
src/services/queryClient.test.ts(46,5): error TS2578: Unused '@ts-expect-error' directive.
src/services/queryClient.ts(48,22): error TS6133: 'category' is declared but its value is never read.
src/services/realtime/WebSocketManager.ts(1,32): error TS1484: 'BaseWebSocketManagerOptions' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.
src/services/skillsService.test.ts(67,33): error TS2554: Expected 2 arguments, but got 3.
src/services/skillsService.ts(36,19): error TS2345: Argument of type '"metrics:update_available"' is not assignable to parameter of type 'EventType'.
src/services/skillsService.ts(41,21): error TS2339: Property 'data' does not exist on type 'CatalogResponse'.
src/services/skillsService.ts(45,21): error TS2345: Argument of type '"security:rate_limit_hit"' is not assignable to parameter of type 'EventType'.
src/services/skillsService.ts(47,27): error TS2339: Property 'headers' does not exist on type 'ApiError'.
src/services/skillsService.ts(108,17): error TS2345: Argument of type '"evolution:skill_auto_created"' is not assignable to parameter of type 'EventType'.
src/services/skillsService.ts(114,19): error TS2339: Property 'data' does not exist on type 'InstallResult'.
src/store/adminStore.ts(90,48): error TS6133: 'totpSetupRequired' is declared but its value is never read.
src/store/adminStore.ts(98,13): error TS6133: 'API_BASE' is declared but its value is never read.
src/store/adminStore.ts(166,25): error TS2345: Argument of type '"auth:login"' is not assignable to parameter of type 'EventType'.
src/store/adminStore.ts(196,21): error TS2345: Argument of type '"auth:logout"' is not assignable to parameter of type 'EventType'.
src/store/adminStore.ts(216,13): error TS6133: 'API_BASE' is declared but its value is never read.
src/store/chatStore.ts(2,10): error TS1484: 'UnifiedChatMessage' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.
src/store/chatStore.ts(2,30): error TS1484: 'ChatConversation' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.
src/store/chatStore.ts(38,33): error TS2339: Property 'data' does not exist on type 'ChatConversation[]'.
src/store/chatStore.ts(41,21): error TS2345: Argument of type '"metrics:update_available"' is not assignable to parameter of type 'EventType'.
src/store/chatStore.ts(43,25): error TS2339: Property 'data' does not exist on type 'ChatConversation[]'.
src/store/chatStore.ts(81,23): error TS2345: Argument of type '"chat:message_sent"' is not assignable to parameter of type 'EventType'.
src/store/chatStore.ts(83,23): error TS2345: Argument of type '"chat:message_received"' is not assignable to parameter of type 'EventType'.
src/store/index.ts(22,3): error TS2578: Unused '@ts-expect-error' directive.
src/store/slices/apiSlice.ts(1,32): error TS6133: 'set' is declared but its value is never read.
src/store/slices/uiSlice.ts(1,31): error TS6133: 'set' is declared but its value is never read.
src/store/slices/userSlice.ts(1,33): error TS6133: 'set' is declared but its value is never read.
src/store/slices/workspaceSlice.ts(1,38): error TS6133: 'set' is declared but its value is never read.
src/store/themeStore.ts(40,23): error TS2345: Argument of type '"theme:changed"' is not assignable to parameter of type 'EventType'.
src/store/themeStore.ts(48,25): error TS2345: Argument of type '"theme:dark_mode"' is not assignable to parameter of type 'EventType'.
src/store/themeStore.ts(50,25): error TS2345: Argument of type '"theme:light_mode"' is not assignable to parameter of type 'EventType'.
src/store/themeStore.ts(57,34): error TS2339: Property 'data' does not exist on type 'unknown'.
src/store/useSupremeStore.ts(8,22): error TS2554: Expected 1 arguments, but got 3.
src/store/useSupremeStore.ts(9,27): error TS2554: Expected 1 arguments, but got 3.
src/store/useSupremeStore.ts(10,20): error TS2554: Expected 1 arguments, but got 3.
src/store/useSupremeStore.ts(11,21): error TS2554: Expected 1 arguments, but got 3.
src/utils/deviceFingerprint.test.ts(15,21): error TS2540: Cannot assign to 'subtle' because it is a read-only property.
../packages/shared-services/src/realtime/BaseWebSocketManager.ts(32,20): error TS6133: 'event' is declared but its value is never read.
../packages/shared-services/src/realtime/BaseWebSocketManager.ts(40,21): error TS6133: 'event' is declared but its value is never read.
../packages/shared-services/src/realtime/BaseWebSocketManager.ts(48,23): error TS6133: 'event' is declared but its value is never read.
../packages/shared-services/src/realtime/BaseWebSocketManager.ts(50,21): error TS6133: 'event' is declared but its value is never read.
../packages/shared-services/src/services/SupremeAIService.ts(157,46): error TS6133: 'suffix' is declared but its value is never read.
../packages/shared-services/src/services/SupremeAIService.ts(157,62): error TS6133: 'fileName' is declared but its value is never read.
../packages/ui-components/src/components/ErrorBoundary.tsx(4,8): error TS6133: 'React' is declared but its value is never read.

