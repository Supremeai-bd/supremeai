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
| **Target Binding** | `backend/api/routes/workspaces_route.py` | `prefix="/admin-api/workspaces"`, `Depends(get_current_admin)`, `check_totp_code` | Customers cannot bind their own GitHub repository or cloud target with READ_ONLY or FULL_CONTROL scope. Requires admin token AND valid JIT OTP header (`X-JIT-OTP`). |
| **Workspace Context** | `backend/tools/mcp/mcp_workspace.py` | `is_admin_authorized()` in `workspace_set_context` | When agents run MCP workspace operations for administrative projects (`WorkspaceType.ADMIN_PANEL`), the MCP tool rejects them unless global `ADMIN_AUTHORIZED=true` is set. |

- **Root Cause & Code Reality:** `core.target_registry.target_registry` is currently an in-memory singleton mapping (`_targets: dict[str, TargetEntity]`) with a hardcoded `main-repository` default. It lacks tenant partition keys (`tenant_id`), meaning target binding is treated as a global platform operation rather than tenant-scoped project workspaces.

---

### Category B: Cloud Deployments & Hosting (নিজস্ব ক্লাউড ডিপ্লয়মেন্ট)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Cloud Deploy Service** | `backend/tools/mcp/mcp_cloud_deploy.py` | `is_admin_authorized()` in `cloud_deploy_service` | Agent cannot deploy customer apps to Render, Railway, or Oracle Cloud on the user's behalf without `ADMIN_AUTHORIZED=true`. |
| **Cloud Scale & Status** | `backend/tools/mcp/mcp_cloud_deploy.py` | `is_admin_authorized()` in `cloud_scale_service`, `cloud_get_deploy_status` | Customers cannot scale their project services or query deploy status via agent. |
| **On-Premise & Docker/Helm** | `backend/api/routes/tools_ops.py` | `router` level `_require_admin` (`payload.get("role") != "admin"`) | Customers cannot generate Helm charts or Docker Compose deployment files (`/tools/devops/on-prem/docker-compose`, `/tools/devops/on-prem/helm`) for their own on-prem project infrastructure. |

- **Root Cause & Code Reality:** The deployment tools pull credentials directly from global platform settings (`_get_render_api_key()`, `_get_railway_token()`, `_get_oracle_api_key()`). There is no mechanism for tenants to supply their own cloud provider tokens or target their own isolated project environments.

---

### Category C: GitHub CI/CD & Pull Request Automation (গিটহাব পিআর ও সিআই)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Create Pull Request** | `backend/tools/mcp/mcp_github_cicd.py` | `is_admin_authorized()` in `github_create_pull_request` | Customers cannot have the agent open a Pull Request against their own GitHub repository. |
| **Run Auto-Fix** | `backend/tools/mcp/mcp_github_cicd.py` | `is_autofix_authorized()` in `github_run_auto_fix` | Auto-fix workflow requires platform-level `AUTOFIX_AUTHORIZED=true`. |
| **Trigger Workflows** | `backend/tools/mcp/mcp_github_cicd.py` | `is_admin_authorized()` in `github_trigger_workflow` | Customers cannot run CI/CD workflows for their own projects. |

- **Root Cause & Code Reality:** `mcp_github_cicd.py` uses a single static repository (`GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "SaifulHaqueNiloy/supremeai")`) and single static `GITHUB_TOKEN`. It does not accept user-specified repos or tenant GitHub tokens.

---

### Category D: Human-in-the-Loop (HITL) Approvals (টাস্ক ও কোড অনুমোদন)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Pending Approvals** | `backend/api/routes/approval_manager.py` | `verify_admin_session_fail_closed` on `/api/v1/hitl/pending` | The customer cannot retrieve tasks requiring their review, even for their own workspace. |
| **Approve / Reject Task** | `backend/api/routes/approval_manager.py` | `verify_admin_session_fail_closed` on `/approve/{task_id}`, `/reject/{task_id}` | Only users with a valid platform admin cookie/session can approve or reject tasks. |
| **Cancel Task** | `backend/api/routes/approval_manager.py` | `verify_admin_session_fail_closed` on `/cancel/{task_id}` | Customers cannot cancel tasks initiated by their own agents. |

- **Root Cause & Code Reality:** Notice that `models/pending_tasks.py` **already has** `tenant_id` and `created_by` columns in its schema, and `list_pending(tenant_id: str | None)` supports tenant filtering! However, `approval_manager.py` fails to pass the current user's `tenant_id` to `list_pending()` and locks the entire endpoint behind `verify_admin_session_fail_closed`.

---

### Category E: Browser Automation, Crawling & Scraper (ওয়েব অটোমেশন ও স্ক্র্যাপিং)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Crawl Policy Engine** | `backend/api/routes/crawler_admin.py` | `router` level `Depends(get_current_admin)` | Customers cannot configure which domains their agents can crawl, rate limits, or depth rules (`/api/v1/admin/crawler/policies`). |
| **Browser Credentials Vault** | `backend/api/routes/browser.py` | `Depends(require_admin_token)` on `POST /credentials`, `POST /credentials/{id}/use`, `DELETE /credentials/{id}` | Storing or utilizing login credentials for browser sessions requires platform admin access. |
| **URL Whitelist / Denylist Rules** | `backend/api/routes/browser.py` | `Depends(require_admin_token)` on `POST /urls/allowed`, `POST /urls/denied`, `POST /urls/allowAll`, `POST /urls/requests/{id}/decision` | Project owners cannot whitelist or authorize URLs their browser agents are permitted to visit. |
| **Autonomous Web Automation** | `backend/api/routes/browser.py` | Authenticated user (`get_current_user_token`) with owner scoping | `/automation/sessions`, `/automation/actions`, `/tasks`, `/policy` are owner-scoped, but administrative web governance is locked behind admin tokens. |

- **Root Cause & Code Reality:** While session automation (`/automation/sessions`) is owner-scoped, the governance layer (credentials, crawl policies, URL whitelist decisions, and admin policies) was routed through admin gates to enforce safety, locking out legitimate project admins from controlling their own browser agents.

---

### Category F: Self-Evolution, Swarm Architect & Skill Governance (সেলফ-ইভোলিউশন)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Evolution Forge & Swarm UI** | `frontend/src/config/navigationRegistry.ts` | `status: 'deprecated'` for `nav-swarm`, `nav-evolution-forge`, `nav-architect-tower`, `nav-runs` | Self-evolution and swarm topology are deprecated and hidden from customer navigation. |
| **Evolution API Endpoints** | `backend/api/routes/evolution.py` | `require_admin_token` on `/evolution/start`, `/metrics`, `/quarantine`, `/auto-patch`, `/calibration-report` | Project owners cannot inspect evolutionary calibration, token estimation errors, or proposal success rates for their own runs. |
| **Librarian Queue** | `backend/api/routes/admin_librarian.py` | `router` level `Depends(get_current_admin)` | Customers cannot review quarantine proposals or approve ephemeral AI patches for skills. |

- **Root Cause & Code Reality:** Self-evolution was originally conceived as a single global engine modifying the server runtime (`skills/` on disk), instead of tenant-scoped custom skills sandboxed in isolated tenant storage.

---

### Category G: Site Actions & UI Auto-Healing (সাইট অ্যাকশন রুলস)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Site Action Registry** | `backend/api/routes/site_actions.py` | `router` level `Depends(get_current_admin)` | Customers cannot register site actions (e.g. click selector patterns, fallback selectors) for their web apps. |
| **Selector Healing Review** | `backend/api/routes/selector_healing.py` | `router` level `Depends(get_current_admin)` | Customers cannot review or approve healed CSS/XPath selectors detected by Playwright agents. |

- **Root Cause & Code Reality:** Site actions are stored in `data/site_actions.db` (SQLite) without a `tenant_id` column. Because all records are unpartitioned, endpoints cannot safely expose writes to non-admin users without risking cross-tenant pollution.

---

### Category H: Code Quality, Smell Detection & Vulnerability Prediction (কোড কোয়ালিটি)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Code Smell Detector** | `backend/api/routes/tools_ops.py` | `router` level `_require_admin` on `POST /tools/code/smell` | Customers cannot invoke automated code smell detection across their project repository via API. |
| **Vulnerability Predictor** | `backend/api/routes/tools_ops.py` | `router` level `_require_admin` on `POST /tools/security/predict` | Customers cannot scan diffs or files for vulnerability patterns using SupremeAI security tooling. |
| **Domain Adapter & Skill Recommender** | `backend/api/routes/tools_ops.py` | `router` level `_require_admin` on `/tools/learning/domain/adapt`, `/tools/learning/skills/recommend` | Customers cannot trigger domain adaptation or receive tailored skill recommendations for their project. |

- **Root Cause & Code Reality:** In `tools_ops.py`, DevOps write operations (Docker Compose / Helm chart generation) and read-only analysis tools (smell detection, vulnerability prediction) are bundled under a single router gated by `_require_admin`.

---

### Category I: Database Branching & Destructive DDL (ডাটাবেস ব্রাঞ্চিং ও কুয়েরি)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Neon Branch Management** | `backend/tools/mcp/mcp_neon.py` | `is_admin_authorized()` in `neon_create_branch`, `neon_delete_branch` | Customers cannot have AI agents create isolated preview branches of their Neon Postgres database or delete temporary branches. |
| **Destructive SQL Guard** | `backend/tools/mcp/mcp_neon.py`, `mcp_supabase.py` | `is_admin_authorized()` on queries containing `DROP`, `DELETE`, `TRUNCATE`, `ALTER` | Table migrations and schema updates are blocked unless global `ADMIN_AUTHORIZED=true` is set. |

- **Root Cause & Code Reality:** The DDL guard checks `is_admin_authorized()` against server environment variables rather than checking if the target database connection string belongs to the tenant's own external database resource.

---

### Category J: Telegram Bot Autonomous Admin & 2FA Challenges (টেলিগ্রাম কন্ট্রোল)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Admin Telegram Control** | `backend/tools/social/telegram_bot.py` | `is_admin(chat_id)`: checks `ADMIN_TELEGRAM_CHAT_ID`, `TELEGRAM_CHAT_ID`, or `"7804133572"` | Only the platform root admin gets the administrative dashboard, `/sys_status`, `/backup_now`, and `/admin`. |
| **Critical Command Approval** | `backend/tools/social/telegram_bot.py` | `not self.is_admin(chat_id)` rejects critical actions with "Access Denied" | Customers managing their projects via Telegram cannot approve critical actions via TOTP 2FA. |

- **Root Cause & Code Reality:** In `telegram_bot.py:310-318`, admin status is determined strictly by comparing `chat_id` against static environment variables or hardcoded `"7804133572"`. There is no link between Telegram accounts and tenant project ownership.

---

### Category K: Living Brain & Self-Sufficiency Analytics (লার্নিং ও মেমোরি ভিজিবিলিটি)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Living Brain Metrics** | `backend/api/routes/living_brain.py` | `router` level `Depends(get_current_admin)` | Customers cannot see how well SupremeAI has adapted to their project domain, learning progress, and self-sufficiency rate (`/api/living-brain/status`, `/metrics`). |
| **Learning Timeline & Costs** | `backend/api/routes/living_brain.py` | `router` level `Depends(get_current_admin)` | Learning timeline events and cost breakdowns are visible only to platform admins. |

- **Root Cause & Code Reality:** `living_brain.py` aggregates data from the global `SupremeLearningEngine` and `SupabaseStore` without tenant filtering. Exposing this directly without tenant isolation would leak cross-tenant system metrics.

---

### Category L: Tenant Limits, Sub-User RBAC & Execution Policies (টিম ও কোটা কন্ট্রোল)

| Component | Code Location | Enforced Gate | Impact on Customer |
|---|---|---|---|
| **Platform Tenant Management** | `backend/api/routes/tenant_admin.py` | `router` level `Depends(get_current_platform_admin)` | Strictly guarded for platform administration (tenant creation, tier updates, global billing), which is correct. However, organization owners lack a delegated sub-user quota endpoint. |
| **Execution Timeout & Budgets** | `backend/api/routes/execution_policies.py` | `router` level `Depends(get_current_admin)` | Project owners cannot configure maximum compute budget (USD) or timeout windows for their project workflows (`/api/admin/execution-policies`). |

- **Root Cause & Code Reality:** `execution_policies.py` operates on a global `ExecutionPolicy` table without tenant partitioning. While platform-level limits are already correctly guarded by `get_current_platform_admin`, project-level budget caps lack a dedicated tenant-scoped API.

---

### Category M: Data Leakage & Cross-Tenant Isolation Gaps (ক্রস-টেন্যান্ট আইসোলেশন গ্যাপ)

| Component | Code Location | Vulnerability / Gap | Impact on Customer |
|---|---|---|---|
| **Repository Listing** | `backend/api/routes/repos.py` | `select("*").eq("status", status)` without `tenant_id` filter; `POST /` inserts without `owner_id` | `GET /repos/` lists all repositories from `github_repos` across all users; any user can view or modify other tenants' repos. |
| **Usage Metrics Query** | `backend/api/routes/usage_metrics.py` | `select("*")` on `usage_metrics` without user/tenant filter | Any authenticated user can view aggregated global platform usage data. |

- **Root Cause & Code Reality:** `repos.py` and `usage_metrics.py` were written as early prototypes querying Supabase directly without applying `eq("tenant_id", current_tenant)` or `eq("owner_id", user_id)`.

---

### Category N: Frontend Workspace Disconnection (ইউজার ইউআই বনাম অ্যাডমিন ইউআই)

| Area | What Platform Admin Has (`AdminShell`) | What Customer Sees (`UserDashboard` / `WorkspaceModulePage`) |
|---|---|---|
| **Projects & Targets** | Full multi-platform target binding & scope selection | Static card: "A home for every outcome" in `WorkspaceModulePage.tsx:7` |
| **Activity & Logs** | Live WebSocket log streamer (`LiveLogs`), audit events | Static action cards: "Review recent events", "Export an audit view" in `WorkspaceModulePage.tsx:8` |
| **Runs & Health** | Observability, Topology Map, Incident Alerts | Static placeholder card in `WorkspaceModulePage.tsx:10` |
| **Approvals** | Interactive `ApprovalQueue` with diff review & OTP | Deprecated or restricted to platform admin session |

---

## 3. The Target Architecture: Two-Tier Governance Model

To restore alignment with the SupremeAI Core Constitution, we maintain and advance the **Two-Tier Governance Model**:

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

## 4. Step-by-Step Evolution Roadmap & Current Status

### Phase 1: Authentication & Role Differentiation
- [x] Create `get_current_platform_admin` in `backend/api/dependencies.py` (Completed: enforces `settings.admin_emails` check for cross-tenant operations).
- [ ] Add `get_project_admin`: Grants administrative privileges scoped strictly to the user's specific `tenant_id`.
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
  - Pass `current_user.tenant_id` to `list_pending(tenant_id)` in `GET /api/v1/hitl/pending`.
  - Allow project owners to approve tasks for their own repositories and skills without requiring Platform God Mode.
- [ ] Make `tools_ops.py` code smell and vulnerability prediction endpoints accessible to project owners for their own codebase (split DevOps file writes from read-only code analysis).

### Phase 4: Safe Multi-Tenant Browser Automation & Crawling
- [ ] Make browser credentials vault (`/api/browser/credentials`) owner-scoped rather than requiring `require_admin_token`.
- [ ] Maintain hard SSRF protection (`_host_is_blocked` and private IP rejection), ensuring safe multi-tenant usage.
- [ ] Scope crawl policies in `crawler_admin.py` to `tenant_id` for authenticated project owners.

### Phase 5: Fixing Cross-Tenant Data Gaps
- [ ] Enforce `tenant_id` / `owner_id` filtering on `backend/api/routes/repos.py` (`github_repos`) and `backend/api/routes/usage_metrics.py`.
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
