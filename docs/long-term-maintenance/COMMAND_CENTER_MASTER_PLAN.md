# 🧠 SupremeAI 2.0 — "AETHEL" Unified Command Center Master Plan

> **Status:** Design / Blueprint (v1.0)
> **Goal:** একটি সত্যিকারের Command Center — সব রিয়েল ডেটা এক জায়গায়, জিরো মক-ডেটা, জিরো সাইলেন্ট ফেইলর, ফুল রিয়েল-টাইম।
> **Normative Rule:** এখানে যা আছে তা "কেমন হতে হবে" — বিদ্যমান ফাইল নিয়ে চিন্তা করা নিষিদ্ধ। Root থেকে ডিজাইন।

---

## ০. প্রায়োরিটাইজড এক্সিকিউশন প্ল্যান (Phase 0)

1. **নীতিমালা ঠিক করা** → ইউনিক ডেটা-ডোমেইন ম্যাপ (কোন ডেটা কোথা থেকে আসবে, প্রতি টাইলে জিরো হার্ডকোড)।
2. **শেল/লেআউট ডিজাইন** → কমান্ড বার + লেফট রেইল + ওয়ার্কস্পেস, ১টি থিম সিস্টেম।
3. **মডিউল ব্লুপ্রিন্ট** → ৮টি ব্যাটল-প্রুফ মডিউল, প্রতিটির KPI + অ্যাকশন + ডেটা-সোর্স + রিয়েল-টাইম চ্যানেল।
4. **রিয়েল-টাইম স্তর** → একক WebSocket/SSE পাইপ → React Query ক্যাশ → ১টি রেন্ডার পাইপলাইন।
5. **সিকিউরিটি ও গভর্নেন্স** → JIT OTP + RBAC + অডিট ট্রেইল প্রতিটি ডেস্ট্রাক্টিভ অ্যাকশনে।
6. **রোডম্যাপ** → ১০ ফেজ ইমপ্লিমেন্টেশন, প্রতিটির ডেলিভারেবল + রেগ্রেশন গেট।

---

## ১. ভিশন ও কোর ফিলোসফি

### ১.১ "True Command Center" মানে কী
- **Command Center ≠ Report Viewer** — প্রতিটি কার্ড শুধু ডেটা দেখায় না, অ্যাকশন ট্রিগার করে।
- **Single Source of Truth** — একটি সংখ্যাও হার্ডকোডেড নয়; প্রতিটি ভ্যালু একটি React Query key বা WS চ্যানেলের সাথে বাঁধা।
- **Pervasive Real-time** — pull/polling নয়, push (WS + SSE)। পর্দা নিজে থেকে "জীবন্ত"।
- **Zero-Cost Stack** — শুধু ফ্রি-টিয়ার (Firebase, Supabase, Upstash Redis, Render/Railway/GCP free)।
- **Self-Healing View** — API DOWN হলে UI কখনো ফ্রিজ/ফাঁকা হবে না; degraded-state + auto-retry + friendly message।

### ১.২ আর্কিটেকচারাল নন-নেগোশিয়েবল (Self-Audit Checklist)
| Blindspot | নিয়ম |
|---|---|
| **Ripple-Effect Guard** | নতুন মডিউল কখনো অন্য মডিউলের স্টেট ভাঙবে না — একমাত্র path হলো কেন্দ্রীয় ইভেন্ট বাস। |
| **Anti-Silent Failure** | কোনো `catch {}` ফাঁকা নয়। প্রতিটি এরর → `dashboard_error_bus` → toast + status। |
| **Stateless Validation** | সার্ভার রিস্টার্ট বা প্যারালাল ইনস্ট্যান্সে UI স্টেট নির্ভরশীল নয় — সব ভারী স্টেট ক্যাশ/সার্ভারে। |
| **Dependency Sync** | শুধু `package.json`/manifest-এ রেজিস্টার্ড ডিপেন্ডেন্সি; রানটাইম ইম্পোর্ট নিষিদ্ধ। |
| **Configuration Drift** | হার্ডকোডেড সিক্রেট জিরো। সব সিক্রেট vault/env থেকে; UI-তে masking। |

---

## ২. ইনফরমেশন আর্কিটেকচার — ডেটা ডোমেইন ম্যাপ

প্রতিটি ডোমেইনের "কোথা থেকে রিয়েল ডেটা আসবে" ঠিক করা হলো:

| Domain | Live Data Source | রিয়েল-টাইম মাধ্যম |
|---|---|---|
| **System Heartbeat** | Backend `/admin-api/metrics`, psutil | WS `metrics.update` (2s) |
| **Traffic** | Redis traffic window `/api/admin/traffic/live` | WS + 30s refetch |
| **Providers & Router** | `/admin-api/providers`, `/admin-api/model-router` | WS `providers.update` |
| **CI/CD** | `/admin-api/ci-logs`, GitHub webhook reports | WS `jobs.status` |
| **Health Map** | `/admin-api/health-map` (GCP/Railway/Render) | WS `health.update` |
| **Events** | `/admin-api/events` (dashboard_events.jsonl) | SSE `dashboard_events` |
| **Logs** | `/admin-api/logs/stream` (tail + follow) | SSE (streaming) |
| **Security** | `/admin-api/security-scan`, audit rules | WS `alerts.emergency` + on-demand scan |
| **Tenants/Users** | `/admin-api/tenant-limits`, `/admin-api/users`, `/admin-api/customers` | CRUD + refetch |
| **Usage & Money** | `/metrics/usage`, CostAuditor, `/admin-api/costs`, `/admin-api/metrics/dashboard` (ROI) | 60s cache-first |
| **Memory/Skills** | Memory store, Skills registry, semantic cache hits | 30s cache-first |
| **Sessions/Workspaces** | `/admin-api/sessions`, `/admin-api/workspaces` | CRUD + refetch |
| **Config & Flags** | `/admin-api/feature-flags`, `/admin-api/settings`, env etag | on-change + etag |
| **Backups** | `/admin-api/backups` | on-action + refetch |
| **Deploy Gate** | Firestore `deploy_gate/status` | WS `jobs.status` + poll |

> 🔒 **নিয়ম:** কোনো প্রদর্শিত সংখ্যায় `Math.random()`, static array বা fallback constant থাকবে না যতক্ষণ না API সত্যিই উত্তর দিতে ব্যর্থ হয় — তখনও তা "degraded (—)" হিসেবে দেখাবে, মক-ভ্যালু নয়।

---

## ৩. ভিজ্যুয়াল ডিজাইন সিস্টেম

### ৩.১ থিম টোকেন (একক সত্য)
```
--sa-cyan:      #00f3ff    (primary / ऊर्जा)
--sa-violet:    #bc13fe    (secondary / intelligence)
--sa-emerald:   #10b981    (healthy / ok)
--sa-amber:     #f59e0b    (warn)
--sa-rose:      #ef4444    (critical / danger)
--sa-bg-0:      #030611    (void bg)
--sa-bg-1:      #0c0d12    (surface)
--sa-bg-2:      #10131c    (raised panel)
--sa-line:      rgba(0,243,255,.14)
--sa-text-0:    #f1f5f9
--sa-text-1:    #94a3b8
--sa-font-mono: 'JetBrains Mono'
--sa-font-hud:  'Space Grotesk'
--sa-glow-cyan: 0 0 12px rgba(0,243,255,.25)
```

### ৩.২ ভিজ্যুয়াল ভাষা (HUD / Sci-Fi Ops)
- **ডার্ক ফার্স্ট**, গ্লো অ্যাকসেন্ট, scanline overlay (এলাকাভেদে), grid background।
- প্রতিটি কার্ড: ১px glowing border + corner brackets; status pill (PULSE dot)।
- প্রতিটি টাইল "alive": খুব সূক্ষ্ম breathe animation যখন WS আপডেট পায়।
- **Font:** HUD headings `Space Grotesk` + mono numbers `JetBrains Mono` (ট্যাবুলার ডিজিট)।
- **4 থিম:** Nexus Dim / Light Ops / Sunset War / Matrix — এক toggle-এ cycle।

### ৩.৩ কম্পোনেন্ট কিট (বিল্ডিং ব্লক)
`KpiTile` · `StatusPill` · `Sparkline` (pure SVG) · `GaugeRing` · `HealthStrip` · `Timeline` · `DataTable` (virtualized) · `LogStream` · `CommandPalette` · `JsonViewer` · `ConfigForm` (masked) · `ConfirmModal` (JIT OTP) · `ToastStack` · `EmptyState` (degraded) · `MetricStrip`

---

## ৪. শেল ও নেভিগেশন আর্কিটেকচার

```
┌────────────────────────────────────────────────────────────────────────┐
│ GLOBAL COMMAND BAR  [PULSE] ⯁ ENV:PROD │ Cmd+K 🔍 │ ⏱ 14:32 │ 👤 God │🔐│
├──────────┬─────────────────────────────────────────────────────────────┤
│          │                                                             │
│  LEFT    │                    WORKSPACE                                │
│  RAIL    │        (active module viewport)                             │
│  ──────  │                                                             │
│  ⌂ DECK  │                                                             │
│  ▸ OPS   │                                                             │
│  ▸ BUILD │                                                             │
│  ▸ OBS   │                                                             │
│  ▸ SEC   │                                                             │
│  ▸ MONEY │   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐              │
│  ▸ SYS   │   │ KPI    │ │ KPI    │ │ KPI    │ │ KPI    │              │
│          │   └────────┘ └────────┘ └────────┘ └────────┘              │
│  ──────  │                                                             │
│  ⚡ ALERT │  [gutter: live event ticker bar]                           │
├──────────┴─────────────────────────────────────────────────────────────┤
│ BOTTOM STATUS DECK   RPS ▪ P95 ▪ ERR% ▪ COST/HR ▪ LAST SYNC ▪ WS ●     │
└────────────────────────────────────────────────────────────────────────┘
```

### ৪.১ গ্লোবাল কমান্ড বার (Top)
1. **System Pulse orb** — সামগ্রিক স্বাস্থ্য (% derived from health-map + metrics); রঙ বদলায় heartbeat-এ।
2. **Environment badge** — PROD/STAGING/DEV + build version + last commit।
3. **⌘K Command Palette** — fuzzy search সব মডিউল, অ্যাকশন, টেন্যান্ট; `/` দিয়ে সরাসরি কমান্ড।
4. **Live clock + timezone।**
5. **Admin identity chip** — name, role badge, "Session JIT 🔐" বাটন (OTP verify/manage)।
6. **Emergency strip collapse button** — প্রথম critical alert-এ অটো-ব্লিঙ্ক।

### ৪.২ লেফট রেইল (নেভিগেশন গ্রুপ)
| গ্রুপ | মডিউল |
|---|---|
| **DECK** | Command Deck (home) |
| **OPERATE** | Agents · Swarm · Tasks & Queues · Sessions · Tenants |
| **BUILD** | Model Router · Providers · Skills · Memory & Knowledge |
| **OBSERVE** | Live Metrics · Logs · Events · CI/CD Pipelines · Health Map · Traffic |
| **SECURE** | Threats · Audit Explorer · Approval Queue · Rules & Policy · Secrets Health · Rate Limits |
| **MONEY** | Cost Auditor · Usage & Billing · Budget Caps · ROI Savings |
| **SYSTEM** | Config Editor · Feature Flags · Workspaces · Backups · Deploy & Gate |

প্রতিটি রেইল-আইটেমে লাইভ badge (e.g., SECURE-এ pending approvals count, MONEY-এ today $)।

### ৪.৩ বটম স্ট্যাটাস ডেক (সবসময় দৃশ্যমান)
রিয়েল-টাইম KPI ticker: `RPS · P95 · P99 · ERR% · ACTIVE AGENTS · CPU · MEM · COST/HR · WS` (সংযোগ ব্লিঙ্ক) · `LAST SYNC 00:02`।

---

## ৫. মডিউল ব্লুপ্রিন্ট (ফিচার স্পেক)

### 🏠 DECK — Command Deck (হোম)
সব প্রশ্নের উত্তর এক স্ক্রিনে:
- **KPI স্ট্রিপ (৬টি):** Active Agents · Active Tasks · RPS · P95 Latency · Error Rate · Cost/hr — সব রিয়েল।
- **System Health Ring** — হেলথ-ম্যাপ (GCP/Railway/Render) + core services একত্রিত %।
- **Live Event Feed** — গ্লোবাল ইভেন্ট টিকারে আসা সাম্প্রতিক ২০টি ইভেন্ট (রঙ-কোডেড severity)।
- **Alert Banner Zone** — critical/high alerts + "ACKNOWLEDGE" বাটন (অডিট-লগড)।
- **Provider Load Donut** — ট্রাফিক ডিস্ট্রিবিউশন (model_call_distribution)।
- **Traffic Sparkline** — গত ৩০ মিনিট RPS (Redis windows থেকে)।
- **Quick Action Grid** — Deploy · Backup Now · Security Scan · Gate Lock/Unlock · New Tenant → প্রতিটি JIT OTP protected।
- **Mini Infra Topology** — ভিজ্যুয়াল নোড (কেন্দ্রীয় orb + cluster), ক্লিকে সংশ্লিষ্ট মডিউল।

### 🤖 OPERATE — Agents
- Agent registry টেবিল: name · role · status (Healthy/Busy/Stalled/Dead) · current task · queue depth · last heartbeat · memory load।
- Row অ্যাকশন: inspect, restart, throttle (RPM), kill — kill/restart-এ JIT OTP।
- Agent timeline (প্রতি এজেন্টের টাস্ক হিস্ট্রি)।
- Live count via WS `metrics.update.active_agents`।

### 🌐 OPERATE — Swarm
- **Swarm Graph** (ReactFlow): নোড = agent/provider/service; edge = 활성 커넥শন; edge width = লোড।
- Live node status: রঙ/glow severity; ডাবল-ক্লিকে detail drawer।
- Swarm broadcast: "pause swarm" / "resume" / "request sync" (JIT OTP)।
- নোড ক্লিক → filtered view বা সংশ্লিষ্ট মডিউল।

### ⚙️ BUILD — Model Router & Providers
- **Provider Cards:** প্রতিটি provider (OpenRouter/Gemini/Groq/DeepSeek/Ollama) — status, latency, latency_history sparkline, rate_limit_remaining/max, models list, mode।
- **Router Panel:** current override, A/B split, cost-quality preference slider, provider_order drag-list।
- **Override Modal:** provider + model + remaining_requests → JIT OTP + audit entry।
- **Traffic Donut:** request distribution per provider/model।

### 🧠 BUILD — Skills & Memory
- Skills marketplace grid: installed/available, enable/disable toggle, version, source (registry BYOC)।
- Memory dashboard: memory banks, entry count, recent writes, semantic cache hit-rate + tokens saved (ROI)।
- Knowledge base stats: docs count, RAG retrieval index status।

### 📈 OBSERVE — Live Metrics (Mini-Grafana)
- মেট্রিক-গ্রুপ breakout: Compute (CPU/GPU/MEM) · Throughput (RPS, total_requests_24h) · Latency (P50/P95/P99 sparkline series) · Reliability (error_rate)।
- প্রতিটি metric: live sparkline (রাখা last N samples in-memory) + gauge।
- Prometheus counters mirror (supremeai_request_total, error_total,...)।
- Time-range selector: 5m/1h/24h — client-side aggregation preserve।

### 📄 OBSERVE — Live Logs
- SSE `logs/stream` — tail -f, auto-scroll toggle (pause on manual scroll)।
- Filter: level (DEBUG→CRITICAL), source, keyword regex; highlight।
- "Jump to event" — ক্লিক করলে আজকের ইভেন্ট টাইমলাইনে যায়।
- Export লগ (client-side blob)।

### 🚀 OBSERVE — CI/CD & Deploy
- Pipeline Rail: recent CI reports → status chips (success/failure/running), commit message, branch, timestamp।
- Workflow Visualizer: ধাপ-ভিত্তিক (lint → test → build → deploy) প্রগতি।
- **Deploy Gate Card:** বর্তমান status (LOCKED/UNLOCKED) + reason + updated_by।
  - Unlock/Lock → JIT OTP + reason (min 10 chars) + audit।
- Trigger deploy / emergency deploy → OTP + confirm; progress toast।

### 🛡️ SECURE — Threat & Audit
- **Security Scan** card: last scan time, finding count by severity, expandable list (item · severity · message), "RE-SCAN" বাটন।
- **Audit Explorer:** টেবিল (timestamp · admin · action · target · result · ip) — source: dashboard_events/audit log; filter/search/paginate।
- **Approval Queue:** pending sensitive ops (যেমন non-God role-এ deploy) — approve/reject with OTP + reason।
- **Rules & Policies:** constitutional rules table (key/value), inline edit → validate → OTP save।
- **Secrets Health:** status-check (হালকা structural check — কখনো real value দেখায় না), weak-secret findings।
- **Rate Limits:** current 429 events, per-IP/tenant limit table, temporarily lift (OTP)।

### 💰 MONEY — Cost & ROI
- **Cost Auditor** rendered report (markdown → formatted panel)।
- **Daily Spend Chart:** usage_metrics থেকে গত ৩০ দিন (total_cost, total_tokens, unique_users)।
- **Forecast Card:** cost_projected_monthly, cost_per_hour live।
- **Budget Caps:** default_cap + per_tenant caps editable (OTP save)।
- **ROI Savings strip:** semantic_cache_hits, estimated_usd_saved, duplicate_executions_prevented, api_cost_reduction_ratio (metrics/dashboard)।

### 👥 OPERATE — Tenants & Users
- **Tenant Table:** tenant_id · org · tier · RPM · tokens/day · concurrent sessions · live usage (requests/tokens/cost today) · quota % bar।
  - Row actions: edit limits, reset usage (OTP), suspend, delete (OTP).
- **Tier matrix editor:** free/starter/pro/enterprise defaults।
- **Users:** CRUD + role/permissions; **impersonate** বাটন (OTP) → impersonation token + session banner "VIEWING AS ...".
- **Sessions & Workspaces** tabs।

### ⚙️ SYSTEM — Config & Control
- **Feature Flags:** toggle switch + rollout % slider + environment; change → cache header (etag) + audit।
- **Config Editor:** env var table — values masked; edit → OTP save → backend etag refetch; "last modified" by etag।
- **Workspaces** admin CRUD।
- **Backup Center:** list (timestamp/size/type/status), "CREATE BACKUP" (progress toast), restore (OTP, never rollback live without confirm+second OTP), retention tag।
- **Settings** (notifications, concurrency caps)।

---

## ৬. রিয়েল-টাইম আর্কিটেকচার (ডেটা প্রবাহ)

```
Backend WS/SSE (events)
   │  dashboard_manager (`/ws/dashboard`)
   │  channels: metrics.update · logs.stream · jobs.status · alerts.emergency · audit.event
   ▼
┌───────────────────────────────┐
│  CommandCenterRealtimeProvider │  ← একটিই WS connection (heartbeat+reconnect+backoff)
│  onEvent(type,payload)          │
│     └─► queryClient.setQueryData(key, patch)   ← React Query = cache-first সত্য
└───────────────────────────────┘
   ▼
useQuery(...) hooks → মডিউল কম্পোনেন্ট (রেন্ডার)
   ▼
মিউটেশন → optimistic update → mutationFn → invalidation → প্রতিটি destructive action-এর আগে
   JIT OTP verify → audit event লিখে পাঠায় → WS-এ ঘুরে আসে সবার কাছে
```

**WS Manager স্পেস (must-have):**
- টোকেন auth, channel subscribe/unsubscribe কমান্ড।
- Heartbeat ping (30s) + পুনঃসংযোগ exponential backoff (max 5), status chip-এ WS state।
- Stale-ডেটা টাইমার: কোনো channel ৬০s+ আপডেট না পেলে `LAST SYNC` amber + auto-refetch।
- Channel → React Query key ম্যাপিং এক জায়গায় (registry টেবিল) — Ripple-Effect Guard।

**SSE:** দুটি ভিন্ন প্রবাহ — `logs/stream` (high frequency) এবং `dashboard_events` — এগুলো WS-এ না এনে আলাদা EventSource, যাতে মেট্রিক্স WS কখনো log flood-এ দম বন্ধ না হয়।

---

## ৭. গভর্নেন্স, রোল ও JIT OTP সিকিউরিটি মডেল

### ৭.১ রোল ম্যাট্রিক্স
| ক্রিয়া | God | Operator | Viewer |
|---|:--:|:--:|:--:|
| দেখুন সব | ✅ | ✅ | ✅ |
| Approve queue / ACK alerts | ✅ | ✅ | ❌ |
| Deploy / Gate override | ✅ | ⚠️ queue→God approve | ❌ |
| Config/Flags/Budget লেখা | ✅ (OTP) | ❌ | ❌ |
| Delete / impersonate / reset | ✅ (OTP) | ❌ | ❌ |

### ৭.২ JIT (Just-In-Time) OTP নিয়ম
- **Trigger set:** deploy · emergency-deploy · gate un/lock · user delete · tenant delete/suspend/reset · impersonate · config write · flag toggle · budget-cap edit · backup restore · role escalate।
- **প্রবাহ:** অ্যাকশন ক্লিক → `JITOTPModal` (reason required) → backend verify (`totp-verify`) → execute → audit event → optimistic state synchronized। OTP ৯০s expiry, ৩ বার fail → lock 5 min।
- UI-তে সব destructive বাটনে ঘড়ি আইকন 🔐 — "will require OTP"।

### ৭.৩ অডিট ট্রেইল
- প্রতিটি অ্যাকশন: `{ ts, admin, role, action, target, params_mask, result, ip, otp_verified }` → dashboard_events JSONL + ফায়ারস্টোর আর্কাইভ।
- **Anti-Silent Failure:** audit লিখতে ব্যর্থ হলে অ্যাকশন সম্পূর্ণ হয় না (atomic rollback)।

### ৭.৪ Rate Limit & Abuse Shield
- Admin API rate limit (existing) + UI-তে 429 → friendly retry-after countdown।
- Session অলস ১৫মিনিট → auto-lock requiring re-OTP (নতুন configurable policy)।

---

## ৮. UI স্টেট ম্যানেজমেন্ট আর্কিটেকচার

```
zustand slices (UI-only state)
├─ useCommandBarStore      (palette open, env badge, clock)
├─ useModuleStore          (active module, saved view filters, drawer state)
├─ useRealtimeStore        (WS status, last-sync-per-channel, subscriptions)
├─ useOtpStore             (JIT OTP modal queue/reason/flow)
└─ useAuditToastStore      (success/error/security toasts)

React Query (server cache — single source of truth)
├─ [cmd,'metrics'] [cmd,'traffic'] [cmd,'providers'] [cmd,'router']
├─ [cmd,'ci'] [cmd,'health'] [cmd,'events'] [cmd,'auth-audit']
├─ [cmd,'tenants'] [cmd,'users'] [cmd,'sessions'] [cmd,'workspaces']
├─ [cmd,'cost'] [cmd,'usage'] [cmd,'roi'] [cmd,'budget-caps']
├─ [cmd,'flags'] [cmd,'settings'] [cmd,'backups'] [cmd,'security']
└─ [cmd,'skills'] [cmd,'memory'] [cmd,'knowledge']
```

**নিয়ম:** মডিউল কম্পোনেন্ট কখনো সরাসরি `fetch()` করবে না — শুধু hooks → queries। মিউটেশন সব mutationFn-এ centralized ধরে, error boundary + toast-এ ঢোকে। কোনো `useState` ডেটা হিসেবে নয়, শুধু UI transient (filters, scroll, modal)।

---

## ৯. পারফরম্যান্স ও রেন্ডার নিয়ম

- **Server cache-first:** `staleTime` প্রতি ডোমেইনে (metrics 15s, health 45s, usage 60s, flags 2min, backups on-action)।
- **Virtualized tables** (>50 rows) — অজস্র DOM থেকে রক্ষা।
- **Sparklines pure SVG** — কোনো chart lib না (হালকা, ল্যাগ-ফ্রি)।
- **Code-splitting:** প্রতিটি মডিউল `React.lazy` → route-level chunk; Command Deck preload শুধু initial।
- **WS payload নিয়ন্ত্রণ:** ২s interval-এ ইতিমধ্যে যা আপডেট হয়েছে তার diff/checksum; full snapshot 30s।
- **P95 render budget:** <100ms interaction; WS→paint path-এ ব্লকিং কাজ জিরো।

---

## ১০. অ্যাক্সেসিবিলিটি, i18n ও কোয়ালিটি গেট

### ১০.১ a11y
- axe-core (Playwright) প্রতিটি মডিউল-রেন্ডারে scan; severity 0 known issues।
- Keyboard-first: ⌘K palette, টেবিল arrow navigation, focus rings glowing।
- High-contrast আলাদা theme token-set + `prefers-reduced-motion` → breathe/scanline বন্ধ।

### ১০.২ i18n (Bangla-first)
- সব লেবেল/টাইটেল bilingual: বাংলা primary + ইংরেজি mono (HUD style) যেমন `মডেল রাউটার · MODEL ROUTER`।
- তারিখ/সংখ্যা `bn-BD` locale formatting; টাইম zone admin-selectable।

### ১০.৩ কোয়ালিটি গেট (প্রতি ফেজ exit-criteria)
1. No hardcoded displayed values (grep `Math.random|> 1000<` guard CI rule)।
2. WS/SSE `onerror` → UI degraded state, NOT silent।
3. Playwright smoke: login→OTP→Deck→each module 200 OK & rendered real data।
4. Bundle: initial chunk < 250KB gz; total < 900KB gz।

---

## ১১. ইমপ্লিমেন্টেশন রোডম্যাপ (১০ ফেজ)

| Ph | নাম | ডেলিভারেবল | Exit Gate |
|----|-----|-----------|-----------|
| P0 | **Data Contracts** | সমস্ত endpoint typed schemas (TS types + zod/OpenAPI gen), রাউটার রেজিস্ট্রি | curl পরীক্ষা, no-mock grep |
| P1 | **Design System + Shell** | টোকেন, কম্পোনেন্ট কিট, কমান্ড বার, রেইল, ওয়ার্কস্পেস, থিমস | axe scan clean |
| P2 | **Realtime Core** | WS manager, SSE bridges, registry→queryClient, status chip | reconnect test |
| P3 | **Command Deck** | KPI strip, health ring, event feed, alerts, quick actions | গেট: সব KPI real |
| P4 | **Observe suite** | Metrics, Logs, Events, CI/CD, Health, Traffic | gate: P95 render |
| P5 | **Operate suite** | Agents, Swarm graph, Tasks, Sessions, Tenants+Users+impersonate | gate: OTP flows |
| P6 | **Build suite** | Router, Providers, Skills, Memory/Knowledge | gate: override OTP |
| P7 | **Secure suite** | Threats, Audit explorer, Approval queue, Rules, Secrets, Rate limits | gate: atomic audit |
| P8 | **Money suite** | Cost, Usage/Billing, Budget caps, ROI | gate: cache-first |
| P9 | **System + polish** | Config/flags, Backups, Deploy/Gate, performance + regression suite | full E2E green |

---

## ১২. টপ-লেভেল কম্পোনেন্ট/ফাইল স্ট্রাকচার (টার্গেট)

```
apps/studio-client/src/
├─ commandcenter/                 # AETHEL কমান্ড সেন্টার (আইসোলেটেড)
│  ├─ main.tsx                    # entry (provider chain)
│  ├─ shell/
│  │  ├─ CommandBar.tsx
│  │  ├─ LeftRail.tsx
│  │  ├─ BottomDeck.tsx
│  │  └─ WorkspaceViewport.tsx
│  ├─ realtime/
│  │  ├─ CommandCenterRealtimeProvider.tsx
│  │  ├─ websocketManager.ts
│  │  ├─ sseBridges.ts
│  │  └─ channelRegistry.ts
│  ├─ modules/
│  │  ├─ deck/  operate/  build/  observe/  secure/  money/  system/
│  ├─ kit/                        # design system কম্পোনেন্ট
│  │  ├─ KpiTile.tsx  Sparkline.tsx  GaugeRing.tsx  LogStream.tsx
│  │  ├─ DataTable.tsx  CommandPalette.tsx  JITOTPModal.tsx  ...
│  ├─ state/                      # zustand slices
│  ├─ data/                       # react-query hooks + types (per domain)
│  └─ styles/tokens.css
backend/api/routes/
├─ commandcenter/                 # aggregate endpoints (ปัจจุบัน admin-api)
│  ├─ overview.py                  # P3 কমান্ড ডেক aggregation (১ রাউন্ড-ট্রিপ)
│  ├─ operate.py  build.py  observe.py  secure.py  money.py  system.py
└─ ws/command_center.py            # বর্ধিত dashboard manager (channels registry)
```

---

## ১৩. ঝুঁকি ও মিটিগেশন

| ঝুঁকি | মিটিগেশন |
|---|---|
| API না থাকা → ড্যাশবোর্ড ফাঁকা | Degraded-state কম্পোনেন্ট + retry + friendly message; কখনো মক নম্বর নয় |
| WS ফ্লাড (logs) | Logs আলাদা SSE channel, metrics WS-এ আলাদা; autoscroll pause |
| টোকেন জাল / privilege escalate | JIT OTP প্রতিটি destructive op; impersonate টোকেন short-TTL + banner |
| OTP ক্লান্তি | শুধু destructive/পরিবর্তনমূলক অপে (read-only-তে নয়); session 15মি রি-অটো-লক |
| Multisource state drift | React Query = একমাত্র সত্য; WS /→ cache; কোনো local store duplicate নয় |
| ফ্রি-টিয়ার কোটার সীমা | Quota ৮০% → provider auto-disable (existing policy); UI-তে quota badges |

---

## ১৪. ডেলিভারি চেকলিস্ট (Elite Gate)

- ✅ Relevant → প্রতিটি মডিউল একটি অপারেশনাল প্রশ্নের উত্তর দেয়
- ✅ No hallucination → ডিসপ্লেতে কোনো ফেক নম্বর নেই
- ✅ Right language → বাংলা-প্রথম, ইংরেজি HUD mono
- ✅ Runnable code → প্রতিটি ফেজ CI-green + playwright
- ✅ Secure → JIT OTP + RBAC + audit atomic
- ✅ No silent failure → error bus + degraded states সর্বত্র
- ✅ Cache-first zero-cost → শুধু ফ্রি-টিয়ার
- ✅ Next step clear → P0 Data Contracts প্রথম তালিকা

