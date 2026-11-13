# SupremeAI অবশিষ্ট ধাপসমূহের বিশদ বাস্তবায়ন পরিকল্পনা
## Comprehensive Implementation Plan: Remaining Phases (Phase 2, Phase 3, Phase 4)

> **ডকুমেন্ট স্ট্যাটাস:** ACTIVE IMPLEMENTATION PLAN  
> **টার্গেট ভার্সন:** 2.1.0 – 2.4.0  
> **কোডবেস যাচাইকৃত ভিত্তি:** `f:\supremeai` (Monorepo) ও `f:\supremeai-frontend` (SPA Client)  
> **রেফারেন্স স্পেক:** `FREE_TIER_SAFEGUARD_AND_PARITY_SPEC.md` ও `supremeai-সম্পূর্ণ-বাস্তবায়ন-পরিকল্পনা-কোডবেস-ভেরিফাইড (1).md`

---

## ১. ভূমিকা ও বর্তমান অগ্রগতি (Baseline Status)

### ১.১ Phase 1 সম্পন্ন ও ভেরিফাইড (Baseline)
1. **Core API MCP Tower Proxy (`core/api/routes/mcp_tower.py`):**
   - Streamable HTTP ক্লায়েন্ট (`ControlTowerClient` via `core/mcp_client.py`) দিয়ে Tower-এর সাথে কানেকশন।
   - Endpoints: `GET /api/v1/mcp-tower/services`, `POST /api/v1/mcp-tower/probe`, `POST /api/v1/mcp-tower/reboot`, `GET /api/v1/mcp-tower/stream` (SSE 15s tick)।
   - Registered in `core/api/routers.py`।
2. **MCP Control Plane Multi-Account Redis & Parity Engine:**
   - `infrastructure/mcp-control-plane/src/lib/redis_chain.ts` এ ৫টি Upstash অ্যাকাউন্টের সম্মিলিত ২৫ লাখ (2.5M) কমান্ড কোটা ট্র্যাক করার জন্য `getFleetQuotaSummary()` কার্যকর।
   - `infrastructure/mcp-control-plane/src/tools/parity.tools.ts` এ প্রতি সার্ভিসের স্বতন্ত্র Git Commit SHA পারিবর্তন ট্র্যাকিং চালু।
3. **Frontend Telemetry & Honesty (`supremeai-frontend`):**
   - `src/types/index.ts` এ `deployAgeDays`, `commitSha`, `freshness` যোগ।
   - `src/services/adminService.ts` এর `mapTowerService()` ১৪টি আসল সার্ভিসের সাথে ম্যাপড।
   - `src/stores/useAdminStore.ts` এ ফেক টোস্ট বন্ধ করে ওয়্যার-অনেস্টি নিশ্চিত।
   - `src/components/ChatInput.tsx` ও `App.tsx`-এ RAG Knowledge Grounding এবং Deep Research মোড টগল ওয়্যারড।

---

## ২. সামগ্রিক রোডম্যাপ ও অগ্রাধিকার ক্রম (Execution Order)

```mermaid
flowchart TD
    subgraph Phase 2: Auth, Data & Chat
        A1[A1: Live Supabase Auth & Route Normalization]
        A3[A3: Knowledge Base RAG Upload & Embedding]
        A6[A6: Multi-Device Session Persistence in Supabase]
        A5[A5: Chat Utilities: Search, Branch, Share]
        A4[A4: Graph RAG Domain Visualization]
        A2[A2: Admin 2FA Security Modal]
        A1 --> A3 --> A6 --> A5 --> A4 --> A2
    end

    subgraph Phase 3: Runtime Environments & Safety
        C3[C3: HITL Safety Interception Modal]
        C4[C4: Render 750h Multi-Account Enforcer]
        C1[C1: Autonomous Browser Screencast & Control]
        C2[C2: MicroVM Terminal Sandbox Log Stream]
        C3 --> C4 --> C1 --> C2
    end

    subgraph Phase 4: Intelligence, Schedule & Billing
        D1[D1: Deep Research Pipeline & Citation Viewer]
        D5[D5: Live Token & Cost Metering Cockpit]
        D3[D3: Scheduled Autonomous Cron Cockpit]
        D2[D2: Bidirectional Real-Time Voice]
        D4[D4: Stripe Checkout & Balance Top-up]
        D1 --> D5 --> D3 --> D2 --> D4
    end

    Phase 2 --> Phase 3 --> Phase 4
```

---

## ৩. Phase 2: Auth, Knowledge Base (RAG), সেশন ও মেমরি

### টাস্ক A1: Live Supabase Auth & Route Normalization
* **সমস্যা:** ফ্রন্টএন্ড `src/services/authService.ts` কল করে `POST /api/auth/login`, কিন্তু ব্যাকএন্ড `core/api/routers.py` রাউটটি মাউন্ট করে `/api/v1/auth/login`-এ। এছাড়া `VITE_USE_MOCK=false` অবস্থায় লাইভ সেশন ও কুকি হ্যান্ডলিং সম্পূর্ণ কার্যকর করতে হবে।
* **ফাইল পরিবর্তন:**
  - Backend: `core/api/routes/auth.py` এবং `core/api/routers.py` (অ্যালিয়াস রাউট `/api/auth/login` ও `/api/v1/auth/login` দুটোই সাপোর্ট করা)।
  - Frontend: `src/services/authService.ts` (Supabase JWT + httpOnly refresh cookie হ্যান্ডলিং, Google SSO redirect URL কনফিগারেশন)।
  - Frontend: `src/stores/useAuthStore.ts` (পেজ রিফ্রেশে `GET /api/v1/auth/me` কল করে লাইভ সেশন রিকভারি)।
* **এক্সেপ্টেন্স ক্রাইটেরিয়া:**
  - টেস্ট ক্রেডেনশিয়াল বা জেনুইন Supabase ইউজার দিয়ে লগইন করলে সঠিক JWT রেসপন্স আসবে এবং ফ্রন্টএন্ডে রিয়েল ইউজার প্রোফাইল শো করবে।
  - রিফ্রেশ দিলে ইউজার লগড-ইন থাকবে (Local Storage মক নয়, লাইভ টোকেন ভ্যালিডেশন)।

### টাস্ক A3: Knowledge Base (RAG) End-to-End Pipeline
* **বিবরণ:** চ্যাট ইনপুটে থাকা ডাটাবেস গ্রাউন্ডিং আইকন অন থাকলে ইউজার ডকস থেকে কিউড্রান্ট ভেক্টরে সার্চ করে কনটেক্সট ইনজেক্ট হবে।
* **ফাইল পরিবর্তন:**
  - Backend: `core/rag/` ও `core/api/routes/knowledge_base.py` (বা `gateway/routes/memory.py`) - ফাইল আপলোড (`POST /api/v1/knowledge/upload`), চ্যাঙ্কিং ও ভেক্টরাইজেশন (Qdrant storage)।
  - Frontend: `src/services/knowledgeService.ts` (লাইভ ফাইল আপলোড ও কিউড্রান্ট ডক স্ট্যাটাস ফেচ)।
  - Frontend: `src/stores/useKnowledgeStore.ts` (মক ডক্সের বদলে কিউড্রান্ট লাইভ কালেকশন প্রদর্শন)।
* **এক্সেপ্টেন্স ক্রাইটেরিয়া:**
  - একটি PDF/Markdown আপলোড করলে ব্যাকএন্ড কিউড্রান্টে ভেক্টরাইজ হবে।
  - চ্যাটে প্রশ্ন করলে প্রম্পটের সাথে `groundingContext` যুক্ত হয়ে সঠিক রেফারেন্স সহ উত্তর আসবে।

### টাস্ক A6: Multi-Device Session Persistence (Supabase Postgres)
* **বিবরণ:** চ্যাট হিস্ট্রি কেবল ব্রাউজারের `localStorage`-এ না রেখে Supabase-এর `conversations` ও `messages` টেবিলে স্বয়ংক্রিয়ভাবে সিঙ্ক হবে।
* **ফাইল পরিবর্তন:**
  - Backend: `core/api/routes/conversations.py` (`GET /api/v1/conversations`, `POST /api/v1/conversations`, `PATCH /api/v1/conversations/:id`, `DELETE /api/v1/conversations/:id`)।
  - Frontend: `src/services/chatService.ts` ও `src/stores/useChatStore.ts` (সেশন তৈরি ও মেসেজ পাঠানোর সময় লাইভ Supabase API-তে পাঠানো)।
* **এক্সেপ্টেন্স ক্রাইটেরিয়া:**
  - অন্য ব্রাউজার বা ইনকগনিটো থেকে লগইন করলেও পূর্বের চ্যাট সেশন হুবহু লোড হবে।

### টাস্ক A5: Chat Utilities (Search, Branch, Share)
* **বিবরণ:**
  1. `ChatSearchBar.tsx` দিয়ে কি-ওয়ার্ড ভিত্তিক দ্রুত সেশন সার্চ।
  2. চ্যাট বাবল থেকে কোনো নির্দিষ্ট পয়েন্টে "Branch" বাটন ক্লিক করে নতুন সেশন তৈরি।
  3. "Share" বাটন দিয়ে রিড-অনলি পাবলিক লিঙ্ক জেনারেশন (`GET /share/:token`)।
* **ফাইল পরিবর্তন:**
  - Backend: `core/api/routes/chat_search.py`, `core/api/routes/branch_conversations.py`, `core/api/routes/share.py`।
  - Frontend: `src/components/ChatSearchBar.tsx`, `src/components/chat/ChatMessageItem.tsx`, `src/stores/useChatStore.ts`।

### টাস্ক A4: Graph RAG & Domain Knowledge Visualization
* **বিবরণ:** `sidecars/memory/graph_store.py`-তে সঞ্চিত নলেজ গ্রাফ ফ্রন্টএন্ডের ইন্টারেক্টিভ নলেজ গ্রাফ ভিউতে ভিজ্যুয়ালাইজ করা।
* **ফাইল পরিবর্তন:**
  - Backend: `core/api/routes/knowledge_graph.py` (`GET /api/v1/knowledge/graph`)।
  - Frontend: `src/components/views/GraphView.tsx` (Cytoscape বা D3/SVG রেন্ডারিং লাইভ নোড ও এজ ডেটা দিয়ে)।

### টাস্ক A2: Admin 2FA Security Modal
* **বিবরণ:** অ্যাডমিন ড্যাশবোর্ডের স্পর্শকাতর কার্যক্রমে (যেমন: ক্লিয়ার ডেটাবেস, এপিআই কি রোটেশন) TOTP ভিত্তিক ২-ফ্যাক্টর অথেনটিকেশন।
* **ফাইল পরিবর্তন:**
  - Backend: `gateway/routes/admin_dashboard/endpoints_security.py` (`POST /api/v1/security/2fa/verify`, `/setup`)।
  - Frontend: `src/components/modals/AdminTwoFactorModal.tsx` ও `src/services/authService.ts`।

---

## ৪. Phase 3: Autonomous Browser, Terminal Sandbox & HITL Safety

### টাস্ক C3: Human-In-The-Loop (HITL) Interception Modal (অগ্রাধিকার: সর্বোচ্চ)
* **উদ্দেশ্য:** যে কোনো ধ্বংসাত্মক কমান্ড (যেমন: `rm -rf`, ফাইল ওভাররাইট, ড্রপ টেবিল, বা প্রোডাকশন ডিপ্লয়মেন্ট) এক্সিকিউশনের পূর্বে এজেন্টের কাজ পজ হবে এবং ফ্রন্টএন্ডে অনুমোদন পপ-আপ আসবে।
* **ফাইল পরিবর্তন:**
  - Backend: `core/api/routes/websocket_hitl.py` অথবা `core/api/routes/stream_hitl_sse.py`।
  - Frontend: `src/hooks/useHitlApproval.ts` (WebSocket/SSE কানেকশন যা ইন্টারাপশন রিকোয়েস্ট শোনে)।
  - Frontend: `src/components/modals/HitlApprovalModal.tsx` (ইউজারের "Approve" বা "Deny" ইনপুট ব্যাকএন্ডে ফেরত পাঠায়)।
* **এক্সেপ্টেন্স ক্রাইটেরিয়া:**
  - এজেন্ট যখন কোনো সুরক্ষিত অ্যাকশন ট্রিগার করবে, তখন সিস্টেম `PENDING_APPROVAL` স্টেটে যাবে; ফ্রন্টএন্ডে ইউজার Approve ক্লিক না করা পর্যন্ত কোড রান হবে না।

### টাস্ক C4: Render 750h Multi-Account Enforcer (Free-Tier Safeguard)
* **উদ্দেশ্য:** আর্কিটেকচারাল স্পেকের ধারা ৩.১ ও ৩.২ অনুযায়ী ৭টি রেন্ডার সার্ভিসের কোনো দুটি যাতে ভুলক্রমেও একই Render অ্যাকাউন্টে ডেপ্লয় হয়ে ফ্রি ৭৫০ ঘণ্টার সীমা অতিক্রম না করে তা নিশ্চিত করা।
* **ফাইল পরিবর্তন:**
  - Backend: `infrastructure/mcp-control-plane/src/diagnostics/service_manifest.ts` ও `infrastructure/mcp-control-plane/src/tools/parity.tools.ts`।
* **এক্সেপ্টেন্স ক্রাইটেরিয়া:**
  - অডিটে কোনো অ্যাকাউন্টে ১টির বেশি ওয়েব সার্ভিস পাওয়া গেলে ডিপ্লয়মেন্ট ব্লক এবং অ্যালার্ট ট্রিগার হবে।

### টাস্ক C1: Autonomous Browser Live Screencast & Action Stream
* **উদ্দেশ্য:** WorkspaceDock-এর Browser ট্যাবে এজেন্টের ব্রাউজিং সেশন লাইভ দেখা এবং ইউজার চাইলে টেকওভার করা।
* **ফাইল পরিবর্তন:**
  - Backend: `browser/autonomous_browser.py`, `browser/ghost_tower/`, `core/api/routes/session_takeover.py` (`/api/v1/browser/stream`, `/api/v1/browser/action`)।
  - Frontend: `src/hooks/useBrowserSession.ts` এবং `src/components/workspace/BrowserDockTab.tsx` (WebSocket বেসড ফ্রেম রেন্ডারিং)।
* **এক্সেপ্টেন্স ক্রাইটেরিয়া:**
  - ব্রাউজার টাস্ক চালু করলে ফ্রন্টএন্ড ডকে রিয়েল-টাইমে পেজের স্ক্রিনশট ও অ্যাকশন লগ আপডেট হবে।

### টাস্ক C2: MicroVM Terminal Sandbox Execution Stream
* **উদ্দেশ্য:** এজেন্টের ব্যাশ বা পাইথন কমান্ড এক্সিকিউশনের টার্মিনাল লগ লাইভ স্ট্রিমিং।
* **ফাইল পরিবর্তন:**
  - Backend: `core/api/routes/sandbox_api.py`, `core/microvm_sandbox.py` (`/api/v1/sandbox/terminal/stream`)।
  - Frontend: `src/hooks/useTerminalStream.ts` এবং `src/components/workspace/TerminalDockTab.tsx` (xterm.js ইন্টিগ্রেশন)।
* **নিরাপত্তা গ্যারান্টি:** শুধুমাত্র ভ্যালিড অ্যাডমিন বিয়ারার টোকেন ছাড়া টার্মিনাল রাউটে এক্সেস নিষিদ্ধ।

---

## ৫. Phase 4: Intelligence, Schedule, Voice & Billing

### টাস্ক D1: Deep Research Pipeline & Citation Viewer
* **উদ্দেশ্য:** চ্যাট ইনপুটে থাকা স্পার্কল/ডিপ-রিসার্চ টগল অন থাকলে মাল্টি-স্টেপ ডিপ ওয়েব রিসার্চ সম্পন্ন করে রেফারেন্স ও সাইটেশন সহ রিপোর্ট জেনারেট করা।
* **ফাইল পরিবর্তন:**
  - Backend: `core/api/routes/deep_research.py` (`POST /api/v1/research/deep`)।
  - Frontend: `src/components/ChatInput.tsx` (ইতিমধ্যে টগল যোগ করা হয়েছে), `src/services/chatService.ts` (`deepResearch: boolean` ফ্ল্যাগ পাস করা), `src/components/chat/ResearchReportViewer.tsx` (সাইটেশন লিঙ্ক ও ফুটনোট সহ মার্কডাউন ভিউয়ার)।
* **এক্সেপ্টেন্স ক্রাইটেরিয়া:**
  - ডিপ রিসার্চ প্রম্পট দিলে ব্যাকএন্ড পর্যায়ক্রমে সার্চ, সিন্থেসিস ও ড্রাফটিং সম্পন্ন করে রেফারেন্স লিঙ্ক সহ স্ট্রিম করবে।

### টাস্ক D5: Live Token & Cost Metering Cockpit
* **উদ্দেশ্য:** ইউজারের টোকেন ব্যবহার, প্রোভাইডার কোটা এবং ফ্রি-টিয়ার লিমিট ফ্রন্টএন্ড Usage ট্যাবে রিয়েল ডেটা দিয়ে দেখানো।
* **ফাইল পরিবর্তন:**
  - Backend: `core/api/routes/usage_metrics.py` (`GET /api/v1/usage/summary`)।
  - Frontend: `src/services/usageService.ts` ও `src/stores/useUsageStore.ts`।
  - Frontend: `src/components/views/UsageView.tsx` (মক ডেটার বদলে রিয়েল প্রোভাইডার কোটা ও ব্যবহার গ্রাফ)।

### টাস্ক D3: Scheduled Autonomous Cron Cockpit
* **উদ্দেশ্য:** ব্যাকগ্রাউন্ড রিকারিং টাস্ক (যেমন: দৈনিক মার্কেট রিপোর্ট, ডেটাবেস অপ্টিমাইজেশন, স্ট্যাটাস অডিট) শিডিউল ও মনিটর করার UI।
* **ফাইল পরিবর্তন:**
  - Backend: `core/api/routes/scheduled_tasks.py`, `scripts/scheduled_task_sweep.py` (`GET /api/v1/tasks/scheduled`, `POST /api/v1/tasks/scheduled`)।
  - Frontend: `src/components/views/ScheduledTasksView.tsx` এবং `src/services/scheduledTaskService.ts`।

### টাস্ক D2: Bidirectional Real-Time Voice (Gemini Live WebSocket)
* **উদ্দেশ্য:** চ্যাট বারে থাকা মাইক্রোফোন আইকন চেপে সরাসরি ভয়েস কমান্ড দেওয়া এবং লো-লেটেন্সি অডিও রেসপন্স শোনা।
* **ফাইল পরিবর্তন:**
  - Backend: `core/api/routes/websocket_voice.py`, `skills/voice/` (`/ws/v1/voice/live`)।
  - Frontend: `src/hooks/useVoiceChat.ts` (Web Audio API PCM অডিও ক্যাচিং ও ব্যাকএন্ডে প্রেরণ)।

### টাস্ক D4: Stripe Checkout & Balance Top-up
* **উদ্দেশ্য:** পেইড টিয়ার বা অতিরিক্ত টোকেন ব্যালেন্স টপ-আপের জন্য স্ট্রাইপ চেকআউট ইন্টিগ্রেশন।
* **ফাইল পরিবর্তন:**
  - Backend: `core/api/routes/billing_api.py`, `core/payments.py` (`POST /api/v1/billing/create-checkout-session`)।
  - Frontend: `src/components/modals/BillingModal.tsx` ও `src/services/billingService.ts`।

---

## ৬. ফ্রি-টিয়ার পলিসি সুরক্ষা ও ইনভ্যারিয়েন্টস (Guaranteed Invariants)

| প্রোভাইডার | কোটা সীমা | সেফগার্ড মেকানিজম | ভায়োলেশন প্রতিরোধ |
| :--- | :--- | :--- | :--- |
| **Render** | ৭৫০ ঘণ্টা / অ্যাকাউন্ট / মাস | ৭টি স্বতন্ত্র অ্যাকাউন্ট ও API কি বরাদ্দ | manifest অডিট নিশ্চিত করে কোনো অ্যাকাউন্টে ২য় সার্ভিস থাকবে না |
| **Upstash Redis** | ৫০০,০০০ কমান্ড / অ্যাকাউন্ট / মাস | ৫টি অ্যাকাউন্ট চেইনে মোট ২৫ লাখ কমান্ড পুলিং | প্রতি অ্যাকাউন্টে ৪৫০,০০০ অতিক্রম করলে পরবর্তীটিতে অটো-রোটেট |
| **Supabase Postgres** | ৫০০ MB স্টোরেজ, ১৫ কানেকশন | Supabase Transaction Pooler (Port 6543) বাধ্যতামূলক | কোনো ভারী ফাইল/ভেক্টর Postgres-এ রাখা নিষিদ্ধ (Qdrant-এ সংরক্ষিত) |
| **Cloudflare** | ১০০,০০০ রিকোয়েস্ট / দিন | এজ ক্যাশিং (TTL: 24h) ও মেমরি রাইট ব্যাচিং | প্রতি হার্টবিটে KV রাইট নিষিদ্ধ, কেবল স্ট্যাটাস পরিবর্তন হলে সিঙ্ক |

---

## ৭. ভেরিফিকেশন ও ডেলিভারি ম্যাট্রিক্স (Definition of Done)

প্রতিটি টাস্ক বাস্তবায়নের সময় নিচের তিন স্তরের ভেরিফিকেশন নিশ্চিত করা হবে:

1. **Reflection & Type-Check:**
   - Frontend: `npx tsc --noEmit` দিয়ে নিশ্চিত করা যে কোনো নতুন টাইপ এরর আসেনি।
   - Backend: `python -m py_compile` ও সিনট্যাক্স অডিট।
2. **Smoke Test:**
   - সংশ্লিষ্ট এন্ডপয়েন্টে curl বা লোকাল রিকোয়েস্ট পাঠিয়ে স্ট্যাটাস `200 OK` এবং ভ্যালিড JSON/SSE পে-লোড নিশ্চিত করা।
3. **Commit & Push Discipline:**
   - Backend: কোড পরিবর্তন কমিট করে `origin/main`-এ পুশ (অথবা অনুমোদিত প্রটোকল অনুসারে bridge submission)।
   - Frontend: `f:\supremeai-frontend`-এ কমিট করে পুশ।
   - Wire-Honesty: কোনো অবস্থাতেই মক ডেটাকে লাইভ বলে ফলস স্ট্যাটাস দেওয়া যাবে না।
