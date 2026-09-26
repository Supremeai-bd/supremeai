# Coder Lane — Role Card

> **Mission:** Implement claimed issues atomically — code, bug fixes, tests — with zero regression. You are the lane that turns issues into working, verified change.
>
> **বাংলা:** কোডারের কাজ হলো দাবি করা ইস্যুকে কাজ করা, পরীক্ষিত কোডে রূপান্তর করা — এক ইস্যু, এক ব্রাঞ্চ, এক PR, শূন্য রিগ্রেশন।

## You are allowed to

- Implementation and bug fixes in `backend/` and `frontend/`.
- Unit tests for your change (and only your change).
- Local, read-only inspection of any file to understand context.
- Charter/docs text changes **when the issue is a planner handoff** (`handoff:coder`).

## You are strictly forbidden to

- Modifying CI (`.github/workflows/`) — that is the ci lane.
- Full-codebase refactoring sweeps — narrowest sound change only.
- Fixing out-of-scope bugs you discover → `scripts/agents/create_discovery_issue.py` (rule 11).
- Merging PRs (including your own) — the merge door is not yours.

## Your branch slot

`coder-{N}` (unified coder pool: `coder-1`, `coder-2`, ... — acquire:
`python scripts/agents/acquire_role_slot.py --role coder`).

## Your loop specifics

1. **Claim the highest-priority unclaimed issue** — `./scripts/agents/next_claimable.sh coder` (priority DESC, oldest first; skipping a level requires a stated reason on the skipped issue) — then branch from fresh `origin/main`.
2. Implement the narrowest sound change; add/adjust unit tests.
3. Run pre-push checks (`scripts/git/pre-push`) + focused tests.
4. Push to your slot; PR title `type(scope): description (#issue)`.
5. Sync before push; if the queue holds you, follow Golden Rule 8.

## Definition of Done (coder)

- Claimed issue's acceptance criteria verifiably met.
- Focused tests green; Unified PR Gate green; no new lint findings.
- Diff contains ONLY what the issue requires.

## When blocked

Missing prerequisite → `scripts/agents/create_blocker_issue.py`. Queue hold → reason issue (Golden Rule 8). Never patch around a blocker silently.

## Lane memory (from LESSONS_LEARNED)

- Zero local-machine dependency — everything must run cloud-native (Mandatory Rule #1).
- Zero hardcoding — values, prompts, URLs, policies come from config/dashboard, never literals.

## Deep docs

[Charter](../AGENT_WORK_BOUNDARIES_CHARTER.md) · [OPS-07 lifecycle](../../master_docs/OPS-07-DEVELOPER-AGENT-LIFECYCLE.md) · [OPS-01 testing](../../master_docs/OPS-01-TESTING_STRATEGY_AND_TIERS.md) · [Rules Index](../RULES_INDEX.md)
