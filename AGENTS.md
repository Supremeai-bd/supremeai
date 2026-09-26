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

### Claiming a Task

Before editing code:

1. Find or create the Issue.
2. Claim the Issue using:

\`\`\`bash
scripts/ci/atomic_claim.sh <issue_number> <agent_name>
\`\`\`

3. The claim must establish:
   * active ownership;
   * \`status:in-progress\`;
   * audit evidence.
4. Re-check the Issue after claiming.

### Single Active Owner

* Only **one agent may actively edit a task branch at a time**.
* Many agents may inspect, advise, or review the work.
* A reviewer does not become a second implementer just because the reviewer finds a problem.
* Do not let two agents write to the same task branch at the same time.

### Ownership Handoff

If another agent must continue or fix the work:

1. The current owner stops editing.
2. Record the current state and outstanding work in the Issue/PR.
3. Release/transfer ownership using the repository's documented mechanism.
4. The next agent claims the Issue.
5. The new owner fetches and verifies the task branch before editing.
6. Only then does the new owner continue.

**No overlapping edits.**

A handoff does **not** require a new Issue or a new branch when the task is still the same.

### Canonical Lock

\`status:in-progress\` is the canonical active-work lock.

\`processing\` is treated only as a legacy equivalent if already present. Do not create multiple competing active-status labels.

### Race Rule

If another agent already owns the Issue or the active-work lock exists:

**STOP. Do not edit the Issue, branch, or files. Choose another task or wait for an explicit handoff.**

Never silently take over another agent's work.

### Claim Failure

If \`atomic_claim.sh\` is unavailable, use the documented repository fallback and verify ownership before editing.

Required environment:

\`\`\`bash
GH_TOKEN=<token>
GH_REPO=<repository>
\`\`\`

A claim is successful only after ownership is verified.

### Split Rule

If the requested work grows into **independent pieces**, split it into separate Issues.

Use:

\`\`\`text
Issue A → Branch A → PR A
Issue B → Branch B → PR B
\`\`\`

Do not place unrelated work into one Issue/branch/PR merely because the tasks were discovered together.

## 4. Agent Workspace & Branch Model

SupremeAI uses **persistent Agent Branches**.

A branch represents a **work slot/workspace**, not a permanent AI model.

### Core Rules

\`\`\`text
1 Branch = 1 Persistent Agent Workspace
1 Branch = 1 Primary Work Type
1 Branch = 1 Active AI Writer at a time
1 Agent = 1 Active Issue at a time
1 Issue = 1 PR
\`\`\`

### Example Branch Groups

\`\`\`text
Planning
  ├── agent-1
  ├── agent-4
  └── agent-7

Architecture
  ├── agent-2
  ├── agent-5
  └── agent-8

Implementation
  ├── agent-3
  ├── agent-6
  └── agent-9
\`\`\`

The numbering is only an example. The actual branch-to-work-type mapping should remain defined by the active project configuration.
See [`docs/agents/AGENT_WORK_BOUNDARIES_CHARTER.md`](docs/agents/AGENT_WORK_BOUNDARIES_CHARTER.md) for full lane discipline and work boundary rules.

### Parallel Work

A busy branch does **not** block the whole work type.

Example:

\`\`\`text
Planning
  agent-1 → BUSY 🔴
  agent-4 → FREE  🟢
  agent-7 → FREE  🟢
\`\`\`

If another Planning task arrives while \`agent-1\` is busy, assign it to another available Planning branch.

Different Agent branches may work in parallel when their tasks do not conflict.

### Branch Lock

When an AI is actively working on an Agent branch:

\`\`\`text
agent-1
  └── BUSY / LOCKED
\`\`\`

Another AI must not simultaneously modify that same branch.

The branch becomes available again after the current work is properly completed, handed off, or otherwise released according to project workflow.

### AI Is Replaceable

An Agent Branch is **not permanently assigned to one AI model**.

For example:

\`\`\`text
Day 1
agent-1 → AI-A → Planning Task A

Day 2
agent-1 → AI-B → Planning Task B

Day 3
agent-1 → AI-C → Planning Task C
\`\`\`

A new AI taking over an existing branch must first inspect:

\`\`\`text
previous commits
previous PRs
current branch state
relevant issues
previous decisions
known problems
\`\`\`

It may correct previous mistakes and improve the existing work.

Therefore:

\`\`\`text
Agent Branch = persistent workspace/history
AI Model     = replaceable worker
Issue        = current task
PR           = proposed integration
History      = evidence
\`\`\`

### Before Starting Work

The assigned AI must:

1. Confirm the assigned Agent Branch.
2. Check whether the branch is free.
3. Inspect the branch's existing work/history.
4. Check the latest \`main\`.
5. Check the assigned GitHub Issue.
6. Check relevant work from other Agent branches.
7. Identify possible overlap before making changes.
8. Start work only when ownership is clear.

### Cross-Agent Work

Different branches may work simultaneously.

However:

\`\`\`text
Different task
    ↓
Independent changes
    ↓
Parallel work is allowed
\`\`\`

If two tasks affect the same important area:

\`\`\`text
Agent A ──┐
          ├── possible conflict
Agent B ──┘
\`\`\`

the agents must recognize and resolve the overlap before silently overwriting each other's work.

An Agent must never assume that another branch's work can be ignored simply because it has not yet been merged.

### Workspace Invariants

* Never modify or push directly to \`main\`.
* Never modify another agent's active branch.
* Prefer an isolated worktree/clone for concurrent agents.
* Unexpected uncommitted changes are **not yours by default**.
* Never discard, reset, overwrite, or delete unknown work without establishing ownership.

Before editing:

**Issue ownership → branch ownership → workspace state → other active work → current main**

If any of these is ambiguous:

**STOP.**

### Simple Mental Model

\`\`\`text
                 SUPREMEAI
                     │
             ┌───────┴───────┐
             │               │
        Work Type         Work Type
             │               │
       Planning          Architecture
             │               │
       ┌─────┼─────┐   ┌─────┼─────┐
       │     │     │   │     │     │
      A1    A4    A7  A2    A5    A8
       │
       ▼
   Current AI
       │
       ▼
     Issue
       │
       ▼
      PR
       │
       ▼
   Verification
       │
       ▼
   Integration
       │
       ▼
      main
\`\`\`

**Key principle:**

> **The branch stays; the AI can change. The history stays; the work can improve.**

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
