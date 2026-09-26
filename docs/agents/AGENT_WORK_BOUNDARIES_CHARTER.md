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
| **Browser** | `browser-{N}` | Live-environment exploration & evidence gathering (screenshots, DOM states, reproduction flows) filed as issues. | Code changes of any kind; credential exfiltration. *(Pool activates with registry v2.1 #1805 + branch regex #1861.)* |
| **Platform** | `platform-{N}` | Cloud services (Render, Upstash, Supabase, Cloudflare, Infisical) health sweeps. | Modifying core application features. |

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
