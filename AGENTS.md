# SupremeAI — AGENTS.md

> Universal rules for AI agents working on SupremeAI.
> Keep this file stable. Project-specific values and changing implementation details belong in the repository's current source of truth.

## 1. Rule Priority

When rules conflict, follow this order:

**Safety & Security → User Intent → Task Scope → Existing Architecture → Correctness → Reliability → Performance/Cost → Convenience**

Never invent or assume facts, credentials, APIs, files, commands, configuration, or system behavior.

---

## 2. Core Agent Loop

Before changing anything, follow:

**Understand → Inspect → Check Other Work → Act → Verify → Report**

Mandatory before implementation:

1. Read the task and relevant GitHub Issue.
2. Inspect the relevant code, configuration, contracts, and tests.
3. Reuse existing project capabilities before creating new ones.
4. Check current work/ownership state when applicable.
5. Check active work that may touch the same files, shared contracts, or nearby behavior.
6. Use repository configuration as the source of truth.
7. Do not guess when evidence is available.

### Cross-Task Safety

Two agents may work on different Issues and still affect each other.

Before editing, ask:

**"Could my change touch something another active task is changing or depends on?"**

Check at least:

* active Issues and PRs;
* changed files when available;
* shared APIs/contracts/configuration;
* recently changed code related to the task.

If likely overlap exists, **do not start editing blindly**. Record the dependency/overlap and coordinate ownership first.

Different Issues do **not** automatically mean independent changes.

### Progress Over Perfection

Agents should prioritize **meaningful, safe, verified progress** over theoretical perfection.

When a change is clearly better than the current state and does not introduce a real blocker:

**improve → verify → move forward**

Do not delay useful work only because:

* a more elegant solution might exist;
* the change could be polished further;
* an edge case is theoretical and does not affect the current task;
* the implementation is not the absolute best possible version.

A possible improvement is **not automatically a reason to stop**.

Real blockers remain blockers, including:

* security or safety risk;
* data loss or corruption;
* broken required behavior;
* incorrect requirements or unacceptable compatibility impact;
* unresolved ownership or cross-task conflict;
* failed required verification.

When no real blocker exists, complete the useful change and record worthwhile follow-up improvements for a later task rather than expanding the current task indefinitely.

**Goal: leave the project materially better, safe, and verified — not theoretically perfect.**

## 3. Issue-First & Single Ownership

### Rule

**1 Branch = 1 Persistent Agent Workspace | 1 Agent = 1 Active Issue | 1 Issue = 1 PR**

An Issue is the unit of work. A commit is only a step inside that work.

Every bug, feature, task, significant gap, or multi-step change must be tracked by a GitHub Issue before implementation.

### 🚫 STRICT FORBIDDEN: Modifying Code Without Claimed Issue

**FORBIDDEN: Touching, modifying, committing, or pushing code without an atomically claimed GitHub Issue is STRICTLY PROHIBITED for ALL agents and operators (`agent-3-coder-1`, `agent-6-coder-2`, `agent-7-solver-b`, `agent-12-ci-fixer`, `agent-2-pr-helper`, and Local IDE sessions including Cline, Antigravity IDE, Cursor, etc.).**

Every code-modifying agent and Local IDE operator MUST strictly uphold:
1. **NO CLAIM, NO CODE (Universal Rule)**: Even in Local IDE, you must NEVER edit, touch, or commit code before an Issue is created/claimed and confirmed with `status:in-progress` lock. Local IDE has omni-role capability, but is NOT exempt from the Issue-first discipline.
2. **VERIFIED OWNERSHIP FIRST**: If an issue is already assigned to another agent or has an active `status:in-progress` lock, STOP immediately. Do NOT touch any file.
3. **COMMITS & PRS MUST REFERENCE ISSUE**: Every commit message and PR must explicitly reference the claimed Issue (e.g. `feat(auth): add router auth (#1706)`).
4. **UNCLAIMED EDITS ARE INVALID**: Any PR or branch modification initiated without an atomically claimed Issue is considered an unauthorized rogue action and will be blocked and rejected by PR gates.

### Self-Assignment via MCP Control Tower

Agents do **not** wait for a human to assign an Issue. Upon activation, every agent:

1. **Connects to the MCP Control Tower** (see §20) and reads its assigned slot from
   `docs/master_docs/AGENT_SLOT_REGISTRY.yaml`.
2. **Queries open Issues** that match its lane (role) and have no `status:in-progress` lock.
3. **Self-selects the highest-priority matching Issue** from the backlog.
4. **Atomically claims it**:

```bash
GH_TOKEN=<token> GH_REPO=SaifulHaqueNiloy/supremeai \
  scripts/ci/atomic_claim.sh <issue_number> <agent_slot>
# e.g. scripts/ci/atomic_claim.sh 1617 agent-3-coder-1
```

5. The claim must establish:
   * active ownership (assignee = slot name);
   * `status:in-progress` label;
   * audit evidence (claim comment on the Issue).
6. Re-read the Issue after claiming to confirm ownership before touching any file.

**If no matching unowned Issue exists**: report idle status via MCP and wait.
**If claim fails (race lost)**: pick the next candidate from the backlog immediately.

### Single Active Owner

* Only **one agent may actively edit a task branch at a time**.
* Many agents may inspect, advise, or review the work.
* A reviewer does not become a second implementer just because the reviewer finds a problem.
* Do not let two agents write to the same task branch at the same time.

### Ownership Handoff

If another agent must continue or fix the work:

1. The current owner stops editing.
2. Record the current state and outstanding work in the Issue/PR.
3. Remove `status:in-progress` label and remove self from assignees.
4. The next agent claims the Issue via `atomic_claim.sh`.
5. The new owner fetches and verifies the task branch before editing.
6. Only then does the new owner continue.

**No overlapping edits.**

A handoff does **not** require a new Issue or a new branch when the task is still the same.

### Canonical Lock

`status:in-progress` is the canonical active-work lock.

`processing` is treated only as a legacy equivalent if already present. Do not create multiple competing active-status labels.

### Race Rule

If another agent already owns the Issue or the active-work lock exists:

**STOP. Do not edit the Issue, branch, or files. Pick the next Issue from the backlog.**

Never silently take over another agent's work.

### Claim Failure

If `atomic_claim.sh` is unavailable, use the documented repository fallback and verify ownership before editing.

Required environment:

```bash
GH_TOKEN=<token>
GH_REPO=SaifulHaqueNiloy/supremeai
```

A claim is successful only after ownership is verified.

### Split Rule

If the requested work grows into **independent pieces**, split it into separate Issues.

Use:

```text
Issue A → Branch A → PR A
Issue B → Branch B → PR B
```

Do not place unrelated work into one Issue/branch/PR merely because the tasks were discovered together.

## 4. Agent Workspace, Branch Model & Bot Identity

SupremeAI uses **persistent Agent Branches** with **fixed role-based names**.

A branch represents a **work slot/workspace**, not a permanent AI model.

### Core Rules

```text
1 Branch = 1 Persistent Agent Workspace
1 Branch = 1 Fixed Role Lane
1 Branch = 1 Active AI Writer at a time
1 Agent = 1 Active Issue at a time
1 Issue = 1 PR
```

### Canonical Slot Registry

The **single source of truth** for all agent slots, branch names, roles, and bot identities is:

```
docs/master_docs/AGENT_SLOT_REGISTRY.yaml
```

Do **not** hardcode slot information here. Read the registry file before starting work.
Always use the registry's `branch` field as the exact branch name.

### Fixed Branch Naming Convention

All agent branches follow the pattern:

```
agent-<N>-<role-slug>
```

**Examples from the current registry:**

```text
Slot         Branch                  Role
─────────────────────────────────────────────────────────────
agent-1      agent-1-planner         Planner & Full Auditor
agent-2      agent-2-pr-helper       PR Gate & Diagnostics
agent-3      agent-3-coder-1         Primary Code Implementer
agent-5      agent-5-ci-action       CI/CD & Workflow Specialist
agent-6      agent-6-coder-2         Parallel Code Implementer
agent-7      agent-7-solver-b        Dedicated Issue Solver
agent-8      agent-8-pr-verifier     PR Verifier
agent-10     agent-10                Orchestrator / Super Agent
agent-11     agent-11-longrun/*      Platform Agent (long-running)
agent-12     agent-12-ci-fixer       CI Log Watcher & Fixer
agent-13     agent-13-browser-tester Post-Merge Browser Tester
```

The `agent-11` slot uses the extended pattern `agent-11-longrun/issue-<N>-<slug>` for
long-running platform tasks (pre-approved exception in the registry).

**FORBIDDEN branch patterns** that will be rejected by Branch Naming Guard:
- Generic `agent-1`, `agent-2` without a role slug (unless the registry explicitly lists that form)
- `feature/...`, `bug/...` (use `feat/`, `fix/`)
- Any slot not present in the registry

### Branch Naming Guard (CI Enforcement)

The `Branch Naming Guard` workflow enforces:

```
^(agent-[a-zA-Z0-9_-]+/issue-[0-9]+-.+  ← agent-11 long-run
|agent-[0-9]+(-[a-zA-Z0-9_-]+)?          ← all named slots
|feat/.+|fix/.+|hotfix/.+|perf/.+
|chore/.+|test/.+|docs/.+|refactor/.+|ci/.+
|dependabot/.+|github-actions/.+|renovate/.+|pr-helper/.+
|develop|main)$
```

A PR with a non-matching branch name is **blocked from merging** to `main`.

### Bot Identity Registry

Every agent slot that creates commits, PRs, or CI comments uses a **fixed bot identity**.
Bot identities prevent authorship confusion and allow per-bot permission scoping.

| Slot | Branch | Bot Identity | Git user.name |
|------|--------|-------------|---------------|
| agent-2 | agent-2-pr-helper | `supremeai-pr-helper[bot]` | `supremeai-pr-helper[bot]` |
| CI self-heal | chore/artifact-regen-latest | `supremeai-pr-helper[bot]` | `supremeai-pr-helper[bot]` |
| agent-11 | agent-11-longrun/* | `supremeai-platform-agent[bot]` | `supremeai-platform-agent[bot]` |
| Dependabot | dependabot/* | GitHub native | (managed by GitHub) |
| Local IDE | (all branches) | developer / operator | (local git config) |

### Local IDE (Omni-Role Operator)

The **Local IDE** (running in Cline, Antigravity IDE, Cursor, etc. via stdio transport) represents the root human-in-the-loop developer and operator environment.
- **No Fixed Narrow Role**: Unlike remote autonomous CI agents that are bound to single fixed roles, Local IDE has **omni-role capability** (`role: admin`, `scopes: [*]`).
- **Cross-Role Execution**: Local IDE can operate across any slot (Planner, Coder, Fixer, PR Verifier, Orchestrator, or Global Admin) and has unrestricted access to all Control Tower MCP tools.

**Token rule for automated pushes:**

> Any workflow that performs `git push` or `gh pr create` **MUST** use
> `secrets.SELF_HEAL_PAT || github.token` — never bare `github.token` alone.
> `GITHUB_TOKEN` pushes are silently suppressed by GitHub's anti-recursion rule:
> no CI workflows fire, required checks are never created, and PRs stay `BLOCKED`
> indefinitely. See issue #1634.

### Parallel Work

A busy branch does **not** block the whole role lane.

```text
Coder lane
  agent-3-coder-1 → ACTIVE 🔴  (Issue #1617)
  agent-6-coder-2 → IDLE   🟢  → picks next Issue
  agent-7-solver-b → IDLE  🟢  → picks next Issue
```

Different Agent branches may work in parallel when their tasks do not conflict.

### Branch Lock

When an AI is actively working on an Agent branch:

```text
agent-3-coder-1
  └── ACTIVE / LOCKED (Issue #1617)
```

Another AI must not simultaneously modify that same branch.

The branch becomes available again after the current work is completed, handed off,
or `status:in-progress` is released (stale cleanup fires after 4 hours of inactivity).

### AI Is Replaceable — Branch Is Not

An Agent Branch is **not permanently assigned to one AI model**.

```text
Day 1:  agent-3-coder-1 → AI-A → Issue #1410
Day 2:  agent-3-coder-1 → AI-B → Issue #1517
Day 3:  agent-3-coder-1 → AI-C → Issue #1617
```

A new AI taking over a branch **MUST** first read:

```text
• docs/master_docs/AGENT_SLOT_REGISTRY.yaml  ← role & constraints
• previous commits on the branch
• previous PRs from this branch
• current branch state (git status, git log)
• linked GitHub Issues
• LESSONS_LEARNED.md
```

Therefore:

```text
Agent Branch = persistent workspace / history
AI Model     = replaceable worker
Role         = fixed lane (read from registry)
Bot Identity = fixed git author (read from registry)
Issue        = current task (self-selected from backlog)
PR           = proposed integration
```

### Before Starting Work (Checklist)

The assigned AI MUST complete in order:

1. Read `docs/master_docs/AGENT_SLOT_REGISTRY.yaml` → confirm own slot, branch, and role.
2. Connect to MCP Control Tower (see §20) and query current system health.
3. Check whether the branch has uncommitted or in-progress work from a previous session.
4. Sync to latest `origin/main` (`git fetch && git merge origin/main`).
5. Query the Issue backlog — pick the highest-priority unowned Issue matching the role lane.
6. Run `atomic_claim.sh` to self-assign.
7. Verify claim success before touching any file.
8. Check active peer PRs for file overlap (`scripts/git/cross_pr_collision_detector.py`).
9. Start implementation only after all above pass.

### Cross-Agent Work

```text
Different Issue + non-overlapping files → parallel work is safe
Different Issue + overlapping files     → coordinate BEFORE editing
Same Issue                              → only one owner allowed
```

An Agent must never assume another branch's unmerged work is invisible or irrelevant.

### Workspace Invariants

* Never push directly to `main`.
* Never modify another agent's active branch.
* Unexpected uncommitted changes are **not yours by default**.
* Never discard, reset, or overwrite unknown work without establishing ownership.
* All self-healing CI commits use `SELF_HEAL_PAT` — never bare `github.token`.

Before editing:

**Slot confirmed → branch free → main synced → Issue claimed → peer overlap clear**

If any of these is ambiguous: **STOP.**

### System Architecture

```text
            SUPREMEAI MULTI-AGENT SYSTEM
                         │
              MCP Control Tower (§20)
                         │
          ┌──────────────┼──────────────┐
          │              │              │
    Planning Lane   Coder Lane    CI/CD Lane
          │              │              │
   agent-1-planner  agent-3-coder-1  agent-5-ci-action
                    agent-6-coder-2  agent-12-ci-fixer
                    agent-7-solver-b
          │              │              │
   PR Gate Lane    Platform Lane   Browser Lane
   agent-2-pr-helper  agent-11     agent-13-browser-tester
   agent-8-pr-verifier
                         │
                    agent-10 (Orchestrator)
                         │
                    origin/main
```

**Key principle:**

> **The branch stays; the AI can change. The role stays; the issue self-selects.**

## 5. Main Synchronization & Push Safety

Before implementation and again before push/PR:

**fetch → compare → update from latest \`origin/main\` → resolve conflicts → verify → push**

### Before Push: Cross-Task Check

A clean diff against \`main\` is **not enough** when another task is still unmerged.

Before pushing:

1. Compare the task branch with the latest \`origin/main\`.
2. Inspect active PRs/branches that may affect the same files, shared APIs, configuration, or behavior.
3. Check for both:
   * direct overlap — both tasks change the same file or area;
   * indirect overlap — one task changes something the other task relies on.
4. If overlap or dependency is unclear, **STOP before pushing** and coordinate.
5. Continue only after the relationship is understood and the change remains safe.

### When Two Different Tasks Need the Same Unfinished Change

Never silently edit the other task's branch.

Prefer:

\`\`\`text
Task A needs Task B
        ↓
record dependency
        ↓
wait for B to finish/merge
        ↓
A updates from main
        ↓
continue
\`\`\`

When the shared change is actually a separate reusable piece:

\`\`\`text
Shared change
     ↓
separate Issue
     ↓
one branch
     ↓
one PR
     ↓
merge
     ↓
A and B use the result
\`\`\`

Do not create hidden cross-branch dependencies.

### After Conflict Resolution

Any time a conflict is resolved:

**resolve → inspect the result → rerun affected checks → then push**

Never assume a successful conflict resolution means the code is correct.

### Requirements

* start from the latest \`main\`;
* re-check \`origin/main\` before PR;
* resolve conflicts locally;
* rerun affected verification after conflict resolution;
* push only verified work;
* never use unsafe force-push;
* never overwrite another agent's commits.

After a review fix:

* keep the fix on the same task branch and same PR;
* add a new commit when appropriate;
* rerun the affected verification;
* do not create a new branch merely because the PR received review feedback.

If rebase or merge produces unexpected changes:

**STOP → inspect → resolve intentionally → verify again.**

### Key Rule

**Before push, check both \`main\` and active peer work.**

## 6. Scope & Engineering Discipline

**Make the narrowest sound change.**

* Change only what the task requires.
* Prefer existing modules, utilities, contracts, and patterns.
* Do not duplicate existing capabilities.
* Preserve APIs, data contracts, and behavior unless change is required.
* Avoid unnecessary rewrites, migrations, or broad refactors.
* Do not mix unrelated improvements into the PR.
* Do not delete tests, audits, plans, safeguards, or required documentation without explicit instruction.
* Keep code modular, maintainable, observable, and production-ready.

---

## 7. Security

**Hard for attackers. Easy for legitimate users.**

* Secure by default.
* Apply least privilege and strict tenant/data isolation.
* Never hardcode, expose, print, commit, or invent secrets.
* Use the project's approved secret/configuration mechanism.
* Never weaken security to make a test, build, deployment, or workflow pass.
* Protect destructive and high-impact operations with appropriate safeguards.
* Do not bypass authentication, authorization, validation, rate limits, or isolation.
* Agents may be powerful, but must never exceed their granted authority.
* Infisical access in this project MUST use the raw secrets path
  (`/api/v3/secrets/raw?...`) — the standard `listSecrets()` API is broken by
  vendor blind-index corruption (#434) and silently returns an empty vault.
  See `docs/SECRETS_OPERATIONS.md` §"Integrator warning" before writing any
  vault-reading integration.

### Security Principle

**Internal complexity may be high; legitimate user interaction should remain simple.**

---

## 8. Dynamic & Extensible Design

Prefer:

**configuration → discovery → execution**

over hardcoded:

**provider → model → resource → value**

Use current configuration and established project standards.

Keep providers, models, tools, resources, and infrastructure replaceable where practical.

Do not introduce arbitrary hardcoded values merely for convenience.

---

## 9. Zero Regression & Real Fixes

**A change must not knowingly reduce existing functionality, security, reliability, or test coverage.**

Before completion:

* run relevant tests;
* run relevant type checks;
* run relevant lint/build checks;
* run relevant regression/security checks;
* verify affected runtime behavior where practical.

### Prohibited

* skipping a failing test to obtain green status;
* weakening assertions;
* hiding failures behind fake configuration;
* masking real failures with cosmetic string/message changes;
* changing behavior only to satisfy a check without fixing the root cause;
* using mocks/stubs to conceal the behavior actually being verified.

Mocks are allowed only where appropriate to test a legitimate boundary and must never be used to manufacture a false green result.

### Rule

**Green means verified, not merely executed.**

Any newly discovered regression blocks completion until resolved or explicitly accepted by the appropriate authority.

---

## 10. Resilience & Safe Failure

**Fail safe. Recover when safe. Never fail silently.**

When something fails:

* protect data and security boundaries;
* avoid corruption or unsafe continuation;
* retry/fallback/recover when appropriate;
* surface a clear blocker when safe recovery is unavailable.

A failed required verification step must never silently become PASS.

---

## 11. Verification Evidence

Do not claim work is complete from assumptions.

Completion requires evidence appropriate to the change.

Verify the **affected behavior**, not only compilation or syntax.

When automation reports PASS, confirm that required steps actually executed successfully and that no required failure was suppressed.

---

## 12. Blockers & Manual Actions

When progress requires:

* human intervention;
* unavailable permission;
* external dependency;
* infrastructure/configuration change;
* destructive approval;

do not bypass the requirement.

Document the blocker and create/link a dedicated GitHub Issue when appropriate.

Independent work may continue only when it does not interfere with the blocked task.

---

## 13. Atomic PR Lifecycle

### Core Rule

**1 Branch = 1 Persistent Agent Workspace | 1 Agent = 1 Active Issue | 1 Issue = 1 PR**

A PR represents the complete change for one Issue originating from the assigned persistent Agent Branch. It is not tied to a single commit.

A task may use:

\`\`\`text
1 commit
2 commits
10 commits
N commits
\`\`\`

All remain on the **same Agent branch** and flow into the **same PR**.

### PR Responsibilities

**Implementing owner:**
* confirms and locks the assigned persistent Agent Branch;
* implements the Issue;
* creates/updates the PR;
* responds to review findings;
* fixes problems on the same Agent branch;
* reruns affected checks after fixes.

**Reviewer/checker:**
* inspects the PR and the evidence;
* identifies problems, missing tests, regressions, or scope issues;
* checks for overlap with other active work when relevant;
* comments or requests changes;
* re-checks after fixes;
* does not modify the Agent branch by default.

### Review Loop

\`\`\`text
Issue
 ↓
Claim & Assign Agent Branch
 ↓
Check other active work
 ↓
Persistent Agent Branch
 ↓
Implement
 ↓
1..N commits
 ↓
Before push: main + peer-work check
 ↓
PR
 ↓
Review
 ├── approved → merge
 │
 └── changes requested
          ↓
      owner fixes
          ↓
       new commit(s)
          ↓
       same Agent branch / PR
          ↓
       review again
\`\`\`

### Fixer Handoff

A separate agent may perform the fix only after an explicit ownership handoff:

\`\`\`text
Owner A stops
    ↓
Handoff recorded
    ↓
Owner B claims Issue & Agent branch
    ↓
Owner B syncs/verifies Agent branch
    ↓
Owner B fixes
    ↓
Same PR
\`\`\`

Never allow Owner A and Owner B to edit the same branch simultaneously.

### Progress Over Perfection in PRs

The goal of Agent work is **safe forward progress**, not unnecessary perfection.

\`\`\`text
Target = 100
Current = 1

PR → 2     = useful forward progress
PR → 1.9   = small issue → fix and continue
PR → 0.9   = backward movement → investigate/block
\`\`\`

The numbers are only an illustration.

Do not reject useful work merely because a theoretically better solution exists.
Do not accept work that creates a real regression, security problem, incorrect behavior, data loss, or other meaningful blocker.

### Final Integration Gate

The final integration/merge agent has a separate responsibility:

Normal Agents:
\`\`\`text
Understand → Work → Verify → PR
\`\`\`

Integration Agent:
\`\`\`text
Review → Check direction → Check conflicts → Keep / combine / rework / stop → Safely integrate
\`\`\`

The integration decision must be based on whether the project is safely moving toward its intended target—not on which AI created the change, which branch created it, or whether the change is theoretically perfect.

### Split Rule

When review or implementation reveals that requested work is actually a separate task:

**stop → create/link a new Issue → assign to an available Agent branch → create a new PR**

Do not grow the original PR into an unrelated collection of changes.

### Merge

Merge only after required verification, review, and cross-task checks are complete.

After merge:

**PR merged → Issue closed/confirmed → Agent branch lock released**

Only then is the task considered finished and the agent/branch free to claim another Issue.

## 14. Safe Evolution

Prefer backward-compatible changes.

Protect existing:

* users;
* APIs;
* data;
* workflows;
* integrations;
* contracts.

When a breaking or destructive change is necessary, make the impact explicit and provide an appropriate migration, rollback, or recovery path.

---

## 15. Source of Truth

Environment-specific and frequently changing information must come from the repository's current source of truth, not this file.

Examples include:

* repository configuration;
* service URLs;
* credentials/secrets;
* providers/models;
* deployment settings;
* infrastructure;
* CI commands;
* feature flags;
* runtime configuration.

Never copy stale values into code or this document merely because they appeared elsewhere.

---

## 16. Communication

Match the user's requested language.

Keep updates and final reports concise, factual, and evidence-based.

Clearly distinguish:

**Verified → Assumption → Blocker → Remaining**

Never claim success without evidence.

---

## 17. Stop Conditions

An agent must stop making changes when any of the following occurs:

* Issue ownership is unclear;
* another agent owns the task;
* another active task appears to overlap with the planned change;
* unexpected workspace changes may belong to another agent;
* required permissions are unavailable;
* secrets are unexpectedly exposed;
* a merge/rebase conflict is unresolved;
* a cross-task dependency is unclear;
* task scope becomes ambiguous;
* a required verification fails and the root cause is not yet understood;
* proceeding would require bypassing a safety, security, or integrity rule.

**STOP → INSPECT → RESOLVE → VERIFY → CONTINUE**

### Conflict Rule

When two agents need to change the same thing:

**Do not race. Do not overwrite. Do not pick a winner silently.**

Instead:

**identify → coordinate → choose one owner → make one clean change → verify → continue**

## 18. Completion

A task is complete only after:

**Claimed → Agent Branch Assigned → Implemented → Verified → PR Created → Review Complete → PR Merged → Issue Closed → Branch Lock Released**

Final report:

**Changed / Verified / Remaining**

For multi-agent work, also record when applicable:

* who currently owns the task;
* whether ownership was handed off;
* which branch and PR contain the work;
* whether review findings were fixed and re-checked.

The final state must be unambiguous: **one Issue, one persistent Agent branch, one focused PR, one completed ownership cycle.**



---

## 19. Final Integration / PR Manager

The final integration agent has a different primary responsibility from ordinary task agents.

### Primary Task

**Protect the project's forward direction while integrating changes safely.**

The integration agent should think in terms of:

\`\`\`text
Current project state → Intended target → Where is this PR taking us?
\`\`\`

A PR does not need to be perfect.

A PR that moves the project clearly forward should normally be welcomed when it is safe and verified.

Think:

\`\`\`text
Target: 100

Current: 1
PR → 2
→ welcome

Current: 1
PR → 1.9
→ welcome after the small issue is fixed

Current: 1
PR → 0.9
→ block and investigate
\`\`\`

The exact numbers are only a way to express **direction**, not a literal score.

### Merge Decision

Before merge, the integration agent should answer:

1. Does this change move the project toward the intended result?
2. Is any small imperfection fixable without changing the overall direction?
3. Did the change introduce a real backward movement, regression, security problem, data risk, or unresolved conflict?
4. Does the combined result of this PR with other changes still move the project forward?
5. Is the resulting state verified enough for this task?

### Do Not Block for Perfection

Do not block a useful change merely because:

* an even better implementation could exist;
* the code could be polished further;
* another architecture might be more elegant;
* a non-critical improvement is still possible.

A real problem must be fixed or explicitly handled.

A better future version is not a reason to reject a clearly useful present version.

### Small Mistakes

If the PR is moving the project in the correct direction but has a small fixable problem:

**fix → verify → continue forward**

Do not treat every imperfection as a reason to redesign the whole change.

### Real Backward Movement

If the combined result makes the project materially worse, the integration agent must not merge it merely because the PR is green.

Examples include:

* required behavior is lost;
* existing functionality is broken;
* security is weakened;
* data may be lost or corrupted;
* another task's required work is silently overwritten;
* an unresolved conflict changes the intended result.

In these cases:

**stop → understand → fix/rework → verify**

### Conflict Resolution

When two changes touch the same thing:

**do not choose by size, age, agent, or "ours/theirs".**

First understand what the final project needs.

Then choose the smallest safe path that keeps the project moving forward:

\`\`\`text
Keep
or
Combine
or
Rework
or
Stop
\`\`\`

If the correct final direction cannot be established from available evidence, stop and request the appropriate human/owner decision.

### Final Integration Check

The integration agent's final question is not:

**"Is this PR perfect?"**

It is:

**"After this is integrated, is the project safely closer to where it needs to be?"**

The desired flow is:

**better → verified → forward**

not:

**perfect → delayed → stalled**

---

## 20. MCP Control Tower Integration

Every agent MUST connect to the **SupremeAI MCP Control Tower** at startup.
The Control Tower is the single authoritative interface for:
- real-time system health
- resource status
- cross-agent coordination
- automated policy approval
- infrastructure operations

### Connecting to MCP

The MCP server is registered in the project's MCP configuration. Agents access it via
the `supremeai-control-tower` server name.

**Mandatory startup sequence for every agent session:**

```text
1. mcp: system_summary          → read current health snapshot
2. mcp: autonomy_status         → confirm agent is authorized to act
3. mcp: resource_list           → check infrastructure readiness
4. mcp: memory_build_context    → restore task context from memory
5. Read AGENT_SLOT_REGISTRY     → confirm own slot, role, branch, bot identity
6. Self-assign from backlog     → pick and claim the highest-priority Issue
```

### Tools Every Agent MUST Know

| Tool | When to Use |
|------|-------------|
| `system_summary` | Startup — get health snapshot |
| `autonomy_status` | Before any destructive/automated action |
| `autonomy_kill_switch` | Emergency stop (admin only) |
| `health_dashboard` | Check live service health |
| `resource_status` | Before touching infra (Render, Supabase, Redis) |
| `github_workflow_runs` | Check if CI is healthy before pushing |
| `github_get_failed_logs` | Diagnose failed CI runs |
| `github_list_prs` | See all open PRs before claiming an Issue |
| `notify_telegram` / `notify_discord` | Alert humans on blockers or critical events |
| `memory_record_task` | Log task start, progress, completion |
| `memory_build_context` | Restore context at session start |
| `memory_remember_fact` | Persist key decisions for future sessions |
| `policy_list_pending` | Check if any action needs human approval |
| `policy_approve` | Approve safe automated actions within agent authority |
| `remote_call` | Execute operations on remote agents/services |

### When to Notify Humans via MCP

Agents MUST use `notify_telegram` or `notify_discord` when:

- A blocker cannot be resolved autonomously.
- A destructive action (data deletion, secret rotation, deploy rollback) is required.
- An autonomy kill-switch event is detected.
- A claim race or stale lock is detected on a critical Issue.
- Post-merge tests fail on `main`.
- System health degrades to a state that blocks the agent's lane.

### Autonomy Boundaries via MCP

```text
Agent CAN do autonomously (no human needed):
  • claim Issues within own lane
  • push code to own branch
  • open / update PRs
  • run CI checks
  • query MCP health and memory tools
  • approve low-risk policies via policy_approve
  • notify via telegram/discord

Agent MUST escalate to human (Admin) before:
  • billing or cost-impacting infra changes
  • production secret rotation
  • changes to another agent's active branch
  • changing own role or slot in AGENT_SLOT_REGISTRY
  • force-pushing to any protected branch
  • autonomy_kill_switch or autonomy_enable
```

### Memory Continuity Protocol

Every agent session MUST:

1. **Start**: call `memory_build_context` and `memory_get_recent_episodes`.
2. **During**: call `memory_record_task` at task start and on significant progress.
3. **End**: call `memory_remember_fact` for any critical decisions or findings.
4. **Handoff**: write a summary comment to the GitHub Issue before releasing the lock.

This ensures any replacement AI can resume from where the previous left off without
requiring human re-briefing.
