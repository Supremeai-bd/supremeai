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

## 3. Issue-First & Single Ownership

### Rule

**One Issue = One Active Owner = One Task Branch = One Focused PR**

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

## 4. Workspace & Branch Isolation

* Never modify or push directly to \`main\`.
* Each Issue gets one dedicated task branch.
* The same task branch remains in use for the whole Issue, including review fixes.
* **Do not create a new branch for each commit, each review round, or each agent.**
* One task may have any reasonable number of commits.
* A PR may therefore contain multiple commits from the same task branch.
* Never modify another agent's active branch.
* Prefer an isolated worktree/clone for concurrent agents.
* Unexpected uncommitted changes are **not yours by default**.
* Never discard, reset, overwrite, or delete unknown work without establishing ownership.

Preferred branch pattern:

\`\`\`text
<type>/<issue-number>-<short-description>
\`\`\`

### Reviewers and Branches

A reviewer normally **does not create a second branch** for review.

The normal flow is:

\`\`\`text
Task Issue
   ↓
Task branch
   ↓
Agent works
   ↓
1..N commits
   ↓
1 PR
   ↓
Reviewer checks
   ↓
Comments / requested changes
   ↓
Owner fixes on the same task branch
   ↓
Same PR updates
   ↓
Reviewer checks again
\`\`\`

If a reviewer must become the person who edits the fix, use an explicit ownership handoff first. Never have both agents edit the same branch concurrently.

Before editing:

**Issue ownership → branch ownership → workspace state → other active work → current main**

If any of these is ambiguous:

**STOP.**

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

**One Issue → One Task Branch → One Focused PR**

A PR represents the complete change for one Issue. It is not tied to a single commit.

A task may use:

\`\`\`text
1 commit
2 commits
10 commits
N commits
\`\`\`

All remain on the **same task branch** and flow into the **same PR**.

### PR Responsibilities

**Implementing owner:**
* creates the task branch;
* implements the Issue;
* creates/updates the PR;
* responds to review findings;
* fixes problems on the same task branch;
* reruns affected checks after fixes.

**Reviewer/checker:**
* inspects the PR and the evidence;
* identifies problems, missing tests, regressions, or scope issues;
* checks for overlap with other active work when relevant;
* comments or requests changes;
* re-checks after fixes;
* does not modify the task branch by default.

### Review Loop

\`\`\`text
Issue
 ↓
Claim
 ↓
Check other active work
 ↓
Task branch
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
       same PR
          ↓
       review again
\`\`\`

### Fixer Handoff

A separate agent may perform the fix only after an explicit ownership handoff.

\`\`\`text
Owner A stops
    ↓
Handoff recorded
    ↓
Owner B claims Issue
    ↓
Owner B syncs/verifies branch
    ↓
Owner B fixes
    ↓
Same PR
\`\`\`

Never allow Owner A and Owner B to edit the same branch simultaneously.

### Split Rule

When review or implementation reveals that requested work is actually a separate task:

**stop → create/link a new Issue → create a new branch → create a new PR**

Do not grow the original PR into an unrelated collection of changes.

### Merge

Merge only after required verification, review, and cross-task checks are complete.

After merge:

**PR merged → Issue closed/confirmed → ownership released**

Only then is the task considered finished and the agent free to claim another Issue.

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

**Claimed → Branch Created → Implemented → Verified → PR Created → Review Complete → PR Merged → Issue Closed → Ownership Released**

Final report:

**Changed / Verified / Remaining**

For multi-agent work, also record when applicable:

* who currently owns the task;
* whether ownership was handed off;
* which branch and PR contain the work;
* whether review findings were fixed and re-checked.

The final state must be unambiguous: **one Issue, one final task branch, one focused PR, one completed ownership cycle.**

