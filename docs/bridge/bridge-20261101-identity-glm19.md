# GLM Agent 19 — Worklog (Job ID 486803)

> Post-purge restart (2026-11-01). The founder's doc purge (#4965,
> wave 1 of the Nov-1 slimming) removed every lane worklog, including
> this lane's 37-slot chain (r1–r37, PRs #3312–#4943). Nothing is
> restored verbatim; full history stays in git and the archive. This
> file restarts the small live slot per the standing hourly mandate
> ("keep worklog small, remove old worklog and keep only important
> part") — only the durable facts a fresh reader needs.

## Durable facts carried forward

- Identity: GLM Agent 19, Job ID 486803; zero-credential lane via the
  MCP tower; `mcp_call.py` session helper (session TTL self-heal).
  Probe targets always quoted from live artifacts, never memory
  (#3966): tower URL from AGENTS.md, canonical gateway from the README
  "Live Federation Services" table.
- **Standing U3 duty (#3806):** the tower's A2A card paths
  (`/.well-known/agent-card.json`, `/a2a`, legacy `/agent.json`) 404
  while the tower card's own `url` field declares the tower as the A2A
  endpoint. False-resolved once (merge-linked ≠ finding-resolved,
  #3955); owner re-open still pending. One probe pass per cycle, no
  hammering.
- **Purge survival:** the slot survived both purge waves under its
  original name (wave 2, #4984 + #4988 + #4995, spared docs/bridge/
  entirely); the pre-declared two-strike clause stood down at r40.
- **Series state (62 datums):** gateway **62 consecutive** card-path
  404s (22 B JSON); tower **31, count frozen** — 9 B plain card shape
  spans boot eras ×8–×15 (8 boots) plus both ×13 lifecycle phases and
  the full ×15 recovery → shape is baked into the deployment, not a
  boot-state function; 429/503 windows are not 404s (only
  JSON-assertable 404s count, U2); the #3806 defect persists. **26
  windows**: self-clearing challenge, hang/hollow, pre-boot escalation
  429→503, progressive 429-CF shell, mixed 503-empty+CF-shell (#25
  pre-boot; #26 plain brownout); **landing-cancelled** (PR #5732
  orphaned: Auto-Landing CANCELLED, content green, carried by
  r63/#5790 first-try; **#5730 exited the board** (glm11 r85
  all-ghost census: 19 ghosts, 0 legit) and #5732 is invisible to the
  tower PR-fallback (0 open PRs shown vs GitHub truth: open) — the
  defect's tower-side footprint is zero, GitHub-side alive); loop
  fail-dark 46× (incl. one full local tool-layer outage, the 23:19
  cycle: 9+ consecutive tool failures, zero observations); no-pick
  57×; delayed-retry 12× + pair failure 1×; deferral 6×;
  certified-clean 2×; informed-retry 2×.
- **Uncertain-submit protocol (proven 5×: #5042, #5059, #5126, r56,
  r58):** on any uncertain failure (5xx, governance MCP timeout) →
  ls-remote the taskId branch → if present, blob-verify → check
  whether the CI Guardian already landed it asynchronously → only
  retry if truly stranded; STALE_BASE on retry is a positive CAS
  proof (#2333). **Bridge idempotence (r63):** resubmit against an
  in-flight taskId → `bridge:idempotent-noop` → a cancelled-landing
  PR cannot be retriggered via its own taskId; recovery =
  fresh-taskId carry; CAS keeps the race safe (late landing =
  STALE_BASE).
- **Tower reboot pattern:** boots 16:19 / 19:19 / 22:19 / 23:19 /
  ~05:19Z / ~09:19Z / ~13:19Z / ~19:19Z Nov 2 / ~23:19–00:16Z /
  (06:26, 06:30:11] / (11:20:37, 12:24:19] Nov 3 (gaps 3/3/1/6/4/4/6/
  ~4/~6/~6 h; no cadence); **×14 bracket (14:20:02, 14:51] and ×15
  instant ~15:30:40Z — both LIVE-CAUGHT by glm29's sentry c144/c145**
  (cross-lane corroboration; gaps ~2–2.5 h, ~40–70 min). Recovery:
  ≤1 h 5×, ~2 h 2× (×7, ×8); ×10 UNSEEN; ×12 COMPLETE; **×13's
  starting-STALLD at +56 min was the OUTLIER — ×15 reached full census
  24/10/34 + a fresh sweep within ~50 min** (16:16:16Z sweep, 16:20:21Z
  census) → r64's slow-×13-vs-fresh-×14 question RESOLVED materially:
  subsequent boots recover at normal speed; ×13 was the slow one.
  **Sweep counter = 0/1 FLAG (confirmed 3rd time, ×15 era):**
  `sweepCompletions` never exceeds 1 across boots; the fresh 16:16:16Z
  sweep still reads 1 → it marks "≥1 sweep since boot", not a count;
  `lastCompletedSweepAt` rolls. Sweep cadence UNKNOWN. Census 24–30/
  4–10/34 at steady; `status` "degraded" tracks degraded>0. Board
  reads, twenty-eight: 2→13→20→27→5→13→14→19→4→31→33→(dark ×2)→10→
  20→26→31→(dark)→5→(dark)→33→(dark)→39→5→15→22→28→9→20.

## This cycle (00:19+08 Nov 4, r65) — ×13 stall = outlier; #5732 tower-invisible

1. **Fail-dark disclosure:** the 23:19+08 cycle was lost entirely to a
   local tool-layer outage (Bash/Write/Read dead, 9+ consecutive
   failures) — zero observations: no probe, no loop, no submit.
   Counters carried without evidence increments (U2); fail-dark +1.
2. **U3 #3806 62nd datum, 16:20:21Z:** tower /health **24/10/34 full
   census**, stale:false, fresh sweep 16:16:16Z — ≤~50 min after the
   ×15 boot ~15:30:40Z (glm29 c145, cross-lane) → **×13's +56-min
   stall confirmed the outlier**; cards 404×3 still 9 B plain through
   the ×14/×15 boots + recovery → tower **31 frozen**; gateway clean →
   **62 consecutive**.
3. **Loop read (28th):** board **20** rows (9→20 refill), claimable
   0/5, preflight zero open P0, **PR-fallback 0 open PRs visible — but
   GitHub truth has #5732 still open** (WebFetch; ~6 h orphaned) →
   tower PR-view divergence recorded, not certified (U2); #5730 exited
   via glm11 r85's all-ghost census. No dispatch → **57th no-pick
   clean-hold**.

Lane discipline: nothing manufactured, nothing passed over; the slot
records what the loop dispatches and what the probes observe (AGENTS.md
§10). Post-purge epoch: restart accepted by the gate (r38/#4971); the
gate remains the final arbiter of this file's existence.
