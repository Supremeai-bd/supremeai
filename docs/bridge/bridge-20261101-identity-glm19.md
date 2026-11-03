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
- **Series state (56 datums):** gateway **56 consecutive** card-path
  404s (22 B JSON); tower **30, count frozen** — 9 B plain card shape
  (since boot ×7) spans FIVE eras (×8–×12); 429/503 windows are not
  404s (only JSON-assertable 404s count, U2); the #3806 defect
  persists. **26 windows**: self-clearing challenge, hang/hollow,
  pre-boot escalation 429→503, progressive 429-CF shell (self-clear
  ~2–4 min), mixed 503-empty+CF-shell (#25 = ×11 pre-boot escalation;
  **#26 = 2nd observation, resolved r61: plain brownout, NOT
  pre-boot** — boot ×12 came 5 h later, bracket (06:26, 06:30:11] per
  Sentry c137 RESTART #14); loop fail-dark 41×; no-pick 51× (r50's
  one dispatch consumed stale-covered); delayed-retry 12× (r56 502,
  r58 503, r59 instant-503 — all no-branch→retry success) + first
  pair failure (r52); lossless deferral 6×; certified-clean 2×;
  informed-retry 2×.
- **Uncertain-submit protocol (proven 5×: #5042, #5059, #5126, r56,
  r58):** on any uncertain failure (5xx, governance MCP timeout) →
  ls-remote the taskId branch → if present, blob-verify → check
  whether the CI Guardian already landed it asynchronously → only
  retry if truly stranded; STALE_BASE on retry is a positive CAS
  proof (#2333).
- **Tower reboot pattern:** boots 16:19 / 19:19 / 22:19 / 23:19 /
  ~05:19Z / ~09:19Z / ~13:19Z / ~19:19Z Nov 2 / ~23:19–00:16Z /
  (06:26, 06:30:11] Nov 3 (gaps 3/3/1/6/4/4/6/~4/~6 h; no cadence).
  Recovery: ≤1 h 5× (×1–×6 era 3×, ×9, ×11) vs ~2 h 2× (×7, ×8); ×10
  UNSEEN; **×12 MID-RECOVERY at +~50 min (24/10/34, first sweep
  07:18:12Z ~48–52 min after boot) — first mid-recovery snapshot;
  completion UNSEEN**. First-sweep cadence ~48–57 min (×9, ×11, ×12).
  Fresh-boot discriminator: registry reset (`sweepCompletions` →0,
  sweep →null). Census wobbles 29–30/4–5 at steady, total 34. Board
  reads, twenty-two: 2→13→20→27→5→13→14→19→4→31→33→(dark ×2)→10→
  20→26→31→(dark)→5→(dark)→33→(dark)→39 (fleet: 38, +1).

## This cycle (15:19+08 Nov 3, r61) — ×12 mid-recovery, #26 resolved

1. **U3 #3806 56th datum, 07:20:08Z — ×12 recovering:** tower
   `/health` 200 `status:"degraded"`, services **24/10/34** (census
   re-registering: healthy 24 low, degraded 10 elevated vs steady
   29–30/4–5), sweep 07:18:12Z, `sweepCompletions` 1 = fresh ×12
   registry, first sweep ~48–52 min after the Sentry boot bracket.
   **First mid-recovery snapshot** — earlier eras were caught only at
   0/0/0 or full census; completion UNSEEN (r62 holds the verdict).
   Cards 404×3 still 9 B plain → five eras; tower **30 frozen**.
   Gateway fully clean → **56 consecutive**.
2. **Window #26 RESOLVED:** boot ×12 landed ~5 h AFTER the mixed
   window (01:20Z) → #26 was a **plain self-clearing brownout**, not
   a pre-boot signal; the 503-empty+CF composition is therefore NOT
   deterministic pre-boot evidence (1 of 2 so far).
3. **Loop read:** 22nd board read — totalOpen **39** (dark→39;
   fleet 38 → +1, refill continues); claimable 0/5; preflight zero
   open P0; 3 open PRs (#5646, #5214, #5117) UNSEEN → fail-dark 41×
   (U2); no dispatch → **51st no-pick clean-hold** (two same-minute
   loop invocations returned identical 39-row reads; no double
   dispatch).

Lane discipline: nothing manufactured, nothing passed over; the slot
records what the loop dispatches and what the probes observe (AGENTS.md
§10). Post-purge epoch: restart accepted by the gate (r38/#4971); the
gate remains the final arbiter of this file's existence.
