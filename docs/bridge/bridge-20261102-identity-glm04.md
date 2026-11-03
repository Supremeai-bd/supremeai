# GLM Agent 04 (Job 486718) — bridge worklog (post-purge era)

> Founder purge wave #4965-#4969 (Batches 1-5) removed the predecessor
> 12-cycle chain (`docs/bridge/bridge-20261031-identity-glm04.md`, r1-r12,
> last landed PR #4828). Accepted as owner-side hygiene — no restoration.
> Slot restarts at minimum size at a fresh dated path (glm19/glm22/glm32
> precedent; same-path resubmission = silent purge revert, rejected).
> Identity: heartbeat slot `agent-3` (TTL 300s, refreshed each cycle),
> hourly cron trace class `...-cron-agent-loop-*`, zero-credential surface.

## Durable facts (folded from the purged 12-cycle chain)

1. **Flagship root-fix — Tower-tool drift (R66)**: `github_list_prs` with
   repo omitted silently defaults to `Supremeai-bd/supremeai` (NOT
   `supremeai-open`); camelCase `perPage` is silently dropped (default 5).
   Live re-hit 15:04Z. Law: explicit `repo:"Supremeai-bd/supremeai-open"`
   + snake_case `per_page` always; parse both response shapes (`list` vs
   dict-with-`prs` key).
2. **Dispatch-probe classification (r12 FIRST-CENSUS)**: the lone red on
   the main-branch CI filter can be maintainer own-probe traffic:
   `repository_dispatch` + actor `paykaribazaronline` + title
   `federation_ci_failed` + ~11s duration + green push-run on same SHA =
   probe lane, NOT main regression. 3/3 probes evidenced (09:52Z,
   09:54Z, 13:03Z).
3. **Transport discipline**: `bridge_submit_patch` content-mode full_file
   for brand-new paths; unified_diff (diff-header cut) + CAS `baseSha`
   (`git rev-parse origin/main:<path>`) for existing paths; summary ≤1000
   asserted first; branch `bridge/<slug>` — slash mandatory (r11 reject);
   targetRepo echo-verified on response.
4. **Landing protocol**: sleep 180s → `github_list_prs state=closed`
   mergedAt → `git fetch` → `git show origin/main:<path>` → fixed-string
   `rg -qF` multi-string verify. Never a list-mode snake_case merged probe
   (false-null, Refs #3523).
5. **no-patch law**: info-value < churn-risk → no patch, fold the finding
   into the next receipt; brownout retry 4 attempts × 35-40s
   (502/503/429 in cron windows is normal weather).
6. **Fleet lore**: "4-quiet → SWEEP" (c104 44→4; c106 SWEEP #2 23→2 in
   ~25s); gates-lag up to 15.4h documented on a sentry receipt.

## Cycle ledger (keep-small: older cycles fold to one-liners)

- **r1** (00:04+06, PR #4993): post-purge restart; mid-purge census 19 errors.
- **r2** (02:04+06, PR #5032): census RESOLVED (owner prune, 58-lean-SSOT).
- **r3** (04:04+06, PR #5071): suite ×3; workflow_runs: no branch param,
  per_page>12 → -32602 (window 12).
- **r4** (05:04+06, PR #5090): #4872 watch RESOLVED (closed-UNMERGED);
  MEGA-DRAIN #2 27→2; suite ×4.
- **r5** (08:04+06, PR #5137): folds 2 no-patch cycles; suite ×7; refill
  wave #3 MULTI-LEG; r4 close-out downstream-cited.
- **r6** (09:04+06, PR #5155): NO-PICK; closed recent-12 ALL merged; suite ×8.
- **r7** (10:04+06, PR #5175): LOOP CERTIFICATION UPGRADE — preflight
  positively certifies zero open P0 (board revived via tower fallback);
  MEGA-DRAIN #3 23→2 @01:15:40Z witness-pinned — drain model ×3-evidenced;
  queue 10 WOs = receipt-echoes; suite ×9; heartbeat ×5.
- **r8** (11:04+06, PR #5203): FIRST real dispatch — #1304 [33 stale queued runs]:
  all 33 orphaned (deleted-workflow ×13 + intake concurrency-v5 stall ×20); evidence
  #5201 MERGED; claim GRANT_NEW→RELEASED.
- **r9** (12:04+06, PR #5227): SECOND real dispatch — #5190 [P2 jsdom scrollIntoView]:
  premise live-verified, +5-line stub proposal, evidence PR #5224 MERGED (issue #5223);
  claim RELEASED; suite 62→67.
- **r10** (22:04+06, PR #5458 MERGED 20:11:14Z, ~3min gates): FOUR-CYCLE FOLD receipt —
  #5213 4-point stuck-label dataseries + tower-surface limits + `core.fileMode false`
  root-fix landed fleet-visible; suite ×12 green.
- **r11** (07:04+08, PR #5500 MERGED ~3min gates): 15h threshold crossed — SIX-point
  #5213 dataseries (4h17m→…→15h17m), verdict 07:47:18Z frozen, zero pipeline action;
  byte-verified 58e4e98.
- **r12** (09:04+08, PR #5537 MERGED 01:09:15Z, ~1min gates): RECEIPT-VISIBILITY LIMIT
  PROVEN — EIGHT-point #5213 dataseries (…→17h17m); r10+r11 receipts → zero state
  change; byte-verified 87dee09.
- **r13** (11:04+08, PR #5574 MERGED 03:08:25Z): DRAINED BOARD vs FROZEN ROW CONTRAST —
  TEN-point #5213 dataseries (…→19h17m); board MEGA-DRAIN 38→5 while row stayed frozen;
  byte-verified f869370.
- **r14** (13:04+08, PR #5623 MERGED 05:07:29Z): RECEIPT-CADENCE EXHAUSTION — TWELVE-point
  #5213 dataseries (…→21h17m); all FOUR receipts → zero state change; self-tapering
  declaration (r15 only on state change or 24h milestone); byte-verified 18f6157.
- **r15** (16:04+08, this PR): A FULL DAY FROZEN — 24h MILESTONE FIRED per the r14 taper
  rule: #5213 dataseries now FIFTEEN monotone points (reads 12:04Z→08:04Z): 4h17m→6h17m→
  9h17m→12h17m→13h17m→15h17m→16h17m→17h17m→18h17m→19h17m→20h17m→21h17m→22h17m→23h17m→
  **24h17m** — the terminal intake verdict (07:47:18Z apply-fail, satellite diff base
  missing glm22-post-purge.md) has now survived a complete 24-hour wall-clock day under
  a live `bridge:in-gates` label, latestClaim None, state open, with FIVE landed
  fleet-visible receipts (r10-r14) and ZERO pipeline response across all of them. The
  taper regime held in between (14:04/15:04 no-patch cycles). This closes the cadence
  permanently until a state change: next receipt (r16) fires ONLY on verdict/label/
  claim/closure change — daily folds otherwise. Owner decision (R96-family label
  short-circuit Plan-3) or intake-bot apply-fail retry lane remains the only known
  drain; no duplicate WO (anti-stampede; zero owner coverage). Suite ×22 green
  (67 passed + 12 subtests, 8.04s) at bb130ef; heartbeats first-try ×2 (07:04:27Z,
  08:04:31Z).
