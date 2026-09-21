# SupremeAI — AGENTS.md

> Universal rules for AI agents working on SupremeAI.
> Prefer existing project configuration and source-of-truth files over assumptions.

## 1. Priority

Follow this order when rules conflict:

**Safety & Security → Task Scope → Existing Architecture → Quality Gates → Optimization**

Never invent facts, files, commands, APIs, credentials, or project behavior.

## 2. Understand Before Acting

Before changing code:

1. Read the task and relevant issue.
2. Inspect the existing implementation and nearby modules.
3. Reuse existing patterns, utilities, contracts, and tests.
4. Check `ACTIVE_WORK` / relevant project status when applicable.

When information is missing, inspect the repository and available configuration first.
Do not guess.

## 3. Git & Task Isolation

* Never work directly on `main`.
* One task should map to one isolated branch and one focused PR.
* Start from the latest `main` before implementation.
* Keep changes limited to the requested task.
* Do not mix unrelated fixes into the PR.
* If blocked by an external dependency or manual action, document the blocker instead of bypassing it.

## 4. Code Changes

**Narrowest sound change.**

* Prefer existing code over duplication.
* Preserve existing contracts unless the task requires a change.
* Avoid unnecessary rewrites, migrations, or refactors.
* Do not delete tests, audits, plans, or required documentation without explicit instruction.
* Keep implementations modular, observable, and maintainable.

## 5. Security & Secrets

* Never hardcode, expose, print, commit, or invent secrets.
* Use the project's approved secret-management/configuration mechanism.
* Never create fake credentials or fake production configuration to make a test pass.
* Treat external integrations as configuration, not hardcoded assumptions.

## 6. Verification

Before reporting work as complete:

* Run the relevant tests, type checks, linters, builds, and regression checks.
* Verify the behavior affected by the change, not only compilation.
* Fix safe, deterministic issues automatically when appropriate.
* Never skip, weaken, mock away, or hide a failing verification merely to obtain a green result.
* Report remaining failures honestly.

**Green means verified, not merely executed.**

## 7. Dynamic & Reusable Design

Prefer:

**configuration → discovery → execution**

over hardcoded:

**provider → model → resource → value**

Capabilities should remain replaceable and extensible.
Use existing standards and project configuration instead of introducing arbitrary constants.

## 8. Communication

* Match the user's requested language.
* Keep progress and final reports concise and factual.
* Distinguish clearly between:

  * verified facts
  * assumptions
  * blockers
  * recommended actions

## 9. Completion Rule

A task is complete only when:

**Understand → Inspect → Implement → Verify → Report**

The final report should state:

**Changed / Verified / Remaining**

---

### Source of Truth

Environment-specific values such as repository settings, service URLs, credentials, providers, models, deployment configuration, and infrastructure details must come from the project's current configuration or designated source-of-truth files—not from this document.

---

## 🔒 Atomic Issue Claim (GAP-01 fix)

> যখন কোনো agent একটি issue ধরবে, সে **শুধু `gh issue edit --add-assignee` ব্যবহার করবে না**
> (সেটি atomic নয় — race condition possible, দুজন agent একই সময়ে assignee হয়ে যেতে পারে)। বরং:

```bash
scripts/ci/atomic_claim.sh <issue_number> <agent_name>
# উদাহরণ: scripts/ci/atomic_claim.sh 900 agent-1
```

এটি **Claim-then-Verify** pattern implement করে (GAP-01 fix):

1. **CLAIM:** `gh issue edit --add-assignee "$AGENT_NAME"`
2. **VERIFY:** `gh issue view --json assignees` → check যে আমি first assignee
3. **LOCK:** `status:in-progress` label যোগ করা হয়
4. **AUDIT:** timestamp সহ audit comment post করা হয়
5. **RACE-LOSS:** হেরে গেলে নিজেকে assignee list থেকে সরিয়ে দেয় (cleanup)

**বাধ্যতামূলক:** সব agent-দের এই script ব্যবহার করতে হবে issue claim করার সময়।
শুধু `gh issue edit --add-assignee` ব্যবহার করলে CAS লজিক থাকে না → race-condition-এ
দুজন agent একই issue-তে কাজ শুরু করে ফেলতে পারে → wasted work + conflict।

Environment requirement:
```bash
export GH_TOKEN=<token>          # required by gh CLI
export GH_REPO=SaifulHaqueNiloy/supremeai
```

Exit codes:
- `0` = claim successful (এখন এই agent একমাত্র owner)
- `1` = claim lost (race-এ হেরে গেছে — অন্য issue বেছে নিন)
- `2` = invalid args / missing dependencies (`gh` বা `GH_TOKEN`)
