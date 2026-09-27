# SupremeAI Agent Work Boundaries & Role Charter

> Invariant role boundaries for all autonomous agents and Local IDE operators. Zero cross-boundary drive-by edits.
>
> **Companion documents:** [`GOLDEN_RULES.md`](GOLDEN_RULES.md) (the 8-rule daily core) · [`roles/`](roles/) (per-lane role cards) · [`RULES_INDEX.md`](RULES_INDEX.md) (canonical map of every rule doc)

---

## 0. The Final Mission (Rule Zero)

**Every agent's final job — beyond any single issue — is to leave SupremeAI better than you found it, day by day.**
Mistake → log once in `LESSONS_LEARNED.md` + prevention rule. Discovery → issue now. Idle → next unclaimed issue in your lane. Every PR must make the system measurably better. (Full text: [`AGENTS.md` §0](../../AGENTS.md).)

---

## 1. Role Pools & Boundaries

| Role Pool | Branch Slot Pattern | Allowed Scope | Strictly Forbidden |
| :--- | :--- | :--- | :--- |
| **Planner** | `planner-{N}` | Full codebase audits, task planning, backlog issues (`docs/plans/`). | Modifying code in `backend/`, `frontend/`, or `.github/`. **Opening pull requests — planner output is ISSUES; plan docs land via `handoff:coder` issues (#1864).** |
| **Coder** | `coder-{N}` | Local issue audits, code implementation, bug fixes, unit tests (`backend/`, `frontend/`). | Modifying CI (`.github/workflows/`), full codebase refactoring. |
| **CI / CD** | `ci-{N}` | GitHub Workflows (`.github/workflows/*`), git hooks, auto-sync engines. | Modifying application business logic. |
| **PR Helper** | `pr-helper-{N}` | PR diagnostics, gate audits, merge train rollups, squash-merging. | Writing new feature PRs. Merging a PR that sits inside an open rollup batch (single merge door — #1872). |
| **Browser** | `browser-{N}` | Live-environment exploration & evidence gathering (screenshots, DOM states, reproduction flows) filed as issues. | Code changes of any kind; credential exfiltration. |
| **Platform** | `platform-{N}` | Cloud services (Render, Upstash, Supabase, Cloudflare, Infisical) health sweeps. | Modifying core application features. |
| **Super** | `super-{N}` | **Omni-lane executor** — union of all six specialist lanes; founder directives, emergencies, cross-lane work. Lane rules travel with the work (planner-scope work = issues-only). | Stealing `handoff:<lane>` work without founder assignment or lane handoff; any universal-invariant violation. (Issue #1924.) |

Per-lane detail (mission, loop specifics, definition of done, blocked-behavior, lane memory): see the **[role cards](roles/)**.

---

## 2. Invariant Rules (Zero Ambiguity)

1. **NEVER TOUCH `main` DIRECTLY**: Always acquire an available branch slot via `scripts/agents/acquire_role_slot.py --role <role>`.
2. **NO CLAIM, NO CODE**: Atomically claim a GitHub issue (`status:in-progress`) before editing any file.
3. **1 ISSUE = 1 BRANCH = 1 PR**: Strict slot isolation. Never bundle unrelated changes.
4. **NO DRIVE-BY FIXES**: If an issue requires fixing an unrecorded prerequisite bug, run `scripts/agents/create_blocker_issue.py` to create a blocker issue.
5. **ALWAYS SYNC BEFORE PUSH**: Run `git fetch origin main && git merge origin/main`.
6. **BOT PUSH TOKEN**: Automated bot pushes must always use `secrets.SELF_HEAL_PAT` to prevent `action_required` hangs.
7. **DISCOVERY-DRIVEN ISSUE CREATION**: Any agent (coder, ci, pr-helper, platform) that discovers a bug, security vulnerability, or architectural gap while working on their claimed issue — **is authorized and required** to create a new GitHub issue for that discovery using `scripts/agents/create_discovery_issue.py`. Constraints:
   - The discovered issue must be **unrelated** to the current task scope (if it's a prerequisite, use the existing blocker flow via `create_blocker_issue.py`).
   - The discovering agent must **NOT** fix the discovered issue themselves (unless they claim it after their current PR merges).
   - The issue must be labeled with `discovered-by:<role>` (e.g. `discovered-by:coder`, `discovered-by:ci`, `discovered-by:pr-helper`).
   - The issue must reference the parent issue where it was discovered.
8. **A MISTAKE HAPPENS ONCE**: Every error gets a `LESSONS_LEARNED.md` entry (Date / Issue / Fix / Lesson) AND a prevention rule — who made it, why, and how it can never recur silently. This is the auditor duty of every lane.
9. **BLOCKED → HOLD + REASON ISSUE**: An agent or PR that cannot proceed must never sit silent: apply the hold label (`queue:hold` / `hold:merge-conflict` / `blocked`) AND create a reason issue carrying the cause and the exact unblock action (#1873).
10. **PRIORITY-FIRST CLAIMING**: Issues are worked in automatic priority order (`P0-critical → P1-high → P2-medium → P3-low`, oldest first within a level). No priority label = lowest priority — nothing jumps the queue unlabelled. The auditor (planner lane) owns priority correctness; every priority change carries a reason comment. Tooling: `scripts/agents/next_claimable.sh <lane>` ([`ISSUE_PRIORITY_POLICY.md`](ISSUE_PRIORITY_POLICY.md)).
11. **AUDITOR DUTY — RULES AUTO-EVOLVE** (#2010): When any agent discovers a violation vector: (1) Document in `docs/audits/violation-matrix.md`, (2) Create prevention rule in AGENTS.md, (3) Create enforcement issue for CI gate, (4) Link rule ↔ issue ↔ vector, (5) Verify enforcement, (6) Mark vector `✅ closed`. An unenforced rule is not a rule — it's a suggestion. Audit cadence: weekly (planner audits merged PRs), monthly (full lifecycle audit), on-incident (immediate root-cause).
12. **NO SELF-MERGE** (#2009): An agent MUST NOT approve or merge their own PR. At least 1 approving review from a different agent or human is required. *(Closes vector 7.4.)*
13. **ONE ACTIVE CLAIM PER AGENT** (#2009): An agent MUST NOT have more than 1 `status:in-progress` issue at any time. *(Closes vector 3.8.)*
14. **BRANCH FROM MAIN ONLY** (#2009): Every new branch MUST be from the latest `origin/main`. Never from another agent's branch or stale local main. *(Closes vector 2.5.)*
15. **NO FORCE-PUSH** (#2009): `git push --force` to agent branches is STRICTLY FORBIDDEN. Use a new commit for review feedback. *(Closes vectors 5.5, 2.4.)*
16. **PR TITLE + DESCRIPTION ENFORCED** (#2009): PR title MUST match `type(scope): description (#issue)`. PR description MUST include what/why/tested. Empty = blocked. *(Closes vectors 6.3, 6.5.)*
17. **NO CROSS-BRANCH PUSH** (#2009): An agent MUST ONLY push to their own slot (`<lane>-<N>`). Pushing to another agent's branch is FORBIDDEN. *(Closes vector 5.2.)*
18. **MANDATORY MCP TOWER CONNECT** (#2009): Every agent MUST connect to MCP Control Tower (no-auth SSE) at startup + heartbeat every 45s. Use `scripts/agents/mcp_tower_client.py`. *(Closes vector 9.3.)*
19. **FILE DECLARATION ON CLAIM** (#2009): When claiming, agent MUST declare target files in audit comment: `Touching files: ...`. Enables file-lock detection. *(Closes vector 1.6.)*
20. **NO TEST MANIPULATION** (#2009): No deleting/skipping/commenting tests, lowering coverage, or mocking real impls to pass CI. Treated as REGRESSION. *(Closes vectors 3.5-3.7, 4.2-4.3.)*
21. **POST-MERGE REGRESSION CHECK** (#2009): Merge-train verifies main CI green within 15 min. If red → auto-revert + root-cause issue. *(Closes vector 8.1.)*
22. **RULES RE-READ ON CHANGE** (#2009): If AGENTS.md/charter changes, active agents MUST re-read before next action. `rules_version` field tracks this. *(Closes vector 1.7.)*
