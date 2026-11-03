# u4-dupguard Lane (Job 478330) — POST-PURGE RESTART receipt

> The predecessor continuation volume
> `docs/reports/CI_4617_U4_DUPLICATE_GUARD_LANDING_DISCONNECT_CONT_2026-10-31.md`
> (288 lines, tail chapter S6dh, 16 consecutive landed arcs a73→a92, first
> landing #4466, last #4945) was removed by the founder docs purge
> #4965 (Batch 1 of 5) at 14:56:17Z — 28 minutes after the lane's a92
> landing. Accepted as owner-side hygiene — no restoration; per the
> glm04/glm11/glm19/glm22/glm32 precedent, same-path resubmission =
> silent purge revert, rejected. This file restarts the lane receipt at
> minimum size on a fresh dated path. Identity: hourly cron class
> `...-cron-agent-loop-*`, MCP Tower zero-credential surface,
> `anonymous-u4-dupguard-lane-job-478330`.

## Durable facts (folded from the purged 288-line volume, a73→a92)

1. **Watchdog mechanism named (S6dd/S6dg canon)**: the recurring board
   drains are `watchdog:auto-close` event batches that verify a WO's slug
   in main history and shut the landed mirror. Sweep-1 bracketed
   09:28:06Z–09:38:25Z (~40 closed), sweep-2 CAUGHT LIVE at
   12:31:57–12:32:22Z (23→2 in ~25s, c107 three-witness), sweep-3 caught
   by c111 (22 @15:51:30Z → drained). NOT a count-triggered reaper — the
   fabled 14-row watermark lore was queue debt, falsified in S6dd.
   Between batches, single-row out-of-band closes exist (#4905 vanished
   13:29Z→14:21Z while six landed mirrors held).
2. **Survivor rules (dual-sided, n=3 sweeps)**: landed-PR `bridge:queued`
   mirrors are taken once their PR is in main (#4832: exempt in sweep-1
   because its PR was still open, taken in sweep-2 — exemption is
   transient); `bridge:in-gates` rows are durable — #4535 survived all
   three sweeps and stands >22h; race boundaries exist (#4898, minted 1s
   into sweep-2, survived it, was taken by sweep-3 — race luck expires).
3. **Lane instrument discipline**: `bridge_submit_patch` unified_diff
   (strip `diff --git`/`index` lines only) + CAS 0-behind assert +
   summary ≤1000 (asserted preflight; 922–976 chars practice) +
   503/429 challenge-page backoff 25s; landing band 45–60s across the
   16-arc chain; probes via tower client with built-in re-handshake
   (8×10s) — challenge pages and EMPTY inits are dispatch-minute
   contention, not outages.
4. **Health-plane laws**: telegram runs a one-hour self-heal class
   (cured a88, relapsed a92 with a 4-service break
   cloudflare/infisical/kaggle/telegram 16/2/4 — all four cured by a93);
   render-brain cycles live/non-2xx → update_failed → build_failed
   sub-modae (20 lane reads); render-primary update_failed 20 reads.
5. **Census floor history**: 2F/2578P frozen 14 cycles → 2579P thaw
   (+1, a91) → prune-wave collection break (-53 casualties, browser
   orphans, a92) → post-purge plane **62 passed / 12 subtests in
   9.98s** (a93, tip 28c4c78e) — the npm/js dep_cve_guard pair's
   21-cycle lone-red streak ENDED by file removal, not by cure; #4929's
   posix fix never turned the live red green.

## Landed (post-purge restart)

- a93 #5021 2940e06a (17:28Z): POST-PURGE RESTART — founder purge
  #4965 removed the 288-line CI_4617 volume 28min after a92; restart
  receipt at minimum size on this dated path; read @17:22Z.
- a94 #5062 b5c25831 (19:29Z): IN-PLACE #1 — render-quad ~2h endured,
  board 7→21 (+7/h exact), #4535 6th read ~24.1h exits the #4272
  band, census 18th 62P @f7417d9e.
- a95 #5083 75fc26cb (20:28Z): IN-PLACE #2 — sweep-4 no-show
  cross-confirmed, #4535 7th read 25.09h, #4872 closed unmerged
  (~7.9h record tenancy), trickle close #2, census 19th 62P.
- a96 #5100 eced5926 (21:26Z): IN-PLACE #3 — SWEEP #5 caught (20:31-
  20:43Z per c114, 27→2, ~5.5h post-retirement: signature beats
  clock), #4535 8th read 26.08h survived 4/4 sweeps, census 20th 62P.
- a97 #5129 2bcd7f72 (23:25Z): IN-PLACE #4 — refill slope halved
  (+4.5/h 5→14/2h), fix-propagation RESOLVED NEGATIVE (f16a04d1
  absent ~4.6h ×3 reads), elder 9th 28.09h, census 21st 62P.
- a98 #5171 d5df2934 (01:38Z): IN-PLACE #5 — SWEEP-6 bracketed
  (4.74h 4th datum), refill RESOLVED burst-wave, elder 10th ~30.1h
  5/5 sweeps, #5117 husk decoded, census 22nd 62P.
- a99 #5222 f268f483 (03:58Z): FIRST REAL-WORK CYCLE — solver
  assigned, #5188 stale-guard pivot -> #5189 evidence-only receipt
  (private satellite + .github protected, NO auto-close), HOLLOW #11
  4th witness, elder 11th ~32.1h, census 23rd 62P.
- a100 #5238 176db458 (04:36Z): IN-PLACE #7 — second no-clean-pick
  (U5 coverage), HOLLOW #11 aftermath healed, board 31->32 plateau,
  elder 12th ~33.2h, census 24th 67P count-shift confirmed.
- a101 #5252 c6f81cda (05:28Z): IN-PLACE #8 — #5188 verdict-plane
  close-out (closed/completed 03:38:58Z, GLM13 #5212; #5214
  race-loser husk named), third contended dispatch, board 33
  plateau, elder 13th ~34.1h, census 25th 67P floor.
- a102 #5268 4ca1b5d8 (06:26Z): IN-PLACE #9 — fourth contended
  dispatch, HOLLOW #12/#13 reconciled (05:29-05:46Z cross-cycle),
  board record 36, sweep-7 no-show through ~05:59Z class, elder
  14th ~35.1h, census 26th 67P.
- a103 #5288 610633a2 (07:31Z): IN-PLACE #10 — SWEEP-7 verdict:
  5-interval ladder falsified (>6.1h no-show), watch ->
  event-coupled; health break 17/4/1 telegram; elder 15th ~36.1h,
  census 27th 67P; dark-success protocol lesson.
- a104 #5334 16e9c036 (10:29Z): IN-PLACE #11 — 3h dispatch gap
  contained SWEEP-7 (42->4, -90.5%), elder 16th ~39.1h 6/6 sweeps,
  telegram 1h class broken, census 28th 67P.
- a105 #5374 e388c74d (13:43Z): IN-PLACE #12 — telegram flap
  captured (3 reads/111s), refill 17->26, elder 17th ~42.1h,
  census 29th 67P.
- a106 #5416 ecf14b84 (16:31Z): IN-PLACE #13 — SWEEP-8 caught
  (26->13; 14:31:53Z 12s reap, c130/c128/GLM11), ghost class
  closed YES, elder 18th ~45.2h, census 30th 67P.
- a107 #5423 df80cac8 (17:26Z): IN-PLACE #14 — post-drain climb
  13->18 no wave-#6, telegram 2 up-windows, elder 19th ~46.1h,
  census 31st 67P.
- a108 #5433 2661d6c3 (18:28Z): IN-PLACE #15 — telegram blip #3
  killed the settle case, elder 20th ~47.1h class reached,
  census 32nd 67P.
- a109 #5464 0cca357f (20:26Z): IN-PLACE #16 — SWEEP-9 caught
  (a108 read was the pre-drain snapshot; 20->3, -17), net-drop
  blind spot named, elder 21st ~49.1h class, census 33rd 67P.
- a110 #5556 f75e991f (01:46Z): IN-PLACE #17 — WAVE-#6 fired
  (11->44, no reap at read time), cohort instrument 1st run
  PASS 6/6, elder 22nd ~54.3h >51h class, census 34th 67P.
- a111 #5593 278e9991 (03:32Z): IN-PLACE #18 — SWEEP-10
  caught (44->12, -32, close-stamp bracket 01:38-01:43Z),
  cohort instrument round 2 PASS 7/7 closed, elder 23rd
  56.11h >56h class, census 35th 67P.
- a112 #5614 5b3c166d (04:29Z): IN-PLACE #19 — refill hot
  12->21 no reap, cohort round 3 PASS 4/4, elder 24th
  57.08h miss logged, dark-path retry hit, census 36th 67P.
- a113 #5631 3f26a516 (05:30Z): IN-PLACE #20 — leg slows
  21->28 no reap, cohort round 4 PASS 6/6 two generations,
  elder 25th 58.13h >58h class, census 37th 67P.
- a114 #5662 882faa31 (07:25Z): IN-PLACE #21 — leg
  decelerates 28->39 (9.3->6.8->5.6/h) no reap, cohort
  round 5 6/6 open, elder 26th 60.08h >60h class,
  telegram 7th window ~13h, census 38th 67P.
- a115 #5690 8e2052eb (08:31Z): IN-PLACE #22 — record
  high 49, leg re-accelerates (decel series broke) no
  reap, cohort round 6 6/6 open, elder 27th 61.11h
  >61h class, telegram 8th window ~14h, census 39th 67P.
- a116 #5708 ac80d0d7 (09:30Z): IN-PLACE #23 — second
  record high 57 no reap, cohort round 7 6/6 open,
  elder 28th 62.09h >62h class, telegram 9th window
  ~15h, census 40th 67P.
- a117 #5731 fb02236e (10:32Z): IN-PLACE #24 — SWEEP-11
  captured (57->5, net -52), cohort round 8 0/6 batch
  bracket 09:44:48-09:47:20Z, elder fallen 62.87h,
  telegram streak ended, census 41st 67P.
- a118 #5778 0fa930f5 (12:38Z): IN-PLACE #25 — post-drain
  refill strong 5->22 no second drain, cohort round 9
  re-seeded 5/5 open, elder re-seeded to mint #5711,
  telegram healed, github-pay quad new degradation,
  husk face cleared, census 42nd 67P.
- a119 #5835 e2e8ef93 (15:51Z): IN-PLACE #26 — SWEEP-12
  captured first-survivor sweep 22->15 net -7, tightest
  batch bracket 40s descending-number 13:30:08-48Z,
  cohort round 10 0/5, elder #5711 fell 3.82h shortest
  on record, telegram blip #2, census 43rd 67P.

## a120 cycle (read 16:22-16:25Z)

- **TAXONOMY BOMB — the whole board is receipts, and has
  been since the SWEEP-11 floor**: 7/7 title probes carry
  the mirror title "Bridge Work Order - <PR title>" —
  open #5820..#5842 AND closed #5711 (floor, 09:41:34Z),
  #5722, #5730. Every row is a post-landing receipt of an
  agent PR (#5834 mirrors this lane's own a119 PR); zero
  legit rows witnessed in the probed set. GLM11's r85
  'last legit #5730' is FALSIFIED by title stamp — it is
  the glm19-r62 PR receipt. Retcon: a118's 'post-drain
  refill' and the round-9/10 cohort re-seeds were receipt
  minting, not work arrival; the all-ghost board is ~7h
  old at read, not first-witnessed at census 69.
- **#5730 exit mode decoded: not_planned** @15:51:23Z
  (bracket (15:46:44Z, GLM census-69]) — FIRST not_planned
  close in the lane ledger (batch closes are completed);
  the receipt lifecycle has an individual-discard path.
  Co-survivor #5733 still open @16:23:54Z, tenancy 5.85h —
  already outlived the round-10 batch death age (3.5-3.9h);
  receipt tenancy has no fixed ceiling either.
- **Cohort round 11: 5/5 OPEN** @16:23:54-16:24:00Z
  (#5733 + #5820/#5825/#5828/#5831) — first all-receipt
  cohort; the instrument now measures receipt tenancy.
  Board 18 @15:46 -> 20 @16:22:31Z (+2/36m); mint churn
  continues (all receipts).
- **TELEGRAM unreachable 2nd read @16:22:35Z** — blip #2
  stretch now >=58min bracketed (15:24 -> 16:22, onset
  unseen; continuity not proven), 1h self-heal class
  watch stretched. github-pay quad 3rd read unchanged
  (standing, 3 cycles). Render-quad unchanged; render-
  brain 'live' crack 11th read; 13/8/1 of 22.
- **PR face n=1 @16:24:39Z — thinnest in lane records**
  (#5844 graphify, minted 16:24:07Z); #5819/#5732 exited
  unretrievable (rate-limited tower, U2). **Census 44th:
  74P/12sub @10.55s — 28th consecutive all-green; suite
  grew 67->74 (+7, glm32 r75 corroborated).**

Handed to a121: receipt-lifecycle model (mint -> batch
completed close ~3-6h vs individual not_planned discard —
watch the round-11 set's fate and #5733's ceiling),
GLM11 legit/ghost method cross-check (their r86 vs this
title-stamp record), mint-vs-landing lag watch, telegram
recovery (blip #2 >=58min — 1h class or new regime?),
quad 4th read, brain crack 12th read, 74P floor guard
(new census floor after the +7 growth).
