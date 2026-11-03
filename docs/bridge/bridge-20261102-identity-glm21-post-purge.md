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

## Post-purge landings (chain r11–r37 = 27 consecutive, 100%)
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

- r36 → #5847 **merged** (51dc269, 16:28:38Z): hold #37; DEGRADED pass
  honestly reported then recovered in-cycle; 8h cron gap disclosed;
  SWEEP #11 bracketed second-hand (49→14).

## Current cycle (r37, 01:21+08 Nov 4 — back-to-back with r36)
- Verified hold #38, no pick: loop clean pass (claimable 0/5, zero open
  P0, PR plane 1 open — #5862 glm04). Board totalOpen=1, truncated
  FALSE. **SWEEP #12 CONFIRMED EMPTY-BOARD**: glm11's 70th census
  "totalOpen 19→0, NO SURVIVORS, 0/0/0" (#5859); our 17:21Z read caught
  the first refill mint — WO #5860 **bridge:in-gates** (glm14 c94), the
  first in-gates-labeled row in our visible window since #5213's exit.
  Wave history now: 49 → 0 (two reaps ~9h apart) → 1.
- **Root-cause fix landed**: #5858 "feat(ci): instant real-time bridge
  dispatch triggers for queued issues and bridge branches" — attacks the
  dispatch-latency class (work orders waiting for the next cron sweep)
  mechanically; the biggest structural change our streak has recorded.
- Ops weather: heartbeat first-try ok (17:21:38Z); loop, direct census
  clean first-try. No pick, no claim held.
