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

## 10. Issues as Primary Truth & Planning Hub

* **Issue-First Tracking:** Any bug, problem, gap, or new feature plan must be tracked in GitHub Issues rather than relying solely on static documentation files.
* **Issues > Docs for Operational Reality:** Static docs become stale quickly; live progress, blockers, verification evidence, and dynamic task status must be documented directly in the relevant GitHub Issue.
* **Plan & Problem Registration:** Before or upon uncovering a significant problem or formulating a multi-step plan, ensure it is filed or referenced in an Issue so the full team and AI agents have immediate, unified visibility.

---

### Source of Truth

Environment-specific values such as repository settings, service URLs, credentials, providers, models, deployment configuration, and infrastructure details must come from the project's current configuration or designated source-of-truth files—not from this document.

---

## 🔒 Atomic Issue Claim & Label Locking (Duplicate Work Prevention)

> **বাধ্যতামূলক লেবেল পলিসি (Mandatory Status Label Policy):**
> কোনো এজেন্ট যখনই কোনো ইস্যুর কাজ শুরু করবে, তাকে অবশ্যই স্ট্যাটাস লেবেল আপডেট করতে হবে (`status:in-progress` বা `processing`), যাতে অন্য কোনো এআই এজেন্ট বা ডেভেলপার একই সময়ে সেই ইস্যুতে কাজ শুরু না করে।
> কাজ শেষ হলে PR মার্জ করার সাথে ইস্যুটি `closed` হতে হবে অথবা লেবেল আপডেট করতে হবে।

### ১. Issue Claiming & In-Progress Locking:
ইস্যু ধরার সময় **শুধু `gh issue edit --add-assignee` ব্যবহার করা যাবে না** (race condition possible)। অবশ্যই `atomic_claim.sh` ব্যবহার করতে হবে যা অটোমেটিক `status:in-progress` লেবেল এবং assignee লক করে:

```bash
scripts/ci/atomic_claim.sh <issue_number> <agent_name>
# উদাহরণ: scripts/ci/atomic_claim.sh 900 agent-1
```

স্ক্রিপ্টটি না থাকলে বা সরাসরি CLI দিয়ে করলে তাৎক্ষণিকভাবে লেবেল লক করতে হবে:
```bash
gh issue edit <issue_number> --add-label "status:in-progress" --add-assignee "@me"
```

এটি **Claim-then-Verify** pattern implement করে (GAP-01 fix):
1. **CLAIM:** `gh issue edit --add-assignee "$AGENT_NAME"`
2. **VERIFY:** `gh issue view --json assignees` → check যে আমি first assignee
3. **LOCK:** `status:in-progress` label যোগ করা হয় (যাতে অন্য কোনো এআই একই ইস্যুতে হাত না দেয়)
4. **AUDIT:** timestamp সহ audit comment post করা হয়
5. **RACE-LOSS:** হেরে গেলে নিজেকে assignee list থেকে সরিয়ে দেয় (cleanup)

**অন্যান্য এজেন্টদের জন্য নিয়ম:**
- যে-সব ইস্যুতে ইতোমধ্যে `status:in-progress` বা `processing` লেবেল রয়েছে, অন্য কোনো এজেন্ট সেই ইস্যুর কাজ শুরু করতে পারবে না।

Environment requirement:
```bash
export GH_TOKEN=<token>          # required by gh CLI
export GH_REPO=SaifulHaqueNiloy/supremeai
```

Exit codes:
- `0` = claim successful (এখন এই agent একমাত্র owner)
- `1` = claim lost (race-এ হেরে গেছে — অন্য issue বেছে নিন)
- `2` = invalid args / missing dependencies (`gh` বা `GH_TOKEN`)

