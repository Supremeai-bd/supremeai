# 🚀 SupremeAI — ফিচার ইমপ্লিমেন্টেশন প্যাচ ও রোডম্যাপ (বাংলা)

**তারিখ:** ১৩ সেপ্টেম্বর ২০২৬ | **বেস ব্রাঞ্চ:** `main` @ `8833e9d`
**প্যাচ ফাইল:** `SUPREMEAI_FEATURE_PATCH.patch` | **পরিসর:** ২৯ ফাইল, +২,০৫৯ / −৮৮ লাইন

> এই প্যাচে **পুরনো পরিকল্পনার ৪টি ফিচার** + **প্রোডাকশন-রেডিনেস প্ল্যানের বাকি ৪টি কাজ** — মোট ৮টি আইটেম সম্পূর্ণভাবে ইমপ্লিমেন্ট করা হয়েছে, সাথে ৭টি লুকানো বাগ ফিক্স। সবকিছু কোডবেস-ভেরিফাইড, টেস্টেড এবং প্রতিটি ফাইলে বাংলা কমেন্টসহ ডকুমেন্টেড।

---

## ✅ অংশ ১ — পুরনো পরিকল্পনার ৪টি High-Value ফিচার (এবার সত্যিই ইমপ্লিমেন্টেড)

### ⚡ Feature 1: 1-Line MCP Connection UX + Glassmorphic Dashboard Polish

| ফাইল | পরিবর্তন |
|---|---|
| `frontend/src/index.css` | **[MODIFY]** `.glass-panel`, `.glass-input`, `.pulse-ring`, `.node-active` utilities + `pulse-neon`/`node-beat` keyframes; `body.light` ও `prefers-reduced-motion` সাপোর্টসহ |
| `frontend/src/components/dashboard/OneLinerMCPConnect.tsx` | **[NEW]** একটি URL দিয়েই MCP/AI-Provider/Webhook connect — Enter-কি সাপোর্ট, inline success/error card |
| `frontend/src/components/dashboard/OneLinerMCPConnect.test.tsx` | **[NEW]** ৫টি vitest টেস্ট |
| `frontend/src/components/dashboard/ConnectedPlatformsVault.tsx` | **[MODIFY]** OneLinerMCPConnect ভল্টের উপরে embed |
| `backend/services/integration_discovery.py` | **[NEW]** `IntegrationDiscoveryService` — MCP handshake (`/.well-known/mcp.json`) → AI provider hostname-প্যাটার্ন → webhook reachability, এই ৩-ধাপ auto-detect |
| `backend/api/routes/integrations.py` | **[MODIFY]** `POST /api/v1/integrations/discover` এন্ডপয়েন্ট (JWT-guarded) |

### 🧠 Feature 2: Auto-RAG Memory Injection (audit G-3 — এখন ✅)

| ফাইল | পরিবর্তন |
|---|---|
| `backend/core/memory/auto_rag_injector.py` | **[NEW]** `AutoRAGInjector` — প্রতিটি অনুরোধের আগে pgvector থেকে top-5 প্রাসঙ্গিক স্মৃতি recall করে prompt-এ prepend; `store_session_memory()` দিয়ে সফল এক্সচেঞ্জ ফেরত সেভ। স্কোর-থ্রেশহোল্ড (0.55), টেন্যান্ট-আইসোলেশন, **সাইলেন্ট graceful degradation** সহ |
| `backend/core/memory/__init__.py`, `backend/core/ai_memory/__init__.py` | **[NEW]** প্যাকেজ init |
| `backend/api/routes/stream_chat_sse.py` | **[MODIFY]** `SafeSSEGenerator`-এ injection + স্ট্রিম শেষে এক্সচেঞ্জ memory-store — **এই এন্ডপয়েন্টে আগে কোনো memory injection-ই ছিল না** |
| `backend/api/routes/chat.py` | **[MODIFY]** `stream_chat`-এর recall-এ `user_id` যোগ — আগে অন্য টেন্যান্টের মেমরিও recall হতো (বাগ ফিক্স) |

### 🕵️ Feature 3: Biometric Stealth Fingerprint Layer

| ফাইল | পরিবর্তন |
|---|---|
| `backend/core/human_behavior.py` | **[MODIFY]** `apply_stealth_fingerprint()` — Canvas noise, WebGL vendor/renderer spoof (37445/37446), `navigator.webdriver` মুছে ফেলা, realistic plugins, ৬-সেটের random viewport; কখনো exception ছোড়ে না |
| `backend/services/scraper/browser_agent.py` | **[MODIFY]** `navigate_and_interact` ও `execute_recipe` — দুই প্লেসেই stealth call wired |
| `backend/tests/test_stealth_browser.py` | **[NEW]** ৫টি টেস্ট |

### ☁️ Feature 4: Cloudflare Worker → Backend Auto-Failover Circuit Breaker

| ফাইল | পরিবর্তন |
|---|---|
| `infrastructure/cloudflare/enhanced-worker.js` | **[MODIFY]** `proxyToOrigin` এখন priority-অর্ডারড multi-node failover: প্রতি নোড ৮ সেকেন্ড টাইমআউট, 5xx/network ব্যর্থতায় KV-সংরক্ষিত OPEN circuit (২ মিনিট TTL = auto HALF-OPEN recovery), শেষ নোড পর্যন্ত ব্যর্থ হলে JSON 503 |
| `infrastructure/cloudflare/wrangler.toml` | **[MODIFY]** `BACKUP_RENDER_URL`/`TERTIARY_RENDER_URL` vars + `SUPREME_KV`/`DUPLICATE_DB`/`CACHE_METADATA` KV bindings ডিক্লেয়ার |

**সাথে ৩টি ক্রিটিকাল worker বাগ ফিক্স** (নিচে অংশ ৩ দেখুন)।

---

## 🔐 অংশ ২ — প্রোডাকশন-রেডিনেস প্ল্যানের বাকি ৪টি হার্ডেনিং কাজ

### ১. Scraper Service Access Guard (P1) ✅

`backend/api/routes/scraper.py` — `/scrape`, `/browse`, `/recipe` তিনটিতেই:
- `Depends(get_current_admin)` — এখন থেকে admin JWT ছাড়া **HTTP 401**; regular user পেলে **403**
- `asyncio.Semaphore(SCRAPER_MAX_CONCURRENCY)` — ক্যাপাসিটি শেষ হলে **HTTP 429**, কোনো লাইনে অপেক্ষা নয়
- **বোনাস:** sync `fetch_page` httpx কল `asyncio.to_thread`-এ — ইভেন্ট লুপ আর ব্লক হয় না (standalone সার্ভিসের সাথে parity)
- `/health` ইচ্ছাকৃতভাবে public রাখা হয়েছে (uptime monitoring-এর জন্য)

### ২. JWT Revocation — Admin-এর জন্য Fail-Closed (P1) ✅

`backend/core/security/__init__.py` + `auth_middleware.py` + `api/routes/auth.py`:
- `is_token_revoked(jti, *, is_admin=False)` — **admin + Redis ডাউন = fail-CLOSED (রিজেক্ট)**; regular user = fail-open (Render cold-start-এ লক-আউট নয়)
- TTL-aware **`_ADMIN_REVOCATION_CACHE`** LRU (সর্বোচ্চ ১০০০ entry, thread-safe `OrderedDict`) — Redis ডাউন থাকলেও সর্বশেষ revoked admin token ধরা পড়ে
- `verify_token` / `verify_token_async` এখন payload-এর `role` claim থেকে নিজেই admin বুঝে নেয় (`admin`/`master_admin`)
- `AuthMiddleware` — revocation check ব্যর্থ হলে admin token 401, user token আগের মতো
- `logout`/`revoke_token`-এ role-aware admin-cache write
- `backend/tests/security/test_admin_fail_closed.py` — ৯টি টেস্ট

### ৩. localStorage → httpOnly Cookie Migration (P1) ✅

**Backend ইতোমধ্যে ছিল** (`_set_auth_cookies` login/register/refresh-এ কল হয় — commit `78ddb9b`-এ হয়ে গেছে); **frontend-এর বাকি অংশ এই প্যাচে সম্পন্ন:**

`frontend/src/store/authStore.ts` — `initialize()`:
- localStorage টোকেন না থাকলেও `credentials: 'include'` সহ `/auth/me` কল করে **cookie-only session detect করে রিস্টোর করে**
- দুই মোডই কাজ করে (dual-mode transition) — কোনো breaking change নেই; পুরনো localStorage সেশন অক্ষত
- `authStore.test.ts`-এ ২টি নতুন টেস্ট (মোট ১২টি পাস)

### ৪. Memory Service Phase-2: pgvector RPC (P2) ✅

| ফাইল | পরিবর্তন |
|---|---|
| `backend/database/migrations/legacy/001_pgvector_match_fn.sql` | **[NEW]** Supabase SQL Editor-এ একবার চালাতে হবে — `CREATE EXTENSION vector`, TEXT→vector guarded conversion, ivfflat index, **`match_ai_memories`** RPC (user/session ফিল্টারসহ, unconstrained vector — 384/1536 দুই dim-এই চলে) |
| `backend/services/memory_service.py` | **[MODIFY]** `query_context()` — ক্যাশড প্রোবে pgvector পেলে ডাটাবেস-সাইড ranking (RPC), না পেলে আগের ২০০০-রো Python-cosine fallback; `_embed`-এর **384/1536 dim-অসঙ্গতি ফিক্স** (`_PG_DIM`-contract) |

---

## 🐛 অংশ ৩ — সাথে ফিক্স হওয়া ৭টি লুকানো বাগ (প্ল্যানের বাইরে, কোডবেস অডিটে ধরা পড়ে)

| # | বাগ | ফাইল | প্রভাব |
|---|---|---|---|
| B1 | `caches.default.putToCache()` — অবাস্তব API; প্রতিটি GET `/api/*` cache-miss 500 করত | `enhanced-worker.js` | **প্রোডাকশন-ডাউন স্তরের** বাগ |
| B2 | AI cache key-তে `sha256Hash()`-এর আগে `await` ছিল না — key-তে `"[object Promise]"` | `enhanced-worker.js` | AI caching কখনোই কাজ করত না |
| B3 | Default route-এ `fetch(request)` — worker নিজেকেই কল করত | `enhanced-worker.js` | non-API traffic origin-এ পৌঁছাত না |
| B4 | `DUPLICATE_DB`/`CACHE_METADATA` কোডে ব্যবহৃত কিন্তু wrangler.toml-এ ডিক্লেয়ার ছিল না | `wrangler.toml` | POST `/ai/*`-এ TypeError |
| B5 | `vector_store.upsert_batch` sync Supabase ক্লায়েন্টকে `await` করত — সবসময় ব্যর্থ, কোনো মেমরি persist হতো না | `core/ai_memory/vector_store.py` | Auto-RAG-এর পুরো স্টোর-পাথ নিষ্ক্রিয় ছিল |
| B6 | `chat.py stream_chat`-এর recall-এ `user_id` পাঠানো হতো না — টেন্যান্ট-আইসোলেশন miss | `api/routes/chat.py` | ক্রস-টেন্যান্ট memory leak ঝুঁকি |
| B7 | `engine/vector_db.py` `query_context(query=, limit=, threshold=)` — ভুল kwargs; প্রতিবার TypeError চুপচাপ গিলে ফাঁকা ফলাফল | `engine/vector_db.py` | experience-recall সবসময় খালি |

---

## 🧪 ভেরিফিকেশন রিপোর্ট (এই স্যান্ডবক্সে সম্পাদিত)

```text
✅ নতুন ব্যাকএন্ড টেস্ট:       ৩০/৩০ পাস
   (Auto-RAG ১০ + Stealth ৫ + Fail-closed ৯ + Scraper-guard ৬)
✅ রিগ্রেশন টেস্ট:            ৪৩/৪৩ পাস
   (memory_service ৩৩ + security/hardening ৬ + chat API ৪)
✅ ফ্রন্টএন্ড vitest:          ১৭/১৭ পাস (OneLinerMCPConnect ৫ + authStore ১২)
✅ TypeScript:                নতুন কোনো এরর নেই (বেসলাইন ১২টি pre-existing এরর
                               pristine main-এও ছিল — প্যাচে অপরিবর্তিত)
✅ ruff lint:                 সব পরিবর্তিত ফাইল ক্লিন
✅ node --check (worker):     সিনট্যাক্স ক্লিন; TOML ভ্যালিড
✅ সিক্রেট-লিক স্ক্যান:         প্যাচে কোনো credential/key নেই
```

---

## 📦 প্যাচ প্রয়োগ করার নিয়ম

```bash
cd supremeai
git checkout main && git pull origin main
git apply --check SUPREMEAI_FEATURE_PATCH.patch   # ড্রাই-রান
git apply SUPREMEAI_FEATURE_PATCH.patch
git add -A
git commit -m "feat: implement 4 old-plan features + 4 production hardening items + 7 bugfixes"
```

> **নোট:** কনফ্লিক্ট হলে `git apply --3way SUPREMEAI_FEATURE_PATCH.patch` ব্যবহার করুন।

---

## 🗺️ ডিপ্লয়মেন্ট-পরবর্তী ম্যানুয়াল ধাপ (কোডের বাইরে)

1. **Supabase SQL Editor:** `backend/database/migrations/legacy/001_pgvector_match_fn.sql` একবার রান করুন — এতেই `match_ai_memories` RPC সক্রিয় হবে (না চালালেও সিস্টেম fallback-এ চলবে, শুধু দ্রুত পথটি বন্ধ থাকবে)।
2. **Cloudflare:** `wrangler kv namespace create SUPREME_KV` (+ `DUPLICATE_DB`, `CACHE_METADATA`) — তৈরি হওয়া id-গুলো `wrangler.toml`-এর `REPLACE_WITH_*` প্লেসহোল্ডারে বসিয়ে `wrangler deploy` করুন। `BACKUP_RENDER_URL`-এ আপনার সেকেন্ডারি Render নোডের URL দিন।
3. **Postman যাচাই:** অ্যাডমিন JWT ছাড়া `POST /api/v1/browse` → **401** আসছে কিনা দেখুন।
4. **ফ্রন্টএন্ড:** লগইন → DevTools → Cookies-এ `supreme_access_token`-এ `HttpOnly ✓` চিহ্ন যাচাই করুন; নতুন `/workspace` পেজে **⚡ 1-Line Connect** প্যানেল দেখা যাচ্ছে কিনা দেখুন।
5. **Env keys:** আপনার শেয়ার করা `4.env`-এর কোনো কী এই প্যাচে ব্যবহার/কমিট করা হয়নি — কীগুলো Infisical/Render-এ propagate করার নিয়ম আপনার `.env` ফাইলের হেডার-নোট অনুযায়ীই রইল। টেস্টিংয়ের পরে revoke করতে ভুলবেন না।

---

## 🛣️ সামনের রোডম্যাপ (audit-এর Priority-B/C অনুযায়ী — পরবর্তী স্প্রিন্ট)

| ধাপ | কাজ | অডিট রেফারেন্স |
|---|---|---|
| Sprint 2 | `match_ai_memories` RPC-কে `recall_memories()`-এর মূল পথ বানানো (Supabase `match_ai_memory`-র ৩-প্যারাম সংস্করণের সাথে ডিমেনশন-কন্ট্রাক্ট একীভূত করা) | Gap-9 |
| Sprint 2 | `BranchPoint.tsx` + `parent_message_id` — কনভারসেশন ব্রাঞ্চিং | G-6 |
| Sprint 2 | `ReasoningLog.tsx`-এ backend streaming-step feed | G-7 |
| Sprint 3 | `intent_router.py` post-response hook — প্রোঅ্যাকটিভ next-step hints | G-8 |
| Sprint 3 | `pr_reviewer.py` unifed-diff inline comments | G-9 |
| Sprint 3 | Cron-builder UI + `scheduler.py` self-serve টাস্ক | G-10 |
| Sprint 4 | MCP Marketplace module (control-plane) | G-4 |
| Sprint 4 | pass^k reliability metric — `self_benchmark.py` | Gap-4 |
| Sprint 5 | `UnifiedModelRouter` convergence (১০ router → ১) | §7.2 |

> **মূলনীতি অটুট:** আমরা model নই — আমরা orchestrator। প্রতিটি নতুন ফিচার Zero-Hardcoding, Free-Tier-First, Tenant-Owned ও HITL নীতির ভেতরেই বানানো হয়েছে।
