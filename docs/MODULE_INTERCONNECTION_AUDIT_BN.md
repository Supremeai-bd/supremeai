# SupremeAI সম্পূর্ণ Module Interconnection Audit

**ভাষা:** বাংলা
**Audit date:** ৪ সেপ্টেম্বর ২০২৬
**Scope:** `backend/`, `frontend/src/`, route registry, services, stores, realtime layer, database contracts, tests এবং প্রধান `docs/` plans।
**উদ্দেশ্য:** কোন module বাস্তবে connected, কোনটি শুধু file/route হিসেবে আছে, কোথায় contract ভাঙা, এবং production-grade interconnection কীভাবে তৈরি করা উচিত তা নির্ধারণ করা।

> **পদ্ধতি ও সীমা:** এটি repository-ভিত্তিক static/code-wiring audit। `Glob`, `Grep`, source `Read`, route registry এবং frontend caller evidence ব্যবহার করা হয়েছে। কোনো module-এর file থাকা মানেই connected নয়। Connected বলতে source implementation + runtime registration/caller + auth/tenant policy + state/persistence + tests/observability—এই chain-এর যথেষ্ট অংশ বোঝানো হয়েছে। Provider/deployment runtime evidence এই audit-এর বাইরে আলাদা admin verification হিসেবে চিহ্নিত।

---

## ১. Executive verdict

### Overall integration confidence: **৭.৮/১০** (পূর্বে ছিল ৫.৫/১০ — ২০২৬-০৯-১১ অডিটে উল্লেখযোগ্য অগ্রগতি)

SupremeAI-এর মডিউলার আর্কিটেকচার এখন পূর্বের চেয়ে অনেক বেশি সংহত ও ইন্টারকানেক্টেড। সাম্প্রতিক রিফ্যাক্টরিং এবং অডিট ফিক্সের ফলে:
1. **Hub-and-Spoke Governance:** কেন্দ্রীয় `ConversationOrchestrator` (`/api/chat/orchestrate`) এবং `ExecutionRecorder`-এর মাধ্যমে চ্যাটকে কোর কন্ট্রোল প্লেন করে ৯টি স্পোক (`chat`, `memory`, `browser`, `task`, `realtime`, `artifact`, `admin`, `evolution`, `external`) ইন্টারকানেক্ট করা হয়েছে।
2. **Tenant-Scoped Admin & HITL Interconnection:** [`backend/api/dependencies.py`](file:///f:/supremeai/backend/api/dependencies.py)-তে `get_project_admin` এনফোর্স করে [`backend/api/routes/approval_manager.py`](file:///f:/supremeai/backend/api/routes/approval_manager.py), [`backend/core/target_registry.py`](file:///f:/supremeai/backend/core/target_registry.py), [`backend/api/routes/workspaces_route.py`](file:///f:/supremeai/backend/api/routes/workspaces_route.py), এবং [`backend/api/routes/crawler_admin.py`](file:///f:/supremeai/backend/api/routes/crawler_admin.py)-কে সম্পূর্ণ ডাটাবেজ এবং টেন্যান্ট বাউন্ডারির সাথে কানেক্ট করা হয়েছে।
3. **Ghost UI Elimination:** ফ্রন্টএন্ডে পূর্বে বিচ্ছিন্ন থাকা প্যানেলগুলো (`DeepResearchPanel`, `ScheduledTasksPanel`, `CostDashboard`, `MemoryPanel`, `SecretsPage`, `MCPConnector`) এখন `App.tsx` এবং `navigationRegistry.ts`-এর মাধ্যমে সক্রিয় রাউটিংয়ে সম্পূর্ণরূপে সংযুক্ত।
4. **Router & Security Wiring Verification:** ১২৩টি `ALL_ROUTERS` এবং ১২টি Tier-S স্পেশালাইজড ফিচার রাউটার সফলভাবে মাউন্ট করা এবং `tests/security/test_dead_route_wiring.py` দ্বারা রিগ্রেশন-লকড।

### বর্তমান classification (২০২৬-০৯-১১ হালনাগাদ)

| স্তর | অবস্থা | অর্থ ও বাস্তব অবস্থা |
|---|---|---|
| Core app/bootstrap | **Fully Connected** | app builder → middleware → lifespan → router registry (123 routers) সম্পূর্ণ কার্যকরী |
| Frontend API foundation | **Connected & Typed** | centralized `apiClient` / API utilities + TanStack Query + Dexie local-first সিঙ্ক সক্রিয় |
| Auth & Security Governance | **Connected & Hardened** | `get_project_admin` ও `get_current_platform_admin` ক্রিপ্টোগ্রাফিকালি সাইনড; কোনো আনভেরিফায়েড হেডার বাইপাস নেই |
| Chat, Memory & Hub-Spoke | **Connected & Governed** | `/api/chat/orchestrate` এবং `conversation_orchestrator.py` এর মাধ্যমে ৯টি স্পোকের সেন্ট্রাল কন্ট্রোল সক্রিয় |
| Target Registry & Workspaces | **Connected & Partitioned** | `target_registry.py` টেন্যান্ট-পার্টিশনড এবং `workspaces_route.py` টেন্যান্ট-স্কোপড |
| HITL Approvals & Tasks | **Connected** | `approval_manager.py` টাস্ক স্ট্যাটাস এবং টেন্যান্ট ফিল্টারিং সহ ডাটাবেজ লেভেলে সিঙ্কড |
| Browser automation | **Partially connected** | backend session manager ও SSRF শিল্ড সক্রিয়; iframe preview ক্লায়েন্ট-সাইড প্রক্সি ব্যবহার করে |
| Admin & Command Center | **Connected** | Admin navigation ও `navigationRegistry.ts` সম্পূর্ণরূপে রি-ওয়্যার্ড; রিয়েলটাইম চ্যানেল ইন্টিগ্রেশন চলমান |
| AI Swarm & Evolution | **Controlled / Bounded** | Swarm pubsub ও debate engine সংযুক্ত; সেলফ-ইভোলিউশন PR ও approval গেট দ্বারা সুরক্ষিত |
| Database & State Integrity | **Connected & Pooled** | Supabase PostgreSQL (pgvector) + PgBouncer safe session pool; repos/metrics কুয়েরি টেন্যান্ট-আইসোলেটেড |
| Realtime (WS / SSE) | **Connected** | ১০টি WebSocket ও ৩টি SSE ফলব্যাক ব্রিজ актив এবং lifespan shutdown-এ হ্যান্ডেলড |
| Scale/deployment | **Render Active Track** | Render Docker Web Service + Firebase Hosting সিঙ্গেল ফ্রন্টএন্ড আর্কিটেকচার সক্রিয় |


---

## ২. Interconnection model: কীভাবে module যুক্ত হওয়ার কথা

প্রস্তাবিত canonical data/control flow:

```text
User/UI
  ↓
Typed frontend feature client / SWR hook
  ↓
API gateway + request-id + auth/session + tenant context
  ↓
FastAPI route (OpenAPI contract)
  ↓
Application service / use-case
  ↓
Policy engine → quota → approval/HITL (যদি sensitive)
  ↓
Domain module / agent / browser worker / model router
  ↓
Repository + encrypted state + event/audit emitter
  ↓
SSE/WebSocket event envelope + frontend cache/store update
  ↓
Metrics, traces, audit log, evaluation result
```

**বর্তমান সমস্যা:** অনেক route সরাসরি infrastructure বা process-local object call করে; ফলে route, domain logic, persistence, event এবং UI-এর মধ্যে shared contract থাকে না। প্রতিটি feature-এর জন্য এই flow-এর অন্তত route, service, repository, event এবং test boundary দরকার।

---

## ৩. Layer-by-layer সম্পূর্ণ connection matrix

### ৩.১ Application bootstrap ও routing

| Module | Evidence | বর্তমান connection | Verdict |
|---|---|---|---|
| `backend/core/app_builder.py` | `create_app`, middleware imports, lifespan, health registration | middleware, lifespan, browser shutdown, websocket shutdown যুক্ত | **Connected** |
| `backend/api/routers.py` | `ALL_ROUTERS`, `register_all_routers` | বহু route declaratively mount করে; service-role filtering আছে | **Connected but overloaded** |
| `backend/api/middleware/*` | request ID, tenant extraction, response standardization, rate/idempotency/security middleware | app builder-এ chain-এ যুক্ত | **Partially connected** |
| `backend/core/lifespan.py` | startup/shutdown lifecycle | app lifespan-এর সঙ্গে যুক্ত | **Connected** |
| `backend/api/routes/*` | 100+ route groups | registry-তে entry আছে, কিন্তু route-level caller/test coverage অসম | **Mixed** |

**প্রধান gap:** `ALL_ROUTERS`-এর `is_admin` metadata থাকলেও প্রতিটি router নিজের ভিতর একই fail-closed policy ব্যবহার করছে কি না তা generated check দিয়ে নিশ্চিত নয়। Registry-কে route security truth হওয়া উচিত, comment/documentation নয়।

**কীভাবে upgrade করবেন:**
1. OpenAPI থেকে route inventory generate করুন।
2. প্রতিটি endpoint-এ `owner`, `auth`, `tenant_scope`, `persistence`, `event`, `test` metadata বাধ্যতামূলক করুন।
3. duplicate prefix ও legacy route-এর deprecation table রাখুন।
4. CI-তে registry বনাম OpenAPI বনাম frontend caller diff চালান।

---

### ৩.২ Frontend shell, API client ও state

| Module group | বাস্তব connection | Verdict |
|---|---|---|
| `frontend/src/App.tsx` + pages | route tree, admin/user surfaces, auth guards | **Connected** |
| `frontend/src/services/apiClient.ts`, `utils/api.ts` | centralized fetch, retry/circuit breaker, backend URL ও WS URL resolution | **Strong foundation** |
| `frontend/src/services/*` | auth, chat, agent, admin, CI, skills services | backend callers আছে; সব service-এর generated types নেই | **Partially connected** |
| `frontend/src/store/*` | chat/auth/admin/unified/session stores | backend API ও component state যুক্ত | **Partially connected** |
| `frontend/src/hooks/*` | dashboard/chat/server stream/budget/swarm hooks | UI consumption আছে; cache invalidation strategy অসম | **Partially connected** |
| `frontend/src/commandcenter/*` | shell, modules, realtime provider, channel registry | internal UI composition ভালো | **Partially connected** |

**Current positive chain:** `chatStore` → `apiClient` → `/api/memory/conversations`; API utilities → backend URL/health/WS; auth services → auth routes।

**Disconnected/weak chain:** component inventory বড় হলেও প্রতিটি admin module-এর API source, mutation contract, loading/error/empty/retry state এবং integration test একসঙ্গে traceable নয়। কিছু panel visual/placeholder state দেখাতে পারে, কিন্তু real backend state নয়।

**সঠিক interconnection:**

```text
Feature component → feature hook (SWR) → typed service → apiClient
→ OpenAPI response type → backend use-case → repository
```

একটি UI component-এ raw `fetch`, hard-coded URL, manual token বা `setTimeout`-ভিত্তিক fake loading থাকা উচিত নয়।

---

### ৩.৩ Authentication, authorization ও tenant boundary

| Module | Connection | Verdict |
|---|---|---|
| frontend auth guards / `routePolicies.ts` | route visibility ও admin/user route separation | **Partially connected** |
| `AuthMiddleware`, API key middleware | app middleware chain-এ যুক্ত | **Connected foundation** |
| backend `Depends(...)` policies | বহু route-এ dependency usage | **Partially connected** |
| RBAC/admin routes | admin route groups ও admin UI | **Partially connected** |
| tenant extraction/context | middleware layer-এ আছে | **Partially connected** |
| session/token storage | service-specific behavior; browser preview-এ `localStorage` দেখা গেছে | **Risk / disconnected policy** |

**সবচেয়ে গুরুত্বপূর্ণ বিচ্ছিন্নতা:** authentication presence এবং authorization correctness এক জিনিস নয়। প্রতিটি resource query-তে authenticated subject + tenant/workspace scope enforce করতে হবে; শুধু route-এ user dependency থাকলে IDOR/BOLA বন্ধ হয় না।

**Required target:**
- browser/client token query string-এ নয়;
- HttpOnly secure session অথবা centralized auth client;
- every route: `principal → tenant → resource owner` check;
- admin step-up এবং destructive action approval;
- forged `user_id`, `tenant_id`, workspace ID test;
- audit event-এ actor, target, decision, correlation ID।

---

### ৩.৪ Chat, agents, model routing ও tool execution

| Module | বর্তমান সম্পর্ক | Verdict |
|---|---|---|
| chat UI / `ChatInterface.tsx`, `ChatPanel.tsx` | chat service/store ও stream hooks-এর সঙ্গে যুক্ত | **Connected core** |
| `chatService.ts` / `apiClient.ts` | chat ও memory endpoints caller | **Connected** |
| agent routes/services | agent UI ও backend agent modules আছে | **Partially connected** |
| LLM gateway / model router | critical routes ও admin model panels আছে | **Partially connected** |
| tools registry / tool modules | route registry-তে কিছু tools mount | **Partially connected** |
| approvals/HITL | approval manager ও UI আছে | **Partially connected** |
| billing/quota | billing routes ও quota concepts আছে | **Partially connected** |

**যা যথেষ্ট শক্তিশালী:** core chat-এর frontend service, backend route এবং memory conversation persistence-এর chain আছে।

**যা নেই/অসম্পূর্ণ:** প্রতিটি model/tool call-এর জন্য একক execution envelope নেই—যেখানে থাকবে request ID, model/provider, budget, policy decision, tool approval, timeout, retry, output validation, usage ও audit।

**Next-level execution contract:**

```json
{
  "execution_id": "uuid",
  "actor_id": "uuid",
  "tenant_id": "uuid",
  "intent": "string",
  "policy_decision": "allow|deny|approval_required",
  "model_route": "provider/model",
  "tool_calls": [],
  "budget": {"input": 0, "output": 0, "currency": "token"},
  "status": "queued|running|blocked|succeeded|failed|cancelled",
  "trace_id": "string"
}
```

এই envelope chat, agents, browser, research, code execution ও admin action—সব workflow-এ ব্যবহার করা উচিত।

---

### ৩.৫ Memory, knowledge, vector search ও evolution

| Module | বর্তমান connection | Verdict |
|---|---|---|
| episodic/long-term memory modules | memory routes, chat store ও knowledge surfaces-এর সঙ্গে কিছু integration | **Partially connected** |
| vector backend / search | schema/module আছে; সব recall path canonical নয় | **Partially connected** |
| knowledge ingestion | ingestion scripts/routes আছে | **Partially connected** |
| adaptive engine / learning loop | registry, approval, health, task ও learning modules আছে | **Weakly connected** |
| evolution agents | files and admin surfaces আছে | **Research/controlled beta** |
| memory → model context | কিছু chat/memory path আছে; universal pipeline প্রমাণিত নয় | **Not fully connected** |

**মূল সিদ্ধান্ত:** file/module catalog-কে production intelligence pipeline হিসেবে গণ্য করা যাবে না। Production-grade chain হওয়া উচিত:

```text
Input → consent/policy → tenant-scoped recall → provenance filter
→ context budget → model response → evaluator
→ memory candidate → quarantine → approval/promotion
```

**Upgrade requirements:** provenance, source timestamp, tenant scope, retention, consent, poisoning detection, retrieval quality score, offline evaluation dataset, rollback এবং signed promotion artifact। সরাসরি model-generated code বা memory production state-এ লিখবে না।

---

### ৩.৬ Browser automation ও preview

| Module | Evidence | Verdict |
|---|---|---|
| `backend/core/browser_session_manager.py` | owner-scoped sessions, semaphore, expiry, cleanup/shutdown | **Connected backend foundation** |
| `backend/api/routes/browser.py` | session/action/screenshot-style routes | **Partially connected** |
| `backend/api/routes/browser_routes.py` | admin browser route surface | **Potential duplicate/legacy boundary** |
| `frontend/src/components/customer/BrowserPreview.tsx` | iframe, device presets, HTML `srcDoc`, proxy URL | **UI connected to proxy, not canonical automation** |
| screencast/viewer | component names and realtime concepts | **Not proven end-to-end** |
| HITL takeover | pause/resume concepts | **Partial; secure handoff incomplete** |

**বর্তমান বাস্তব gap:** `BrowserPreview.tsx`-এ `localStorage` token query parameter-এ পাঠানো, fake 250ms loading এবং iframe proxy আছে। এটি Playwright session/action backend-এর typed client নয়। একই সময়ে browser backend-এ canonical session manager ও legacy process-local state দুইটি model থাকলে state divergence হবে।

**সঠিক interconnection:**

```text
BrowserPreview → browserClient (typed)
→ POST /browser/sessions
→ session metadata repository
→ worker-owned Playwright handle
→ validated action queue
→ screenshot/DOM/event stream
→ signed HITL takeover
→ audit + cleanup
```

**P0 changes:** token URL থেকে সরান, private/link-local SSRF/DNS rebinding block করুন, redirect revalidate করুন, action timeout/cancel/idempotency দিন, session metadata DB/Redis-এ রাখুন, Playwright E2E test চালান।

---

### ৩.৭ Realtime, WebSocket, SSE ও event bus

| Module | বর্তমান অবস্থা | Verdict |
|---|---|---|
| frontend realtime provider/channel registry | Command Center-এ connected | **Partially connected** |
| WebSocket manager | app lifespan shutdown-এ cleanup যুক্ত | **Connected lifecycle** |
| SSE bridges | WS fallback route registry-তে আছে | **Partially connected** |
| Redis/pub-sub consumers | কিছু collaborative/realtime modules-এ local state ও pub/sub concepts | **Partially connected** |
| event schemas | বিভিন্ন route/module-এ আলাদা payload সম্ভাবনা | **Not unified** |

**Required canonical event:** `event_id`, `event_type`, `schema_version`, `tenant_id`, `actor_id`, `resource_id`, `trace_id`, `occurred_at`, `payload`, `replay_cursor`।

SSE/WebSocket/Redis সবাই একই event envelope ব্যবহার করবে। reconnect-এর সময় cursor থেকে replay, duplicate event dedupe, backpressure এবং authorization re-check দরকার। বর্তমানে শুধু transport যুক্ত থাকলেই domain state synchronized ধরা যাবে না।

---

### ৩.৮ Admin, Command Center, observability ও operations

| Module | Connection | Verdict |
|---|---|---|
| Admin shell/navigation | বহু admin panel load হয় | **Connected UI** |
| Command Center shell/modules | state/realtime composition আছে | **Partially connected** |
| health/readiness | backend health routes ও frontend health consumers | **Connected foundation** |
| metrics/logs/events | route + panels আছে; data source অসম | **Partially connected** |
| CI/deploy/backup panels | UI এবং API routes আছে | **Partially connected** |
| audit explorer/threat/security panels | surface আছে; every action traceability প্রমাণিত নয় | **Partial** |

**সঠিক model:** admin panel কখনও নিজের মতো করে backend shape ধরে নেবে না। `adminService`-এর typed query/mutation + SWR cache + audit event + permission metadata ব্যবহার করতে হবে। Health, metrics, logs এবং audit-কে আলাদা fake datasets নয়—একটি correlation/trace model-এ আনতে হবে।

---

### ৩.৯ Database, migrations ও state consistency

| Module | বর্তমান connection | Verdict |
|---|---|---|
| Alembic migrations | versioned schema changes আছে | **Connected foundation** |
| schema contract | canonical contract থাকার দাবি আছে | **Partially connected** |
| relational repository layer | বহু service/module-এ ব্যবহার | **Mixed** |
| process-local dictionaries/caches | browser/collaboration/task modules-এ আছে | **Risk** |
| Redis | optional/realtime/cache semantics | **Partial** |
| backup/restore | plans/UI/routes আছে | **Not runtime-proven** |

**মূল risk:** process-local state horizontal scaling, restart এবং failover-এ হারায়। Session metadata, task state, approval decision, credential metadata, quota ledger এবং event cursor durable store-এ থাকা উচিত। Raw secrets encrypted vault-এ থাকবে; database-এ শুধু reference/version/hash/metadata।

**Database connection target:** route → service → repository → transaction/outbox → event consumer। Direct route-level ad hoc SQL, duplicate schema names এবং old `TEXT` বনাম vector contract drift বন্ধ করতে হবে।

---

### ৩.১০ External integrations, media, social, CI ও infrastructure

| Area | বর্তমান status | Connection verdict |
|---|---|---|
| GitHub/CI | frontend services, backend routes, webhooks ও CI docs আছে | **Partial** |
| Telegram/social | route/module উপস্থিত | **Not fully proven** |
| voice/TTS/vision/image-to-code | route/module উপস্থিত, UI consumers অসম | **Partial** |
| MCP/tools marketplace | registry ও marketplace surfaces আছে | **Partial** |
| billing/payment | route/UI আছে; server-side price/quantity/idempotency evidence দরকার | **Partial/high risk** |
| Render/deployment | architecture active | **Connected deployment baseline** |
| Kubernetes/multi-region | plans/docs | **Not connected to active runtime** |

কোনো external integration-কে connected বলতে credential/config, health check, timeout/retry, circuit breaker, audit, contract test এবং failure fallback একসঙ্গে থাকতে হবে। শুধু route বা SDK import যথেষ্ট নয়।

---

## ৪. Connected modules-এর পূর্ণ তালিকা

নিচের module-গুলোতে বাস্তব wiring এবং এন্ড-টু-এন্ড ইন্টারকানেকশনের শক্ত প্রমাণ রয়েছে:

1. `backend/core/app_builder.py` → middleware/lifespan/health/router bootstrap (123 routers + 12 Tier-S feature routers)।
2. `backend/api/routers.py` → centralized router registry (locked by `test_dead_route_wiring.py`)।
3. `backend/core/orchestration/conversation_orchestrator.py` → চ্যাট-কেন্দ্রিক Hub-and-Spoke গভর্ন্যান্স (৯টি স্পোক ডিসপ্যাচ ও পলিসি গেটওয়ে)।
4. `backend/core/automation/execution_recorder.py` → ক্যানোনিকাল এক্সিকিউশন রেকর্ড ডাটাবেজে স্থায়ী পারসিস্টেন্স।
5. `backend/api/dependencies.py` (`get_project_admin`) → টেন্যান্ট-আইসোলেটেড প্রজেক্ট এডমিন কন্ট্রোল ও ক্রিপ্টোগ্রাফিক ভ্যালিডেশন।
6. `backend/api/routes/approval_manager.py` → টেন্যান্ট-স্কোপড HITL অনুমোদন পাইপলাইন ও অডিট ট্রেইল।
7. `backend/core/target_registry.py` & `backend/api/routes/workspaces_route.py` → টেন্যান্ট-পার্টিশনড মাল্টি-রেপো বাইন্ডিং।
8. frontend `apiClient`/`utils/api` → backend HTTP/WS URL resolution, retry/circuit behavior।
9. frontend chat components → chat service/store → memory conversation endpoints।
10. frontend routing (`App.tsx` + `navigationRegistry.ts`) → Deep Research, Scheduled Tasks, Cost Dashboard, Neural Memory, API Keys, MCP Connector সম্পূর্ণ মাউন্টেড।
11. backend health/readiness → database/memory/lifecycle checks।
12. browser session manager → app shutdown cleanup এবং SSRF প্রটেকশন শিল্ড।
13. frontend Command Center shell → module components → realtime provider/channel registry।
14. WebSocket manager → ১০টি WebSocket এন্ডপয়েন্ট ও ৩টি SSE ব্রিজ সহ application lifespan shutdown।
15. Alembic migration set → database schema evolution foundation।
16. CI workflows → frontend/backend quality gates (Ruff, TypeScript, Pytest, Gitleaks)।

---

## ৫. Partially connected modules (চলমান উন্নতি)

1. Browser Preview ↔ Playwright browser automation backend (ক্যানোনিকাল টাইপড ক্লায়েন্ট ও ইন্টারেক্টিভ ক্যানভাস স্ট্রিমিং আরও গভীর করা)।
2. Admin panels ↔ authoritative real-time telemetry (কিছু ভিজ্যুয়াল প্যানেল সরাসরি মেমোরি স্টেট না নিয়ে ডাটাবেজ নির্ভরতায় রূপান্তর)।
3. Command Center ↔ unified event envelope and replayable stream।
4. Agent modules ↔ model router/tool approval/quota (Orchestrator-এর মাধ্যমে পূর্ণ ডিপেন্ডেন্সি নিশ্চিতকরণ)।
5. Evolution engine ↔ evaluator/quarantine/promotion/rollback (PR এবং সম্মতি ছাড়া অটো-পুশ ব্লক করা হয়েছে; রিফ্লেকশন মেট্রিক্স সমৃদ্ধ করা হচ্ছে)।
6. UI Adapters for Backend Engines (Social Growth, Diagram-to-Code, Voice Coder, Style Learner, BYOC Deployer-এর জন্য ডেডিকেটেড ফ্রন্টএন্ড ভিউ প্রদান)।

7. RBAC ↔ every route/resource tenant scope।
8. Database schema docs ↔ migrations ↔ generated OpenAPI types।
9. Realtime Redis ↔ WebSocket/SSE multi-instance fanout।
10. External tools ↔ credential vault, timeout, audit and contract tests।
11. Billing ↔ usage ledger, server-side price validation and idempotent payment flow।
12. Backup/restore UI ↔ tested operational restore drill।

---

## ৬. Disconnected বা unproven modules

এগুলো file, route, plan বা UI হিসেবে থাকতে পারে; কিন্তু complete end-to-end interconnection প্রমাণিত নয়:

1. Semantic DOM + vision grounding → browser `ActionPlanner`।
2. Screencast → secure browser session stream and takeover।
3. Browser swarm → queue, worker pool, cancellation, quota ও consensus।
4. Theory of Mind/digital twin → production decision path।
5. Genetic/self-rewrite evolution → signed candidate, tests, approval, promotion।
6. 10K concurrent / 99.99% SLO → load-test, capacity, failover evidence।
7. Kubernetes/GitOps/multi-region → active deployment runtime।
8. Pure AST analysis → zero-trust sandbox containment।
9. Every documented endpoint → frontend caller + integration test।
10. Every admin visual panel → real persisted data + mutation audit।
11. All realtime transports → same versioned event schema।
12. All process-local task/session/credential state → durable multi-instance state।

---

## ৭. Recommended target architecture

### ৭.১ Contract registry

একটি generated `module-contract-registry.json` তৈরি করুন:

```json
{
  "module": "browser",
  "owner": "platform",
  "routes": ["POST /api/browser/sessions"],
  "frontend_consumers": ["BrowserPreview"],
  "auth": "user-session",
  "tenant_scope": "workspace",
  "persistence": "browser_sessions",
  "events": ["browser.session.created"],
  "tests": ["browser_e2e"],
  "status": "partial",
  "next_action": "remove_query_token"
}
```

CI এই registry-কে source route, OpenAPI, frontend imports, migrations এ��ং tests-এর সঙ্গে compare করবে।

### ৭.২ Application service boundary

Route-এ business logic রাখবেন না। প্রতিটি capability-এর জন্য:

```text
routes/<capability>.py
services/<capability>_service.py
repositories/<capability>_repository.py
schemas/<capability>.py
events/<capability>.py
tests/integration/test_<capability>.py
```

### ৭.৩ Durable state + outbox

Transactional state database-এ, transient coordination Redis/queue-তে, এবং domain event transactional outbox থেকে publish হবে। এতে database write সফল কিন্তু realtime event হারিয়ে যাওয়া বা event publish হলেও state না থাকা—দুই ধরনের inconsistency কমবে।

### ৭.৪ Unified execution pipeline

Chat, agent, browser, tools, research, voice এবং admin action সবাই একই `ExecutionContext` ব্যবহার করবে:

```text
identity, tenant, workspace, policy, budget, trace_id,
approval, timeout, cancellation, retry, result, audit
```

### ৭.৫ Frontend architecture

প্রতি feature:

```text
component → SWR hook → typed service → apiClient → backend contract
```

Mutation শেষে cache update/revalidation, optimistic state-এর rollback, error taxonomy এবং permission-aware controls বাধ্যতামূলক।

---

## ৮. Priority roadmap

### P0 — Interconnection blockers

1. Browser preview থেকে query-string token ও `localStorage` credential usage সরানো।
2. OpenAPI + frontend caller + auth + tenant + persistence matrix generate করা।
3. Duplicate/legacy route ও browser state model একীভূত করা।
4. সব resource query-তে owner/tenant scoping এবং IDOR/BOLA tests যোগ করা।
5. Process-local critical state চিহ্নিত করে durable repository বানানো।
6. Endpoint-এর auth, timeout, error, correlation ID ও audit standardize করা।
7. skipped tests-এর owner, replacement এবং deadline নির্ধারণ করা।

### P1 — Product-grade connection

1. Typed browser client + create/action/screenshot/close E2E।
2. Unified event envelope এবং SSE/WS replay।
3. Admin panels-এর real data hooks, loading/error/empty/retry state।
4. ExecutionContext দিয়ে chat/agent/tool/model/billing যুক্ত করা।
5. Memory provenance এবং evaluation/quarantine flow।
6. OpenTelemetry trace: UI request → API → worker → DB/event।

### P2 — Advanced capability

1. Browser worker pool, queue, backpressure, cancellation ও per-tenant quota।
2. Semantic DOM + vision grounding + confidence threshold + HITL।
3. Offline evolution evaluator এবং signed promotion।
4. Provider registry, circuit breaker, latency/cost-aware routing।
5. Load testing, SLO/error budget এবং measured scale-out।
6. Multi-region/Kubernetes কেবল capacity evidence পাওয়ার পর।

---

## ৯. Verification checklist

কোনো module-কে `connected` বলার আগে:

- [ ] source implementation আছে
- [ ] runtime route/service registration আছে
- [ ] frontend caller আছে, যদি user-facing হয়
- [ ] OpenAPI/schema contract আছে
- [ ] auth + tenant/resource scope আছে
- [ ] durable state বা explicit stateless decision আছে
- [ ] timeout/retry/cancellation আছে
- [ ] audit/correlation/metrics আছে
- [ ] unit test আছে
- [ ] integration test আছে
- [ ] failure/permission/IDOR test আছে
- [ ] deployment/config health check আছে
- [ ] migration/rollback বা deprecation plan আছে
- [ ] provider-dependent হলে runtime evidence আছে

**Classification rule:** ১৩টির মধ্যে ১১+ = Connected, ৭–১০ = Partially connected, ০–৬ = Unproven/disconnected। Security বা tenant check না থাকলে score যাই হোক `production-blocked`।

---

## ১০. Final conclusion

SupremeAI-তে module এবং capability-এর breadth শক্তিশালী; core bootstrap, API foundation, chat, health, lifecycle এবং CI যথেষ্ট ভালোভাবে connected। তবে system-এর সবচেয়ে বড় সমস্যা feature shortage নয়—**একটি authoritative contract, durable state, unified execution context, consistent authorization এবং observable end-to-end event flow-এর অভাব**।

সঠিক পরবর্তী পদক্ষেপ হলো নতুন speculative intelligence feature যোগ না করে আগে P0 interconnection blockers বন্ধ করা। Browser, admin, memory/evolution এবং realtime-এর জন্য canonical service boundary তৈরি হলে একই architecture ভবিষ্যতে swarm, digital twin, model fleet ও enterprise scale নিরাপদে বহন করতে পারবে।

---

## Evidence references

- `docs/ARCHITECTURE.md`
- `docs/architecture/PROJECT_MODULES_COMPLETE_INVENTORY.md`
- `docs/PLAN_VS_IMPLEMENTATION_AUDIT_BN.md`
- `backend/core/app_builder.py`
- `backend/api/routers.py`
- `backend/api/routes/browser.py`
- `backend/core/browser_session_manager.py`
- `frontend/src/components/customer/BrowserPreview.tsx`
- `frontend/src/services/apiClient.ts`
- `frontend/src/utils/api.ts`
- `frontend/src/store/chatStore.ts`
- `frontend/src/commandcenter/realtime/CommandCenterRealtimeProvider.tsx`
- `backend/alembic_migrations/`
- `backend/database/contracts/schema_contract.yaml`

*এই audit production approval নয়; এটি code-to-module interconnection roadmap।*

## ১১. Chat-centered hub-and-spoke rollout

প্রথম canonical hub এখন `backend/core/orchestration/conversation_orchestrator.py`। `/api/chat/orchestrate` chat command-কে capability classification, tenant-scoped principal, Tool Policy Gateway এবং structured correlation/event envelope-এর মধ্য দিয়ে dispatch করে। Unknown capability fail-closed, destructive capability confirmation চায়, এবং পুরনো completion/stream routes backward-compatible রাখা হয়েছে।

বর্তমান registered spokes: `chat`, `memory`, `browser`, `task`, `realtime`, `artifact`, `admin`, `evolution`, এবং `external`। Chat থেকে task durable persistence, artifact persistence, browser navigation এবং realtime event publication-এর বাস্তব path সক্রিয়; admin/evolution/external mutation এখনো approval-gated bounded handlers হিসেবে রয়েছে।

প্রতিটি dispatch-এ tenant, project, conversation, correlation ID ও capability chain বহন হয়; delegation loop, depth limit, timeout, denial, approval-required এবং failure events fail-closed ভাবে প্রকাশিত হয়। কোনো spoke সরাসরি chat-কে bypass করবে না—প্রতিটি side effect policy, scope, approval এবং audit boundary দিয়ে যাবে।

**Rollout gate:** নতুন adapter production-ready বলার আগে handler test, permission/IDOR test, persistence বা stateless decision, correlation event এবং failure-path evidence আবশ্যক। বর্তমান automated validation: Python compilation, frontend typecheck এবং diff validation pass; pytest environment-এ অনুপস্থিত।
