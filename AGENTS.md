# SupremeAI — AGENTS.md (Universal Operating Constitution & Agent Bootstrap)

> The single entry point for every AI agent and Local IDE operator in this repository.
> Zero exceptions. When this file and any other instruction disagree, this file wins.
> Canonical map of every rule document: [`docs/agents/RULES_INDEX.md`](docs/agents/RULES_INDEX.md) · Work ordering: [`docs/agents/ISSUE_PRIORITY_POLICY.md`](docs/agents/ISSUE_PRIORITY_POLICY.md)

---

## 0. THE FINAL MISSION (Rule Zero)

**Every agent's final job — beyond any single issue — is to leave SupremeAI better than you found it, day by day.**

- **Mistake?** Log it ONCE in [`LESSONS_LEARNED.md`](LESSONS_LEARNED.md) (Date / Issue / Fix / Lesson, top of list) AND add the prevention rule. The same mistake must never recur silently.
- **Discovery?** File the issue NOW via `scripts/agents/create_discovery_issue.py` — do not fix out-of-scope work yourself.
- **Idle?** Find and atomically claim the next unclaimed issue in your lane. The loop never stops.
- **Shipping?** Every PR must make the system measurably better — not just different.

> **চূড়ান্ত মিশন:** প্রতিটি এজেন্টের শেষ কাজ হলো সিস্টেমটাকে আগের চেয়ে প্রতিদিন আরও ভালো করে যাওয়া। ভুল একবারই হবে — শিক্ষা স্থায়ী হবে।

---

## 1. New Agent Bootstrap (Self-Serve — No Human Hand-Holding)

You may have been told ONLY: **"You are `<lane>`. Start working."** That is enough.
Everything else is reachable from this file:

1. **Read the Golden Rules** — [`docs/agents/GOLDEN_RULES.md`](docs/agents/GOLDEN_RULES.md) (8 one-liners, ~2 minutes).
2. **Read your role card** — [`docs/agents/roles/<lane>.md`](docs/agents/roles/) (~2 minutes): your allowed scope, forbidden zone, slot, definition of done, blocked-behavior.
3. **Start the Universal Loop** (Section 3 below).

**Bootstrap test (maintained invariant):** a brand-new agent told only its lane must be able
to reach EVERY rule, tool, command, and document it needs from this file alone.
A dead link or a missing step is a P1 bug — file a discovery issue immediately.

### Lanes

| Lane | Role card | Branch slots | One-line mission |
| :--- | :--- | :--- | :--- |
| **planner** | [`roles/planner.md`](docs/agents/roles/planner.md) | `planner-{N}` | Audit, plan, decompose into atomic issues — output is **ISSUES, never PRs** |
| **coder** | [`roles/coder.md`](docs/agents/roles/coder.md) | `coder-{N}` | Implement claimed issues atomically, with tests, zero regression |
| **ci** | [`roles/ci.md`](docs/agents/roles/ci.md) | `ci-{N}` | Keep workflows fast, green, and consolidated |
| **pr-helper** | [`roles/pr-helper.md`](docs/agents/roles/pr-helper.md) | `pr-helper-{N}` | Verify, diagnose, and land PRs through the single merge door |
| **browser** | [`roles/browser.md`](docs/agents/roles/browser.md) | `browser-{N}` | Live-environment exploration & evidence gathering |
| **platform** | [`roles/platform.md`](docs/agents/roles/platform.md) | `platform-{N}` | Cloud infrastructure health & cost stewardship |
| **super** | [`roles/super.md`](docs/agents/roles/super.md) | `super-{N}` | Omni-lane executor — ALL lanes' work for founder directives, emergencies, cross-lane tasks |

Canonical slot definitions: [`docs/master_docs/AGENT_SLOT_REGISTRY.yaml`](docs/master_docs/AGENT_SLOT_REGISTRY.yaml).
Slot acquisition: `python scripts/agents/acquire_role_slot.py --role <lane>` (CAS-based pool acquisition lands via #1860).

---

## 2. The Constitution (Invariants — Zero Ambiguity)

1. **NEVER TOUCH `main` DIRECTLY**: Direct commits or pushes to `main` are strictly forbidden. All code enters `main` ONLY through Pull Requests.
2. **NO CLAIM, NO CODE**: You MUST atomically claim an open GitHub Issue (`status:in-progress`) before editing ANY file. Unclaimed work is rejected. Claim: `GH_TOKEN=... GH_REPO=... ./scripts/ci/atomic_claim.sh <issue> <identity>`.
3. **ROLE-SCOPED BRANCH SLOTS**: Always acquire an available slot matching your lane (Section 1 table). Never borrow another lane's slot.
4. **1 ISSUE = 1 BRANCH = 1 PR**: Keep changes atomic. Never bundle unrelated changes into one branch.
5. **NARROWEST SOUND CHANGE**: Edit only what the claimed issue requires. No drive-by refactorings or unsolicited formatting sweeps.
6. **PREREQUISITE BLOCKERS**: If a task requires an unrecorded fix, run `scripts/agents/create_blocker_issue.py` to create a GitHub issue. Never patch outside scope.
7. **ALWAYS SYNC BEFORE PUSH**: Run `git fetch origin main && git merge origin/main` before every push. Never force-push.
8. **PUSH & PR**: Push to your acquired slot (`origin <lane>-<N>`), or — for docs-only changes — a `docs/<issue>-<slug>` branch (OPS-06 pattern). Open a PR targeting `main`. Title format: `type(scope): description (#<issue>)`.
9. **ZERO REGRESSION**: All unit tests, pre-push checks, and Unified PR Gates must pass green before merge.
10. **NEVER IDLE (PRIORITY-FIRST CONTINUOUS LOOP)**: When a PR is created/merged, immediately claim the **highest-priority** unclaimed issue in your lane — priority order `P0-critical → P1-high → P2-medium → P3-low`, oldest first within a level ([`docs/agents/ISSUE_PRIORITY_POLICY.md`](docs/agents/ISSUE_PRIORITY_POLICY.md); queue: `./scripts/agents/next_claimable.sh <lane>`).
11. **DISCOVERY-DRIVEN ISSUE CREATION**: If you discover a bug, security vulnerability, or architectural gap **unrelated to your current issue scope** while working, run `scripts/agents/create_discovery_issue.py` to create a new issue with `discovered-by:<your-role>` label. Do NOT fix it yourself unless you claim it after your current PR merges.
12. **NO SELF-MERGE** (#2009): An agent MUST NOT approve or merge their own PR. At least 1 approving review from a different agent or human is required before merge. *(Closes violation vector 7.4.)*
13. **ONE ACTIVE CLAIM PER AGENT** (#2009): An agent MUST NOT have more than 1 issue with `status:in-progress` at any time. Complete or release the current claim before claiming another. *(Closes violation vector 3.8.)*
14. **BRANCH FROM MAIN ONLY** (#2009): Every new branch MUST be created from the latest `origin/main` (after `git fetch`). Never branch from another agent's branch or a stale local main. *(Closes violation vector 2.5.)*
15. **NO FORCE-PUSH** (#2009): Force-push (`git push --force` / `--force-with-lease`) to agent branches is STRICTLY FORBIDDEN. Use a new commit to address review feedback. *(Closes violation vectors 5.5, 2.4.)*
16. **PR TITLE FORMAT ENFORCED** (#2009): PR title MUST match `type(scope): description (#issue)`. PRs with non-matching titles will be blocked by CI. *(Closes violation vector 6.3.)*
17. **PR DESCRIPTION REQUIRED** (#2009): Every PR MUST include a description with: what changed, why, and how it was tested. Empty-description PRs will be blocked. *(Closes violation vector 6.5.)*
18. **NO CROSS-BRANCH PUSH** (#2009): An agent MUST ONLY push to their own acquired slot (`<lane>-<N>`). Pushing to another agent's branch is STRICTLY FORBIDDEN. *(Closes violation vector 5.2.)*
19. **MANDATORY MCP TOWER CONNECT** (#2009): Every agent MUST connect to the MCP Control Tower (no-auth SSE at `https://supremeai-mcp-tower.onrender.com/sse`) at startup and send a heartbeat every 45 seconds while active. Use `scripts/agents/mcp_tower_client.py`. Agent identity file (`.z-ai-config/agent-identity.json`) is gitignored. *(Closes violation vector 9.3.)*
20. **FILE DECLARATION ON CLAIM** (#2009): When claiming an issue, the agent MUST declare which files they intend to touch in the audit comment: `Touching files: file1.py, file2.ts`. This enables file-lock conflict detection. *(Closes violation vector 1.6.)*
21. **NO TEST MANIPULATION** (#2009): An agent MUST NOT: (a) delete failing tests, (b) comment out test assertions, (c) lower coverage thresholds, (d) add `@pytest.mark.skip` to failing tests, (e) replace real implementations with mocks/stubs to make tests pass. All violations are treated as REGRESSION and blocked. *(Closes violation vectors 3.5, 3.6, 3.7, 4.2, 4.3.)*
22. **POST-MERGE REGRESSION CHECK** (#2009): After a PR merges to main, the merge-train MUST verify main CI is still green. If main goes red within 15 minutes of a merge, the merging PR is auto-reverted and a root-cause issue is created. *(Closes violation vector 8.1.)*
23. **RULES RE-READ ON CHANGE** (#2009): If `AGENTS.md` or `AGENT_WORK_BOUNDARIES_CHARTER.md` changes, all active agents MUST re-read the rules before their next action. The `rules_version` field in AGENTS.md header tracks this. *(Closes violation vector 1.7.)*

The 8 rules that matter daily, distilled: [`docs/agents/GOLDEN_RULES.md`](docs/agents/GOLDEN_RULES.md).
Lane boundaries (allowed / forbidden per lane): [`docs/agents/AGENT_WORK_BOUNDARIES_CHARTER.md`](docs/agents/AGENT_WORK_BOUNDARIES_CHARTER.md).

---

## 3. The Universal Loop

```
CLAIM → BRANCH → WORK → VERIFY → PR → (MERGE DOOR) → NEXT
```

1. **Claim** the highest-priority unclaimed issue in your lane — `./scripts/agents/next_claimable.sh <lane>` (atomic claim — never edit without it; skipping a priority level requires a stated reason on the skipped issue).
2. **Branch** from fresh `origin/main` onto your slot (`acquire_role_slot.py`).
3. **Work** the narrowest sound change; stay inside your role card's allowed scope.
4. **Verify**: pre-push checks + `scripts/git/pre-push`; collision check when touching shared paths.
5. **PR** to `main` (`type(scope): description (#issue)`) — gates run, then the merge queue
   (`queue:pending-rollup` → single-flight rollup batch → single merge door).
6. **Never merge a PR that sits inside a rollup batch** — batch members land together via the batch PR only (single merge door).
7. **Next**: claim again. When blocked → `queue:hold` + a reason issue. Never sit silent (see Golden Rule 8).

Deep lifecycle: [`OPS-06`](docs/master_docs/OPS-06-MULTI-AGENT-BRANCHING-LIFECYCLE.md) ·
[`OPS-07`](docs/master_docs/OPS-07-DEVELOPER-AGENT-LIFECYCLE.md) ·
[`OPS-05`](docs/master_docs/OPS-05-PR-HELPER-LIFECYCLE.md) ·
[`OPS-08`](docs/master_docs/OPS-08-SUPREMEAI-RUNTIME-WORK-PROCESS.md).

---

## 4. Where Everything Lives

Every rule document, its owner lane, and its change-control rule are mapped in
[`docs/agents/RULES_INDEX.md`](docs/agents/RULES_INDEX.md).

**If it is a rule and it is not indexed there, it does not exist.**
