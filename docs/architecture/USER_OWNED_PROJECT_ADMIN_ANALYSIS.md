# SupremeAI: Architecture Analysis & Blueprint
## Transforming from "Platform-Admin Locked" to "User-Owned Project Admin"

> **Status:** Strategic Architectural Blueprint & Control Plane Master Spec (Version 2.3.0 — Codebase Verified & Consolidated)  
> **Target Alignment:** [`docs/architecture/SUPREMEAI_CORE_CONSTITUTION.md`](file:///f:/supremeai/docs/architecture/SUPREMEAI_CORE_CONSTITUTION.md) §7 (*User-Owned SupremeAI*)  
> **Date:** September 2026  
> **Single Source of Truth:** [`STATUS.md`](file:///f:/supremeai/STATUS.md) | [`CHECKPOINT.md`](file:///f:/supremeai/CHECKPOINT.md)  
> **Consolidated Authorities:** Incorporates and unifies canonical control plane boundaries and product surfaces.

---

## 1. Executive Summary & The Core Paradox

### The Core Vision
SupremeAI Core Constitution §7 stipulates:
> **"Every customer/tenant should be able to govern the SupremeAI environment they own within platform, security and policy boundaries... Users should be able to discover and activate only the capabilities they need."**

In simple terms:
- **Platform Owner (Root Admin):** Manages the SupremeAI global infrastructure, cluster health, shared LLM pools, server topologies, system-wide FinOps, and cross-tenant platform billing/abuse.
- **Customer / User (Project Admin):** Is the sovereign **Owner & Administrator** of their own project workspace, GitHub repositories, cloud deployments, browser automation sessions, agent swarms, and HITL decision workflows.

### The Current Code Reality (The Paradox & Progress)
During our in-depth codebase audit across backend routes, MCP tools, and frontend views:
1. **Progress Made:**
   - **Auth dependency separation:** Began with [`get_current_platform_admin`](file:///f:/supremeai/backend/api/dependencies.py#L136-L151) in [`backend/api/dependencies.py`](file:///f:/supremeai/backend/api/dependencies.py) (checking `settings.admin_emails`).
   - **Tenant binding in models:** Tenant columns (`tenant_id`, `created_by`, `payload_hash`, `expires_at`) exist in [`backend/models/pending_tasks.py`](file:///f:/supremeai/backend/models/pending_tasks.py#L70-L85) with tenant filtering supported in `list_pending(tenant_id)`.
   - **Browser session scoping:** Browser sessions and actions (`/automation/sessions`, `/automation/actions`, `/tasks`) in [`backend/api/routes/browser.py`](file:///f:/supremeai/backend/api/routes/browser.py) are user-scoped via `get_current_user_token`.
   - **Frontend route parity:** Parity significantly improved in [`frontend/src/App.tsx`](file:///f:/supremeai/frontend/src/App.tsx) and [`frontend/src/config/navigationRegistry.ts`](file:///f:/supremeai/frontend/src/config/navigationRegistry.ts) (Deep Research, Scheduled Tasks, Neural Memory, API Keys, and MCP Connector are now fully wired).
2. **Remaining Paradox:**
   - Despite backend data models supporting tenants, crucial administrative capabilities remain gated behind global platform checks:
     - **Target binding:** [`backend/api/routes/workspaces_route.py`](file:///f:/supremeai/backend/api/routes/workspaces_route.py) requires `Depends(get_current_admin)` + TOTP OTP header (`X-JIT-OTP`), and [`backend/core/target_registry.py`](file:///f:/supremeai/backend/core/target_registry.py) is an unpartitioned in-memory singleton.
     - **HITL approvals:** [`backend/api/routes/approval_manager.py`](file:///f:/supremeai/backend/api/routes/approval_manager.py) locks `/api/v1/hitl/pending` and `/approve/{task_id}` behind `verify_admin_session_fail_closed` without passing `current_user.tenant_id`.
     - **DevOps & Code Quality:** [`backend/api/routes/tools_ops.py`](file:///f:/supremeai/backend/api/routes/tools_ops.py) gates all endpoints with `_require_admin`, bundling harmless code-smell analysis and vulnerability scans with on-prem Docker/Helm generation.
     - **Browser Credentials & Crawling:** [`backend/api/routes/browser.py`](file:///f:/supremeai/backend/api/routes/browser.py#L312-L389) locks `/credentials`, `/urls/allowed`, and `/admin/policy` behind `require_admin_token`, while [`backend/api/routes/crawler_admin.py`](file:///f:/supremeai/backend/api/routes/crawler_admin.py) requires `Depends(get_current_admin)` at router level.
     - **MCP Tools:** [`backend/tools/mcp/mcp_workspace.py`](file:///f:/supremeai/backend/tools/mcp/mcp_workspace.py), [`backend/tools/mcp/mcp_cloud_deploy.py`](file:///f:/supremeai/backend/tools/mcp/mcp_cloud_deploy.py), [`backend/tools/mcp/mcp_github_cicd.py`](file:///f:/supremeai/backend/tools/mcp/mcp_github_cicd.py), and [`backend/tools/mcp/mcp_neon.py`](file:///f:/supremeai/backend/tools/mcp/mcp_neon.py) enforce server-level `is_admin_authorized()` checks.
     - **Data isolation leaks:** [`backend/api/routes/repos.py`](file:///f:/supremeai/backend/api/routes/repos.py) and [`backend/api/routes/usage_metrics.py`](file:///f:/supremeai/backend/api/routes/usage_metrics.py) lack `tenant_id` filtering on database queries.

---

## 2. Canonical Control Plane & Surface Architecture

### 2.1 Canonical Authorities & Information Architecture

| Concern | Canonical Authority | Compatibility / Governance Rule |
|---|---|---|
| **Identity & Session** | [`frontend/src/store/authStore.ts`](file:///f:/supremeai/frontend/src/store/authStore.ts) | Do not read role from URL or ad-hoc storage keys. Server JWT is final. |
| **Admin Step-Up** | [`frontend/src/store/adminStore.ts`](file:///f:/supremeai/frontend/src/store/adminStore.ts) | Keep separate from regular user session until backend unification is complete. |
| **Route UX Policy** | [`frontend/src/auth/routePolicies.ts`](file:///f:/supremeai/frontend/src/auth/routePolicies.ts) | Backend authorization remains authoritative over frontend navigation. |
| **Visible Navigation** | [`frontend/src/config/navigationRegistry.ts`](file:///f:/supremeai/frontend/src/config/navigationRegistry.ts) | Deprecated advanced routes remain routable but are not shown in core user navigation. |
| **Command Access** | [`frontend/src/config/commandRegistry.ts`](file:///f:/supremeai/frontend/src/config/commandRegistry.ts) | Commands are filtered by runtime portal context. |
| **User Shell** | [`frontend/src/components/layout/WorkspaceLayout.tsx`](file:///f:/supremeai/frontend/src/components/layout/WorkspaceLayout.tsx) | Routes through Unified App Shell. |
| **Shared UI State** | [`frontend/src/hooks/useWorkspaceSettings.ts`](file:///f:/supremeai/frontend/src/hooks/useWorkspaceSettings.ts) | Single source of truth for modular layout & settings. |
| **Server Data** | TanStack Query (`@tanstack/react-query`) | Direct server caching; do not mirror query data into Zustand without documented need. |

### 2.2 Portal & Route Ownership Boundaries

- **User Workspace (`/workspace/*`, `/projects`, `/activity`, `/settings`):** Outcome-oriented user surface. Default navigation is clean (Home, AI Studio, Agents, Deep Research, Scheduled Tasks, Skills, Integrations, Usage, Billing, Settings).
- **Tenant Admin Console (`/tenant-admin/*`):** Tenant-scoped administration requiring project/tenant admin permissions (members, capability activation, project HITL approvals, integrations, usage limits, audit logs).
- **Platform Root Console (`/admin/*`, `/platform/*`):** Platform/developer operations requiring root platform permissions (`get_current_platform_admin`).
- **Capability Execution Boundary (`/api/v1/capabilities/*`):** Governed execution boundary; not a substitute for portal authorization.

```text
User / Project Admin / Agent
  -> Chat or Dashboard
  -> CapabilityRequest
  -> Central discovery and policy
  -> MCP / control interface
  -> Circle adapter
  -> Backend engine / provider
  -> Verification
  -> Audit and reusable experience
```

---

## 3. Comprehensive Inventory of Admin-Locked Features & Architectural Gaps

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        SUPREMEAI CURRENT CODE CONTROL MODEL                            │
│                                                                                        │
│   PLATFORM ROOT ADMIN (Tier 1)                 PROJECT CUSTOMER / TENANT (Tier 2)      │
│   [Full Platform Infrastructure Access]        [Current Status Across Codebase]        │
│   ├── Target Platform Registry                 ├── Target Binding ❌ (Admin OTP locked) │
│   ├── Cloud Deployment Engines                 ├── Cloud Deployments ❌ (Admin env lock)│
│   ├── GitHub PR & CI/CD Automation             ├── GitHub PRs ❌ (Static repo lock)     │
│   ├── HITL Approvals & Decision State          ├── HITL Approvals ❌ (Admin session)    │
│   ├── Browser Credentials & URL Policies       ├── Browser Sessions ✅ / Vault ❌       │
│   ├── Self-Evolution & Librarian Queue         ├── Skill Catalog ✅ / Quarantines ❌    │
│   ├── Site Actions & UI Healing                ├── Site Actions ❌ (No tenant_id)       │
│   ├── Code Smell & Vuln Scanner Tooling        ├── Code Ops ❌ (_require_admin bundled) │
│   ├── Neon Branching & DDL Execution           ├── DB Branching ❌ (is_admin_authorized)│
│   ├── Root Telegram Commands & SysStatus       ├── Telegram Admin ❌ (Hardcoded Chat ID)│
│   ├── Living Brain & Learning Observability    ├── Neural Memory ✅ / Engine Pulse ❌   │
│   ├── Tenant Quotas & Execution Policies       ├── Quota Mgmt ❌ (Admin-only policy)    │
│   └── Global Cross-Tenant Aggregation          └── Cross-Tenant Repos/Usage Query ⚠️    │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### Category A: Workspaces & Repository Binding (প্রোজেক্ট রেপো বাইন্ডিং)

| Component | Code Location | Enforced Gate | Current Impact on Customer |
|---|---|---|---|
| **Target Binding** | [`backend/api/routes/workspaces_route.py`](file:///f:/supremeai/backend/api/routes/workspaces_route.py) | `prefix="/admin-api/workspaces"`, `Depends(get_current_admin)`, `check_totp_code` (`X-JIT-OTP`) | Customers cannot bind their own GitHub repository or cloud target with READ_ONLY or FULL_CONTROL scope. Requires admin token AND valid JIT OTP header. |
| **Workspace Context** | [`backend/tools/mcp/mcp_workspace.py`](file:///f:/supremeai/backend/tools/mcp/mcp_workspace.py#L190-L198) | `is_admin_authorized()` in `workspace_set_context` | When agents execute MCP workspace operations for administrative projects (`WorkspaceType.ADMIN_PANEL`), the tool rejects unless global `ADMIN_AUTHORIZED=true` is set. |

- **Root Cause & Code Reality:** [`backend/core/target_registry.py`](file:///f:/supremeai/backend/core/target_registry.py) stores `_targets: dict[str, TargetEntity]` in an unpartitioned in-memory singleton with a hardcoded `main-repository` default. It lacks tenant partition keys (`tenant_id`), meaning target binding is treated as a global platform operation rather than tenant-scoped project workspaces.

---

### Category B: Cloud Deployments & Hosting (নিজস্ব ক্লাউড ডিপ্লয়মেন্ট)

| Component | Code Location | Enforced Gate | Current Impact on Customer |
|---|---|---|---|
| **Cloud Deploy Service** | [`backend/tools/mcp/mcp_cloud_deploy.py`](file:///f:/supremeai/backend/tools/mcp/mcp_cloud_deploy.py) | `is_admin_authorized()` in `cloud_deploy_service` | Agent cannot deploy customer apps to Render, Railway, or Oracle Cloud on the user's behalf without `ADMIN_AUTHORIZED=true`. |
| **Cloud Scale & Status** | [`backend/tools/mcp/mcp_cloud_deploy.py`](file:///f:/supremeai/backend/tools/mcp/mcp_cloud_deploy.py) | `is_admin_authorized()` in `cloud_scale_service`, `cloud_get_deploy_status` | Customers cannot scale their project services or query deploy status via agent. |
| **On-Premise & Docker/Helm** | [`backend/api/routes/tools_ops.py`](file:///f:/supremeai/backend/api/routes/tools_ops.py#L18-L34) | `router` level `_require_admin` (`payload.get("role") != "admin"`) | Customers cannot generate Helm charts or Docker Compose deployment files (`/tools/devops/on-prem/docker-compose`, `/tools/devops/on-prem/helm`) for their own on-prem project infrastructure. |

- **Root Cause & Code Reality:** Deployment tools pull credentials directly from global platform settings (`_get_render_api_key()`, `_get_railway_token()`, `_get_oracle_api_key()`). There is no mechanism for tenants to supply their own cloud provider tokens or target their own isolated project environments.

---

### Category C: GitHub CI/CD & Pull Request Automation (গিটহাব পিআর ও সিআই)

| Component | Code Location | Enforced Gate | Current Impact on Customer |
|---|---|---|---|
| **Create Pull Request** | [`backend/tools/mcp/mcp_github_cicd.py`](file:///f:/supremeai/backend/tools/mcp/mcp_github_cicd.py) | `is_admin_authorized()` in `github_create_pull_request` | Customers cannot have the agent open a Pull Request against their own GitHub repository. |
| **Run Auto-Fix** | [`backend/tools/mcp/mcp_github_cicd.py`](file:///f:/supremeai/backend/tools/mcp/mcp_github_cicd.py) | `is_autofix_authorized()` in `github_run_auto_fix` | Auto-fix workflow requires platform-level `AUTOFIX_AUTHORIZED=true`. |
| **Trigger Workflows** | [`backend/tools/mcp/mcp_github_cicd.py`](file:///f:/supremeai/backend/tools/mcp/mcp_github_cicd.py) | `is_admin_authorized()` in `github_trigger_workflow` | Customers cannot run CI/CD workflows for their own projects. |

- **Root Cause & Code Reality:** `mcp_github_cicd.py` uses a single static repository (`GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "SaifulHaqueNiloy/supremeai")`) and single static `GITHUB_TOKEN`. It does not accept user-specified repos or tenant GitHub tokens.

---

### Category D: Human-in-the-Loop (HITL) Approvals (টাস্ক ও কোড অনুমোদন)

| Component | Code Location | Enforced Gate | Current Impact on Customer |
|---|---|---|---|
| **Pending Approvals** | [`backend/api/routes/approval_manager.py`](file:///f:/supremeai/backend/api/routes/approval_manager.py#L99-L105) | `verify_admin_session_fail_closed` on `/api/v1/hitl/pending` | Customer cannot retrieve tasks requiring review for their own workspace. |
| **Approve / Reject Task** | [`backend/api/routes/approval_manager.py`](file:///f:/supremeai/backend/api/routes/approval_manager.py#L107-L130) | `verify_admin_session_fail_closed` on `/approve/{task_id}`, `/reject/{task_id}` | Only users with a valid platform admin cookie/session can approve or reject tasks. |
| **Cancel Task** | [`backend/api/routes/approval_manager.py`](file:///f:/supremeai/backend/api/routes/approval_manager.py#L216-L230) | `verify_admin_session_fail_closed` on `/cancel/{task_id}` | Customers cannot cancel tasks initiated by their own agents. |

- **Root Cause & Code Reality:** In [`backend/models/pending_tasks.py`](file:///f:/supremeai/backend/models/pending_tasks.py#L70-L85), the schema already includes `tenant_id` and `created_by` columns, and `list_pending(tenant_id: str | None)` accepts a tenant filter! However, [`backend/api/routes/approval_manager.py`](file:///f:/supremeai/backend/api/routes/approval_manager.py#L104) calls `list_pending()` with zero arguments and guards the entire endpoint behind `verify_admin_session_fail_closed`.

---

### Category E: Browser Automation, Crawling & Scraper (ওয়েব অটোমেশন ও স্ক্র্যাপিং)

| Component | Code Location | Enforced Gate | Current Impact on Customer |
|---|---|---|---|
| **Crawl Policy Engine** | [`backend/api/routes/crawler_admin.py`](file:///f:/supremeai/backend/api/routes/crawler_admin.py#L21-L25) | `router` level `Depends(get_current_admin)` | Customers cannot configure which domains their agents can crawl, rate limits, or depth rules (`/api/v1/admin/crawler/policies`). |
| **Browser Credentials Vault** | [`backend/api/routes/browser.py`](file:///f:/supremeai/backend/api/routes/browser.py#L312-L580) | `Depends(require_admin_token)` on `POST /credentials`, `/credentials/{id}/use`, `DELETE /credentials/{id}` | Storing or utilizing login credentials for browser automation sessions requires platform admin token. |
| **URL Allowed / Denied Rules** | [`backend/api/routes/browser.py`](file:///f:/supremeai/backend/api/routes/browser.py#L655-L700) | `Depends(require_admin_token)` on `/urls/allowed`, `/urls/denied`, `/urls/allowAll`, `/urls/requests/{id}/decision` | Project owners cannot whitelist or authorize URLs their browser agents are permitted to visit. |
| **Autonomous Web Automation** | [`backend/api/routes/browser.py`](file:///f:/supremeai/backend/api/routes/browser.py#L48-L100) | Authenticated user (`get_current_user_token`) with owner scoping | `/automation/sessions`, `/automation/actions`, `/tasks`, `/policy` are owner-scoped, but governance and credentials are admin-locked. |

- **Root Cause & Code Reality:** Session automation is owner-scoped, but the governance layer (credentials, crawl policies, URL whitelist decisions, and admin policies) was routed through admin gates to enforce safety, locking out legitimate project admins from controlling their own browser agents.

---

### Category F: Self-Evolution, Swarm Architect & Skill Governance (সেলফ-ইভোলিউশন)

| Component | Code Location | Enforced Gate | Current Impact on Customer |
|---|---|---|---|
| **Evolution Forge & Swarm UI** | [`frontend/src/config/navigationRegistry.ts`](file:///f:/supremeai/frontend/src/config/navigationRegistry.ts#L125-L129) | `status: 'deprecated'` for `nav-swarm`, `nav-evolution-forge`, `nav-architect-tower`, `nav-runs` | Self-evolution and swarm topology are routable in `App.tsx` but marked deprecated in user navigation rails. |
| **Evolution API Endpoints** | [`backend/api/routes/evolution.py`](file:///f:/supremeai/backend/api/routes/evolution.py#L51-L135) | `require_admin_token` on `/evolution/start`, `/metrics`, `/quarantine`, `/auto-patch`, `/calibration-report` | Project owners cannot inspect evolutionary calibration, token estimation errors, or proposal success rates for their own runs. |
| **Librarian Queue** | [`backend/api/routes/admin_librarian.py`](file:///f:/supremeai/backend/api/routes/admin_librarian.py#L10-L15) | `router` level `Depends(get_current_admin)` | Customers cannot review quarantine proposals or approve ephemeral AI patches for skills. |

- **Root Cause & Code Reality:** Self-evolution was originally conceived as a single global engine modifying the server runtime (`skills/` on disk), instead of tenant-scoped custom skills sandboxed in isolated tenant storage.

---

### Category G: Site Actions & UI Auto-Healing (সাইট অ্যাকশন রুলস)

| Component | Code Location | Enforced Gate | Current Impact on Customer |
|---|---|---|---|
| **Site Action Registry** | [`backend/api/routes/site_actions.py`](file:///f:/supremeai/backend/api/routes/site_actions.py) | `router` level `Depends(get_current_admin)` | Customers cannot register site actions (e.g. click selector patterns, fallback selectors) for their web apps. |
| **Selector Healing Review** | [`backend/api/routes/selector_healing.py`](file:///f:/supremeai/backend/api/routes/selector_healing.py) | `router` level `Depends(get_current_admin)` | Customers cannot review or approve healed CSS/XPath selectors detected by Playwright agents. |

- **Root Cause & Code Reality:** Site actions are stored in `data/site_actions.db` (SQLite) without a `tenant_id` column. Because all records are unpartitioned, endpoints cannot safely expose writes to non-admin users without risking cross-tenant pollution.

---

### Category H: Code Quality, Smell Detection & Vulnerability Prediction (কোড কোয়ালিটি)

| Component | Code Location | Enforced Gate | Current Impact on Customer |
|---|---|---|---|
| **Code Smell Detector** | [`backend/api/routes/tools_ops.py`](file:///f:/supremeai/backend/api/routes/tools_ops.py#L34-L46) | `router` level `_require_admin` on `POST /tools/code/smell` | Customers cannot invoke automated code smell detection across their project repository via API. |
| **Vulnerability Predictor** | [`backend/api/routes/tools_ops.py`](file:///f:/supremeai/backend/api/routes/tools_ops.py#L48-L60) | `router` level `_require_admin` on `POST /tools/security/predict` | Customers cannot scan diffs or files for vulnerability patterns using SupremeAI security tooling. |
| **Domain Adapter & Skill Recommender** | [`backend/api/routes/tools_ops.py`](file:///f:/supremeai/backend/api/routes/tools_ops.py#L140-L175) | `router` level `_require_admin` on `/tools/learning/domain/adapt`, `/tools/learning/skills/recommend` | Customers cannot trigger domain adaptation or receive tailored skill recommendations for their project. |

- **Root Cause & Code Reality:** In `tools_ops.py`, DevOps write operations (Docker Compose / Helm chart generation) and read-only analysis tools (smell detection, vulnerability prediction) are bundled under a single router gated by `_require_admin`.

---

### Category I: Database Branching & Destructive DDL (ডাটাবেস ব্রাঞ্চিং ও কুয়েরি)

| Component | Code Location | Enforced Gate | Current Impact on Customer |
|---|---|---|---|
| **Neon Branch Management** | [`backend/tools/mcp/mcp_neon.py`](file:///f:/supremeai/backend/tools/mcp/mcp_neon.py) | `is_admin_authorized()` in `neon_create_branch`, `neon_delete_branch` | Customers cannot have AI agents create isolated preview branches of their Neon Postgres database or delete temporary branches. |
| **Destructive SQL Guard** | [`backend/tools/mcp/mcp_neon.py`](file:///f:/supremeai/backend/tools/mcp/mcp_neon.py), [`backend/tools/mcp/mcp_supabase.py`](file:///f:/supremeai/backend/tools/mcp/mcp_supabase.py) | `is_admin_authorized()` on queries containing `DROP`, `DELETE`, `TRUNCATE`, `ALTER` | Table migrations and schema updates are blocked unless global `ADMIN_AUTHORIZED=true` is set. |

- **Root Cause & Code Reality:** The DDL guard checks `is_admin_authorized()` against server environment variables rather than checking if the target database connection string belongs to the tenant's own external database resource.

---

### Category J: Telegram Bot Autonomous Admin & 2FA Challenges (টেলিগ্রাম কন্ট্রোল)

| Component | Code Location | Enforced Gate | Current Impact on Customer |
|---|---|---|---|
| **Admin Telegram Control** | [`backend/tools/social/telegram_bot.py`](file:///f:/supremeai/backend/tools/social/telegram_bot.py#L310-L325) | `is_admin(chat_id)` checks `ADMIN_TELEGRAM_CHAT_ID`, `TELEGRAM_CHAT_ID`, or `"7804133572"` | Only the platform root admin gets the administrative dashboard, `/sys_status`, `/backup_now`, and `/admin`. |
| **Critical Command Approval** | [`backend/tools/social/telegram_bot.py`](file:///f:/supremeai/backend/tools/social/telegram_bot.py) | `not self.is_admin(chat_id)` rejects critical actions with "Access Denied" | Customers managing their projects via Telegram cannot approve critical actions via TOTP 2FA. |

- **Root Cause & Code Reality:** In `telegram_bot.py`, admin status is determined strictly by comparing `chat_id` against static environment variables or hardcoded `"7804133572"`. There is no link between Telegram accounts and tenant project ownership.

---

### Category K: Living Brain & Self-Sufficiency Analytics (লার্নিং ও মেমোরি ভিজিবিলিটি)

| Component | Code Location | Enforced Gate | Current Impact on Customer |
|---|---|---|---|
| **Living Brain Metrics** | [`backend/api/routes/living_brain.py`](file:///f:/supremeai/backend/api/routes/living_brain.py) | `router` level `Depends(get_current_admin)` | Customers cannot see how well SupremeAI has adapted to their project domain, learning progress, and self-sufficiency rate (`/api/living-brain/status`, `/metrics`). |
| **Learning Timeline & Costs** | [`backend/api/routes/living_brain.py`](file:///f:/supremeai/backend/api/routes/living_brain.py) | `router` level `Depends(get_current_admin)` | Learning timeline events and cost breakdowns are visible only to platform admins. |

- **Root Cause & Code Reality:** `living_brain.py` aggregates data from the global `SupremeLearningEngine` and `SupabaseStore` without tenant filtering. Exposing this directly without tenant isolation would leak cross-tenant system metrics.

---

### Category L: Tenant Limits, Sub-User RBAC & Execution Policies (টিম ও কোটা কন্ট্রোল)

| Component | Code Location | Enforced Gate | Current Impact on Customer |
|---|---|---|---|
| **Platform Tenant Management** | [`backend/api/routes/tenant_admin.py`](file:///f:/supremeai/backend/api/routes/tenant_admin.py) | `router` level `Depends(get_current_platform_admin)` | Strictly guarded for platform administration (tenant creation, tier updates, global billing), which is correct. However, organization owners lack a delegated sub-user quota endpoint. |
| **Execution Timeout & Budgets** | [`backend/api/routes/execution_policies.py`](file:///f:/supremeai/backend/api/routes/execution_policies.py) | `router` level `Depends(get_current_admin)` | Project owners cannot configure maximum compute budget (USD) or timeout windows for their project workflows (`/api/admin/execution-policies`). |

- **Root Cause & Code Reality:** `execution_policies.py` operates on a global `ExecutionPolicy` table without tenant partitioning. While platform-level limits are already correctly guarded by `get_current_platform_admin`, project-level budget caps lack a dedicated tenant-scoped API.

---

### Category M: Data Leakage & Cross-Tenant Isolation Gaps (ক্রস-টেন্যান্ট আইসোলেশন গ্যাপ)

| Component | Code Location | Vulnerability / Gap | Current Impact on Customer |
|---|---|---|---|
| **Repository Listing** | [`backend/api/routes/repos.py`](file:///f:/supremeai/backend/api/routes/repos.py#L41-L67) | `select("*").eq("status", status)` without `tenant_id` filter; `POST /` inserts without `owner_id` | `GET /repos/` lists all repositories from `github_repos` across all users; any user can view or modify other tenants' repos. |
| **Usage Metrics Query** | [`backend/api/routes/usage_metrics.py`](file:///f:/supremeai/backend/api/routes/usage_metrics.py#L24-L43) | `select("*")` on `usage_metrics` without user/tenant filter | Any authenticated user can view aggregated global platform usage data. |

- **Root Cause & Code Reality:** `repos.py` and `usage_metrics.py` query Supabase directly without applying `eq("tenant_id", current_tenant)` or `eq("owner_id", user_id)`.

---

### Category N: Frontend Workspace State & Parity (ইউজার ইউআই বনাম অ্যাডমিন ইউআই)

| Area | What Platform Admin Has (`AdminShell`) | What Customer Sees (`UserDashboard` / `WorkspaceModulePage` / `App.tsx`) |
|---|---|---|
| **Projects & Targets** | Multi-platform target binding & scope selection | Static card in `WorkspaceModulePage.tsx:7` ("A home for every outcome") |
| **Activity & Logs** | Live WebSocket log streamer (`LiveLogs`), audit events | Static action cards in `WorkspaceModulePage.tsx:8` ("Review recent events", "Export an audit view") |
| **Runs & Health** | Observability, Topology Map, Incident Alerts | Static placeholder card in `WorkspaceModulePage.tsx:10` |
| **Approvals** | Interactive `ApprovalQueue` with diff review & OTP | Deprecated or restricted to platform admin session |
| **Wired Panels (Resolved)** | Full admin controls | ✅ `DeepResearchPanel` (`/research`), `ScheduledTasksPanel` (`/scheduled-tasks`), `CostDashboard` (`/usage`), `MemoryPanel` (`/memory`), `SecretsPage` (`/settings/api-keys`), and `MCPConnector` (Integrations tab) are now live for authenticated users. |

---

## 4. The Target Architecture: Two-Tier Governance Model

To restore alignment with the SupremeAI Core Constitution, we enforce the **Two-Tier Governance Model**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TWO-TIER GOVERNANCE MODEL                       │
├───────────────────────────────────┬────────────────────────────────────┤
│     TIER 1: PLATFORM ROOT ADMIN   │      TIER 2: PROJECT ADMIN (TENANT)│
│     (Owner of SupremeAI Platform) │      (Owner of Project / Workspace)│
├───────────────────────────────────┼────────────────────────────────────┤
│ • Server & Cluster Topology       │ • Target Repository Binding        │
│ • Global Cloud Provider Keys      │ • Project Deployment & Scaling     │
│ • Platform-Wide Rate Limits       │ • Project-Level HITL Approvals     │
│ • System Database Migrations      │ • Project Browser Automation       │
│ • Platform FinOps & Infrastructure│ • Tenant Vault & Secrets           │
│ • Cross-Tenant Security Audit     │ • Project Agents & Swarm Config    │
│ • Core Constitution Governance    │ • Code Smell & Vuln Scanning       │
│ • Global Fail-Closed Interceptors │ • Project Neon DB Preview Branches │
│ • Global Abuse Monitoring         │ • Project Execution Policy/Budgets │
│ • Root Telegram Command Center    │ • Project-Level Audit Logs & Runs  │
└───────────────────────────────────┴────────────────────────────────────┘
```

---

## 5. Step-by-Step Evolution Roadmap & Current Implementation Status

### Phase 1: Authentication & Role Differentiation
- [x] **Platform Admin Distinction:** Created `get_current_platform_admin` in [`backend/api/dependencies.py`](file:///f:/supremeai/backend/api/dependencies.py#L136-L151) (enforces `settings.admin_emails` check for cross-tenant operations).
- [ ] **Project Admin Helper:** Add `get_project_admin`: Grants administrative privileges scoped strictly to the user's specific `tenant_id`.
- [ ] **Tenant Scope Propagation:** Ensure `tenant_id` and project role (`role: "owner" | "admin" | "member"`) are consistently available in all JWT and request state contexts.

### Phase 2: Decoupling the MCP Tools
- [ ] **`mcp_workspace.py`**:
  - Replace `is_admin_authorized()` with tenant-isolated workspace checks (`tenant_id == session.tenant_id`).
  - Allow users to bind repos and directory contexts within their own tenant sandbox.
- [ ] **`mcp_cloud_deploy.py`**:
  - Allow tenants to supply their own Render/Railway/Vercel API tokens (stored in encrypted tenant vault).
  - Check project ownership before triggering deployments.
- [ ] **`mcp_github_cicd.py`**:
  - Inject tenant-specific GitHub PAT / OAuth tokens into requests so agents can create PRs directly in customer repositories.
- [ ] **`mcp_neon.py` & `mcp_supabase.py`**:
  - Distinguish between platform databases and tenant-owned database connections; allow DDL operations on customer databases.

### Phase 3: Tenant-Scoped HITL Approval Manager & Code Review
- [ ] Refactor [`backend/api/routes/approval_manager.py`](file:///f:/supremeai/backend/api/routes/approval_manager.py):
  - Pass `current_user.tenant_id` to `list_pending(tenant_id)` in `GET /api/v1/hitl/pending`.
  - Allow project owners to approve tasks for their own repositories and skills without requiring Platform God Mode.
- [ ] Make [`backend/api/routes/tools_ops.py`](file:///f:/supremeai/backend/api/routes/tools_ops.py) code smell and vulnerability prediction endpoints accessible to project owners for their own codebase (split DevOps file writes from read-only code analysis).

### Phase 4: Safe Multi-Tenant Browser Automation & Crawling
- [ ] Make browser credentials vault (`/api/browser/credentials` in [`backend/api/routes/browser.py`](file:///f:/supremeai/backend/api/routes/browser.py)) owner-scoped rather than requiring `require_admin_token`.
- [x] Maintain hard SSRF protection (`_host_is_blocked` and private IP rejection) in [`backend/api/routes/browser.py`](file:///f:/supremeai/backend/api/routes/browser.py), ensuring safe multi-tenant usage.
- [ ] Scope crawl policies in [`backend/api/routes/crawler_admin.py`](file:///f:/supremeai/backend/api/routes/crawler_admin.py) to `tenant_id` for authenticated project owners.

### Phase 5: Fixing Cross-Tenant Data Gaps
- [ ] Enforce `tenant_id` / `owner_id` filtering on [`backend/api/routes/repos.py`](file:///f:/supremeai/backend/api/routes/repos.py) (`github_repos`) and [`backend/api/routes/usage_metrics.py`](file:///f:/supremeai/backend/api/routes/usage_metrics.py).
- [ ] Scope `site_actions.db` by adding `tenant_id` column.

### Phase 6: Telegram Bot Multi-Tenant Binding
- [ ] Allow customers to link their Telegram Chat ID to their SupremeAI project via OAuth or `/link <token>`.
- [ ] Grant project-level TOTP 2FA approvals to project owners via Telegram.

### Phase 7: Elevating Customer UI Parity
- [x] **Route Ghost Panels in `App.tsx`:** Deep Research (`/research`), Scheduled Tasks (`/scheduled-tasks`), Cost Dashboard (`/usage`), Memory (`/memory`), Secrets (`/settings/api-keys`), and MCP Connector (`/integrations` tab) are live.
- [ ] Replace placeholder cards in `WorkspaceModulePage.tsx` (`projects`, `activity`, `runs`) with live tenant-filtered modules.
- [ ] Reactivate `/evolution-forge` and `/swarm` in [`frontend/src/config/navigationRegistry.ts`](file:///f:/supremeai/frontend/src/config/navigationRegistry.ts) as standard user capabilities under the "Build" and "Observe" groups once tenant sandboxing is complete.

---

## 6. Conclusion

SupremeAI's strength lies in its **centralized intelligence and composable capabilities**, but its true value is unlocked when **each customer is the sovereign administrator of their own project**.

By continuing to eliminate artificial platform-admin locks on developer tooling, deployments, browser workflows, database preview branching, and approvals, SupremeAI fulfills its Core Constitution: **Empowering users to build, automate, and evolve their software autonomously.**
