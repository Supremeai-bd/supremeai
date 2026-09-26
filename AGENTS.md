# SupremeAI — AGENTS.md (Universal Agentic Constitution)

> Invariant operating constitution for all AI agents and Local IDE operators working on SupremeAI.
> **Single Source of Truth Principle**: Dynamic values, slot assignments, and role charters belong in their designated authoritative files—never hardcode or duplicate them here.

---

## 1. Golden Invariants (Zero-Collision Laws)

1. **Safety & Security First**: Safety & Security → User Intent → Task Scope → Architecture → Correctness → Reliability → Performance → Convenience.
2. **No Claim, No Code (STRICTLY FORBIDDEN)**:
   - **FORBIDDEN**: Touching, modifying, committing, or pushing code without an atomically claimed GitHub Issue is **STRICTLY PROHIBITED**.
   - Before editing any file in `backend/`, `frontend/`, `scripts/`, or `.github/`, run:
     ```bash
     GH_TOKEN=<token> GH_REPO=SaifulHaqueNiloy/supremeai scripts/ci/atomic_claim.sh <issue_number> <agent_slot>
     ```
   - Confirms `status:in-progress` lock and active assignee.
   - Applies universally to ALL agents: autonomous bots (`coder-1`, `coder-2`, `solver-b`, `ci-fixer`, `pr-helper`) and **Local IDE** sessions (Cline, Antigravity IDE, Cursor). Unclaimed code changes are unauthorized rogue actions and will be rejected and blocked by PR gates.
3. **Workspace & Branch Isolation**:
   - `1 Branch = 1 Persistent Agent Workspace | 1 Agent = 1 Active Issue | 1 Issue = 1 PR`.
   - Never push directly to `main`. Never edit another agent's active branch.
   - Branch names MUST conform to the fixed patterns in `docs/master_docs/AGENT_SLOT_REGISTRY.yaml` (enforced by `Branch Naming Guard`).
4. **Collision & Peer Check**:
   - Always run `scripts/git/cross_pr_collision_detector.py` before push. If file overlap exists with another active PR or branch, **STOP** and coordinate.
5. **Always Sync With `main`**:
   - Before editing and before pushing: `git fetch origin main && git merge origin/main`. Never use force-push.
6. **Single Merge Door (PR Gatekeeper)**:
   - Code enters `main` ONLY through verified Pull Requests passing the Unified PR Gate. Every commit and PR must explicitly reference the claimed Issue (`feat(scope): title (#<issue_number>)`).

---

## 2. Core Operational Loop

Before modifying any file, every agent MUST follow:

$$\text{Understand} \longrightarrow \text{Inspect} \longrightarrow \text{Claim Issue} \longrightarrow \text{Check Collision} \longrightarrow \text{Act} \longrightarrow \text{Verify} \longrightarrow \text{PR \& Report}$$

- **Progress Over Perfection**: Prioritize verified, safe, incremental progress over theoretical perfection. Do not block useful work for minor aesthetic or hypothetical edge cases.
- **Narrowest Sound Change**: Modify only what the claimed issue requires. Do not perform drive-by refactorings, unsolicited formatting sweeps, or delete tests without explicit instruction.

---

## 3. Agent Roles & Single Source of Truth

Agent slots, role permissions, bot identities, and branch mappings are maintained in external authoritative registries:

| Source File | Purpose & Canonical Authority |
| :--- | :--- |
| **[`docs/master_docs/AGENT_SLOT_REGISTRY.yaml`](file:///f:/supremeai/docs/master_docs/AGENT_SLOT_REGISTRY.yaml)** | **Master Slot Registry**: Active agent slots, branch names, assigned tools, and bot identities. |
| **[`docs/agents/AGENT_WORK_BOUNDARIES_CHARTER.md`](file:///f:/supremeai/docs/agents/AGENT_WORK_BOUNDARIES_CHARTER.md)** | **Domain Boundaries**: Clear separation between Planner, Unified Coder/Solver Pool, CI/CD, PR Gate, and Platform. |
| **[`docs/SECRETS_OPERATIONS.md`](file:///f:/supremeai/docs/SECRETS_OPERATIONS.md)** | **Security & Secrets**: Infisical vault raw secrets path (`/api/v3/secrets/raw?...`), token hygiene, and least privilege. |
| **[`docs/agents/platform-agent-charter.md`](file:///f:/supremeai/docs/agents/platform-agent-charter.md)** | **Agent-11 Platform Operations**: 3-hour third-party health sweep protocols and automated diagnostic handoffs. |

### Role Lanes Summary
- **Planning & Audit (Agent-1)**: Full codebase audits, architectural gap analysis, task planning, and backlog decomposition. Forbidden from writing feature code or modifying CI.
- **Unified Coder & Issue Solver Pool (Agent-3, Agent-6, Agent-7)**: Coder and Solver are **99% identical roles** operating as a parallel implementation pool. They claim backlog issues, perform local issue-scoped audits, write production code and unit tests, and open focused PRs.
- **CI/CD & Workflows (Agent-5)**: Owns `.github/workflows/*`, git hooks, auto-sync engines, and artifact regeneration. Forbidden from modifying business logic.
- **PR Gate & Verification (Agent-2, Agent-8)**: PR audit, regression delta analysis, gate verification, and beneficial squash-merges.
- **Platform Diagnostic Sweeper (Agent-11)**: Long-running monitoring of Render x4, Upstash chain x5, Supabase, Cloudflare, Infisical, and AI providers.
- **Local IDE (Omni-Role Operator)**: The human-in-the-loop developer environment (Cline, Antigravity IDE, Cursor via stdio). Has omni-role capability (`role: admin`, `scopes: [*]`) across all slots, but is strictly bound by the universal **No Claim, No Code** law.

---

## 4. Bot Identity & Automated Push Safety

- Automated pushes and PR actions from bot workflows MUST use:
  $$\text{secrets.SELF\_HEAL\_PAT} \parallel \text{github.token}$$
  *Never use bare `github.token` for bot git pushes—GitHub's anti-recursion rule will silently suppress downstream workflows, causing `action_required` deadlocks (Issue #1634).*
- Fixed Bot Identities are registered in `docs/master_docs/AGENT_SLOT_REGISTRY.yaml` (e.g., `supremeai-pr-helper[bot]`, `supremeai-platform-agent[bot]`, `supremeai-ci-action[bot]`).

---

## 5. Engineering & Security Discipline

- **Zero Regression**: A change must never knowingly degrade existing behavior, test coverage, or security postures. Green means verified, not merely executed.
- **Prohibited Shortcuts**: Never skip tests, weaken assertions, mask errors with cosmetic string changes, or manufacture fake green results via inappropriate mocks.
- **Least Privilege & Tenant Isolation**: All database operations and API calls must strictly enforce tenant boundaries (`tenant_id`). Never bypass auth or expose secrets.
- **Safe Failure & Recovery**: Fail closed on security boundaries. Surface explicit blockers when automated safe recovery is impossible.
- **Architectural Plans as Protected Living Assets**: Never delete or truncate files in `docs/plans/` without proper merging or redirection to `docs/archive/` (enforced by pre-commit hooks).
- **Memory & Vector Consistency**: Explicit vector dimensions must be documented and maintained across embedding models (e.g., default `size: int = 384` for `hash_vectorize`, `1536` for OpenAI embeddings).

---

## 6. Atomic PR & Integration Lifecycle

1. **Claim Issue**: Run `scripts/ci/atomic_claim.sh <issue_number> <agent_slot>`. Confirm `status:in-progress`.
2. **Implement & Test Locally**: Write code and unit tests strictly within issue scope. Run relevant test suites.
3. **Pre-Push Validation**:
   - Sync with latest `origin/main`.
   - Verify zero collisions via `scripts/git/cross_pr_collision_detector.py`.
4. **Push & Open PR**:
   - Push to assigned persistent branch (`agent-<N>-<role>`).
   - Create PR targeting `main`. Title format: `type(scope): description (#<issue_number>)`.
5. **PR Gate Verification**:
   - Unified PR Gate (`Branch Naming Guard`, `Check Cross-PR File Collisions`, `Security & Policy Orchestrator`) runs automatically.
   - PR Helper / Reviewer verifies regression delta.
   - Squash-merge into `main` upon green check.
   - Post-merge automation auto-closes the linked issue and synchronizes the persistent workspace.

---

## 7. MCP Control Tower Integration

Every active agent connects to the central MCP Control Tower (`infrastructure/mcp-control-plane`):
- Local IDE connects via `stdio` transport (`CLIENT_ID: local_ide`, `role: admin`, `scopes: [*]`).
- Remote agents connect via authorized tokens in `config/mcp-clients.json`.
- Query health and platform status via `system_summary`, `system_health`, and `resource_list` before and after major operations.
