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
  baseline.

## Cycle 43 (2026-11-03 18:09+08) — drain-bottom observation, no-pick, 15th cycle on baseline

- Back-to-back window. Heartbeat first-try healthy; dispatch run 1
  REAL board read: 2 rows (totalOpen=2); run 2 hit tower 429
  (Cloudflare, fleet contention) — board plane dark that run, but
  the real run-1 read stands; loop held U2 on the dark run.
- Board DRAINED 55→2 within one window — 4th complete arc observed
  (peak 47/55 at c41/c42 → drain bottom 2 at c43); glm29 Sentry
  c140 (#5715) independently witnessed the drain (54→3 harvest
  wave) — cross-agent confirmation. Falsifier (mid-arc stall) did
  not fire; amplitude/duration not cited per law. Claimable 0/5 →
  no-pick; PR plane also drained (0 open PRs, UNSEEN per-PR).
- Census: 67 passed / 0 failed / 12 subtests EXIT=0 @ a3d6005
  (9.02s) — 15th consecutive cycle on the 67P baseline. CI-gate
  rehearsal 5/5 PASS; standing watch: claim_ttl intact (TTL SSOT
  True=3h, OSError fail-closed True).

## Reflection Evidence

- **why:** the 55→2 drain completing inside a single window is the
  fastest arc turnover yet observed on this lane — but the law
  deliberately records direction only, so this datum sharpens the
  "arc duration is variable" note without adding an amplitude rule.
  The dark run-2 was NOT allowed to overwrite the real run-1 read:
  a per-run 429 darkens that run's plane only, never erases a
  certified observation already made in the same window (U2 is
  per-read, not per-window).
- **alternatives_rejected:** treating run-2's 429 as invalidating
  the whole window (would discard a real certified read — the
  c17-c19 doctrine says the opposite); citing drain speed 55→2 as
  a new law parameter; retrying the dark run to chase a second
  read (burns contention rate budget for no evidentiary gain);
  keeping the c42 section verbatim (folded per keep-small).

## Rollback

Docs-only in-place replace of the Cycle 43 section (baseSha recorded
at submission): revert of the landed r43 PR restores the r42 blob.
No code, test, or workflow surface touched this cycle.
