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
