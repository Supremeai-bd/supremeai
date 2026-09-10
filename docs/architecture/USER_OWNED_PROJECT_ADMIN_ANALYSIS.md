# SupremeAI: Architecture Analysis & Blueprint
## Transforming from "Platform-Admin Locked" to "User-Owned Project Admin"

> **Status:** Strategic Architectural Blueprint  
> **Target Alignment:** `docs/architecture/SUPREMEAI_CORE_CONSTITUTION.md` §7 (*User-Owned SupremeAI*)  
> **Date:** September 2026  

---

## 1. Executive Summary & The Core Paradox

### The Core Vision
SupremeAI Core Constitution §7 stipulates:
> **"Every customer/tenant should be able to govern the SupremeAI environment they own within platform, security and policy boundaries... Users should be able to discover and activate only the capabilities they need."**

In simple terms:
- **Platform Owner (Root Admin):** Manages the SupremeAI infrastructure, platform health, shared LLM pools, server topologies, and platform-wide billing/abuse.
- **Customer / User (Project Admin):** Is the absolute **Owner & Administrator** of their own project workspace, GitHub repositories, cloud deployments, browser automation sessions, agent swarms, and HITL decision workflows.

### The Current Reality (The Paradox)
During our deep codebase audit, we found that a large portion of SupremeAI's most powerful capabilities were implemented with **Global Admin Gates** (`Depends(get_current_admin)`, `is_admin_authorized()`, `verify_admin_session_fail_closed`, or hardcoded `ADMIN_AUTHORIZED=true`). 

As a consequence, **a customer cannot perform essential administrative operations on their own project**, turning their workspace into an artificially restricted viewer rather than a fully empowered command center.

---

## 2. Comprehensive Inventory of Admin-Locked Features & Architectural Gaps

Below is the complete technical breakdown of features currently unusable by project owners, including file paths, security checks, and real-world user impacts:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SUPREMEAI CURRENT CONTROL MODEL                      │
│                                                                         │
│   ROOT PLATFORM ADMIN                         PROJECT CUSTOMER          │
│   [Full Access to Everything]                 [Blocked with 403/Locked] │
│   ├── Target Binding                          ├── Target Binding ❌     │
│   ├── Cloud Deployments                       ├── Cloud Deployments ❌  │
│   ├── GitHub CI/CD & PRs                      ├── GitHub PRs ❌         │
│   ├── HITL Approvals & Decisions              ├── HITL Approvals ❌     │
│   ├── Browser Automation & Crawling           ├── Browser Automation ❌ │
│   ├── Self-Evolution & Skill Forge            ├── Evolution Forge ❌    │
│   ├── Site Actions & UI Healing               ├── Site Actions ❌       │
│   ├── DevOps & Code Smell / Vuln Scanner      ├── Code Quality Tools ❌ │
│   ├── Neon Branching & DB DDL Operations      ├── Neon DB Branching ❌  │
│   ├── Telegram Privileged Commands & 2FA      ├── Telegram Admin Bot ❌ │
│   ├── Living Brain & Learning Observability   ├── Project Brain Pulse ❌│
│   ├── Tenant Rate Limits & Budget Caps        ├── Team Quota Setting ❌ │
│   └── Cross-Tenant Data Leaks in Repos/Usage  └── Cross-Tenant Blind ❌ │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Category A: Workspaces & Repository Binding (প্রোজেক্ট রেপো বাইন্ডিং)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Target Binding** | `backend/api/routes/workspaces_route.py` | `Depends(get_current_admin)` | Customers cannot bind their own GitHub repository or cloud target with READ_ONLY or FULL_CONTROL scope. |
| **Workspace Context** | `backend/tools/mcp/mcp_workspace.py` | `is_admin_authorized()` | When agents run MCP workspace operations for administrative projects, the MCP tool rejects them unless global `ADMIN_AUTHORIZED=true` is set. |

- **Root Cause:** The workspace registry was designed as a single central registry (`core.target_registry.target_registry`) rather than a multi-tenant, tenant-scoped target registry (`tenant_id -> targets`).

---

### Category B: Cloud Deployments & Hosting (নিজস্ব ক্লাউড ডিপ্লয়মেন্ট)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Cloud Deploy Service** | `backend/tools/mcp/mcp_cloud_deploy.py` | `is_admin_authorized()` | Agent cannot deploy customer apps to Render, Railway, or Oracle Cloud on the user's behalf. |
| **Cloud Scale & Status** | `backend/tools/mcp/mcp_cloud_deploy.py` | `is_admin_authorized()` | Customers cannot scale their project services or query deploy status via agent. |
| **On-Premise & Docker/Helm** | `backend/api/routes/tools_ops.py` | `_require_admin` (`role == 'admin'`) | Customers cannot generate Helm charts or Docker Compose deployment files for their own on-prem project infrastructure. |

- **Root Cause:** The deploy tool relies on environment variables (`RENDER_API_KEY`, etc.) belonging to the platform, without supporting customer-provided cloud credentials or isolated project deploy targets.

---

### Category C: GitHub CI/CD & Pull Request Automation (গিটহাব পিআর ও সিআই)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Create Pull Request** | `backend/tools/mcp/mcp_github_cicd.py` | `is_admin_authorized()` | Customers cannot have the agent open a Pull Request against their own GitHub repository. |
| **Trigger Workflows** | `backend/tools/mcp/mcp_github_cicd.py` | `is_admin_authorized()` | Customers cannot run or inspect CI/CD workflows for their own projects. |

- **Root Cause:** The tool expects platform-level admin authorization and uses a single `GITHUB_TOKEN` from `.env` rather than the customer's OAuth / Personal Access Token stored in their vault.

---

### Category D: Human-in-the-Loop (HITL) Approvals (টাস্ক ও কোড অনুমোদন)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Pending Approvals** | `backend/api/routes/approval_manager.py` | `verify_admin_session_fail_closed` | The customer cannot retrieve tasks requiring their review (`/api/v1/hitl/pending`). |
| **Approve / Reject Task** | `backend/api/routes/approval_manager.py` | `verify_admin_session_fail_closed` | Even if a task affects the customer's codebase, only the SupremeAI Platform Admin can approve or execute it. |

- **Root Cause:** The approval manager treats all approvals as global platform approvals rather than scoping tasks by `tenant_id` / `project_id`.

---

### Category E: Browser Automation, Crawling & Scraper (ওয়েব অটোমেশন ও স্ক্র্যাপিং)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Live Web Actions** | `backend/api/routes/browser.py` | `Depends(require_admin_token)` | `/api/browser/scrape`, `/browse`, `/extract` are locked behind admin tokens. |
| **Crawl Policy Engine** | `backend/api/routes/crawler_admin.py` | `Depends(get_current_admin)` | Customers cannot configure which domains their agents can crawl, rate limits, or depth rules. |
| **Browser Credentials Vault** | `backend/api/routes/browser.py` | `Depends(require_admin_token)` | Storing login credentials for browser sessions (`/api/browser/credentials`) requires platform admin access. |
| **URL Whitelist / Denylist** | `backend/api/routes/browser.py` | `Depends(require_admin_token)` | Project owners cannot whitelist URLs their browser agents are allowed to visit. |

- **Root Cause:** While SSRF protection is necessary, it was enforced by completely locking out non-admin users instead of providing tenant-scoped, SSRF-filtered browser sessions.

---

### Category F: Self-Evolution, Swarm Architect & Skill Governance (সেলফ-ইভোলিউশন)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Evolution Forge UI** | `frontend/src/config/navigationRegistry.ts` | `status: 'deprecated'` | The Evolution Forge and Swarm Architect pages are removed/deprecated from the user navigation. |
| **Skill Quarantine** | `backend/api/routes/evolution.py` | `Depends(require_admin_token)` | Customers cannot quarantine buggy or misbehaving skills in their agent workspace. |
| **Evolution Metrics** | `backend/api/routes/evolution.py` | `Depends(require_admin_token)` | Project owners cannot see calibration, token estimation errors, or proposal success rates for their own runs. |
| **Librarian Queue** | `backend/api/routes/admin_librarian.py` | `Depends(get_current_admin)` | Customers cannot review quarantine proposals or approve ephemeral AI patches for skills. |

- **Root Cause:** Self-evolution was viewed as a global system capability modifying the central server runtime, rather than project-level custom skills sandboxed per tenant.

---

### Category G: Site Actions & UI Auto-Healing (সাইট অ্যাকশন রুলস)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Site Action Registry** | `backend/api/routes/site_actions.py` | `Depends(get_current_admin)` | Customers cannot register site actions (e.g. click selector patterns, fallback selectors) for their web apps. |
| **Selector Healing Review** | `backend/api/routes/selector_healing.py` | Registered with `is_admin=True` | Customers cannot review or approve healed CSS/XPath selectors detected by Playwright agents. |

- **Root Cause:** Site actions were implemented in a shared SQLite database (`data/site_actions.db`) without a `tenant_id` column.

---

### Category H: Code Quality, Smell Detection & Vulnerability Prediction (কোড কোয়ালিটি)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Code Smell Detector** | `backend/api/routes/tools_ops.py` | `_require_admin` | Customers cannot invoke automated code smell detection across their project repository via API. |
| **Vulnerability Predictor** | `backend/api/routes/tools_ops.py` | `_require_admin` | Customers cannot scan diffs or files for vulnerability patterns using SupremeAI security tooling. |

- **Root Cause:** Implemented under `tools_ops.py` which applies `_require_admin` across the entire router, even though code quality tools are prime customer-facing features.

---

### Category I: Database Branching & Destructive DDL (ডাটাবেস ব্রাঞ্চিং ও কুয়েরি)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Neon Branch Management** | `backend/tools/mcp/mcp_neon.py` | `is_admin_authorized()` | Customers cannot have AI agents create isolated preview branches of their Neon Postgres database or delete branches. |
| **Destructive SQL Guard** | `backend/tools/mcp/mcp_neon.py`, `mcp_supabase.py` | `is_admin_authorized()` | Table migrations (`ALTER TABLE`, `DROP`, `TRUNCATE`) are blocked by `is_admin_authorized()` even when executed on the customer's own database. |

- **Root Cause:** Centralized DDL protection blocks non-admin users without differentiating between platform infrastructure databases and customer project databases.

---

### Category J: Telegram Bot Autonomous Admin & 2FA Challenges (টেলিগ্রাম কন্ট্রোল)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Admin Telegram Control** | `backend/tools/social/telegram_bot.py` | Hardcoded `7804133572` / `is_admin` | Only the platform root admin gets the interactive administrative dashboard, `/sys_status`, and `/backup_now`. |
| **Critical Command Approval** | `backend/tools/social/telegram_bot.py` | `not self.is_admin(chat_id)` | Customers managing their projects via Telegram cannot approve critical actions via TOTP 2FA — they are rejected with "Access Denied". |

- **Root Cause:** Telegram bot maps administrative privileges to a single static Telegram Chat ID rather than linking Telegram accounts to tenant project owners.

---

### Category K: Living Brain & Self-Sufficiency Analytics (লার্নিং ও মেমোরি ভিজিবিলিটি)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Living Brain Metrics** | `backend/api/routes/living_brain.py` | `Depends(get_current_admin)` | Customers cannot see how well SupremeAI has adapted to their project domain, learning progress, and self-sufficiency rate. |
| **Learning Timeline** | `backend/api/routes/living_brain.py` | `Depends(get_current_admin)` | Timeline of learned patterns and auto-corrections is visible only to platform admins. |

- **Root Cause:** The learning metrics endpoint aggregates data globally across all tenants instead of supporting per-tenant learning stats.

---

### Category L: Tenant Limits, Sub-User RBAC & Execution Policies (টিম ও কোটা কন্ট্রোল)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Project Rate Limiting** | `backend/api/routes/tenant_admin.py` | `Depends(get_current_admin)` | An organization owner cannot set sub-user rate limits (e.g. limit junior developers to 50k tokens/day). |
| **Execution Timeout & Budgets** | `backend/api/routes/execution_policies.py` | `Depends(get_current_admin)` | Project owners cannot configure maximum compute budget (USD) or timeout windows for their workflows. |

- **Root Cause:** Tenant admin and execution policies were designed as root admin control planes rather than delegated organizational administration.

---

### Category M: Data Leakage & Cross-Tenant Isolation Gaps (ক্রস-টেন্যান্ট আইসোলেশন গ্যাপ)

| Component | Code Location | Vulnerability / Gap | Impact on Customer |
|---|---|---|---|
| **Repository Listing** | `backend/api/routes/repos.py` | `select("*").eq("status", status)` without `tenant_id` filter | `GET /repos/` lists all repositories from `github_repos` across all users; `POST /repos/` inserts without `owner_id`. |
| **Usage Metrics Query** | `backend/api/routes/usage_metrics.py` | `select("*")` on `usage_metrics` without user filter | Any authenticated user can view aggregated global platform usage data. |

- **Root Cause:** Legacy routes rely on Supabase table reads without appending `.eq("tenant_id", current_tenant)`.

---

### Category N: Frontend Workspace Disconnection (ইউজার ইউআই বনাম অ্যাডমিন ইউআই)

| Area | What Platform Admin Has (`AdminShell`) | What Customer Sees (`UserDashboard`) |
|---|---|---|
| **Projects & Targets** | Full multi-platform target binding & scope selection | Static marketing card: "A home for every outcome" |
| **Activity & Logs** | Live WebSocket log streamer (`LiveLogs`), audit events | Static placeholder: "Nothing here yet" |
| **Runs & Health** | Observability, Topology Map, Incident Alerts | Deprecated route / placeholder |
| **Approvals** | Interactive `ApprovalQueue` with diff review & OTP | Locked behind modal or inaccessible |

---

## 3. The Target Architecture: Two-Tier Governance Model

To restore alignment with the SupremeAI Core Constitution, we must migrate to a **Two-Tier Governance Model**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TWO-TIER GOVERNANCE MODEL                       │
├───────────────────────────────────┬────────────────────────────────────┤
│     TIER 1: PLATFORM ADMIN        │      TIER 2: PROJECT ADMIN         │
│     (Owner of SupremeAI)          │      (Owner of Project / Tenant)   │
├───────────────────────────────────┼────────────────────────────────────┤
│ • Server & Cluster Topology       │ • Target Repository Binding        │
│ • Global Cloud Provider Keys      │ • Project Deployment & Scaling     │
│ • Platform-Wide Rate Limits       │ • Project-Level HITL Approvals     │
│ • System Database Migrations      │ • Project Browser Automation       │
│ • Platform FinOps & Infrastructure│ • Tenant Vault & Credentials       │
│ • Cross-Tenant Security Audit     │ • Project Agents & Swarm Config    │
│ • Core Constitution Governance    │ • Code Smell & Vuln Scanning       │
│ • Global Fail-Closed Interceptors │ • Project Neon DB Preview Branches │
│ • Global Abuse Monitoring         │ • Project Execution Policy/Budgets │
│ • Root Telegram Command Center    │ • Project-Level Audit Logs & Runs  │
└───────────────────────────────────┴────────────────────────────────────┘
```

---

## 4. Step-by-Step Evolution Roadmap

### Phase 1: Authentication & Role Differentiation
- [ ] Split `get_current_admin` into:
  - `get_platform_admin`: For infrastructure, global server topologies, and platform-wide billing.
  - `get_project_admin`: Grants administrative privileges scoped to the user's specific `tenant_id`.
- [ ] Add `tenant_id` and project role (`role: "owner" | "admin" | "member"`) to all JWT and session contexts.

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
- [ ] Refactor `backend/api/routes/approval_manager.py`:
  - Add `tenant_id` column to `pending_tasks`.
  - Filter `GET /api/v1/hitl/pending` by `current_user.tenant_id`.
  - Allow project owners to approve tasks for their own repositories and skills without requiring Platform God Mode.
- [ ] Make `tools_ops.py` code smell and vulnerability prediction endpoints accessible to project owners for their own codebase.

### Phase 4: Safe Multi-Tenant Browser Automation & Crawling
- [ ] Make browser automation routes (`/api/browser/scrape`, `/browse`, `/extract`) available to all authenticated project owners.
- [ ] Maintain hard SSRF protection (`_assert_safe_public_url`), so no user (admin or customer) can access internal infrastructure targets.
- [ ] Scope browser credential storage and crawl policies by `tenant_id`.

### Phase 5: Fixing Cross-Tenant Data Gaps
- [ ] Enforce `tenant_id` filtering on `backend/api/routes/repos.py` (`github_repos`) and `backend/api/routes/usage_metrics.py`.
- [ ] Scope `site_actions.db` by adding `tenant_id` column.

### Phase 6: Telegram Bot Multi-Tenant Binding
- [ ] Allow customers to link their Telegram Chat ID to their SupremeAI project via OAuth or `/link <token>`.
- [ ] Grant project-level TOTP 2FA approvals to project owners via Telegram.

### Phase 7: Elevating the Customer UI (UserDashboard & Modules)
- [ ] Replace placeholder cards in `WorkspaceModulePage.tsx` (`projects`, `activity`, `runs`, `approvals`) with the live components already built for the admin console, filtered by `tenant_id`.
- [ ] Reactivate `/evolution-forge` and `/swarm` in `navigationRegistry.ts` as standard user capabilities under the "Build" and "Observe" groups.

---

## 5. Conclusion

SupremeAI's strength lies in its **centralized intelligence and composable capabilities**, but its value is realized only when **each customer is the sovereign administrator of their own project**.

By eliminating artificial platform-admin locks on developer tooling, deployments, browser workflows, database preview branching, and approvals, SupremeAI fulfills its Core Constitution: **Empowering users to build, automate, and evolve their software autonomously.**
