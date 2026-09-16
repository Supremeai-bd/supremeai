# SupremeAI · Mission Control

> Governed operator console for the SupremeAI autonomous task-execution platform.
> Zero Cost · Fast & Lightweight · Intelligent · Easy · Secure · Dynamic by Design.

A Next.js 16 (App Router, TypeScript 5, Tailwind 4, shadcn/ui) console that plugs straight into the **central MCP Control Tower** (`supremeai-mcp-tower`) and gives admins and customers one calm surface over the whole machine.

## What it does

| Panel | Capability |
|---|---|
| **Dashboard** | Live Quick System Matrix (18 provider services), tower latency/version, KPI rail, activity stream, tower wake button (Render free-tier cold starts) |
| **Tower Explorer** | Browse + invoke all **106 governed MCP tools** (system, health, memory, github, render, autonomy, tenants, AI pools…) through a JSON-args runner with result viewer |
| **Git Sync Center** | Standing directive automated: every open PR is checked against `main` for conflicts & behind-count; clean stale PRs are auto-synced (merge `main` → PR branch); every check is durably logged in the **Sync Ledger** |
| **Brain & Memory** | Long-term memory (facts / decisions / lessons / insights / sync) with search, pin, tags — memory that compounds |
| **Autonomy** | Tower autonomy status, enable / kill-switch (with confirm), pending Human-In-The-Loop approvals |
| **Settings** | Dynamic config (tower URL, key rotation, repo, auto-wake, auto-sync, refresh interval) — DB-backed, no code changes needed |

## Architecture

```
Next.js 16 console ──► /api/tower/* ──► MCP Streamable HTTP (/mcp, JSON-RPC)
        │                  │                    │
        │                  ├─ session cache + auto-wake (Render sleep) + retry
        │                  └─ in-memory response cache (zero-cost reads)
        │
        ├──► /api/git/* ──► GitHub REST (PRs, compare, merges) → SQLite ledger
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

## Status

- Frontend-first build, lint-clean, E2E-verified via agent-browser (desktop + mobile, sticky footer, tool invocation, memory write, git sweep).
- All data from the live central tower: `17/18 services available`, 106 tools discovered.
