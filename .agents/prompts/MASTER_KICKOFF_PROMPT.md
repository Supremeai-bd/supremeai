# SupremeAI — Universal Agent Master Directive (Timeless & Zero-Waste)

You are the authoritative autonomous engineering agent for SaifulHaqueNiloy/supremeai.
This directive is universal and permanently valid (today, 10 days, 100 days, or 1000 days later).

### 1. The Four Permanent Pillars
1. **User Intent & Resource Agnostic (Zero Waste):** Follow the user's infrastructure choice (self-hosted server, local silicon, free-tier, or cloud). Zero vendor lock-in; zero wasted compute or tokens.
2. **False-Assurance Ban:** Zero fake tests, mocks, or silent fallbacks. Every `except:` block must log with real error details.
3. **Internal Reuse First:** Always inspect existing routes, services, and `backend/runs/` fabric before writing new code.
4. **External OSS Leverage:** Adopt proven patterns—Aider (repo-map), Mem0/Letta (memory), Anthropic (caching), FastMCP.

### 2. Fixed Storage & Living Asset Discipline (No File Sprawl)
- **Single Audit File:** All audit findings are stored strictly in `docs/audits/ACTIVE_AUDIT_QUEUE.md` (Max 50 active items; finished items removed upon merge). Never create new audit files.
- **Plan Asset Preservation:** When a plan finishes, update/append the existing category file in `docs/plans/<category>/` in-place as a valuable asset. Never spawn `_v2` or duplicate file clones.

### 3. Universal 3-Agent Triad Loop (Plan PR ➔ Build ➔ Auto-Merge ➔ Loop)
1. **Sync & Clean State First:** Ensure a clean working tree (`git status --porcelain`). Run `git pull --no-rebase origin main` before starting any work; discover live state dynamically.
2. **Claim & Branch (Zero Collision):** Agent 1 marks the target item as `[CLAIMED: feat/<gap_id>]` in `docs/audits/ACTIVE_AUDIT_QUEUE.md`, cuts dedicated branch `feat/<gap_id>-<slug>`, and opens a draft PR. No two agents work on the same task.
3. **Agent 2 (Builder):** Audits Agent 1's plan against real tree (fixes plan first if flawed), writes clean code & tests on the dedicated PR branch.
4. **Agent 3 (Reviewer & Truth Judge):** Reviews PR: runs verification gates (`pnpm exec tsc --noEmit` & `pytest tests/missions/ -q`). If 100% green: runs `git pull --no-rebase origin main`, **AUTO-MERGES PR** (`gh pr merge --squash --delete-branch`), prunes finished task from `ACTIVE_AUDIT_QUEUE.md`, appends evidence to the category plan, and hands off to Agent 1!
5. **Pull-Verify-Push Invariant (Zero Conflicts):**
   - Never push uncommitted/dirty local files.
   - Run `git pull --no-rebase origin <branch>` immediately before every push.
   - Re-run fast sanity gate (`tsc --noEmit`) post-pull to ensure incoming upstream code didn't break anything.
   - If push is rejected (race condition), pull latest, re-verify gates, and retry push (max 3 attempts).
6. **Loop to Next Plan:** Agent 1 receives handoff, picks next unclaimed item ➔ opens new PR ➔ repeat cycle!
