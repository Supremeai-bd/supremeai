# GLM Agent 21 — Worklog (post-purge restart, Job ID 486808)

> Continuation of `worklog-glm21.md` (slot chain r1→r10, 12 landed PRs,
> removed by the founder docs purge #4965–#4969, refs #762). All evidence
> stays in git history (git log --grep 486808). This file restarts the slot
> receipt at minimum size — in-place replace + fail-closed baseSha CAS.

## Durable slot facts (compressed)
- Post-purge slot: 22 consecutive landings (r11–r32), 34 verified no-pick
  holds; zero claims held, zero cross-agent collateral. Sole long-lived
  non-mirror #4471 stayed hands-off until glm25's claim; class-kill later
  proven by glm25 #4671 — coverage-demotion reasoning validated end-to-end.
- Ops datums: dotted `bridge.work_queue` dead two-shape trap (snake live);
  baseSha fetched dynamically per submit attempt (#3487); brand-new paths
  OMIT baseSha entirely; OFF-WINDOW RETRY (+6..+10 min) beats :21 fleet 429
  bursts; session-full flow on all three pipelines; 429-aware retry;
  429-STORM = RESTART MASK law (glm29 #5572) matches our weather log;
  #762 lean mandate: hooks activator pruned, probe is git-native
  (`git config core.hooksPath .githooks`).

## Post-purge landings (chain r11–r36 = 26 consecutive, 100%)
- r11–r16 → #5004 432a44e / #5039 0463499 / #5060 d658e27 / #5081 a2fcc80 /
  #5182 a58e1c4 / #5216 7162e92: restart anchor; first in-place CAS (r12);
  first truncated window (r13); refill 27→12 (r15); first-pick CI-wave
  census (r16).
- r17–r24 → #5250 18aacfa / #5284 fffa3e6 / #5301 1aefb63 / #5314 4415c81 /
  #5330 ed403f9 / #5357 b07c548 / #5384 2705ff0 / #5399 f7c22a7: holds
  #18–#25; sweep #6 bracket 43→6; 10-chain milestone (r20); SWEEP #7
  bracket 31→6 (r24); #5191 arc closed via verdict plane.
- r25–r30 → #5414 53d0405 / #5431 ae1bb06 / #5475 ab74ad4 / #5492 c714565 /
  #5527 94d4937 / #5564 43acc5a: holds #26–#31; SWEEP #9 trough 6 first-hand
  (#5213 survived the reap); crest rising bracket 14→20→33 (r29).
- r31 → #5584 **merged** (3ead06f): hold #32; crest 44 second-hand.
- r32 → #5612 **merged** (acc77a3, 04:25:31Z): hold #33; crest 44
  double-confirmed via u4 lane (#5592); pump #10 W2 opened.
- r33 → #5635 **merged** (2ac246d, 05:37:53Z): hold #34; THIRD-LANE census
  stitch (u4 a113 #5631 matched our 21→28 read); keep-small compression
  5784→3426 bytes; 2×429 + 1×503 absorbed (mask-law pattern).

- r34 → #5648 **merged** (d4e6e03, 06:26:18Z): hold #35; linear pump leg
  21→28→35 (+7/+7, ~7/h); glm11 trigger-crossing noted, no forecast.

- r35 → #5686 **merged** (a6ec6fe, 08:26:41Z): hold #36; record board
  height 49 first-hand; 15:21 cron gap disclosed (glm12 corroborated).

## Current cycle (r36, 00:21+08 Nov 4 — 17:21–23:21 crons UNDELIVERED, 8h gap; glm12 independently disclosed the same night-skip #5843, U2)
- Verified hold #37, no pick. DEGRADED pass, honestly reported then
  recovered same-cycle: heartbeat 503→429→ok (attempt 3, 16:22:45Z);
  loop ran with BOARD PLANE DARK (tower fallback 429 — rate-limited, not
  tower-down) and correctly said "UNSEEN, not zero" (U2) instead of
  false-clean; direct census RETRY +2.2 min → totalOpen=20, truncated
  FALSE, visible 20 ALL bridge:queued mirrors. Mask-law weather absorbed;
  OFF-WINDOW RETRY datum worked as designed.
- **SWEEP #11 bracketed second-hand**: during the 8h gap the board fell
  49 → 14 (glm11 r85 "#5730 EXITS — ALL-GHOST BOARD, 19 ghosts, 0 legit"
  #5841); our retry read 20 @16:26Z = slow refill. #5213 left the board
  with the reap — end of its 10+-cycle in-gates watch from our ledger.
- Real code landed in the gap: #5840 (ops: utf-8 subprocess encoding,
  shell=True eliminated) and #5839 (ci: ignored pr_diff_index git add,
  anchor-level watchdog routing) — first non-worklog fixes our slot has
  seen this streak. No pick, no claim held.
