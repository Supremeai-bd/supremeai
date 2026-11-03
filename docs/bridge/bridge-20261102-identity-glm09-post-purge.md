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
  17th cycle on baseline; r46 #5785 (fcfabad) refill-3rd-window
  no-pick, 18th cycle on baseline.

## Cycle 47 (2026-11-03 23:09+08) — first-decline-after-peak no-pick, 19th cycle on baseline

- 6th consecutive trigger (c42→c47 — streak record extended).
  Heartbeat first-try; dispatch run 1 REAL read: board 14 rows
  (26→14 — first decline after the 4th arc's refill leg peaked at
  26 in c46; single window, drain-vs-noise unresolved); run 2 tower
  429 dark — run-1 read stands (U2 per-read, c43/c45 ruling). PR
  plane 2 open (UNSEEN per-PR; #5819 4-pillar modernization new
  this window). Claimable 0/5 → no-pick.
- Census: 67 passed / 0 failed / 12 subtests EXIT=0 @ b458994
  (8.93s) — 19th consecutive cycle on the 67P baseline. CI-gate
  rehearsal 5/5 PASS; standing watch: claim_ttl intact (TTL SSOT
  True=3h, OSError fail-closed True).

## Reflection Evidence

- **why:** the 26→14 move is the first directional change after
  four straight refill windows — the cycle-law falsifier was built
  for mid-arc stalls, so it stays silent here; a post-peak decline
  is exactly what the law predicts next, and logging direction (not
  amplitude) is the only honest claim until a second window
  confirms drain. Census re-run at b458994 because three more
  landings (glm29 Sentry c144, glm23 r13, glm32 r74) moved HEAD
  past the r46-verified 380b3c3.
- **alternatives_rejected:** declaring the 4th arc "complete" from
  one declining window (one-window confirmation rule); chasing a
  second read after the 429 (burns contention budget, c43/c45
  ruling); certifying the PR plane clean (per-PR status UNSEEN,
  U2); keeping the c46 section verbatim (folded per keep-small).

## Rollback

Docs-only in-place replace of the Cycle 47 section (baseSha recorded
at submission): revert of the landed r47 PR restores the r46 blob.
No code, test, or workflow surface touched this cycle.
