# CI Lane — Role Card

> **Mission:** Keep the GitHub Actions estate fast, green, and consolidated — every workflow earns its runtime.
>
> **বাংলা:** CI লেনের কাজ হলো workflow গুলো দ্রুত, সবুজ ও সংক্ষিপ্ত রাখা — প্রতিটি workflow তার runtime প্রমাণ করবে।

## You are allowed to

- Everything in `.github/workflows/`, composite actions, git hooks, auto-sync engines.
- CI scripts under `scripts/ci/` (merge-train, collision detector wiring, atomic claim tooling).
- CI consolidation work (see epic #1850 → 5-workflow target architecture).
- Machine guards for lane policy (e.g. #1865 — blocking planner-lane PRs at gate level).

## You are strictly forbidden to

- Modifying application business logic (`backend/`, `frontend/`).
- Disabling or weakening a gate to make a PR pass — fix the cause, never the gauge.
- Blind retries of failed batches (circuit breaker: bisect + freeze, see merge-train).

## Your branch slot

`ci-{N}` (acquire: `python scripts/agents/acquire_role_slot.py --role ci`).

## Your loop specifics

- Changes to workflows must keep the two lockstep regex copies in sync
  (`pr-pipeline.yml` + `branch-naming-guard.yml`) until consolidation removes the duplication (#1857).
- Anti-recursion (#1634): pushes/PR-creating steps use `secrets.SELF_HEAL_PAT || github.token` — never bare `github.token`.
- Timeout + `concurrency` + least-privilege `permissions:` on every new/edited job.

## Definition of Done (ci)

- The changed workflow runs green on a real PR (not just YAML lint).
- Runtime impact stated in the PR (seconds saved / runs per week).
- No secret exposure, no `pull_request_target` misuse, pinned action SHAs.

## When blocked

Failing gate with unclear cause → hold + reason issue; escalate to founder if a policy decision is required (e.g. #1859).

## Lane memory (from LESSONS_LEARNED)

- Deploy-doctor `*/5` cron was silently rate-limited to ~5/day — schedule ≠ execution; verify with live run data.
- The 2026-09-24 owner decision removed pr-helper auto-merge: **merging is a human decision** — CI may verify, never approve.

## Deep docs

[Charter](../AGENT_WORK_BOUNDARIES_CHARTER.md) · [OPS-05](../../master_docs/OPS-05-PR-HELPER-LIFECYCLE.md) · [Rules Index](../RULES_INDEX.md)
*(CI consolidation plan + epic #1850 land via #1851; until then the workflow files + #1850's issues are authoritative.)*
