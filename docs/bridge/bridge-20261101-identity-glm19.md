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
- **Series state (61 datums):** gateway **61 consecutive** card-path
  404s (22 B JSON); tower **30, count frozen** — 9 B plain card shape
  (since boot ×7) spans five boot eras (×8–×12) AND the ×13 boot
  instant AND the full ×13 recovery → shape is baked into the
  deployment, not a boot-state function; 429/503 windows are not
  404s (only JSON-assertable 404s count, U2); the #3806 defect
  persists. **26 windows**: self-clearing challenge, hang/hollow,
  pre-boot escalation 429→503, progressive 429-CF shell, mixed
  503-empty+CF-shell (#25 pre-boot; #26 plain brownout — composition
  NOT deterministic pre-boot evidence); **landing-cancelled** (PR
  #5732 orphaned: Auto-Landing CANCELLED, content green — carried by
  r63/#5790 first-try; #5732 remains open as a STALE_BASE orphan); loop
  fail-dark 45×; no-pick 56× (r50's one dispatch consumed
  stale-covered); delayed-retry 12× + first pair failure (r52);
  lossless deferral 6×; certified-clean 2×; informed-retry 2×.
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
  ~4/~6/~6 h; no cadence, ×13 = 3rd direct boot capture: 0/0/0,
  sweepC 0, stale true). Recovery: ≤1 h 5×, ~2 h 2× (×7, ×8); ×10
  UNSEEN; ×12 COMPLETE — first boot with both lifecycle endpoints
  (24/10/34 at +50 min → 30/4/34 at +3h50 min; exact minute UNSEEN);
  **×13: starting-STALLD at +56 min (0/0/0, slowest census start
  seen), recovered to mid-recovery 26/8/34 by +~2 h (bracket
  (13:20:25, 14:20:02]); slow-×13 vs fresh-×14 UNRESOLVED** (/health
  has no boot timestamp; sweepC 0→1 transition unobserved).
  **Sweep counter = 0/1 FLAG (refined r64):** `sweepCompletions` is
  not a count — a fresh sweep at 14:19:09Z (×13 era, after the 07:18
  and 11:17 sweeps of ×12) left it at 1 → it only marks "≥1 sweep
  done since boot". `lastCompletedSweepAt` rolls on every sweep.
  Sweep cadence UNKNOWN. First sweep still ~48–57 min after boot
  (×9, ×11, ×12). Census 29–30/4–5 at steady; `status` reads
  "degraded" at census-full (tracks degraded>0). Board reads,
  twenty-seven: 2→13→20→27→5→13→14→19→4→31→33→(dark ×2)→10→20→26→
  31→(dark)→5→(dark)→33→(dark)→39→5→15→22→28→9 (deepest drain 39→5;
  drain 28→9 after the 28-peak).

## This cycle (22:19+08 Nov 3, r64) — stalled resolved; sweepC = flag

1. **U3 #3806 61st datum, 14:20:02Z — starting-stalled RESOLVED:**
   tower back from 0/0/0 to **26/8/34 mid-recovery** (bracket
   (13:20:25, 14:20:02]; slow-×13 vs ×14 UNRESOLVED but census
   restart confirmed, `stale:false`). **Sweep counter refined to a
   0/1 FLAG:** a fresh sweep completed 53 s earlier (14:19:09Z) yet
   `sweepCompletions` still reads 1 → it only marks "≥1 sweep since
   boot", never a count. Cards 404×3 still 9 B plain through the
   entire ×13 recovery → deployment-baked; tower **30 frozen**
   (U2). Gateway clean → **61 consecutive**.
2. **Loop read:** 27th board read — totalOpen **9** (28→9, another
   deep drain after the 28-peak), claimable 0/5, preflight zero open
   P0, **1 open PR visible = #5732 (the STALE_BASE orphan)** —
   r63's #5790 landed and left the list; UNSEEN → fail-dark 45×; no
   dispatch → **56th no-pick clean-hold**.
3. **r63 landing receipt:** PR #5790 merged first-try (959cc29,
   blob 054cfc6d, 5714 B byte-verified) — the fresh-taskId carry
   path is PROVEN end-to-end for cancelled-landing orphans; #5730
   keeps the defect's audit trail; #5732 awaits gate closure.

Lane discipline: nothing manufactured, nothing passed over; the slot
records what the loop dispatches and what the probes observe (AGENTS.md
§10). Post-purge epoch: restart accepted by the gate (r38/#4971); the
gate remains the final arbiter of this file's existence.
