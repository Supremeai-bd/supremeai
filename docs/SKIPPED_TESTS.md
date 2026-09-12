# Skipped Tests — Governance Register

**Recreated:** 2026-09-13 (MASTER_PLAN Phase 0 close-out item #2)
**Previous copy** was lost in repo restructuring; CI references this file (see
`.github/workflows/ci.yml` → "Publish skipped-test summary"), so it must always exist.

> বাংলা: স্কিপ কোনো অদৃশ্য জিনিস নয় — প্রতিটি স্কিপ এখানে নিবন্ধিত হবে।
> একটি স্কিপ = একটি স্বীকৃত দায়। "Silent skip" মানে ভুয়া সবুজ টিক — আর ভুয়া
> সবুজ টিক "No Silent Failure" constitution-এর সরাসরি লঙ্ঘন।

## Policy (the rules)

1. **Every skip must carry a reason string** — `pytest.mark.skip(reason="...")`
   with a real explanation, never `reason=""`.
2. **Every skip must be tracked here** — one row in the inventory below, with
   owner-agnostic triage label (ENV / DEBT / EXT).
3. **Skip budget** — total skip markers must trend down: 125 (baseline
   2026-09-13) → < 30 by end of Phase 2. A PR that adds a skip without adding
   a row here must be rejected in review.
4. **Labels:**
   - `ENV` — test cannot run in CI environment (external service, GPU, network);
   - `DEBT` — feature/test is genuinely unfinished; must link to a plan item;
   - `EXT` — depends on third-party service quota/credentials (key rotation etc.).

## Current inventory (baseline audit 2026-09-13)

Marker-count audit via:
`rg -c "pytest\.mark\.skip|pytest\.skip\(|pytest\.mark\.skipif|@pytest\.mark\.xfail" backend/tests/`

| Area | Files | Skip markers | Dominant label | Notes |
|---|---|---|---|---|
| tests/unit (legacy endpoint suite) | ~6 | 25 | DEBT | `test_api_endpoints.py` alone holds 25; candidates for deletion/rewrite into route-tier tests |
| tests/api (admin/task/auth/bootstrap) | ~9 | 20 | DEBT/ENV | `test_admin_routes.py` = 9; mostly external-service mocks that were never finished |
| tests/core (payments/config/e2e/sandbox) | ~20 | 40 | ENV/DEBT | payments & gcp need live creds (EXT); sandbox tests need docker |
| tests/scripts (billing) | 4 | 4 | DEBT | billing reporters mocked halfway |
| tests/agents | 3 | 5 | ENV | marketplace/sentinel need external registry |
| tests/security | 1 | 2 | DEBT | auth edge-cases |
| tests/hitl, tests/other | ~10 | 29 | mixed | long tail |

**Total baseline: 125 markers across 53 files.**

## Triage plan (toward < 30 by end of Phase 2)

1. **Delete-and-document pass (week 1):** legacy `tests/unit/test_api_endpoints.py`
   duplicates route coverage that now lives in `tests/api/routes/` — verify
   overlap with coverage report, delete dead duplicates (expected −20).
2. **Credential quarantine (week 2):** move all EXT skips behind a single
   `@pytest.mark.ext_service` marker, excluded by default but runnable in the
   nightly job where secrets exist (expected −15 from gate count).
3. **Rewrite pass (weeks 3–6):** each DEBT skip either becomes a real test or
   gets a linked issue in `docs/plans/` — no orphan skips.

## Verification

- CI prints total collected/skipped every backend run ("Publish skipped-test
  summary" step) — the number must never silently grow.
- Mission suite (`backend/tests/missions/`) must contain **zero** skips — the
  pass^k scoreboard (scripts/ci/mission_passk.py) is computed on real results only.
