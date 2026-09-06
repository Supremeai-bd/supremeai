# SupremeAI Engineering Intelligence Decision Log

This log records policy decisions, accepted risks, false positives, false negatives, and rule changes for the engineering-intelligence system. It is append-only in spirit: correct an entry with a new decision rather than rewriting history.

## Entry format

- **ID:** `POL-YYYY-MM-DD-NNN`
- **Date:** ISO-8601 date
- **Scope:** detector, CI, deployment, repository index, planner, repair, or autonomy
- **Decision:** what was decided
- **Evidence:** reports, tests, commit SHA, or source locations
- **Risk/impact:** known consequence
- **Owner:** accountable reviewer
- **Status:** proposed, accepted, rejected, superseded

## Decisions

### POL-2026-09-07-001

- **Date:** 2026-09-07
- **Scope:** policy baseline
- **Decision:** Use four risk levels: `low`, `medium`, `high`, and `critical`. Unknown risk cannot be labeled low.
- **Evidence:** `docs/ai-engineering/INTELLIGENCE_POLICY.md`; roadmap Phase 0
- **Risk/impact:** Conservative classifications may create review overhead until measured.
- **Owner:** SupremeAI engineering
- **Status:** accepted

### POL-2026-09-07-002

- **Date:** 2026-09-07
- **Scope:** protected surfaces
- **Decision:** Treat CI, deployment, migrations, secrets, authentication, tenant isolation, billing, and production configuration as protected by default.
- **Evidence:** `scripts/ai/change_impact_detector.py`; policy protected-path section
- **Risk/impact:** Protected changes require explicit review and cannot be silently automated.
- **Owner:** SupremeAI engineering
- **Status:** accepted

### POL-2026-09-07-003

- **Date:** 2026-09-07
- **Scope:** automation boundary
- **Decision:** Deterministic tools own gate status; AI may plan and explain but cannot mark its own evidence as verified.
- **Evidence:** roadmap Sections 2, 3, and 5
- **Risk/impact:** Model failures degrade planning quality, not safety-gate integrity.
- **Owner:** SupremeAI engineering
- **Status:** accepted

### POL-2026-09-07-004

- **Date:** 2026-09-07
- **Scope:** enforcement rollout
- **Decision:** Keep the current intelligence checks advisory until fixture coverage, reproducibility, false-positive review, and rollback evidence justify blocking mode.
- **Evidence:** `.github/workflows/ci.yml`; roadmap Phase 3
- **Risk/impact:** A defect may be reported without immediately blocking a merge during the measurement period.
- **Owner:** SupremeAI engineering
- **Status:** accepted

## False-positive and false-negative review template

When a finding is disputed, append a new entry containing:

- the exact command and commit SHA;
- the finding category and report excerpt without secret values;
- why it was a false positive or false negative;
- the proposed rule/test change;
- regression-fixture coverage;
- reviewer and final disposition.
