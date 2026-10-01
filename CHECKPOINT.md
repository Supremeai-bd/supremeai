# SupremeAI Session Checkpoint
> Auto-updated by AI agents after each major session. Next agent must read this first.

## Last Session
- **Date:** 2026-10-01 22:57 UTC
- **Agent:** Auto-updated (checkpoint_update.py)
- **Summary:** Auto-updated via pre-commit hook

## Completed This Session
  - (see git log for details)

## Files Changed
  - `scripts/ci/pipeline_failure_register.py`
  - `tests/test_pipeline_failure_register.py`
  - `tests/test_continuous_agent_loop.py`
  - `docs/archive/lessons_2026-10.md`
  - `LESSONS_LEARNED.md`
  - `.github/constitution/rules.yml`
  - `scripts/agents/continuous_agent_loop.py`

## Pending (Carry Forward)
- Skip budget trending: 26 active skip-marker sites / 24 files (machine-enforced in docs/SKIPPED_TESTS.md — was 103/53 at the 2026-09-14 audit; <30 target reached 2026-09-25, keep it there)
- Root-level lint issues to be continuously monitored
- MCP gateway production rollout: persistence, routing, management API, security review, and deployment verification (#927, #928 open)
- Supabase `ai_memory` schema execution and privacy/retention sign-off
- Review stale remote branches and repository stashes before cleanup
- Production certification gate runtime evidence (#1096); live-smoke target-resolution unification (#1132)

## Recent Lessons Learned
  - 2026-10-01 — 🛡️ Advisory Templates & Allowlist-Identity: "উপদেশ-ভিত্তিক গভর্নেন্স মানেই ফাঁকা দরজা" (#2912)
  - 2026-09-28 — 🏛️ Rules vs. Architecture Conflation: কন্সটিটিউশনে পাইপলাইন অটোমেশন ঢুকিয়ে এজেন্টদের কনফিউজ করা এবং 'The 101% Benefit Principle'
  - 2026-09-28 — 🔁 Duplicate PRs: 12টি Branch-এ Issue-Number না থাকায় ও `has-pr` Label-বিহীন PR খোলায় ১টি Issue-এ ৪টি পর্যন্ত PR (GAP-DUPLICATE-01) (#2296)

## Key Architecture Reminders
- Extension = 100% Thin Client. No third-party API keys from user.
- `SupremeAIService.ts` lines 350-424: OpenRouter fetch logic → MUST be removed.
- Only local Ollama permitted as offline fallback.
- Supabase `ai_memory` table setup pending (Phase C).

## Next Agent Start Point
1. Read `AGENTS.md` + this file (done ✅)
2. Check task type → read relevant files per Context Matrix in `AGENTS.md`
3. Continue from Pending list above
