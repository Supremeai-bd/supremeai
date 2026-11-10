# SupremeAI Agent Operating Contract

> **Purpose:** Enable agents to do the most useful work they can within the assigned task, with clear authority, preserved user work, and evidence-based safeguards against regressions.**Operating principle:** Be autonomous in *how* you solve the task. Be conservative about data loss, permissions, security, and irreversible external actions. Do not turn uncertainty into either a guess presented as fact or an unnecessary stop.

This file is the repository's concise agent contract. Detailed, changeable procedures belong in the linked source-of-truth documents and live tool contracts. Keep this file consistent with them; do not copy volatile tool schemas, test counts, runner timings, service IDs, or incident anecdotes here.

---

## 1. Authority, task mode, and precedence

### 1.1 Identify the task mode

- **User-directed work:** The user's explicit request is the assignment. Work on it directly; do not launch the autonomous loop or select unrelated queue work unless the user asks or the task genuinely depends on it.

- **Autonomous queue work:** The continuous agent loop and its emitted task envelope determine the assignment, role, acceptance criteria, scope, and stop conditions. Do not self-assign a different issue or expand the task to unrelated backlog work.

- **Scheduled or routine work:** Run only when the authorized scheduler, loop, or task contract dispatches it.

The loop is the assignment authority **for autonomous dispatch**, not a reason to ignore a direct, authorized user request. All modes follow the same security, preservation, and verification rules.

### 1.2 Resolve conflicts safely

Apply, in order:

1. Platform, law, security, and explicit authorization boundaries.

1. The active task's explicit acceptance criteria, scope, and stop conditions.

1. This repository contract.

1. Current canonical docs and live tool/API contracts referenced below.

If two applicable requirements materially conflict, do not silently choose the riskier interpretation. Continue independent, safe work; state the conflict and ask only if it changes the outcome, scope, authorization, or safety of the work. A lower-priority note, stale example, issue label, or copied tool name does not override current evidence or a higher-priority rule.

### 1.3 Use judgment; do not wait for perfect instructions

- Choose the simplest complete solution that meets the acceptance criteria. You may inspect related code, follow established patterns, and make low-risk implementation decisions without asking for routine approval.

- If an ambiguity is minor, choose a reasonable default, record the assumption, and continue.

- Do not ask the user to decide implementation details that can be safely determined from the codebase, tests, or established conventions.

- Ask or pause only when proceeding would risk data loss, cross an authorization/security boundary, cause an irreversible or material external effect, violate an explicit stop condition, or require choosing between materially different user outcomes.

---

## 2. Repository and task boundaries

### 2.1 Single repository and domain placement

`Supremeai-bd/supremeai` is the monorepo source of truth. Work in the relevant in-repository domain (`core/`, `gateway/`, `studio/`, `browser/`, `vscode/`, `infrastructure/`, or the appropriate shared `scripts/`, `docs/`, and configuration paths). Do not create or modify a retired external satellite repository as a substitute for work here.

Place code in its owning domain. Root-level files are appropriate for repository-wide governance, configuration, shared tooling, and documentation; do not place domain implementation in a shadow root directory when an approved domain folder exists. Cross-domain edits are allowed only when they are required to complete the assigned change and are within the task's authorization and scope.

### 2.2 Respect declared scope without producing half-fixes

- For loop/issue work, treat the task envelope's declared files, domain, acceptance criteria, and forbidden paths as binding.

- For a direct user task without an envelope, infer the smallest sensible scope from the request and repository structure.

- Include all mutually dependent code, tests, migrations, configuration, API wiring, and documentation required for a complete solution. Do not omit a necessary piece merely to keep the diff artificially small.

- If a necessary file lies outside a declared scope, do not silently edit it or deliver an incomplete fix. Explain the dependency and use the task's authorized scope-update or escalation route.

- Do not bundle unrelated cleanup, speculative refactors, or formatting churn into the task.

### 2.3 Protect the existing worktree and other agents' work

Before any operation that may change files, branches, or the index:

1. Inspect the current branch and `git status`, including staged, unstaged, and untracked files.

1. Inspect diffs for files that overlap the task.

1. Treat all pre-existing edits and untracked files as owned work: preserve them unless the user explicitly includes them in the task.

Never use `git reset --hard`, `git clean`, broad checkout/restore, blind full-file overwrite, or a destructive script to make the tree look clean. Do not stash, delete, move, overwrite, or reformat unrelated work. If a pre-existing change overlaps the required edit, make only a surgical compatible change; if that cannot be done safely, stop mutation on the conflicting file and report the blocker while continuing independent work.

Do not switch branches, rebase, merge, commit, push, or create a worktree as an incidental side effect. Do so only when required by the task and allowed by the applicable workflow. A dirty worktree is a preservation warning, not a reason to discard user work or to refuse safe read-only analysis.

### 2.4 Remote freshness and stale branches

- Check the remote base when freshness matters and network access is available. Distinguish verified freshness from an offline or unavailable check; never claim the branch is current without evidence.

- Do not automatically rebase a dirty worktree. Preserve its edits first; use an isolated worktree only when authorized and safe.

- For a published stale PR branch, follow the repository's documented no-force-push repair procedure (merge the current base when that procedure applies). Never force-push or rewrite a published branch to bypass a stale-base gate.

- A failed freshness check blocks submission or landing when the configured gate requires freshness; it does not prohibit unrelated read-only work or safe local investigation.

---

## 3. Safety, permissions, and external actions

- Never expose credentials, tokens, private keys, or secret values in logs, commits, prompts, reports, or test output. Use approved secret stores and authorized tools.

- Do not evade access controls, protected-path rules, review requirements, branch protections, or CI gates. If a required tool is unavailable, discover the supported tools/schemas and use an authorized documented alternative; do not invent endpoint names or retry a side-effecting call blindly.

- Read using authorized read-only surfaces. Write or submit only through the route authorized for the current agent and task. External/chat-only agents must use the configured bridge submission path and must not directly commit, push, or open a PR through an unauthorized route.

- Never push directly to a protected branch. Do not merge, deploy, change production infrastructure, alter user data, or perform another consequential external action unless the task explicitly authorizes it and the repository's required gates are satisfied.

- Follow the current live bridge/tool contract for payload shape, scope declarations, file-size limits, and base-SHA requirements. If the contract cannot be read or verified, report that limitation; do not fabricate compliance.

- Before creating an issue, work order, or PR, check for an existing matching item and follow the authorized idempotency/deduplication procedure. Never blindly retry a request that may already have created an external side effect.

---

## 4. Implementation and regression prevention

### 4.1 Solve the root cause with a complete, proportionate change

- Reproduce or otherwise establish the defect using the task's evidence, a failing test, a minimal test case, or an acceptance criterion. Reproduction may be on the task branch or a safe fixture; do not require a defect to reproduce on live production when that would be unsafe or irrelevant.

- Inspect the owning code, nearby callers, contracts, and tests before changing behavior. Prefer the smallest coherent fix, not necessarily the fewest lines.

- Preserve public behavior, data formats, API compatibility, security boundaries, and existing user expectations unless the task explicitly changes them.

- For schema, persistence, permissions/RLS, configuration, or API changes, include the migration/configuration/wiring and verification needed for the end-to-end behavior in the same cohesive change.

- Use targeted patches for existing files. Replace a whole file only when the task genuinely requires a full rewrite and the current content has been reviewed and preserved where relevant.

### 4.2 Tests are protection, not obstacles

- Never delete, disable, skip, weaken, or loosen a relevant passing test merely to make a gate green.

- When fixing a confirmed defect, add or update focused regression coverage that fails before the fix and passes after it, where practical.

- Replace an obsolete test only when the old behavior is demonstrably no longer the contract; retain equivalent or stronger coverage for the intended behavior.

- Add a mechanical guard when it can reliably prevent a repeatable defect class. Do not create a new abstraction, broad guard, or permanent rule for a one-off issue when a focused regression test is sufficient.

- Do not claim “zero regressions” as a mathematical guarantee. The required objective is **no known regression, no weakened protection, and no unverified success claim**.

### 4.3 Report defects without derailing the assignment

- A confirmed defect that blocks the task, risks security/data loss, or makes the requested change unsafe must be addressed or treated as a blocker.

- For an unrelated defect, check for duplication, capture the evidence and impact, and report or file it through an authorized route. Continue the assigned task when it remains safe and independent.

- In autonomous queue mode, use the loop's priority and claim rules. A P0 preempts routine queue work when the authorized policy says it does; a label alone does not justify abandoning an unrelated user-directed task unless the P0 actually affects its safety or feasibility.

- Do not silently ignore a failure, but do not create duplicate tickets or expand the current diff to fix unrelated systems.

---

## 5. Verification and evidence

Use the repository's three verification phases, scaled to the change:

1. **Reflection:** Re-read the final diff. Confirm scope, intended behavior, compatibility, secret safety, and that no pre-existing work was altered.

1. **Smoke:** Run the cheapest relevant syntax, type, build, or focused behavior check.

1. **Tests:** Run targeted regression tests and the relevant broader suite or CI checks required by the change and active workflow.

Choose tests by risk and impact. A documentation-only edit does not require an unrelated application test suite; a cross-cutting or security-sensitive code change requires broader evidence. Prefer focused checks first, then expand as needed.

For every check, report one truthful state: **passed**, **failed**, **not run**, or **blocked**. Include the command and material output/exit code where useful. If a tool, dependency, network, service, or runner is unavailable, state what was not verified and why; use an authorized alternative when reasonable. Never convert a skipped, timed-out, unreachable, or partial check into a pass.

A failed test is evidence to investigate, not permission to mask it. Fix the cause when within scope; otherwise preserve the failure evidence, explain its relationship to the task, and do not claim full verification. Do not submit, merge, or mark complete when a required gate is red or bypassed.

Use current commands and requirements from the relevant project documentation and the active workflow, including:

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — contributor workflow and verification phases.

- [`docs/AGENT_LOOP_SPEC.md`](docs/AGENT_LOOP_SPEC.md) — autonomous task envelope and loop verification contract.

- [`docs/PR_TO_PRODUCTION_LIFECYCLE.md`](docs/PR_TO_PRODUCTION_LIFECYCLE.md) — CI, runner, merge, and deployment policy.

- [`.github/workflows/unified-pipeline.yml`](.github/workflows/unified-pipeline.yml) — current unified CI/CD implementation.

If a linked source-of-truth file is absent, disagrees materially with the active implementation, or cannot be verified, report the drift and avoid claiming that its requirement has passed.

---

## 6. Branches, PRs, and submission

- Keep one logical task on one branch/PR. Include all interdependent changes together; do not fragment a fix into partial changes that leave the project failing between submissions.

- Do not create duplicate PRs or work orders for the same task. Reuse or update the existing authorized work item when policy requires it.

- Never call `gh pr merge` or another direct merge command to bypass the repository's configured landing gate. Land only through the active approved merge workflow after all required checks pass.

- Before submitting, run the applicable repository preflight (currently documented as `python scripts/ci/pr_preflight_guard.py --branch <branch> --files <changed-files> --pr-body <body-file>`), if present and appropriate. Do not claim it passed if it was not run.

- PRs/work orders must contain the required issue reference, concise reflection on **why this solution** was chosen and **alternatives rejected**, and real test evidence. Use the exact current template/bridge contract; do not invent required field names.

- Commit, push, and PR creation are not automatic consequences of editing. Perform them only when the user's request and the current agent's route authorize them.

---

## 7. CI, workflows, and deployment

- Treat the active workflow and [`docs/PR_TO_PRODUCTION_LIFECYCLE.md`](docs/PR_TO_PRODUCTION_LIFECYCLE.md) as the sources for runner routing, required gates, and deployment behavior. Do not copy their volatile details into this file.

- When changing CI, determine which workflow actually runs for the relevant event. Preserve required PR checks and fail-closed merge behavior. A green workflow name is not proof that all required jobs ran; inspect job-level results when needed.

- Apply runner hierarchy rules to the jobs covered by the current policy. Keep documented safety exceptions—such as isolating untrusted fork code—and deployment independence where the canonical lifecycle requires them. Do not force deployment jobs onto a test-runner hierarchy or run untrusted code on a privileged local runner.

- A CI policy exception must be explicit, justified, narrowly scoped, and protected by an alternative verification/security control. Do not add exceptions merely to avoid a failing check.

- Do not silently convert a required gate into an optional, skipped, advisory, or success-shaped no-op. If a required gate is broken, surface the defect and repair it within scope or report a concrete blocker.

---

## 8. Definition of done and final report

A task is complete only when:

- The requested outcome and acceptance criteria are met.

- All necessary interdependent changes are included; unrelated work is preserved.

- Relevant verification has been run and its results are accurately reported.

- Remaining failures, assumptions, unavailable checks, and risks are visible—not hidden behind a “done” claim.

- Any external submission or deployment has occurred only through the authorized route and required gates.

Use a concise final report:

- **Outcome:** completed, partially completed, or blocked.

- **Changes:** key files/behavior changed, if any.

- **Verification:** checks run, results, and checks not run.

- **Open issues:** material risk, assumption, or unrelated confirmed defect needing follow-up.

If no changes were needed, say so. If blocked, state the exact blocker and the smallest next step; do not simply stop without explaining what remains possible.

---

## 9. Maintenance of this contract

Keep this file short enough for every agent to apply consistently. Add a rule only when it addresses a real, evidenced failure mode and has a clear scope and behavior. Prefer an automated test or guard for a repeatable defect, and keep the guard aligned with the canonical docs and active workflows. Remove or revise duplicated and stale instructions when their source of truth changes.

When this file conflicts with the active task, another canonical document, or an unavailable tool contract, preserve safety and existing work, continue safe independent work, and report the exact discrepancy. Never invent a passing state or a permission that was not granted.