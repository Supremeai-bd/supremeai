# ADR-002: Tier 3 (Core/Evolution/Memory extraction) স্থগিত — আগে logging-decoupling

- **তারিখ:** ২০২৬-১০ (probe-রায়-সমর্থিত)
- **Status:** Accepted

## Context
Task 24 audit-এ অবশিষ্ট কাজ ৩ স্তরে ভাগ হয়: Tier 1 (লাল-CI নিরাময়), Tier 2 (roadmap-গ্যাপ: §21 integration-CI, release-train, supremeai-open, Mission Control), Tier 3 (extraction)।

## Decision
Tier 3 স্থগিত। যখন হবে, ক্রম: logging-decoupling আগে (৩৬ core import-এর ২৩টি logging_config), তারপর Core/Evolution/Memory extraction।

## Consequences
- শক্তি গেছে Tier 1 → Tier 2-তে (Task 25–29-এ সম্পন্ন — দেখুন `worklogs/worklog.md`)।
- extraction-এর ভবিষ্যৎ-খরচ logging-decoupling পরিকল্পনায় আগেই কমানো।
