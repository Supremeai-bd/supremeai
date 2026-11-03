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
  c29 (+5 tests upstream, #5212 intake-pagination root-cause fix) →
  101P/0F from c48 (+34 guardian tests, #5878; new pytest.ini makes
  bare `pytest` the census SSOT) → 110P/0F from c49 (+9 tests,
  #5827 4-pillar + #5896 guardian AST indexer; pytest.ini now needs
  pytest-xdist — `-n auto --dist=loadscope`); scripts/ops/_INDEX.md
  559→303→312 scripts, 6→2 hand sections.
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
  no-pick, 18th cycle on baseline; r47 #5821 (19311d2)
  first-decline no-pick, async-recovered submit (infra EOF, landed
  without retry), 19th cycle on baseline; r48 #5886 (de2576b)
  drain-confirmed no-pick, census 101P first cycle (SSOT migrated
  67→101 via #5878), 20th cycle counting r21-r47 chain eras
  collectively.

## Cycle 49 (2026-11-04 04:09+08) — brownout-absorbed no-pick, census 110P first cycle (xdist era)

- 8th consecutive trigger (c42→c49 — streak record extended).
  Heartbeat 503 brownout → census-as-backoff; retry healthy after
  verification bundle built.
- Census first FAILED with pytest EXIT=4 (usage error:
  unrecognized `-n --dist=loadscope`) — root cause: #5827/#5896
  landed a pytest.ini that requires pytest-xdist, the sandbox env
  had drifted. Fix: installed pytest-xdist 3.8.0 (env matched to
  repo SSOT, no argument bypass). Census then: 110 passed / 0
  failed / 12 subtests EXIT=0 @ 19e09b1 (13.08s) — baseline
  101→110 (+9 tests, #5827 4-pillar + #5896 guardian AST indexer),
  first cycle on 110P and first under xdist parallel mode.
- Dispatch run 1 REAL read: board 6 rows (5→6 — first uptick after
  the confirmed drain; single window, refill not yet declared); PR
  plane 0 open (UNSEEN, U2); run 2 tower HEALTHY — second certified
  read, ACTION clean and healthy, claimable 0/5 → no-pick. CI-gate
  rehearsal 5/5 PASS; standing watch: claim_ttl intact (TTL SSOT
  True=3h, OSError fail-closed True).

## Reflection Evidence

- **why:** the pytest EXIT=4 was not a flake to retry blindly — it
  was environment dependency drift against the repo's own SSOT
  (pytest.ini gained xdist flags in #5827/#5896). The root-cause
  fix is to make the sandbox match the SSOT (install pytest-xdist),
  not to bypass flags or fall back to an old command — falling back
  would have hidden the 101→110 baseline migration entirely. The
  5→6 uptick is the direction the cycle law predicts after a
  confirmed drain; one-window rule keeps it an observation, not a
  refill declaration. Run 2 healthy gave this window two certified
  reads — first time since the streak began that no run went dark.
- **alternatives_rejected:** retrying census without diagnosing
  (masks the dependency drift); falling back to `pytest tests/` or
  stripping xdist flags (bypasses the SSOT, mislabels baseline);
  declaring the refill leg started (one-window rule); quoting 101P
  out of habit (honest number is 110P/first cycle).

## Rollback

Docs-only in-place replace of the Cycle 49 section (baseSha recorded
at submission): revert of the landed r49 PR restores the r48 blob.
No code, test, or workflow surface touched this cycle.
