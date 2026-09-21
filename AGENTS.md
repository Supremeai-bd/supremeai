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

**Understand → Inspect → Reason → Act → Verify → Report**

Mandatory before implementation:

1. Read the task and relevant GitHub Issue.
2. Inspect the relevant code, configuration, contracts, and tests.
3. Reuse existing project capabilities before creating new ones.
4. Check current work/ownership state when applicable.
5. Use repository configuration as the source of truth.
6. Do not guess when evidence is available.

---

## 3. Issue-First & Single Ownership

### Rule

**One Issue = One Owner = One Branch = One Focused PR**

Every bug, feature, task, significant gap, or multi-step change must be tracked by a GitHub Issue before implementation.

### Claiming a Task

Before editing code:

1. Find or create the Issue.
2. Claim the Issue using:

```bash
scripts/ci/atomic_claim.sh <issue_number> <agent_name>
```

3. The claim must establish:

   * agent ownership;
   * `status:in-progress`;
   * audit evidence.

4. Re-check the Issue after claiming.

### Canonical Lock

`status:in-progress` is the canonical active-work lock.

`processing` is treated only as a legacy equivalent if already present. Do not create multiple competing active-status labels.

### Race Rule

If another agent already owns the Issue or the active-work lock exists:

**STOP. Do not edit the Issue, branch, or files. Choose another task.**

Never silently take over another agent's work.

### Claim Failure

If `atomic_claim.sh` is unavailable, use the documented repository fallback and verify ownership before editing.

Required environment:

```bash
GH_TOKEN=<token>
GH_REPO=<repository>
```

A claim is successful only after ownership is verified.

---

## 4. Workspace & Branch Isolation

* Never modify or push directly to `main`.
* Each Issue gets its own dedicated branch.
* Prefer:

```text
agent-<agent>/issue-<number>-<short-description>
```

* Never modify another agent's active branch.
* Prefer an isolated worktree/clone for concurrent agents.
* Unexpected uncommitted changes are **not yours by default**.
* Never discard, reset, overwrite, or delete unknown work without establishing ownership.

Before editing:

**Issue ownership → branch ownership → workspace state → current main**

If any of these is ambiguous:

**STOP.**

---

## 5. Main Synchronization & Push Safety

Before implementation and again before push/PR:

**fetch → rebase/update from latest `origin/main` → resolve conflicts → verify → push**

Requirements:

* start from the latest `main`;
* re-check `origin/main` before PR;
* resolve conflicts locally;
* rerun affected verification after conflict resolution;
* push only verified work;
* never use unsafe force-push;
* never overwrite another agent's commits.

If rebase or merge produces unexpected changes:

**STOP → inspect → resolve intentionally → verify again.**

---

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

**One Issue → One Focused PR**

A PR must:

* address the claimed Issue;
* contain only relevant changes;
* include the Issue reference;
* avoid unrelated refactors or fixes.

Use the repository's standard Issue-closing mechanism, such as:

```text
Fixes #<issue>
```

Do not begin another Issue in the same task branch/PR.

After merge:

**PR merged → Issue closed/confirmed → task released**

Only then claim another Issue.

---

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
* unexpected workspace changes may belong to another agent;
* required permissions are unavailable;
* secrets are unexpectedly exposed;
* a merge/rebase conflict is unresolved;
* task scope becomes ambiguous;
* a required verification fails and the root cause is not yet understood;
* proceeding would require bypassing a safety, security, or integrity rule.

**STOP → INSPECT → RESOLVE → VERIFY → CONTINUE**

---

## 18. Completion

A task is complete only after:

**Claimed → Implemented → Verified → PR Created → PR Merged → Issue Closed**

Final report:

**Changed / Verified / Remaining**
