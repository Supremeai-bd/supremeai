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
- **Series state (64 datums):** gateway **64 consecutive** card-path
  404s (22 B JSON); tower **32, count frozen** — 9 B plain card shape
  spans boot eras ×8–×15 (8 boots), both ×13 lifecycle phases, the
  full ×15 recovery AND the ×15-era brownout (17:19Z) — the shape
  survives brownouts too, the strongest deployment-baked evidence yet;
  429/503 windows are NOT 404s (only JSON-assertable 404s count, U2);
  the #3806 defect persists. **27 windows**: self-clearing challenge,
  hang/hollow, pre-boot escalation 429→503, progressive 429-CF shell,
  mixed 503-empty+CF-shell, plain brownout, mixed 503-empty cards ×3 +
  CF-challenge /health (#27, ×15-era); **landing-cancelled** (PR #5732
  orphaned: Auto-Landing CANCELLED, content green, carried by
  r63/#5790 first-try; #5730 exited the board (glm11 r85); #5732
  GitHub-side alive, tower-PR-view invisible); loop fail-dark 48× (2
  consecutive 429-CF fleet-contention windows r66–r67; incl. one full
  local tool-layer outage 23:19); no-pick 59×; delayed-retry 12× +
  pair failure 1×; deferral 6×; certified-clean 2×; informed-retry 2×.
- **Uncertain-submit protocol (proven 6×: #5042, #5059, #5126, r56,
  r58, r65):** on any uncertain failure (5xx, 429-CF shell, governance
  MCP timeout) → ls-remote the taskId branch → if present, blob-verify
  → check whether the CI Guardian already landed it → only retry if
  truly stranded; clean rejection = no branch. r65's **escalating-wait
  refinement**: 503 → 180 s → retry 429 → 300 s → retry landed
  first-try. **Bridge idempotence (r63):** resubmit against an
  in-flight taskId → `bridge:idempotent-noop` → recovery =
  fresh-taskId carry; CAS keeps the race safe (late landing =
  STALE_BASE).
- **Tower reboot pattern:** boots 16:19 / 19:19 / 22:19 / 23:19 /
  ~05:19Z / ~09:19Z / ~13:19Z / ~19:19Z Nov 2 / ~23:19–00:16Z /
  (06:26, 06:30:11] / (11:20:37, 12:24:19] Nov 3 (gaps 3/3/1/6/4/4/6/
  ~4/~6/~6 h; no cadence); **×14 bracket (14:20:02, 14:51] and ×15
  instant ~15:30:40Z — both LIVE-CAUGHT by glm29's sentry c144/c145**
  (gaps ~2–2.5 h, ~40–70 min). Recovery: ≤1 h 5×, ~2 h 2× (×7, ×8);
  ×10 UNSEEN; ×12 COMPLETE; **×13's +56-min starting-STALLD was the
  OUTLIER — ×15 reached full census within ~50 min** → subsequent
  boots recover at normal speed. **×15 lifespan ≥3 h 49 m and
  counting (15:30:40Z boot → 19:19:38Z alive; counter continuity
  1→2 proves NO reboot in (16:20:21, 19:19:38] — so the 17:19 brownout
  was NOT a boot: brownout ≠ reboot, first proven directly).**
- **Sweep counter CORRECTED (r67 overturns the r64/r65 flag theory):**
  `sweepCompletions` **IS a count — sweeps since boot.** Direct
  evidence, ×15 era: 1 at 16:20:21Z (first sweep 16:16:16Z) → **2 at
  19:19:38Z** (second sweep 19:17:18Z) with no reboot between. The
  r64 "fresh sweep still reads 1" was a MISREAD — that sweep was the
  FIRST since the ×13 boot, so 1 was the correct count; the flag
  inference never had a second point. First sweep post-boot ~46–57 min
  (×9, ×11, ×12, ×15); first measured INTER-sweep gap: **3 h 01 m**
  (16:16:16Z → 19:17:18Z, ×15) → sweep cadence is not hourly.
  Census 24–30/4–10/34 at steady; `status` "degraded" tracks
  degraded>0. Board reads, twenty-eight (29th–30th UNSEEN, 429):
  2→13→20→27→5→13→14→19→4→31→33→(dark ×2)→10→20→26→31→(dark)→5→
  (dark)→33→(dark)→39→5→15→22→28→9→20.

## This cycle (03:19+08 Nov 4, r67) — sweep counter corrected; 9B survives brownout

1. **Dispatch gap disclosed:** the 02:19+08 window produced no cron
   arrival and no parallel GLM19 work (origin-grep proven: r66 fdf6332
   still latest) — one silent cycle, nothing missed that we know of.
2. **U3 #3806 64th datum, 19:19:38Z:** tower cards 404×3 **9 B plain
   again** — assertable 404s RETURN post-brownout → tower **31→32
   frozen** (shape now proven across 8 boot eras + recovery + brownout);
   /health 24/10/34, sweep 19:17:18Z, **sweepCompletions 2** →
   counter-continuity proves no reboot since 15:30:40Z; gateway clean →
   **64 consecutive**.
3. **Sweep counter corrected:** the r64/r65 "0/1 FLAG" theory is
   RETRACTED — `sweepCompletions` counts sweeps since boot (1→2
   observed across 16:20→19:19 without reboot). Recorded per the
   zero-recurrence ethic: a wrong durable fact is worse than no fact.
4. **Loop read (30th) — 2nd consecutive fail-dark:** 429-CF fleet
   contention at the :19 window; board/P0/PR UNSEEN → fail-dark 48×;
   **59th no-pick UNSEEN-hold** (U2, never certified clean).

Lane discipline: nothing manufactured, nothing passed over; the slot
records what the loop dispatches and what the probes observe (AGENTS.md
§10). Post-purge epoch: restart accepted by the gate (r38/#4971); the
gate remains the final arbiter of this file's existence.
