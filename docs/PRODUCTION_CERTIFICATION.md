---
id: production-certification
title: Production Certification Gate — GO/CONDITIONAL/NO-GO
document_role: runbook
status: active
canonical: true
owner: coder-lane
last_verified: 2026-10-07
related_docs:
  - "[docs/INDEX.md](./INDEX.md)"
  - "[AGENT_RULES.md](../AGENT_RULES.md)"
supersedes: []
superseded_by: []
source_issue: "#4167"
source_pr: null
---

# Production Certification Gate (#3071, #4167)

একটি authoritative, machine-checkable রিপোর্ট যেকোনো প্রশ্নের একটাই উত্তর দেয়:
**"এই নির্দিষ্ট main SHA কি production-এ যেতে পারে?"** — একাধিক dashboard/issue
ম্যানুয়ালি মেলানো ছাড়াই।

```bash
GH_TOKEN=<token> python scripts/ci/production_certification.py --output cert.json
# exit: 0=GO, 1=CONDITIONAL, 2=NO-GO
```

## GO পাওয়ার ঠিক শর্ত (SSOT: `CRITICAL_ITEMS` in script)

| Item | Critical | উৎস | শর্ত |
|---|---|---|---|
| `sha_alignment` | ✅ | deploy-train.yml সফল run | সর্বশেষ production deploy-এর HEAD == candidate SHA |
| `deploy_freshness` | ✅ | deploy-train.yml সফল run | deploy ≤ ৭ দিন (DEFAULT_MAX_AGE_S) |
| `ci_green` | ✅ | check-runs API | candidate SHA-র কোনো check-run লাল নয় |
| `secret_scan` | ✅ | in-process regex | hardcoded secret-মুক্ত |
| `release_freeze_git` | ✅ | git status | tree clean @ candidate SHA |
| `rollback_target` | — | deploy-train.yml N-1 run | ফিরে যাওয়ার টার্গেট বিদ্যমান? |
| `py_compile` / `ruff_lint` / `yaml_valid` / `gate_tests` | — | in-process | code-quality স্বাস্থ্য |

## Verdict নিয়ম (deterministic — `compute_verdict`)

- **NO-GO** — যেকোনো `FAIL`; অথবা যেকোনো **critical** item `STALE`/`UNKNOWN`/`BLOCKED`
  (fail-closed: মিসিং প্রমাণ = অনুপস্থিত অনুমতি)।
- **CONDITIONAL** — কোনো `FAIL`/critical-gap নেই, কিন্তু non-critical item
  `STALE`/`UNKNOWN`/`BLOCKED` (documented gap সহ চলবে)।
- **GO** — সব critical `PASS`; বাকি সব `PASS`/`NA`।

## Fail-closed চুক্তি (#4167 Required Behavior)

1. মিসিং evidence → `UNKNOWN`, কখনো `PASS` infer হয় না।
2. `evidence_sha != candidate_sha` → `STALE` — ভিন্ন commit-এর প্রমাণে candidate
   certify হয় না।
3. `checked_at` মিসিং → `UNKNOWN` (timestamp ছাড়া প্রমাণ প্রমাণ নয়)।
4. evidence-এর বয়স > `max_age_s` → `STALE`।
5. প্রতিটি item বহন করে: `checked_at` + `source` (+ `evidence_sha` যেখানে প্রযোজ্য)।

## Blocker vs backlog (#4167)

- **P0 open** → `release_blockers` — সত্যিক release blocker।
- **P1 open** → `operational_backlog` — tracked backlog; GO-র পথে বাধা নয়
  (বিস্তারিত ফাইন্ডিং deep-audit issues-এই থাকে; এই gate শুধু aggregation layer)।

## Contract tests

```bash
python -m pytest tests/test_production_certification_gate.py -q --no-cov
```

কভার করে (issue-র Verification চুক্তি): stale evidence, missing evidence,
SHA mismatch, successful certification + FAIL/non-critical-UNKNOWN ladder।

## পরিচিত সীমাবদ্ধতা (honest UNKNOWN)

- Render health-check, DB-migration state, provider/credential health, post-deploy
  smoke — এখনো wired উৎস নেই; এগুলো non-critical `UNKNOWN` হিসেবে রিপোর্ট হয়
  (CONDITIONAL verdict)। wire করতে হলে `generate_report()`-এ নতুন collector যোগ করে
  `CRITICAL_ITEMS`/critical flag আপডেট করতে হবে + contract test।

## Related Documents

- [docs/INDEX.md](./INDEX.md) — ব্রড ডকুমেন্টেশন ইনডেক্স
- [AGENT_RULES.md](../AGENT_RULES.md) — verification চুক্তি (§9)
- [scripts/_INDEX.md](../scripts/_INDEX.md) — script SSOT
