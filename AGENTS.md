# SupremeAI — AGENTS.md

> **The Universal Agent Constitution (Single Door SSOT)**  
> **Freedom:** Agent controls **HOW** to solve any task inside its contract.  
> **Control:** Admin/System controls **WHERE, WHAT, ACCESS, LIMITS, STOPPING**.  
> **Zero-Admin Target:** Work budget ≤ 0.01% · **The loop is the permission (U10).**

---

## 🚪 The Single Door: Soul & Engine of SupremeAI Agents

All agents enter, execute, and govern through exactly two unified pillars:

1. **The Life & Senses — MCP Control Tower:**  
   Zero-credential proxy hub providing context, tools, and actions (`https://supremeai-mcp-tower.onrender.com/mcp`).
2. **The Soul & Engine — Continuous Autonomous Loop:**  
   Run `python scripts/agents/continuous_agent_loop.py`. The loop self-dispatches:  
   - Inspects board for unclaimed issues -> dispatches `solver`.  
   - Checks role cadence timers -> dispatches scheduled routine role.  
   - Directly injects Universal Invariants and role mandates into execution.

---

> **Operating System (the two-sided guarantee in action):** the step-by-step
> verification ladder, the harm-containment map, and the self-healing /
> self-evolving flywheel that keep this constitution alive:
> [`docs/AGENT_OPERATING_SYSTEM.md`](docs/AGENT_OPERATING_SYSTEM.md)

---

## 📜 The Universal Invariants (Must Follow vs Must Avoid)

- **MUST FOLLOW:**
  1. **Dual-Rebase & Single-Monorepo SSOT Topology Continuity:** Rebase `origin/main` at work-start AND pre-push (0 behind). Strictly adhere to the **Pure Single-Repository Monorepo SSOT Topology**: `Supremeai-bd/supremeai` as the Single Door Monorepo SSOT containing Core, Gateway, Browser, VSCode, Studio & Infrastructure. All historical external satellite repositories are permanently retired, archived, and frozen read-only; all development, PRs, and CI/CD operations reside 100% within `Supremeai-bd/supremeai`. Routine PR-lane CI failures never spawn duplicate work orders; failures are labeled strictly in-place (`ci-failed`, `status:unclaimed`) on the failing PR and linked issue. Sub-issues attach strictly for genuine domain feature tasks or systemic architectural remediation.
  2. **Boundary:** Satellite code lives strictly in its approved domain mirror in the umbrella monorepo (`studio/*`, `gateway/*`, `core/*`, `browser/*`, `vscode/*`, `infrastructure/*`).
  3. **Superior Replacement:** Discard broken legacy code/tests rather than hacking new code to appease past mistakes. Work must tangibly benefit Machine, Admin, or User.
  4. **Verification & PR Blueprint:** 3-Tier Verify (Reflection -> Smoke -> Tests). PRs must carry issue closure references and `## Reflection Evidence (why + alternatives_rejected)`.
  5. **P0 Drainage & Anti-Stampede Invariant:** Open architectural blockers (`P0-critical`) supersede all speculative research, routine audits, and lower-priority work. Agents and Bridge pipelines MUST verify idempotency (zero duplicate work orders, zero duplicate issues/PRs for the same task/branch) before filing or claiming.
  6. **Zero-Recurrence Invariant (Anti-Regression & Continuous Learning):** Every identified mistake, defect, false closure, or contract violation MUST have an automated mechanical guard or test written against it. A mistake once discovered and remediated MUST NEVER recur. Machine enforcement supersedes human vigilance.
  7. **Loop-Driven Determinism:** Agents NEVER guess, speculate, or arbitrarily pick tasks. The continuous autonomous loop (`continuous_agent_loop.py`) is the sole SSOT for task assignment, dispatching, and role constraints. "The loop is the permission (U10)."
  8. **Universal Defect Ownership & Anti-Blindspot Invariant:** Whenever an agent discovers, uncovers, or observes ANY unhandled defect, pipeline failure (such as failed unmerged PRs or silent gate rejections), architectural blindspot, or unowned failure anywhere in the federation during execution, the agent MUST NEVER ignore, bypass, or silently discard it. The agent must record, claim, or surface an actionable structured work order with proper deduplication before considering its cycle complete. Avoidance of discovered defects is strictly prohibited.
  9. **Full-Scope Completeness Invariant (End-to-End Implementation):** Agents (specifically `solver`) MUST NEVER deliver half-done or partial solutions. When a task requires database changes, schema migrations, environment configurations, security rules (RLS), or API wiring, the agent MUST write and submit the migration/config files as part of the exact same patch or PR. Leaving database schemas unmigrated, configs unmapped, or tests unwritten while marking a task "fixed" or "complete" is strictly prohibited.
  10. **The Simplest Solution & Anti-Bloat Invariant (Occam's Razor for Code & PRs):** Every agent (whether working on PRs or committing to branches) MUST always adopt the **simplest, most minimal, and most direct solution** that satisfies the contract. Never over-engineer, never invent complex multi-layered abstractions when a direct fix suffices, and never bloat existing files with sprawling logic. The smallest clean patch that solves the root cause and protects against regressions is the only acceptable pattern. Complexity is a liability, not an asset.
  11. **Zero Cross-Agent Collateral Invariant (Task-Scope & Code Preservation):** An agent MUST NEVER break, delete, or overwrite another agent's work. PRs are strictly scoped to the declared task domain (cross-domain file tampering is rejected by preflight guards). Agents MUST NOT delete existing passing tests or weaken assertion suites to pass CI. Changes to shared files MUST be minimal, surgical diff patches with current baseSha verification—full-file blind overwrites are strictly prohibited.
  12. **Atomic Completeness & Anti-Micro-PR Fragmentation Invariant:** While PRs must remain minimally scoped to their task (anti-bloat), agents MUST NEVER artificially fragment a single interdependent solution into multiple fragile micro-PRs. Fragmenting mutually dependent fixes leaves `main` in a broken intermediate state, chokes CI queue budgets, and triggers cascade stale-base rejections. A PR must be **atomically complete**: all mutually dependent changes required to make CI green, pass test collection, and fulfill the contract must land together in one cohesive, green-verified submission.
  13. **Universal 3-Tier Runner & Lowest-Runtime Constitution (Zero Cloud Waste for ALL Present & Future Workflows):**
      - **Single Universal Rule (Zero Rule Proliferation):** Whether there are 10, 10,000, or 1,000,000 similar workflows or tasks, all follow THIS EXACT SAME SINGLE RULE. We NEVER invent separate rules for separate workflows. If any genuine exception ever exists, that exception MUST be formally documented in `docs/PR_TO_PRODUCTION_LIFECYCLE.md` with explicit justification (what is the exception, and why).
      - **Zero Unchecked PR Invariant:** Every pull request without exception must trigger CI checks; merging a PR with 0 checks is strictly prohibited.
      - **Tier 1 (Priority 1 — Local-PC Native):** Any job taking > 30 seconds MUST query `resolve_execution_tier.py`. If `local-pc` is online, 90–95% of execution runs on the local Windows runner (`[self-hosted, local-pc]`). GitHub Cloud minutes spent = 0m.
      - **Tier 2 (Priority 2 — Render CI Runner):** If `local-pc` is offline/asleep, fallback dispatches to Render CI Runner pool.
      - **Tier 3 (Priority 3/4 — GitHub Cloud Fallback):** GitHub Actions Ubuntu runner is ONLY a safety-net fallback when both local-pc and Render are unavailable.
      - **GitHub Cloud Action Window Cap (≤ 15-20 Seconds):** The GitHub Cloud job's responsibility is strictly limited to pre-flight trigger and auto-merge land. Consuming minutes on GitHub-hosted cloud runners when local or Render infrastructure is alive is a direct constitutional violation.

- **MUST AVOID:**
  - **NO Direct Push:** Never push directly to satellites or protected branches without PR gate.
  - **NO Root Shadowing:** Never put satellite code in repo root (`src/*`, `service/*`, `packages/*`).
  - **NO Ghost Fixes:** Never mask errors or fix issues not reproduced on live `main`.
  - **NO Over-Engineering & Code Bloat:** Never introduce sprawling, multi-hundred-line monolith logic or complex speculative architectures when a simple, direct 5-10 line patch solves the root cause.
  - **NO Micro-PR Fragmentation:** Never split a single interdependent fix into multiple partial PRs that leave `main` in an unbuildable or broken-test intermediate state.
  - **NO Cross-Domain Contamination:** Never touch or alter files belonging to other domain desks outside the assigned task envelope.
  - **NO Test Weakening / Erasure:** Never delete, skip, or comment out another agent's existing tests to force a green CI build.
  - **NO Incomplete / Half-Baked Submissions:** Never claim a task or bug is resolved when the underlying database migration, configuration, or integration dependency remains missing or unapplied.
  - **NO Backlog Starvation / Duplicate Stampede:** Never bypass open P0 blockers to create or pick up fast-follow research tickets, and never spawn duplicate PRs/work orders for the same task.
  - **NO Speculative Dispatch:** Never manually claim or work on issues outside the loop's dispatch envelope.
  - **NO Defect Avoidance / Blindspot Bypassing:** Never observe a broken pipeline, failed unmerged PR, or system defect and walk away without mechanical recording or remediation.

**Beyond these guardrails, you have absolute freedom on HOW to solve your task. Never ask for permission.**

---

## 🌐 External Agent Hybrid Invariant

External web agents participate through the hybrid bridge contract. The following rules are non-negotiable:

- **READ Boundary:** External web agents MAY read the codebase, history, and issue tracking through direct `github-reader` tools (`get_issue`, `get_file_contents`, `search_repositories`). Read access is read-only.
- **Single Write Gateway (Enforced):** No external agent may commit to GitHub or open a direct PR. Every code change MUST arrive through the Tower's `bridge_submit` / `bridge_submit_patch` API (`taskId`, `files`, `summary`, `reflectionWhy`, `alternativesRejected`, `testsEvidence`, `agentIdentity`).
- **Stale-Base Pin (Fail-Closed CAS Gate):** For `full_file` on a path that already exists, always declare `files[].baseSha` pinned to the CURRENT landed blob SHA (`git rev-parse HEAD:<path>` on a freshly rebased tree). The gate is **fail-closed**: a stale `baseSha` is rejected with `STALE_BASE_ERROR`; an existing path with **no declared `baseSha`** is rejected with `STALE_BASE_MISSING`; an unverifiable main read rejects with `STALE_BASE_UNVERIFIED`; only a **brand-new path** (absent on main) may omit it. This dynamically guarantees that concurrent landed commits are never silently overwritten.
- **Credential Zero-Leak Rule:** No agent may print or expose GitHub tokens or secrets in plaintext in console output or prompt logs. Secrets are loaded from secret stores into memory only (`GITHUB_READONLY_TOKEN`).
- **Render Service Health & Cold-Start Policy (Zero-Leniency Invariant):** SupremeAI maintains a persistent, zero-cost Cloudflare Keep-Warm Mesh (`infrastructure/cloudflare-render-keepwarm/worker.js`) pinging all service endpoints on a tight 5-minute schedule. Render free-tier instances dormancy threshold is 15 minutes; with the keepwarm mesh active, **services MUST NEVER sleep or cold-start**. AI agents (`platform-guardian`, `solver`, `inspector`, etc.) MUST NEVER excuse or dismiss a non-2xx health check or read timeout as "normal cold-start". Any service reporting degraded, read timeout, or 5xx MUST be treated as an **ACTIVE SYSTEM DEFECT / INCIDENT (ERROR)**, investigated for underlying root causes (OOM, unhandled crash, route mismatch, or keepwarm failure), and escalated or remediated immediately.

---

### Tool Routing Contract

- **Rule 1 (Intel / Reading):** Use only `github-reader` tools (`get_issue`, `get_file_contents`, `search_repositories`) for GitHub issues, file contents, discussions, and history.
- **Rule 2 (Submission / PR):** Never call direct GitHub push tools. Send code changes through the Tower `bridge_submit` / `bridge_submit_patch` API with `taskId`, `files`, `summary`, `reflectionWhy`, `alternativesRejected`, `testsEvidence`, `agentIdentity`, and per-file `baseSha` pinned to the current blob (see Stale-Base Pin above).
- **Rule 3 (Infrastructure Health):** Use only Tower tools such as `supabase_schema_inspect` and `render_service_health` for database, cache, or deployment status.
- **Rule 4 (Payload Shape Conventions & Truth Verification):** The Tower's GitHub list adapters emit **camelCase** keys (`createdAt`, `updatedAt`, `mergedAt`, `closedAt`), and list-mode rows omit `body` / `labels` / `head` / `draft` and the `merged` boolean. Single-PR addressability (`github.list_prs` with `pull_number`) returns the complete truth state (`merged: true|false` plus timestamps). Landing verification ("did the PR merge?") MUST use `pull_number` addressability or direct `git log origin/main` — never a list-mode snake_case probe.

---

## Push Mode Policy (Anti-Regression)

- **Prefer patch over full_file.** Use `bridge_submit_patch` for existing files.
- **full_file is allowed ONLY for brand-new paths** (absent on main).
- **full_file on existing paths requires baseSha CAS** (stale-base check).
- This reduces regression risk: patches are smaller, targeted, and conflict-detectable.
- Agents MUST NOT use full_file to overwrite large files when a patch suffices.

---

## Stale PR Fix Workflow (No Force-Push)

When a PR fails CI due to stale base (Autonomous Auto-Landing / Stale-Base Guard):

1. Fetch the PR branch: `git fetch origin <branch>`
2. Create worktree: `git worktree add <path> origin/<branch>`
3. Merge main (NOT rebase): `git merge origin/main --no-edit`
4. Resolve conflicts: deleted file in main -> `git rm <file>`; others -> resolve + `git add`
5. Commit merge: `git commit --no-verify --no-edit`
6. Push (no force, no verify): `git push origin HEAD:<branch> --no-verify`
7. Cleanup: `git worktree remove <path> --force`

NEVER use `git rebase + force push` (regression risk + branch protection blocks).  
NEVER use `git push --force` (blocked by branch protection).

### Pre-submission checks (before creating PR):
- Run: `python scripts/ci/pr_preflight_guard.py --branch <name> --files <changed> --pr-body <file>`
- pre-commit hook runs automatically on commit (branch naming, boundary, lint, parity)

### Landing & Merge Policy (Zero Failed-Merge Invariant):
- Agents MUST NEVER call `gh pr merge` (or `gh pr merge --auto`) from the terminal upon PR creation. In private repositories on GitHub Free plans, native CLI auto-merge evaluates with 0 required checks and merges immediately before CI can run, completely bypassing test verification!
- PRs MUST land EXCLUSIVELY via the in-workflow `🛬 Autonomous Auto-Landing` gate in `.github/workflows/unified-pipeline.yml`, which evaluates all Tier 1 and Tier 2 test results and executes `gh pr merge` ONLY when all gates are 100% green. If a single test fails, the merge is strictly skipped and blocked.
- PR bodies MUST always contain `## Reflection Evidence`, `3-Tier Verify` (or `Test Evidence`), and issue linkage to satisfy the Tower Verification Signature Guard.

### Operational Modes & Task Routing:
- **New work:** `git checkout -b <branch-prefix>/<slug>`, commit, push (pre-commit guards run).
- **Stale PR fix:** merge main + push `--no-verify` (via isolated worktree workflow above).
- **Failed PR audit:** loop reports failing PRs; solver marks existing issue as `ci-failed`.
- **Close PR:** only if superseded or invalid branch name (document reason in issue).
