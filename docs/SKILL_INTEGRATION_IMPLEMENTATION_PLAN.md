# Skill Integration Implementation Plan

Goal: Make SupremeAI skills actively beneficial by wiring them into loop dispatch, keeping skill planes in sync, adding runnable entry points, and measuring effectiveness.

## Phase 1 — Trigger-based skill injection (high impact)
- Edit `scripts/agents/continuous_agent_loop.py` (skill loader around line 2207): add `load_matching_skills(task_text)` using `ProgressiveLoader.match()` over `skills/` root.
- Inject matched skill bodies into solver/role instruction context (cap: top-1 skill, max 4k chars) with a `<!-- skill: name -->` marker.
- Fail-closed: if no match, proceed normally; never block dispatch.
- Add unit test `tests/test_skill_injection.py` verifying match + injection marker.

## Phase 2 — Skill plane parity guard
- Add `scripts/ci/skill_plane_parity_guard.py` comparing `.agents/skills/*/SKILL.md` and `skills/*/SKILL.md` (frontmatter name/version + body hash).
- Allow intentional divergence only via a declared `parity: divergent` frontmatter flag.
- Register in `.github/workflows` CI and pre-commit.
- Add `tests/test_skill_plane_parity_guard.py`.

## Phase 3 — Runnable entry points for high-value skills
- `skills/diagnosing-bugs/scripts/repro-harness.py`: wrap Phase-1 feedback loop (run a test command, report red/green).
- `skills/refactor/scripts/bloat-check.py`: detect oversized functions/monoliths (line-count threshold).
- `skills/performance-optimization/scripts/baseline.py`: timing harness template.
- Each entry referenced via `entry:` frontmatter; add tests for `--help` exit 0.

## Phase 4 — Effectiveness measurement
- Extend `scripts/agents/learning_feedback.py` to record skill usage (skill name, task id, outcome) in `skill_usage.jsonl`.
- Add `scripts/agents/skill_effectiveness_report.py` aggregating usage -> success rate per skill.
- Surface top-3 / bottom-3 skills in continuous loop summary.

## Phase 5 — Continuous curation
- Schedule `skill-curator` via continuous loop cadence (read-only).
- skill-curator outputs candidate cards; solver implements only approved, non-duplicate skills through bridge.
- Add dedup check against existing skill names before creation.

## Verification (3-tier)
- Tier-1: reflection sweep (no dead refs, parity guard green).
- Tier-2: boot smoke (`python -c "import ..."` for new scripts).
- Tier-3: pytest (skills/tests + new tests) + skill_conformance_guard.

## Rollout order
1. Phase 1 (injection) + tests.
2. Phase 2 (parity guard).
3. Phase 3 (entry scripts).
4. Phase 4 (metrics).
5. Phase 5 (curation cadence).

## Success criteria
- At least one matched skill injected per solver task when triggers hit.
- Zero plane drift without declared divergence.
- Conformance guard and skills tests green.
- Skill usage log populated after one loop cycle.

