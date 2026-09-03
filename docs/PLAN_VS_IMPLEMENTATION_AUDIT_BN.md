# SupremeAI পরিকল্পনা বনাম বাস্তব বাস্তবায়ন অডিট

**ভাষা:** বাংলা (প্রযুক্তিগত নাম/পাথ ইংরেজিতে রাখা হয়েছে)
**তারিখ:** ৪ সেপ্টেম্বর ২০২৬
**উদ্দেশ্য:** `docs/`-এর প্রধান পরিকল্পনা, architecture, security, browser, intelligence, deployment ও production-readiness দাবিগুলো বাস্তব source code, route, test এবং configuration-এর সঙ্গে মিলিয়ে দেখা।

> **গুরুত্বপূর্ণ সীমা:** এই নথি ১,৪০০+ source file-এর line-by-line formal verification নয়। এটি repository-র canonical/master plan, implementation plan, module inventory, API/security docs এবং সংশ্লিষ্ট backend/frontend entry point-এর evidence-based audit। কোনো file বা plan-এ capability লেখা থাকলেই সেটিকে implemented ধরা হয়নি; route registration, caller, persistence, test এবং runtime wiring না থাকলে status `অসম্পূর্ণ` বা `দাবি যাচাই করা যায়নি`।

---

## ১. Executive verdict

### সামগ্রিক অবস্থা

**SupremeAI এখন একটি শক্তিশালী prototype / pre-production platform; enterprise-grade self-evolving platform হিসেবে পরিকল্পিত ক্ষমতার কাছাকাছি এখনও নয়।**

- **বর্তমান বাস্তব ভিত্তি:** মাঝারি থেকে ভালো। FastAPI backend, React/Vite Studio, বহু route group, Supabase/PostgreSQL, Redis, CI, health checks, agent ও admin surfaces আছে।
- **বাস্তব end-to-end product capability:** মাঝারি। অনেক module আছে, কিন্তু সবগুলো একে অন্যের সঙ্গে production contract, persistence, authorization, observability এবং tests দিয়ে যুক্ত নয়।
- **পরিকল্পনার তুলনায় gap:** বড়। বিশেষ করে self-evolution, 10K concurrent users/99.99% uptime, multi-region, zero-trust sandbox, browser intelligence, swarm consensus, distributed tracing এবং complete HITL দাবিগুলো source evidence দিয়ে সম্পূর্ণ প্রমাণিত নয়।
- **বর্তমান release posture:** controlled beta/staging-এর জন্য উপযুক্ত; unrestricted production/enterprise SLA-এর জন্য নয়।

### Status legend

| Status | অর্থ |
|---|---|
| **শক্তিশালী / যথেষ্ট** | বাস্তব code + wiring + test/contract evidence আছে; সীমা নথিভুক্ত। |
| **আংশিক** | মূল কাঠামো আছে, কিন্তু end-to-end wiring, persistence, security বা tests অসম্পূর্ণ। |
| **দুর্বল / পরিকল্পনা-স্তরের** | docs-এ দাবি আছে, কিন্তু বাস্তব implementation বা runtime evidence অপর্যাপ্ত। |
| **বিরোধ / drift** | plan, canonical architecture এবং code-এর মধ্যে অসামঞ্জস্য। |
| **Admin verification** | code দিয়ে নিশ্চিত করা যায় না; deployment/runtime/provider evidence দরকার। |

---

## ২. কোন পরিকল্পনা যথেষ্ট শক্তিশালী

### ২.১ Architecture reference ও deployment source-of-truth — **শক্তিশালী, তবে legacy drift আছে**

`docs/ARCHITECTURE.md` সঠিকভাবে active architecture হিসেবে Render Docker backend + PostgreSQL/Supabase + Firebase Hosting frontend চিহ্নিত করেছে এবং Cloud Run/GCP/Firebase Functions-কে legacy বলেছে। এটি গুরুত্বপূর্ণ governance improvement। Folder structure, stack, API contract, testing rules এবং security rules-ও পরিষ্কার।

**যা ভালো:**

- active বনাম retired infrastructure আলাদা করা হয়েছে;
- backend/frontend/extension-এর দায়িত্ব নির্ধারিত;
- thin-client ও provider-key non-exposure নীতি স্পষ্ট;
- test ও PR rules লেখা আছে।

**সীমা:** একই docs tree-তে পুরোনো Cloud Run/Kubernetes/microservices plan এখনও আছে। নতুন developer ভুল deployment path বেছে নিতে পারে। প্রতিটি legacy plan-এর header-এ `HISTORICAL / NOT ACTIVE` banner অথবা `_archive/` relocation দরকার।

### ২.২ Production go-live gate — **শক্তিশালী নীতি**

`docs/SUPREMEAI_PRE_PRODUCTION_GO_LIVE_MASTER_TODO.md`-এর rule—CRITICAL 100%, HIGH 100%, MEDIUM known/accepted/documented—ভালো release discipline। Secret, auth, tenant isolation, billing, backup, migration, rollback, health, frontend, dependency এবং API checks-এর তালিকা যথেষ্ট বিস্তৃত।

**যা পরবর্তী level-এ দরকার:** checkbox-এর সঙ্গে owner, evidence URL, last-run SHA, expiry date এবং pass/fail automation যোগ করতে হবে। শুধু checklist completion production evidence নয়।

### ২.৩ Security governance categories — **শক্তিশালী নকশা, অসম্পূর্ণ enforcement**

`docs/security/SUPREME_SECURITY_GOVERNANCE.md` prompt injection, sandbox escape, secret exfiltration, memory poisoning, rate limiting এবং RBAC-এর মতো বাস্তব threat cover করে। Threat categories ভালোভাবে বাছাই করা।

**কিন্তু:** pure AST filtering-কে পূর্ণ sandbox containment হিসেবে ধরা যাবে না। `exec`/`eval` block করলেও Python/runtime escape, filesystem, network, dependency abuse এবং kernel/container boundary আলাদা control চায়। তাই এটি security architecture হিসেবে ভালো, security proof হিসেবে যথেষ্ট নয়।

### ২.৪ Health/readiness ও lifecycle hardening — **আংশিকভাবে শক্তিশালী**

Backend-এ liveness/readiness/deep health ধারণা, database mandatory readiness, Redis optional degradation, WebSocket cleanup, bounded HTTP pool এবং application lifespan wiring আছে। Browser session manager-এ owner scope, maximum session count, idle expiry, context cleanup এবং shutdown আছে। এগুলো বাস্তব reliability improvement।

**সীমা:** বহু state এখনও process-local; multi-worker/multi-instance deployment-এ shared session, task, credential ও permission state-এর জন্য database/Redis contract দরকার।

### ২.৫ CI/quality gates — **শক্তিশালী ভিত্তি, evidence discipline দরকার**

Frontend typecheck, tests, build এবং backend compile/CI setup আছে। Main branch-এর CI run সফল হওয়ার evidence-ও এসেছে। Forced backend/frontend/infra checks এবং admin handoff documentation আছে।

**সীমা:** skipped বা auto-remediated tests কখনও pass হিসেবে গণ্য করা যাবে না। সব conditional skip-এর কারণ, owner ও replacement test থাকা আবশ্যক। CI workflow-এর warning budget ধাপে ধাপে zero-তে নামাতে হবে।

---

## ৩. কোন পরিকল্পনা আংশিক বাস্তবায়িত

### ৩.১ Browser master plan — **আংশিক (সবচেয়ে বড় feature gap)

| পরিকল্পিত capability | বাস্তব evidence | verdict |
|---|---|---|
| Live iframe preview, device viewport | `frontend/src/components/customer/BrowserPreview.tsx`-এ iframe, desktop/tablet/mobile ও landscape আছে | আংশিক |
| Session-based Playwright automation | `backend/core/browser_session_manager.py`-এ isolated context, owner, max sessions, expiry | আংশিকভাবে ভালো |
| Unified browse actions | `browser.py`-এ navigate/click/fill/type/screenshot/content actions | আংশিক |
| URL safety | `is_safe_url` ব্যবহার করা হয়েছে | আংশিক; SSRF/DNS rebinding test দরকার |
| Browser pool | manager-এ semaphore আছে, কিন্তু global browser/context lifecycle ও multi-worker model সীমিত | আংশিক |
| Semantic DOM | plan-এ আছে; canonical route-এ সম্পূর্ণ extractor/endpoint evidence নেই | অসম্পূর্ণ |
| Vision grounding | plan-এ আছে; route wiring ও end-to-end test evidence নেই | অসম্পূর্ণ |
| Screencast WebSocket | frontend-এ `ScreencastViewer` নাম আছে, কিন্তু backend canonical stream contract প্রমাণিত নয় | অসম্পূর্ণ |
| Secure HITL takeover | pause/resume state endpoint আছে; tokenized browser handoff নেই | অসম্পূর্ণ |
| Swarm 3–10 sessions | max 3 browser sessions আছে; swarm coordinator/isolation/cancel semantics নেই | অসম্পূর্ণ |
| Stealth/bot bypass | কিছু stealth-related modules/plan আছে; reliability বা ethical target policy নেই | অসম্পূর্ণ |

**মূল সমস্যা:** `browser.py`-তে canonical session routes-এর পাশাপাশি legacy process-local state (`BROWSER_STATUS`, `CREDENTIALS`, `URL_PERMISSIONS`, `TASKS`, `FINDINGS`) রয়ে গেছে। দুটি state model একসঙ্গে থাকায় frontend কোন contract ব্যবহার করছে তা স্পষ্ট নয়।

**Next level plan:**

1. `BrowserSession`-কে database/Redis-backed metadata + process-local Playwright handle হিসেবে নির্ধারণ;
2. canonical `/api/browser/automation/*` contract-এর জন্য typed frontend client বানানো;
3. action schema-তে enum, max payload, timeout, selector policy, idempotency ও trace ID যোগ;
4. DNS resolve করে private/link-local/loopback block, redirect revalidation এবং egress policy চালু;
5. semantic DOM ও vision grounding-কে একই `ActionPlanner` abstraction-এ যুক্ত;
6. screencast/takeover-এ short-lived signed token, ownership, audit এবং reconnect semantics যোগ;
7. Playwright-installed CI-তে create → navigate → action → screenshot → close end-to-end test চালানো।

### ৩.২ Intelligence/self-evolution plan — **আংশিক থেকে দুর্বল**

`docs/intelligence/SUPREME_AI_INTELLIGENCE_MASTER.md`-এ Eternal Brain, vector recall, পাঁচ reasoning type, swarm consensus, fitness engine ও continuous evolution-এর পরিষ্কার blueprint আছে। `docs/architecture/PROJECT_MODULES_COMPLETE_INVENTORY.md`-তে বহু agent/module catalogued।

**বাস্তব gap:** module file থাকা এবং runtime pipeline-এ সক্রিয় থাকা এক নয়। বর্তমান code audit থেকে সব পরিকল্পিত adapter, memory tree, breed/tune/persist lifecycle এবং swarm consensus-এর একটি single request path প্রমাণিত নয়। Evolution flags production-এ disabled—এটি নিরাপদ, কিন্তু capability active নয়।

**Next level plan:**

- প্রতিটি reasoning adapter-এর typed interface ও capability registry;
- একটি traceable pipeline: request → policy → memory recall → model route → tool approval → result → evaluation → quarantine → promotion;
- memory write-এর আগে provenance, tenant, consent, retention ও review status;
- auto-rewrite কখনো সরাসরি production code-এ নয়—candidate artifact → tests → human approval → signed release;
- fitness score reproducible dataset ও offline evaluation দিয়ে মাপা;
- model/provider claim docs থেকে সরিয়ে runtime registry/config-এর সঙ্গে sync করা।

### ৩.৩ API/database plan — **আংশিক এবং documentation drift আছে**

`docs/api-database/SUPREME_API_DATABASE_SPEC.md` নিজেই historical/partially superseded ঘোষণা করেছে এবং `backend/database/contracts/schema_contract.yaml`-কে canonical বলেছে—এটি ভালো। কিন্তু একই নথিতে পুরোনো schema (`embedding TEXT`) এবং active architecture-এ `VECTOR(384)` দেখা যায়।

**Gap:** plan-এর endpoint list এবং বাস্তব route tree একে অপরের exact contract নয়; অনেক route আছে, কিন্তু frontend caller, auth guard, persistence এবং integration test সব route-এর জন্য সমান নয়।

**Next level plan:** OpenAPI থেকে generated endpoint inventory, route-to-caller matrix, schema contract CI, deprecation policy এবং প্রতি endpoint-এর auth/tenant/test metadata তৈরি করা।

### ৩.৪ Free-tier/model routing plan — **দাবি বেশি, প্রমাণ কম**

Gemini/Groq/Cloudflare/OpenRouter/Ollama fleet এবং cost-sensitive routing পরিকল্পনায় আছে। কিন্তু active provider, model ID, credential source, fallback behavior, budget enforcement, data residency ও failure semantics runtime config থেকে যাচাই করতে হবে। Docs-এ provider list থাকলেই multi-model fleet implemented ধরা যাবে না।

**Next level:** provider-neutral adapter interface, model registry, health/cost/latency metrics, per-tenant budget, deterministic fallback order, circuit breaker এবং provider contract tests।

### ৩.৫ UI/UX master plan — **visual surface শক্তিশালী, backend connectivity অসম**

Frontend-এ admin, command center, health, metrics, sessions, swarm, approvals, security, browser preview ও dashboard-এর অনেক surface রয়েছে। কিন্তু component উপস্থিতি data integration প্রমাণ করে না। প্রতিটি panel-এর জন্য loading/error/empty/retry state, API source, auth policy এবং real data test দরকার।

`BrowserPreview.tsx`-এ `localStorage` token ব্যবহার, hard-coded preview proxy query token, missing/placeholder icon definitions এবং arbitrary `setTimeout` loading simulation দেখা যায়। এটি production browser security/UX contract-এর সঙ্গে অসামঞ্জস্যপূর্ণ।

**Next level:** centralized authenticated API client, HttpOnly/session-based auth, real request state, typed query hooks, accessibility assertions, and contract-backed component tests।

---

## ৪. যে পরিকল্পনাগুলো এখনো পরিকল্পনা-স্তরে

### ৪.১ 10K concurrent users, 99.99% uptime, <100ms P95 — **প্রমাণিত নয়**

`docs/plans/PRODUCTION_UPGRADE_PLAN.md`-এ Kubernetes multi-region, microservices, 10K users, 99.99% uptime এবং <100ms P95 target আছে। বাস্তব architecture reference active হিসেবে Render single-region monolith বলে। কোনো load-test report, SLO dashboard, error budget বা multi-region failover evidence ছাড়া এগুলো target মাত্র।

**ভালো replacement:** প্রথমে measurable beta SLO নির্ধারণ করুন—যেমন availability, chat first-byte latency, error rate, browser action success rate—তারপর load test ও capacity model দিয়ে target বাড়ান।

### ৪.২ Kubernetes/GitOps/microservices — **active plan নয়**

Production upgrade plan-এ EKS/GKE/AKS, Helm, Terraform, NetworkPolicy, External Secrets, kubectl deploy লেখা আছে। কিন্তু canonical architecture Render deployment বলছে। বর্তমানে দুটিকে একই active roadmap রাখা উচিত নয়।

**সিদ্ধান্ত:** Render track-কে active রাখুন; Kubernetes-কে future scale track হিসেবে আলাদা করুন এবং exit criteria ছাড়া implementation শুরু করবেন না।

### ৪.৩ Pure AST sandbox = zero-trust execution — **ভুল/অতিরঞ্জিত**

AST sanitizer useful pre-filter, কিন্তু untrusted code নিরাপদে চালাতে process/container/VM isolation, seccomp/AppArmor, no-network, read-only filesystem, CPU/memory/PID quota, timeout এবং kill verification দরকার। AST bypass সম্ভব। এটি critical security correction।

### ৪.৪ Full digital twin, Theory of Mind, genetic self-rewrite — **অপর্যাপ্ত runtime evidence**

Catalogued modules ও plan language শক্তিশালী হলেও production decision-making path, evaluation data, rollback, consent এবং bounded autonomy অনুপস্থিত/অসম্পূর্ণ প্রমাণিত। এগুলো research/controlled experiment হিসেবে label করা উচিত, core production promise হিসেবে নয়।

### ৪.৫ Complete HITL/JIT OTP/zero-trust governance — **partial**

Security plan-এ JIT OTP, device fingerprint, quarantine এবং approval matrix আছে। কিন্তু বাস্তব endpoint-by-endpoint enforcement, replay tests, audit evidence এবং destructive action coverage আলাদা করে প্রমাণ করতে হবে।

---

## ৫. আন্তঃসংযোগ (interconnection) audit

### ৫.১ ইতিবাচক সংযোগ

- frontend Studio → backend API client layer আছে;
- backend app builder → route groups mount করার ব্যবস্থা আছে;
- health/readiness → database/Redis dependency semantics আছে;
- browser routes → authenticated dependency ও canonical session manager যুক্ত;
- WebSocket lifecycle → application shutdown-এর সঙ্গে যুক্ত;
- CI → frontend quality gates, backend setup এবং schema/security checks-এর সঙ্গে যুক্ত;
- admin documentation → deployment/runtime manual gates উল্লেখ করে।

### ৫.২ প্রধান বিচ্ছিন্নতা

1. **দুটি browser state model:** canonical Playwright sessions বনাম legacy in-memory surf/credential/task state।
2. **Frontend BrowserPreview canonical automation API ব্যবহার করছে না:** iframe proxy UI এবং backend session/action API আলাদা flow।
3. **UI panel বনাম backend contract:** component inventory বড়, কিন্তু সব panel-এর real API caller/contract test নিশ্চিত নয়।
4. **Docs endpoint list বনাম route tree:** documented prefixes ও বাস্তব registered prefixes drift করতে পারে; generated inventory দরকার।
5. **Memory/evolution modules বনাম production write path:** quarantine/provenance/tenant-scoped promotion end-to-end প্রমাণিত নয়।
6. **Security plan বনাম enforcement:** documented guardrails-এর সবগুলো route/middleware/test-এ কেন্দ্রীভূত নয়।
7. **Process-local state বনাম multi-instance deployment:** restart, horizontal scaling ও failover-এ state loss/inconsistency ঝুঁকি।
8. **Tests বনাম capability:** skipped browser/legacy tests capability pass প্রমাণ করে না।

### ৫.৩ Interconnection scorecard

| স্তর | মূল্যায়ন | মন্তব্য |
|---|---:|---|
| Route registration | ৭/১০ | বহু route আছে; duplicate/legacy surface আছে। |
| Frontend-to-API contract | ৫/১০ | core chat/health ভালো; browser/admin সবখানে নয়। |
| Auth/RBAC/tenant isolation | ৫/১০ | guard আছে; সম্পূর্ণ adversarial evidence দরকার। |
| Persistence/state consistency | ৪/১০ | process-local state বেশি। |
| Observability/audit | ৫/১০ | audit/log modules আছে; সব action traceable নয়। |
| Test coverage of real capability | ৫/১০ | frontend ভালো; browser/evolution integration gap। |
| Deployment parity | ৬/১০ | Render active, legacy plans confusing। |
| Overall integration confidence | **৫/১০** | controlled staging-এর জন্য; unrestricted production নয়। |

---

## ৬. Feature/module upgrade priority

### P0 — release blocker

1. **Canonical API registry:** OpenAPI route inventory, frontend caller mapping, auth requirement, tenant scope, persistence ও test link।
2. **Browser security:** remove query-string token and client `localStorage` token usage; central auth client; SSRF/DNS rebinding protection; action limits।
3. **State persistence:** credentials, URL permissions, task state ও session metadata database/Redis-এ; encryption/key rotation; owner/tenant scope।
4. **Authorization audit:** every protected route, IDOR/BOLA, forged `userId`/`tenant_id`, admin separation এবং destructive actions।
5. **Skipped-test closure:** skip reason, replacement test, owner, deadline; auto-skip কখনও green release evidence নয়।
6. **Clean deployment contract:** Render active path একমাত্র active path; Kubernetes/GCP docs archive/banner।

### P1 — product capability

1. Browser canonical frontend client ও real session UX।
2. Semantic DOM extractor + deterministic selector grounding।
3. Vision grounding with confidence threshold and human fallback।
4. Screencast + secure takeover token + audit trail।
5. Typed event envelope across SSE/WebSocket/Redis।
6. Unified error taxonomy, correlation ID এবং trace propagation।
7. Real admin panels with loading/error/empty/retry states and contract tests।

### P2 — scale and intelligence

1. Browser worker pool with per-tenant quotas, cancellation, backpressure ও queueing।
2. Offline evolution evaluator, quarantine/promotion workflow এবং signed candidate artifacts।
3. Provider/model registry with cost, latency, quota এবং circuit breakers।
4. Distributed tracing (OpenTelemetry), SLO/error budget এবং load testing।
5. Read replica/multi-region only after measured bottleneck।
6. Digital twin/Theory of Mind as opt-in experiments, not uncontrolled production automation।

---

## ৭. Recommended revised roadmap

### Stage A — Contract truth (আগে করুন)

- canonical architecture ও active deployment path এক করুন;
- OpenAPI/schema contract থেকে generated inventory বানান;
- duplicate/legacy routes mark/deprecate করুন;
- route-to-frontend caller matrix CI-তে যাচাই করুন।

### Stage B — Safe browser product

- canonical session manager + persistent metadata;
- typed client and real frontend flow;
- URL/egress security;
- action validation, timeout, cancellation, audit;
- Playwright CI E2E।

### Stage C — Reliability and security

- adversarial auth/tenant tests;
- secret rotation and no-secret-in-URL check;
- state recovery, graceful shutdown, multi-instance test;
- OpenTelemetry, SLO, load and failure tests।

### Stage D — Intelligence safely

- memory provenance/quarantine;
- model registry and evaluation harness;
- approval-gated evolution candidates;
- no direct self-modification of production code।

### Stage E — Scale only when evidence requires

- queue/worker separation;
- browser capacity model;
- read replica/CDN/multi-region decision based on P95 and cost data;
- Kubernetes migration only with explicit trigger criteria।

---

## ৮. Required acceptance evidence

কোনো feature-কে `implemented` বলার আগে নিচের সবগুলো থাকা উচিত:

```text
[ ] Source implementation exists
[ ] Runtime route/service wiring exists
[ ] Auth and tenant policy exists
[ ] Persistence/recovery behavior defined
[ ] Unit test exists
[ ] Integration test exists
[ ] Failure/timeout/cancellation test exists
[ ] Observability/audit event exists
[ ] OpenAPI/schema contract updated
[ ] Frontend caller exists, if user-facing
[ ] Deployment configuration exists
[ ] Admin verification task/evidence exists, if provider-dependent
```

---

## ৯. Admin manual tasks

এই audit-এর code-side ফলাফলের বাইরে administrator-এর করণীয়:

- Render-এর active service revision ও environment matrix verify করা;
- `SUPABASE_DATABASE_URL`, Redis, auth, billing ও vault variables-এর production presence যাচাই করা;
- deployed backend-এর `/health/live`, `/health/ready`, `/health/deep` evidence সংরক্ষণ করা;
- browser runtime-এ Playwright browser binary/permissions এবং create → action → close smoke flow চালানো;
- skipped tests-এর business acceptance বা implementation owner নির্ধারণ করা;
- current release SHA-তে full CI run URL নথিভুক্ত করা;
- secret rotation সম্পন্ন ও historical credential revoke করা;
- evolution flags disabled রেখে logs/metrics review করা; enable করার আগে written approval নেওয়া;
- backup/restore এবং rollback drill-এর evidence সংরক্ষণ করা।

এই tasks `docs/ADMIN_TASKS.md`-এও প্রতিফলিত হওয়া উচিত।

---

## ১০. Final conclusion

SupremeAI-এর documentation ambition অনেক শক্তিশালী এবং architecture/security/production checklist-এর ভিত্তি ভালো। কিন্তু docs-এর capability claims বাস্তব implementation-এর চেয়ে এগিয়ে আছে। সবচেয়ে বড় বাস্তব gap হলো **contract truth, browser end-to-end productization, persistent multi-tenant state, authorization evidence এবং safe evolution pipeline**।

সুতরাং বর্তমান classification:

```text
Core chat + frontend quality       = যথেষ্ট শক্তিশালী ভিত্তি
Health/lifecycle/CI foundation     = আংশিক থেকে শক্তিশালী
Browser automation                 = prototype / foundation
Self-evolution intelligence        = research / controlled beta
Enterprise scale/SLO               = target only
Zero-trust sandbox                 = design intent, not proof
Overall                            = Production candidate নয়; controlled staging/beta
```

সবচেয়ে ভালো next move হলো নতুন বড় feature যোগ না করে প্রথমে **generated contracts + browser canonical integration + security/adversarial tests** সম্পন্ন করা। এতে documentation, frontend, backend, admin এবং deployment—সব স্তরের বিচ্ছিন্নতা কমবে।

---

## Evidence references

- `docs/ARCHITECTURE.md`
- `docs/architecture/PROJECT_MODULES_COMPLETE_INVENTORY.md`
- `docs/api-database/SUPREME_API_DATABASE_SPEC.md`
- `docs/intelligence/SUPREME_AI_INTELLIGENCE_MASTER.md`
- `docs/plans/PRODUCTION_UPGRADE_PLAN.md`
- `docs/security/SUPREME_SECURITY_GOVERNANCE.md`
- `docs/SUPREMEAI_PRE_PRODUCTION_GO_LIVE_MASTER_TODO.md`
- `docs/browser/SUPREME_BROWSER_MASTER_PLAN.md`
- `docs/browser/implementation_plan.md`
- `backend/api/routes/browser.py`
- `backend/core/browser_session_manager.py`
- `frontend/src/components/customer/BrowserPreview.tsx`
- `docs/KNOWN_ISSUES.md`
- `backend/database/contracts/schema_contract.yaml` (canonical schema contract; verify directly for schema changes)

*এই নথি implementation audit; এটি production approval নয়।*
