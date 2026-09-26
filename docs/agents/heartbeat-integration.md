# Agent Heartbeat Integration Guide

> **Issue:** [#1402 — feat(agents): instrument all agent tools to POST heartbeat → real-time online status](https://github.com/SaifulHaqueNiloy/supremeai/issues/1402)
> **Related:** AGENT_SLOT_REGISTRY.yaml (source of truth for slot assignments — read it at run time, never hardcode a slot map), OPS-06 §5, #1411 (slot-map drift fix)

Every agent slot can now report **real-time liveness** while its tool is
actually running. The dashboard (`/api/agents` on the Z.ai preview) merges
two sources:

| State | Meaning | Source |
|---|---|---|
| 🟢 **online** | heartbeat written within 90s | runtime signal (this guide) |
| 🟡 **stale** | heartbeat 90–300s old | runtime signal (tool idle or degraded) |
| 🔵 **assigned** | slot allocated in `AGENT_SLOT_REGISTRY.yaml`, no live heartbeat | policy |
| ⚪ **standby** | slot inactive (`active: false`) | policy |

## The contract

All writers produce the same Redis record (TTL 300s):

```
Key    supremeai:agent-heartbeat:agent-N
Value  {"slot":"agent-N","agentId":"Tool Name","source":"mcp-tower|backend|dashboard|cli",
        "clientId":"optional-audit-id","updatedAtMs":1758857500000,"updatedAt":"…Z"}
TTL    300 seconds   (a missed ping does NOT immediately drop the slot)
```

Readers derive the state from `updatedAtMs`: **≤90s → online**, **90–300s →
stale**, **key gone → assigned/standby**.

### Multi-account failover (important)

The canonical Upstash PRIMARY repeatedly hits its 500k/day command ceiling.
Every heartbeat writer therefore walks the account chain
**primary → secondary → tertiary → quaternary → quinary** until one accepts
the write, and readers **merge across accounts keeping the freshest record
per slot**. Configure any subset of:

```
UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN                 # primary
UPSTASH_REDIS_SECONDARY_REST_URL / UPSTASH_REDIS_SECONDARY_REST_TOKEN
UPSTASH_REDIS_TERTIARY_REST_URL / UPSTASH_REDIS_TERTIARY_REST_TOKEN
UPSTASH_REDIS_QUATERNARY_REST_URL / UPSTASH_REDIS_QUATERNARY_REST_TOKEN
UPSTASH_REDIS_QUINARY_REST_URL / UPSTASH_REDIS_QUINARY_REST_TOKEN
```

## Three ways to ping

### 1. MCP tool (recommended for MCP-connected tools — zero setup)

The control tower (`$MCP_TOWER_URL` — set via Infisical/env, see vault) exposes:

- **`agent_heartbeat`** — args: `slot` (required, `agent-N`), `agentId`
  (optional label). Ping it every 45s while your session runs.
- **`agent_status`** — lists all live heartbeats with derived state.

```jsonc
// tools/call
{ "name": "agent_heartbeat", "arguments": { "slot": "agent-4", "agentId": "Cline" } }
```

### 2. Universal pinger scripts (for tools that can run a subprocess)

```bash
# Loop while the tool runs (45s cadence):
python3 scripts/agents/heartbeat_ping.py --slot agent-1 --agent-id Antigravity

# Single ping (cron / CI / session-start hook):
python3 scripts/agents/heartbeat_ping.py --slot agent-8 --agent-id Aider --once

# Shell-only environments (curl + python3):
scripts/agents/heartbeat_ping.sh agent-1 Antigravity      # loop
scripts/agents/heartbeat_ping.sh agent-8 Aider once       # single ping

# Already MCP-connected but no Redis creds? Ping via the tower:
python3 scripts/agents/heartbeat_ping.py --slot agent-2 --agent-id "Claude Code" \
    --mode mcp --once    # uses MCP_URL + MCP_API_KEY
```

### 3. Raw Upstash REST (single curl, for locked-down environments)

```bash
curl -X POST "$UPSTASH_REDIS_REST_URL" \
  -H "Authorization: Bearer $UPSTASH_REDIS_REST_TOKEN" \
  -H "Content-Type: application/json" \
  -d '["SET","supremeai:agent-heartbeat:agent-N","{\"slot\":\"agent-N\",\"agentId\":\"Tool\",\"source\":\"cli\",\"updatedAtMs":0,\"updatedAt\":\"…\"}","EX","300"]'
```

(Prefer the scripts — they build the payload and timestamps correctly.)

## Cadence & lifecycle rules

- **Ping every 45s** while the tool is running (`AGENT_HEARTBEAT_INTERVAL` for
  the backend loop; `--interval` / `HEARTBEAT_INTERVAL` for the scripts).
- Start pinging on session/tool start; stop when the tool exits.
- A stopped tool degrades 🟢→🟡 within 90s and 🔵 within 300s — automatic.
- **Only ping your own assigned slot** from `AGENT_SLOT_REGISTRY.yaml`. Pings
  are attributed with the authenticated MCP client id for auditability.

## Per-tool integration status

> ⚠️ **`AGENT_SLOT_REGISTRY.yaml` is the single source of truth.** The slot →
> tool map below mirrors the **2026-09-26 registry rewrite** (10 slots,
> active cap 10 — OPS-06 Safeguard 5). When the YAML changes, tools MUST
> re-read it instead of trusting this section (#1411: this section
> previously documented the retired Windsurf/Devin/Copilot/Aider map and
> hijackable slots).

| Slot | Tool (2026-09-26 registry) | Active | Integration path |
|---|---|---|---|
| agent-1 | Z.ai Code (sleep) | ❌ | none — inactive/sleep; do not ping |
| agent-5 | planner-and-issues | ✅ | `heartbeat_ping.py --slot agent-5 --agent-id planner-and-issues` loop, or tower `agent_heartbeat` |
| agent-6 | solver-a | ✅ | session-manager startup: pinger loop + 45s scheduler (cron/systemd timer) |
| agent-7 | solver-b | ✅ | same as agent-6 (parallel solver) |
| agent-8 | pr-verifier | ✅ | single `--once` ping per CI/verification run (GitHub Action or job wrapper) |
| agent-9 | Continue | ❌ standby | VSCode/JetBrains extension approach when activated |
| agent-10 | SupremeAI (super agent) ✅ IMPLEMENTED IN REPO | ✅ | `backend/core/agent_heartbeat.py` supervisor loop (45s), started in `backend/core/startup/agents.py`; kill switch `ENABLE_AGENT_HEARTBEAT=false`; interval `AGENT_HEARTBEAT_INTERVAL` |
| agent-11 | platform-agent ✅ ALREADY PINGING | ✅ | preview dashboard self-ping from `src/app/page.tsx → postHeartbeat()`; exposes `POST/GET /api/agents/heartbeat` + `GET /api/agents` |
| agent-12 | browser-tester + log watcher | ✅ | pinger loop alongside the test/watch session |

Legacy per-tool recipes (Claude Code SessionStart hook, VSCode extension
`setInterval` pattern, `.vsix` packaging) remain valid **techniques** for
whatever tool occupies a slot — see `tools/agent_heartbeat/` reference
clients and `scripts/agents/heartbeat_ping.*`.

## Dashboard endpoints (Z.ai preview)

```
POST /api/agents/heartbeat      {"slot":"agent-N","agentId":"Tool"}   → ping
GET  /api/agents/heartbeat      → live heartbeat records + state
GET  /api/agents                → full merged view (YAML policy × runtime)
```

The production state store is the shared Upstash chain — the dashboard and
the tower read the same records, so an MCP ping shows up in the dashboard
within one poll cycle.

## Testing

- Tower contract tests: `npm run test:heartbeat` (in
  `infrastructure/mcp-control-plane`, wired into `test:unit`) — slot
  validation, state derivation, key layout, chain assembly, fail-loud when
  Redis is unconfigured.
- Live check: call `agent_status` on the tower, or `curl GET /api/agents`
  on the dashboard.
