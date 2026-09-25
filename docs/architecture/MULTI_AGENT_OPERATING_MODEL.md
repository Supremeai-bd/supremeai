# SupremeAI — Multi-Agent Operating Model

> Canonical operating flow for AI agents working together on SupremeAI.
>
> Keep roles simple, replaceable, and configurable. The role matters; the AI provider does not.

## 1. The Whole System

The system follows one repeatable lifecycle:

```text
Issue
  ↓
Task Assignment
  ↓
Claim / Ownership Lock
  ↓
Plan / Understand
  ↓
Task Branch
  ↓
Implement
  ↓
Verify
  ↓
PR
  ↓
Review / Check
  ↓
Fix on the same branch
  ↓
Final Integration / PR Manager
  ↓
Final-State Verification
  ↓
Merge
  ↓
Issue Close + Ownership Release
```

The same flow works whether there are **2 agents or 200 agents**.

The number of agents may change. The ownership rules do not.

---

## 2. The Core Rule

**One Issue → One Active Owner → One Task Branch → One Focused PR**

A task may contain many commits.

A reviewer may inspect the work.

A fixer may take over after an explicit handoff.

But **two agents must never edit the same task branch at the same time**.

---

## 3. Agent Roles

Roles are responsibilities, not permanent identities.

An administrator/orchestrator may assign any available AI to any role.

### Agent 1 — Planner / Analyst

**Purpose:** understand before implementation.

Responsibilities:

- read the Issue and acceptance criteria;
- inspect relevant code and existing behavior;
- identify dependencies and possible overlap;
- propose the smallest sound implementation path;
- identify risks or missing information.

Output:

**Plan → files/areas → dependencies → verification needs**

The planner does not need to write code.

---

### Agent 2 — Builder / Implementer

**Purpose:** turn the agreed task into working changes.

Responsibilities:

- claim the Issue;
- create/use the task branch;
- implement only the requested scope;
- reuse existing capabilities;
- add/update tests when required;
- verify the affected behavior;
- update the PR.

The builder owns the task while actively editing it.

---

### Agent 3 — Reviewer / Checker

**Purpose:** independently check whether the implementation is actually correct.

The reviewer asks:

- Does this solve the Issue?
- Is anything missing?
- Did it break existing behavior?
- Are the tests meaningful?
- Are there security or compatibility problems?
- Does it overlap with other active work?
- Does the implementation contain unnecessary changes?

The reviewer normally **does not edit the branch**.

If changes are needed:

**comment/request changes → owner fixes → reviewer checks again**

---

### Agent 4 — Fixer

A fixer is optional.

It may take over implementation when:

- the original owner is unavailable;
- review requires substantial changes;
- another specialist is better suited to the fix.

Required:

**Owner A stops → handoff recorded → Owner B claims → Owner B verifies branch → Owner B edits**

The fixer continues on the **same task branch and same PR**.

---

### Agent 5 — Final Integration / PR Manager

**Purpose:** decide what the final project state should be and safely integrate it.

This is the final decision gate.

### Final Outcome First

The PR Manager must first determine the **intended final outcome** before judging the PR.

Follow this decision loop:

1. **What are we ultimately trying to achieve?**
2. **What state should the project be in after this work?**
3. **Does this PR move the project toward that state?**
4. **Does it move any required behavior, dependency, or protection away from that state?**
5. **Does another active/merged PR change that conclusion?**
6. **What should the final combined state contain?**
7. **Can that final state be verified?**

Use this priority:

**Final Outcome → Required Behavior → Dependencies/Impact → Implementation → Tests**

Tests and CI are evidence, not the definition of the goal. A PR can be green and still move the project away from the intended outcome.

The PR Manager does **not** simply ask:

> "Are all checks green?"

It asks:

> **"What final state are we trying to create, and does the combined result move us toward that state?"**

Responsibilities:

1. Understand the Issue's original intent.
2. Read the PR and important changed code.
3. Check review findings and verification evidence.
4. Check active/merged related work.
5. Identify direct and indirect conflicts.
6. Decide what should be **kept, removed, combined, or reworked**.
7. Resolve conflicts based on purpose and evidence.
8. Verify the final combined state.
9. Merge only when the final result is sufficiently verified.

### Important

**PASS ≠ MERGE**

A passing test can prove that something works under that test.

It does not automatically prove that the code:

- belongs in the final system;
- is not redundant;
- does not conflict with another feature;
- preserves the intended architecture;
- should not be replaced by another implementation.

Likewise, code that looks unnecessary at first glance must not be deleted without checking what depends on it.

---

## 4. How a Task Starts

A task starts with an Issue.

```text
User / Admin / System
        ↓
      Issue
        ↓
   Find dependencies
        ↓
   Assign an agent
        ↓
     Claim Issue
```

Before work begins, the assigned agent checks:

- task intent;
- current source of truth;
- relevant files;
- existing implementation;
- active peer work;
- ownership state.

If ownership or scope is unclear:

**STOP.**

---

## 5. Planning

The planner/owner creates a small mental or written map:

```text
What is requested?
        ↓
What already exists?
        ↓
What must change?
        ↓
What might be affected?
        ↓
How will we prove it works?
```

Planning should be proportional to the task.

Small task → small plan.

Large/risky task → deeper plan.

Do not create unnecessary planning documents.

---

## 6. Implementation

The builder:

1. works only on the claimed Issue;
2. uses the task branch;
3. makes the narrowest sound change;
4. keeps unrelated work out;
5. commits logical progress;
6. verifies continuously.

The builder does not modify another agent's branch.

If another active task appears related:

**pause → inspect → coordinate.**

---

## 7. Verification

Verification has two levels.

### Local / Task Verification

The builder checks the affected behavior.

Examples:

- tests;
- type checks;
- lint;
- build;
- targeted runtime checks;
- security checks.

### Integration Verification

The final integration agent checks the **combined result**.

This matters because:

```text
PR A passes alone
+
PR B passes alone
≠
A + B is automatically correct
```

The final combined state must be checked.

---

## 8. Review

The reviewer examines the PR independently.

Possible result:

### Approved

The PR proceeds to final integration.

### Changes Requested

The owner/fixer updates the same branch.

### Unclear

The reviewer records what evidence is missing.

Do not manufacture approval because a deadline exists.

---

## 9. Review Fixes

Normal path:

```text
Reviewer
   ↓
Finding
   ↓
Owner
   ↓
Fix on same branch
   ↓
New commit
   ↓
Same PR
   ↓
Reviewer checks again
```

No new branch is needed merely because review produced more work.

If the new work becomes a separate task:

**new Issue → new branch → new PR**

---

## 10. Cross-Agent Conflict

Two different Issues can still affect the same system.

Examples:

- same file;
- same API;
- same database contract;
- same configuration;
- same UI behavior;
- one change depends on another unfinished change.

Therefore:

**Different Issue ≠ independent work**

Before push and before final merge, inspect related active work.

---

## 11. When Two Changes Conflict

Never use:

> "ours wins"

or:

> "the newer PR wins"

as the decision rule.

Instead:

```text
Conflict
  ↓
Understand A
  ↓
Understand B
  ↓
Identify what each protects/enables
  ↓
Check dependencies + behavior + evidence
  ↓
Keep A / Keep B / Combine / Rework
  ↓
Verify combined result
```

### Example

Agent A removes an old fallback.

Agent B adds a new feature that still depends on that fallback.

Both PRs may pass separately.

The integration agent must notice the dependency before merging both.

The answer may be:

- keep A and change B;
- keep B and retain part of A;
- combine both;
- redesign the affected part.

The correct result comes from evidence, not from which PR is newer or larger.

---

## 12. What the PR Manager Must Never Do

Never:

- merge only because CI is green;
- reject a change only because it looks unusual;
- delete code only because it looks unused;
- keep code only because tests pass;
- blindly choose one side of a conflict;
- overwrite another agent's work;
- hide a failing check;
- weaken tests to make a merge possible;
- invent a reason for a change;
- merge when the intended final state is still unclear.

When evidence is insufficient:

**STOP → ask for clarification or escalate.**

---

## 13. Final Integration Decision

For every important disputed change, the PR Manager chooses one of five outcomes:

| Decision | Meaning |
|---|---|
| **Keep** | The change is required or justified. |
| **Remove** | The change is obsolete, redundant, unsafe, or not justified. |
| **Combine** | Multiple changes are needed together. |
| **Rework** | The intent is valid, but the implementation needs redesign/fix. |
| **Escalate** | Evidence is insufficient for a safe decision. |

This is not a score or ranking system.

It is a final-state decision.

---

## 14. Merge Gate

A PR is merge-ready only when:

- Issue intent is understood;
- scope is appropriate;
- ownership is clear;
- review findings are resolved;
- cross-task relationships are understood;
- conflicts are intentionally resolved;
- required verification passes;
- the final combined state is verified;
- no known security/integrity blocker remains.

Then:

```text
Verified Final State
       ↓
      Merge
       ↓
   Main updated
       ↓
Issue confirmed/closed
       ↓
Ownership released
```

---

## 15. Human Escalation

The system should automate routine decisions, but uncertainty must remain visible.

Escalate when:

- requirements conflict;
- two valid designs have materially different consequences;
- a destructive change cannot be safely judged;
- security impact is unclear;
- migration/data-loss risk is unclear;
- the final intended behavior is ambiguous;
- available evidence is insufficient.

**Escalation is a safety mechanism, not a failure.**

---

## 16. Simple Mental Model

Every agent should remember only this:

```text
1. Understand the task.
2. Check who is working on related things.
3. Own one task at a time.
4. Change only what is needed.
5. Verify your work.
6. Let another agent check it.
7. Fix findings on the same task branch.
8. Let the PR Manager understand the whole picture.
9. Resolve conflicts by purpose + evidence.
10. Verify the final combined state.
11. Merge only when the final state is correct and verified.
12. Close the Issue and release ownership.
```

### The Core Principle

**Agents may work independently, but the final codebase must behave as one system.**

