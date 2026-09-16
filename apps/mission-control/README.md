# SupremeAI · Mission Control

> Governed operator console for the SupremeAI autonomous task-execution platform.
> Zero Cost · Fast & Lightweight · Intelligent · Easy · Secure · Dynamic by Design.

A Next.js 16 (App Router, TypeScript 5, Tailwind 4, shadcn/ui) console that plugs straight into the **central MCP Control Tower** (`supremeai-mcp-tower`) and gives admins and customers one calm surface over the whole machine.

## What it does

| Panel | Capability |
|---|---|
| **Dashboard** | Live Quick System Matrix (18 provider services), tower latency/version, KPI rail, activity stream, tower wake button, **System Dependency Map** (lazy, from tower) |
| **Tower Explorer** | Browse + invoke all **106 governed MCP tools** (system, health, memory, github, render, autonomy, tenants, AI pools…) through a JSON-args runner with result viewer |
| **Git Sync Center** | Standing directive automated: every open PR is checked against `main` for conflicts & behind-count; clean stale PRs are auto-synced (merge `main` → PR branch); every check is durably logged in the **Sync Ledger**; live **CI Pipeline panel** (workflow runs per branch/SHA) |
| **Brain & Memory** | Long-term memory (facts / decisions / lessons / insights / sync) with search, pin, tags, **one-click mirror to the tower brain** (`memory_remember_fact`) |
| **Autonomy** | Tower autonomy status, enable / kill-switch (with confirm), pending Human-In-The-Loop approvals |
| **Settings** | Dynamic config (tower URL, key rotation, repo, auto-wake, auto-sync, refresh interval) — DB-backed, no code changes needed |
| **⌘K Palette** | Keyboard-first command center: navigate, wake tower, run sync sweep, force refresh, toggle theme, open PRs |

## Architecture

```
Next.js 16 console ──► /api/tower/* ──► MCP Streamable HTTP (/mcp, JSON-RPC)
        │                  │                    │
        │                  ├─ session cache + auto-wake (Render sleep) + retry
        │                  └─ in-memory response cache (zero-cost reads)
        │
        ├──► /api/git/* ──► GitHub REST (PRs, compare, merges, CI runs) → SQLite ledger
        └──► Prisma (SQLite) — brain & memory: snapshots, activity, memory notes,
             git-sync ledger, tool-call journal, dynamic settings
```

- **MCP client** (`src/lib/tower-client.ts`): handshake → `mcp-session-id` → tools/list / tools/call; auto-wakes sleeping Render instances via `/health` pings; never blocks on cold starts.
- **Git sweep** (`src/lib/github-client.ts`): `compare main...PR` for behind/ahead, `mergeable_state` for conflicts, `POST /merges` to sync clean stale branches.
- **Secrets**: server-side only (env or masked DB settings). Nothing touches the client bundle.

## Run it

```bash
bun install
bun run db:push        # Prisma → SQLite
bun run dev            # http://localhost:3000
```

`.env`:

```ini
DATABASE_URL=file:./db/custom.db
TOWER_URL=https://supremeai-mcp-tower.onrender.com
TOWER_ADMIN_KEY=<your-admin-key>
GITHUB_TOKEN=<token-with-repo-scope>
GITHUB_REPO=SaifulHaqueNiloy/supremeai
```

See `.env.example` for the full list.

## Changelog

### v2.1 — Honest Health: "not configured" is not "down"
- **Cloudflare false DOWN fixed**: the dashboard trusted `system_summary`, whose `available` flag only means "API key present in tower env" — Cloudflare (no `CLOUDFLARE_API_TOKEN`) rendered as DOWN with a red bar although the edge itself was never probed. The console now calls `system_health` (live provider-aware probes) first and merges registry rows only for services the health tool does not cover; registry availability no longer maps to healthy/down
- **`unconfigured` is a first-class state**: matrix rows whose API key is missing show honest gray "unknown · not configured on tower — <role>" (hover for the reason); a new **Unconfigured** filter chip appears only when such rows exist; watchdog ignores unknown rows (no false alerts, no false recoveries)
- **Uptime strips no longer paint fake DOWN bars**: `statusLevel` mapped unknown to 0 (down bucket); unknown is now "no data" — never-probed services show `gathering…` instead of a 0% trend
- **PR Watch is real**: the KPI counted git-sync LEDGER entries (showed "17" with zero actual PRs); it now fetches the real open-PR count from the GitHub API (60s in-process cache) and shows `—` + "GitHub token needed" when unconfigured
- **Tower probe fixes** (same PR): Upstash REST URL strips the TCP-only `:6379` port ("fetch failed" becomes a real ping), supabase auth-health sends the `apikey` header, Cloudflare gets a real `tokens/verify` probe (token present → healthy/degraded; absent → honest `unconfigured`), and `system_health` covers the whole registry with a `X healthy · Y degraded · Z unreachable · W unconfigured` summary
- Probe errors surface verbatim as hover tooltips on matrix status chips (e.g. "GitHub auth rejected — token missing, invalid or expired")
- Footer v2.1

### v2.0 — Real Data Everywhere: zero mocks, zero dead ends
- **Every integration now works with real data** — round audit found the console quietly running on cached fallbacks: `towerKey` and `githubToken` were missing from DB settings (env had neither), so the tower reported "unreachable", `git/status` 500'd, `git/ci` 502'd, and `tower/tools` returned "Tower not configured"
- **`git/status` crash fix**: when GitHub returns an error, `listOpenPRs()`/`listBranches()` passed the parsed error *object* (not an array) to `.map` → `raws.map is not a function` 500; now guarded with `Array.isArray`
- **`git/ci` token fix**: the route read `process.env.GITHUB_TOKEN` directly, ignoring the DB setting — now resolves through `getConfig()` (DB → env, Dynamic by Design) and returns an actionable "paste it in Settings" error when unconfigured
- **GitHub Token (PAT) is now configurable** in Settings → Control Tower & Repo (masked server-side, rotate-only, same pattern as the Tower Admin Key); `githubTokenMasked` added to the settings API
- **Settings draft type safety**: rotate-only secret fields are now part of the typed draft superset (`towerKey?` / `githubToken?`) — previously they only existed via a runtime spread with no type checking
- **Type-level fixes**: missing `RadioTower` lucide import (crashed service rows matching mcp/tower), missing `McpToolInfo` type import in tower-client, `TowerServiceRow.id` in the dashboard normalizer
- Companion tower fixes ship in the same PR: provider-aware `system.health` probes (render `/health` vs github API vs supabase auth-health vs Upstash REST ping — kills the false "1/8 healthy"), honest memory-sidecar error, regenerated capability matrix + restored root `MODULES_LIST.md` contract
- Footer v2.0

### v1.9 — Journal Deep-Linking, Watchdog Drill & Doc Extraction
- **Uptime → journal deep link**: every uptime-strip bucket in the service matrix is a button — click it to jump to the Operations Journal pre-filtered to that exact time window (violet custom-window chip, one click to clear); closes the observe→inspect loop
- **Journal time-window presets**: All / 1h / 6h / 24h chips next to the status filter; `GET /api/journal` accepts `sinceMin` + `untilMin` (minutes-ago bounds, also honored by CSV export)
- **Watchdog drill** (Settings): fires a clearly-labeled synthetic DOWN transition through the full alerting path — journal entry, activity stream, notify channel — without touching real statuses; bypasses cooldown, respects mute overrides, requires the watchdog armed; `POST /api/watchdog/drill`; events carry a violet **DRILL** badge in Watchdog History
- **Doc reader HTML extraction** (bug fix + upgrade): tower `docs_fetch` returns raw page HTML — the reader now strips scripts/styles/head/comments, converts headings/lists/links/tables to markdown, decodes entities, and renders proper typography (react-markdown) instead of HTML soup; **Raw source** toggle keeps the original payload; "excerpt — tower fetch cap" badge surfaces the tower's ~5KB truncation
- Footer v1.9

### v1.8 — Per-Provider Overrides & Inline Docs
- **Per-provider watchdog overrides** (Settings): mute noisy providers, or give each its own cooldown / notify channel — dynamic JSON setting (`watchdogOverrides`), validated + normalized server-side, prefix-aware matching (`cloudflare` covers `Cloudflare (DNS + Workers + Analytics)`); muted providers are skipped entirely (no journal, no broadcast)
- **Matrix mute indicator**: dashboard rows show an eye-off badge for providers muted via overrides
- **Inline doc reader** (Tower Explorer → Docs Sources): per-source "Read" button opens a dialog that fetches full page content via tower `docs_fetch` — skeleton loading, word count, copy-to-clipboard, original link; journaled (operator action)
- **Command palette**: keyboard-hints footer (↑↓ navigate · ↵ run · esc close) + new **Copy diagnostics to clipboard** action (tower health + fleet statuses + git snapshot as JSON)
- Footer v1.8

### v1.7 — Reliability History & Docs Registry
- **Watchdog History panel** (Autonomy tab): filterable reliability audit over every automated transition + notify attempt (kind filters: down / degraded / recovered / notify), per-provider summary chips with event counts (↓ down ≈ degraded ↑ recovered ✉ notifies) that double as provider filters, animated timeline, new `GET /api/watchdog/history` (local journal — tower-independent)
- **Notify channel test button** (Settings): send-and-see-result test via the selected channel, graceful tower-side error surfacing (journaled)
- **Docs Sources panel** (Tower Explorer): the tower's documentation registry via `docs_list`/`docs_search` — lazy, collapsed by default, category badges, relevance scores, external links
- **Matrix severity sort**: down services surface first (down → degraded → unknown → healthy, then name)
- **Dynamic-by-Design fix**: Tower Explorer search placeholder now reflects the live tool count instead of a hardcoded "106"
- Footer v1.7

### v1.6 — Service Watchdog & Operator Flow
- **Service-down watchdog** (server-side, zero-cost): every dashboard refresh compares fresh tower statuses against local ServiceSnapshot evidence and detects transitions (down / degraded / recovered) — journals an ActivityEvent with severity coloring, always auditable
- **Dynamic notify channel**: on actionable transitions the watchdog broadcasts via tower `notify_send_telegram`/`notify_send_discord` (Settings: none | telegram | discord) with per-provider **cooldown window** (0–240 min) to prevent alert storms; failed notifies are retried on the next transition and logged gracefully (tower asleep / chat id missing never break the dashboard)
- **Settings UI**: watchdog arm/disarm switch, notify channel select, cooldown input — all Dynamic-by-Design (no redeploy)
- **Command palette**: new "Export journal as CSV" and "Toggle service watchdog" actions
- **Journal drill-down**: click any tool in the "Most used · 24h" chart to filter the journal table by that tool
- **Watchdog status chip** in the Activity Stream header (armed / channel / off with tooltip)
- **Styling**: matrix rows tinted by status (red for down, amber for degraded — works in light + dark), philosophy cards hover lift, footer v1.6

### v1.5 — Journal Intelligence & HITL Approvals
- **HITL Approvals panel** (Journal tab): live `policy_list_pending` view with approve/reject via `policy_approve` (APPROVED/REJECTED), silent 60s polling (no journal spam), decisions ARE journaled for audit; collapses to a slim "policy engine clear" line when empty; defensive normalization of tower payload shapes
- **Journal CSV export**: one-click filtered export (max 5000 rows) from the Operations Journal
- **Journal retention** (dynamic setting): `journalRetentionDays` prunes ToolCallLog automatically (1–365 days, default 14) — configurable in Settings
- **Per-tool p95 latency**: global + per-tool 95th percentile in journal stats and top-tools chart (nearest-rank over 24h samples)
- **Uptime strip tooltips**: per-bucket UTC time ranges + status on the 6h reliability sparklines, with proper `role="img"` a11y labels and hover emphasis
- **Brain tower-memory chip upgrade**: online/down/unreachable states with engine's own `lastError` surfaced (real diagnostics beat counters) + inline refresh
- **Mobile overflow hardening**: fixed grid `min-width:auto` blowouts on Dashboard, Git Sync and Journal (PR titles now clip with `block truncate`; tables scroll inside cards); all 8 tabs verified at 390px


### v1.4 — Operations Journal & Reliability
- **Journal tab (new, 8th nav tab)**: every governed tool call, journaled locally — works even while the tower sleeps. 24h KPI rail (calls, success rate with tone thresholds, avg latency, top tool), status filter chips (All/Ok/Failed) + debounced tool-name search, zebra table with duration + relative time, click-any-row detail dialog (parsed response snippet + UTC timestamp), **Most Used · 24h** animated bar chart with failure marks and a failed-calls callout. Backed by new `GET /api/journal` (Prisma groupBy stats + filtered entries over the local `ToolCallLog`)
- **Uptime trend in the System Matrix**: new `Trend · 6h` column (hidden on mobile) renders per-service sparkline strips + uptime % badge from the local `ServiceSnapshot` reliability memory (new `GET /api/matrix/history`, 6h window bucketed into 16 slots, stale provider identities auto-dropped, fuzzy provider matching in the UI against tower payload shape drift)
- **Risk-aware tool invocation (HITL)**: Tower Explorer invoke dialog now classifies every tool — heuristic mutation detection surfaces an amber `mutating` badge vs green `read-only`. Mutating tools trigger an automatic `policy_preview` consult (silent governed call, defensively normalized: risk / decision / allowed badges) and gate the invoke button behind an "I understand" acknowledgment checkbox with destructive styling until acknowledged
- **Tower memory engine chip in Brain**: `memory_status` poll (silent, 5-min stale) shows online/offline pill with engine counters (entities/relations/facts/episodes/documents) and inline refresh
- **Styling/UX details**: tool cards denser on mobile (p-3) with the "click to invoke" hint always visible on touch devices, matrix table horizontally scrollable on small screens with tighter service-name truncation, per-tab document title for the Journal, command palette auto-gains the Journal entry, footer bumped to v1.4
- Verified in-browser: journal stats match API (66 calls / 89% / 175ms), failed-filter + detail dialog surface real tower diagnostics (e.g. `TELEGRAM_CHAT_ID not configured`), trend strips live (100% up / 0% for the down Cloudflare probe), risk gate blocks then releases on acknowledgment, mobile 390px + footer flush

### v1.3.1 — Render Fleet, tenant creation, alert broadcast (same PR, incremental)
- **Render Fleet panel** on Dashboard (lazy): live service inventory from `render_list_services` (account id from dynamic settings, default `render-primary`) — region / plan / branch / suspended badges, service + dashboard links, **Latest deploy dialog** (`render_get_logs` -> deploy id, status, commit, age, raw payload), **Trigger deploy** with governed confirm (risky actions surface as HITL pending requests)
- **Create tenant dialog** in Tenancy: name + owner email + type (admin/customer) + plan -> `tenant_create`, one-time admin-token reveal
- **Operator Alert - Test Broadcast** in Autonomy: Telegram/Discord test messages via `notify_send_telegram` / `notify_send_discord`, optional chat-id override; targets stay tower-side (never in the console)
- **Zero-hardcode fix #2**: `git/status` no longer hardcodes the console branch - watch branch comes from dynamic settings and the banner tracks the primary open PR branch automatically (`trackedBranch`)
- **Quiet polls**: background tenant/client polls now use a `silent` flag on the governed call proxy - no more activity-stream/telemetry spam from `client_list`/`tenant_list` errors while a tab is open
- **Styling/UX**: git banner shows skeletons while loading (no fallback flash), matrix zebra rows, KPI subtitles wrap on mobile (no more `...` truncation), tenancy empty-state copy updated
- Verified in-browser: Render Fleet (1 service live, deploy dialog surfaces real `update_failed` diagnostic), tenant dialog validation, notify panel (graceful `TELEGRAM_CHAT_ID not configured` tower error surfaced), tracked-branch banner, mobile 390px + footer flush

### v1.3 — Governance & Zero-Hardcode
- **Zero-hardcode compliance (CI policy fix)**: tower URL + admin key removed from source (`tower-client.ts`, `settings.ts`, footer, palette). Resolution is now fully dynamic: DB setting → `TOWER_URL` / `TOWER_ADMIN_KEY` env → graceful "not configured" state with operator guidance. Added `.env.example` (referenced since v1.0 — now actually present)
- **Tenancy & Clients tab** (new): multi-tenant governance over tower tools — tenant list with suspend/activate + admin-token rotation (one-time token reveal dialog), AI client registry with provider/role/protocol enrollment (`client_register`), inline role switching (viewer/agent/admin), approve pending clients, rotate client tokens, revoke with confirm; raw-payload inspector for operators
- **Knowledge Graph & Semantic Search** in Brain: interactive SVG graph from `memory_read_graph` (type-colored nodes sized by observations, hover highlights relations, click for entity detail), node search (`memory_search_nodes`), meaning-based search (`memory_search_semantic`) with similarity scores
- **AI Provider Pools** panel on Dashboard: lazy per-provider key counts from `ai_list_providers` (gemini/groq/openrouter/mistral) with health flags
- **System Matrix status filters**: one-click all/healthy/degraded/down chips with live counts
- **UX fixes**: Git Sync Center keeps previous data while refetching (no more `…` flash), sync ledger now reports `conflict-free` / `mergeability pending (CI running)` instead of raw `unknown`

### v1.2 — Tower memory sync
- **Pull from Tower**: import recent tower episodic memories (`memory_get_recent_episodes`) into the local brain as insights — the bridge now works **both ways**
- **Per-tab document titles** (browser history readability)

### v1.1 — Command Center
- **⌘K / `/` Command Palette**: navigate tabs, wake tower, run sync sweep, force refresh, toggle theme, open PRs — keyboard-first operation
- **CI Pipeline panel** in Git Sync Center: latest workflow runs with per-run status icons (in-progress / success / failure), branch + SHA + event, deep links to Actions
- **Memory → Tower bridge**: one-click mirror of any local memory into the platform brain via `memory_remember_fact`
- **System Dependency Map**: lazy-loaded adjacency view from tower `system_dependencies`
- **Dynamic refresh interval** honored from Settings (no code change needed)
- **Styling polish**: per-service icons in the System Matrix, live heartbeat shimmer on the tower pill, UTC clock + PR links in footer, dialog a11y (descriptions), row hover states

### v1.0 — initial console (merged via PR #371)
- Dashboard, Tower Explorer (106 tools), Git Sync Center + ledger, Brain & Memory, Autonomy, Settings
- MCP client with session cache, auto-wake, retries; Prisma brain schema

## Status

- Lint-clean, E2E-verified via agent-browser (desktop + mobile, sticky footer, tool invocation, memory write, git sweep, command palette, CI panel, tower memory bridge).
- Live tower telemetry: `17/18 services available`, 106 tools discovered.
- v1.3 E2E-verified: tenancy tables + register dialog, knowledge graph panel, semantic search (graceful tower-sidecar cold start), AI pools (4 pools/4 keys), matrix filters, dynamic footer host, mobile 390px.
