# Admin Dashboard — Tab Audit & Better Plan (2026-08-16)

> Auditor: Kilo | Method: code-level review (`frontend/src/components/admin/*`,
> `frontend/src/hooks/useDashboardData.ts`, `backend/api/routes/admin_dashboard.py`)
> + live backend probe with real admin JWT (Render: `supremeai-backend-docker.onrender.com`).

## ১. সারসংক্ষেপ (Executive Summary)

Admin dashboard টি **ভাঙা নয়** — বরং বেশিরভাগ data tab backend-এর সাথে ওয়্যারড। তবে দুটো স্তরে সমস্যা আছে:
1. **Dead props** — `AdminShell` `gcpHealth={null}` ও `cloudStats={null}` পাঠায়, কিন্তু কম্পোনেন্টগুলো সেগুলো ব্যবহার করে না (তারা React Query hooks ব্যবহার করে)। এটা কোড স্মেল, ফাংশনাল বাগ নয়।
2. **Real backend আছে কিন্তু frontend-এ wire করা হয়নি** — অনেক tab (Memory, Threats, SecurityDashboard, Config, Users, Backups, GitHub, RateLimits, LiveLogs, VisualRulesBuilder, HealthMap) backend endpoint পেলেও হার্ডকোডেড/খালি দেখায়।
3. **Mock "Quick Action" buttons** — Dashboard-এর "System Optimization / Generate Report / Restart Services / Security Scan" বাটনগুলো শুধু UI (setTimeout), backend call নেই।
4. **Static resource numbers** — `CloudOrchestrator` Resource Utilization (CPU 42%, Mem 68%, 1.2 Gbps) হার্ডকোডেড।

**Live probe নিশ্চিত করেছে** যে এই backend endpoints গুলো real data দেয় (200):
`/admin-api/metrics`, `/admin-api/health-map`, `/admin-api/security-scan`,
`/admin-api/model-router`, `/admin-api/providers`, `/admin-api/costs`,
`/admin-api/ci-logs`, `/admin-api/events`, `/admin-api/reports`, `/admin-api/feature-flags`,
`/admin-api/users`, `/admin-api/config`, `/admin-api/roles`, `/admin-api/settings`,
`/admin-api/backups`, `/admin-api/workspaces`, `/admin-api/sessions`, `/admin-api/customers`,
`/admin-api/deploy`, `/admin-api/backup`, `/api/admin/fixes/apply`।

---

## ২. বর্তমান tab গুলো — কি আছে & কিভাবে আছে

Sidebar (11 tab) + Command Palette (২০+ option)। MODULE_MAP অনুযায়ী render হয়।

| Tab (sidebar) | কম্পোনেন্ট | বর্তমান অবস্থা | Data source |
|---|---|---|---|
| DASHBOARD | `Dashboard.tsx` | ✅ কাজ করে | `useDashboardData` hooks → `/admin-api/metrics`, `/health-map`, `/security-scan`, `/ci-logs`, `/events`, `/reports` (live) |
| SYSTEM ALERTS | `AdminAlertsTab.tsx` | ⚠️ খালি/মক | `apiClient` call নেই; backend-এ `/admin-api/events` আছে (wire করা হয়নি) |
| AI CORE (model-router) | `ModelRouter.tsx` | ✅ কাজ করে | `/admin-api/model-router`, `/admin-api/providers` (live) |
| SKILLS & AGENTS | `EnhancedSkillMarketplace.tsx` | ✅ আংশিক | `/api/skills/search`; install/delete মক |
| MEMORY | `MemoryBrowser.tsx` | ❌ মক/খালি | `apiClient` call নেই; backend-এ memory endpoint নেই (build করতে হবে) |
| INFRASTRUCTURE (cloud) | `CloudOrchestrator.tsx` | ⚠️ আংশিক | health-map live, কিন্তু Resource Utilization হার্ডকোডেড |
| DEPLOYMENTS (cicd) | `CICDVisualizer.tsx` | ✅ আংশিক | `/admin-api/feature-flags` live; CI list মক |
| OBSERVABILITY | `ObservabilityDashboard.tsx` | ❌ মক | static arrays |
| SECURITY (threats) | `ThreatDetection.tsx` | ⚠️ আংশিক | `/admin-api/security-scan` আছে কিন্তু component-এ wire নয় |
| SETTINGS (config) | `ConfigEditor.tsx` | ⚠️ আংশিক | `/admin-api/config` আছে, `handleSaveConfig` POST করে কিন্তু GET load নেই |
| TERMINAL (interactive-chat) | `InteractiveChatTab.tsx` | ⚠️ মক | sample conversation; backend chat endpoint বাঁধতে হবে |
| Core Canvas (command-center) | `CommandCenter.tsx` | ⚠️ মক-heavy | ৩৫টা sample object; `/admin-api/commandcenter/*` backend আছে কিন্তু বাঁধা নয় |

Command Palette-এ থাকা কিন্তু sidebar-এ নেই এমন tab গুলো (বেশিরভাগ মক বা খালি):
`logs` (LiveLogs), `costs` (CostAuditor — `/admin-api/costs` live), `health` (HealthMap — `/admin-api/health-map` live),
`users` (UserManager — `/admin-api/users` live), `rules` (VisualRulesBuilder — `/admin-api/rules` live),
`backups` (Backend `/admin-api/backups` আছে, frontend মক), `rate-limits` (RateLimitManager — মক),
`github` (GithubIntegration — মক), `security-dashboard` (SecurityDashboard — মক), `sandbox` (মক)।

**Dead code:** `AdminShell` → `gcpHealth={null}`, `cloudStats={null}` props; `Dashboard` import করে কিন্তু ব্যবহার করে না।

---

## ৩. কি থাকা উচিত & কিভাবে থাকা উচিত (Better Plan)

### A. গঠন (Restructure) — ২০+ ছোট tab-এর বদলে ৬টা গ্রুপ
বর্তমানে tab ছড়িয়ে ছিটিয়ে আছে (Threats vs SecurityDashboard, Security vs commandcenter/security duplicate)।
নিচের ৬ গ্রুপে নিয়ে আসা উচিত:

1. **Command Bridge** (Dashboard + CommandCenter + InteractiveChat + LiveLogs + DynamicPanel)
2. **AI Operations** (ModelRouter + Skills & Agents + Memory)
3. **Infrastructure** (CloudOrchestrator + CICD/Deployments + Observability + HealthMap)
4. **Security** (ThreatDetection + SecurityDashboard + RBAC/Users + Rules + RateLimits)
5. **Admin/Config** (Config + Backups + GitHub + Sessions/Customers)
6. **Developer** (Terminal/Sandbox + Reports)

### B. Wire করতে হবে যা backend-এ ready আছে
| Tab | করণীয় |
|---|---|
| System Alerts | `/admin-api/events` দিয়ে real feed |
| Threats / SecurityDashboard | `/admin-api/security-scan` দিয়ে findings render (একসাথ merge করে ১টা Security tab) |
| Settings/Config | GET `/admin-api/config` + `/admin-api/settings` দিয়ে load, সেভ করা আছে |
| Users/RBAC | `/admin-api/users`, `/admin-api/roles`, `/admin-api/permissions` দিয়ে real CRUD |
| Backups | `/admin-api/backups` + POST `/admin-api/backup` |
| GitHub | `/admin-api/ci-logs` + `/admin-api/workspaces` দিয়ে real |
| RateLimits | backend-এ rate-limit endpoint বাঁধতে হবে (নেই → তৈরি করতে হবে) |
| LiveLogs | SSE `/api/dashboard/stream` (Dashboard-এর SSE hook আছে, reuse করতে হবে) |
| InteractiveChat | backend chat/agent endpoint বাঁধতে হবে |

### C. দ্রুত ফিক্স (low-effort, high-impact)
1. `AdminShell` থেকে `gcpHealth`/`cloudStats` null props সরানো (dead code)।
2. Dashboard-এর "Quick Action" বাটনগুলোকে সত্যি backend call-এ বাঁধা: "Restart Services" → `POST /admin-api/emergency-deploy`, "Security Scan" → `POST` trigger + refetch `/security-scan`, "Generate Report" → `/admin-api/reports` export। না হলে "Demo only" ব্যাজ দেওয়া।
3. `CloudOrchestrator` Resource Utilization বর্তমানে `/admin-api/metrics` দিয়ে বাঁধা — কিন্তু backend ঐ endpoint-এ `cpu_percent`/`memory_percent` দেয় না (শুধু latency/RPS/cost), তাই frontend request throughput (`requests_per_second`) থেকে derived % দেখায় (live, কিন্তু সত্যি system CPU/Mem নয়)। সত্যি system CPU/Mem পেতে backend `/admin-api/metrics` এ এই ফিল্ডগুলো যোগ করতে হবে (P2)।
4. Command Palette-এ যেসব tab backend ছাড়াই মক, সেগুলোকে "Beta / Not connected" ব্যাজ দেওয়া যাতে ইউজার বুঝে।

### D. Build required (backend নেই)
- **Memory** tab → `/admin-api/memory` endpoint + Firestore `ai_memory` collection বাঁধা।
- **RateLimits** → rate-limit stats endpoint তৈরি।

---

## ৪. প্রায়োরিটি রোডম্যাপ

| Priority | Item | Effort |
|---|---|---|
| P0 | Dead props + Dashboard Quick-Action mock সরানো/বাঁধা | S |
| P0 | CloudOrchestrator static → live metrics | S |
| P1 | Alerts / Threats / SecurityDashboard → `/admin-api/events`, `/security-scan` | M |
| P1 | Users/RBAC, Config, Backups → real CRUD (backend ready) | M |
| P1 | LiveLogs via SSE reuse | M |
| P2 | Tab regroup (6 groups) + duplicate remove | L |
| P2 | Memory, RateLimits backend build | L |
| P2 | InteractiveChat backend bind | M |

> সবচেয়ে বড় সমস্যা: dashboard ভাঙা নয়, কিন্তু **অনেক tab "দেখতে আছে কিন্তু data নেই"** — ইউজার ভাবে ভাঙা। তাই P0/P1 wire-আপ করলেই ৮০% সমস্যা সলভ।
