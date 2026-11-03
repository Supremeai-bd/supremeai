# GLM Agent 09 — Worklog (post-purge restart, Job ID 486738)

> Continuation of `bridge-20261031-identity-glm09.md` (chain r12→r20, 9
> landings there: #4520→#4870; r1-r11 live in
> `bridge-20261030-identity-glm09.md`; last landing = 843a8d0/PR #4870),
> removed by the owner-side docs purge (Batch 1 of 5, refs #762). This
> file restarts the slot receipt at minimum size (r21 re-anchor). Total
> merged landings across both files: 20. Compressed durable facts:

- **Root-cause fixes shipped (r1-r12)**: parity reds (27 tests), tower
  tool-name drift, clock-coupled fixture bomb class, no-secret-logs FP
  class, shield whole-tree precision 58 FP→0, stale-branch pruner
  fail-open→fail-closed (#4470), ingress opener divergence lie (#4502),
  claim watchdog fail-closed + #57 TTL SSOT (#4516 — scripts/agents/
  claim_ttl_expirer.py SURVIVED the code purge, re-verified below).
- **Watch closed**: #4471 (pipeline.yml regen `|| true` defeating the
  index gate) class-killed upstream by 25604a3/#4612 `--check-committed`;
  verified locally rc=0 before the purge.
- **Brownout doctrine (c17-c19)**: 429 challenge = fleet cron-window
  contention, not tower-down; census-as-backoff; UNSEEN never certified
  (U2); the healthy rerun always yielded a REAL dispatch.
- **Census across eras**: pre-purge 2358/13/0 flat ×8 → lean era after
  owner prunes #4984/#4988/#4995: 62P/0F ×8 (c22-c28) → 67P/0F from
  c29 (+5 tests upstream, #5212 intake-pagination root-cause fix);
  scripts/ops/_INDEX.md 559→303 scripts, 6→2 hand sections.
- **Landed**: r21 re-anchor #5033 (c014fd9); r22 #5053 (9bcac54)
  brownout receipt; r23 #5072 (28f519b) first certified dispatch +
  zombie-PR escalation #5068 (stale PR #4872 → closed-unmerged,
  cross-confirmed glm04 r4 #5090, end-to-end resolved glm14 u5 #5094);
  r24 #5096 (f8cf5a6) payoff; r25 #5113 (b0541ff) refill no-pick;
  r26 #5124 (f26b0d1) brownout rerun, 6th flat; r27 #5138 (bb48b4b)
  brownout rerun, 7th flat; r28 #5159 (b57cf8d) first-try healthy
  no-pick, 8th flat; r29 #5246 (43f5fa5) full-coverage no-pick, census
  baseline 67P; r30 #5278 (3002f8c) record-board no-pick, 67P held;
  r31 #5309 (7c86eb3) post-mega-drain no-pick, flap self-resolved;
  r32 #5323 (d2d7647) wave-5 refill no-pick, back-to-back window;
  r33 #5354 (ac5f8e2) brownout-absorbed no-pick, 5th cycle on
  baseline; r34 #5379 (e58bd51) refill-band no-pick, 6th cycle on
  baseline; r35 #5420 (2dfea0f) post-drain no-pick, 7th cycle on
  baseline; r36 #5488 (05ab684) brownout-absorbed no-pick, 8th cycle
  on baseline; r37 #5524 (d1e3c2b) brownout-absorbed no-pick, 9th
  cycle on baseline; r38 #5576 (31578fb) drained-board no-pick, 10th
  cycle on baseline; r39 #5608 (552cd5d) refill no-pick, 11th cycle
  on baseline (dup no-op #5606 ad40449 disclosed & fixed in r40);
  r40 #5671 (1f3bd1f) dark-window no-pick (429×3, U2 held), 12th
  cycle on baseline; r41 #5681 (a6c5642) back-to-back
  first-try-healthy no-pick, 13th cycle on baseline; r42 #5703
  (9a937e6) heartbeat-brownout-absorbed no-pick, 14th cycle on
  baseline; r43 #5717 (bce3470) drain-bottom observation no-pick,
  15th cycle on baseline; r44 #5746 (374e426) refill-again no-pick,
  16th cycle on baseline; r45 #5762 (5a146f1) refill-holds no-pick,
  17th cycle on baseline.

## Cycle 46 (2026-11-03 21:09+08) — refill-3rd-window no-pick, 18th cycle on baseline

- 5th consecutive trigger (c42→c46). Heartbeat first-try; dispatch
  run 1 REAL read: board 26 rows (19→26 — refill leg's 3rd
  consecutive window, longest post-drain climb observed on this
  lane); run 2 tower 429 dark — run-1 read stands (U2 per-read,
  c43/c45 ruling). PR plane 1 open (UNSEEN per-PR). Claimable 0/5
  → no-pick.
- Upstream tower CODE landed this window (#5782 database-first PR
  diff intelligence) — first non-bridge HEAD seen in days; census
  re-run at the new tip anyway per freshness rule.
- Census: 67 passed / 0 failed / 12 subtests EXIT=0 @ 380b3c3
  (9.23s) — 18th consecutive cycle on the 67P baseline, holding
  across the upstream code landing. CI-gate rehearsal 5/5 PASS;
  standing watch: claim_ttl intact (TTL SSOT True=3h, OSError
  fail-closed True).

## Reflection Evidence

- **why:** the upstream tower-code landing (#5782) was the real
  test of the census baseline this window — intake planes (board,
  PR) are noisy by design, but a code change to the tower itself
  could plausibly shift test outcomes; re-running the full census
  at the new tip and holding 67P ×18 is what turns "baseline" from
  a habit into a measurement. Refill leg at 3 windows beats every
  prior post-drain climb — direction continues, falsifier still
  silent.
- **alternatives_rejected:** skipping the census re-run because
  the landing was "someone else's" code (freshness rule requires
  verification at the actual tip); citing 26 as a law parameter;
  racing the loop's 0/5 threshold; keeping the c45 section
  verbatim (folded per keep-small).

## Rollback

Docs-only in-place replace of the Cycle 46 section (baseSha recorded
at submission): revert of the landed r46 PR restores the r45 blob.
No code, test, or workflow surface touched this cycle.
