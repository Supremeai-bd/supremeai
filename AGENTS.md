# SupremeAI — AGENTS.md (Universal Operating Constitution)

> Invariant operating constitution for all AI agents and Local IDE operators. Zero exceptions.

1. **NEVER TOUCH `main` DIRECTLY**: Direct commits or pushes to `main` are strictly forbidden. All code enters `main` ONLY through Pull Requests.
2. **NO CLAIM, NO CODE**: You MUST atomically claim an open GitHub Issue (`status:in-progress`) before editing ANY file. Unclaimed work is rejected.
3. **ROLE-SCOPED BRANCH SLOTS**: Always acquire an available slot matching your role (`scripts/agents/acquire_role_slot.py`):
   - `planner-{N}`: Architecture, planning, audits. Never write feature code.
   - `coder-{N}`: Implementation, bug fixes, unit tests. (Unified Coder Pool: coder-1, coder-2, coder-3...).
   - `ci-{N}`: Workflows, GitHub Actions, git hooks, auto-sync engines.
   - `pr-helper-{N}`: PR verification, diagnostics, rollups.
   - `platform-{N}`: Cloud infrastructure (Render, Supabase, Redis, Cloudflare, Infisical).
4. **1 ISSUE = 1 BRANCH = 1 PR**: Keep changes atomic. Never bundle unrelated changes into one branch.
5. **NARROWEST SOUND CHANGE**: Edit only what the claimed issue requires. No drive-by refactorings or unsolicited formatting sweeps.
6. **PREREQUISITE BLOCKERS**: If a task requires an unrecorded fix, run `scripts/agents/create_blocker_issue.py` to create a GitHub issue. Never patch outside scope.
7. **ALWAYS SYNC BEFORE PUSH**: Run `git fetch origin main && git merge origin/main` before every push. Never force-push.
8. **PUSH & PR**: Push ONLY to your acquired slot (`origin <role>-<N>`) and open a PR targeting `main`. Title format: `type(scope): description (#<issue>)`.
9. **ZERO REGRESSION**: All unit tests, pre-push checks, and Unified PR Gates must pass green before merge.
10. **NEVER IDLE (CONTINUOUS LOOP)**: When a PR is created/merged, immediately query and claim the next unclaimed issue in your role lane.
