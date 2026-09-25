# agent_heartbeat — keep-alive pingers for the agent status dashboard

Reference implementations for [issue #1402](https://github.com/SaifulHaqueNiloy/supremeai/issues/1402):
each agent tool POSTs its liveness to `POST /api/agents/heartbeat` so the
dashboard can show the 6-state lifecycle (`standby → assigned → connected →
idle ↔ working → stale`) in real time instead of guessing from the policy
registry alone.

| File | Purpose |
|---|---|
| `heartbeat.sh` | POSIX shell pinger (`loop` / `once` / `working <task>` / `stop`). curl → wget → python fallback chain. |
| `heartbeat.py` | Stdlib-only Python client. Library (`HeartbeatClient`) + same CLI modes. Background thread keeps a slot online. |
| `claude-code/heartbeat-hook.sh` | agent-2 (Claude Code) `SessionStart` hook: sends `connected`, starts the 45 s keep-alive in the background, pidfile-guarded (one session = one pinger). |
| `claude-code/settings-snippet.json` | `~/.claude/settings.json` fragment registering the hook + endpoint env vars. |

## Contract (what the endpoint accepts)

```json
POST /api/agents/heartbeat
Content-Type: application/json

{
  "slot": "agent-2",              // required, /^agent-\d+$/
  "agentId": "Claude Code",       // optional label
  "status": "working",            // connected | idle | working (default idle)
  "task": "migrating shim imports" // optional, only meaningful with status=working
}
```

TTL on the server is 300 s; the dashboard calls a slot `online` while the last
ping is < 90 s old. Ping every **45 s**.

## Configuration (all clients read the same env vars)

| Var | Meaning | Default |
|---|---|---|
| `HEARTBEAT_URL` | dashboard heartbeat endpoint | *(unset → scripts are safe no-ops)* |
| `AGENT_SLOT` | slot id | `agent-2` |
| `AGENT_ID` | tool label | `Unknown Tool` |
| `PING_INTERVAL` | keep-alive seconds | `45` |

## Quickstart

```bash
# background keep-alive for this slot
HEARTBEAT_URL=https://<dashboard-host>/api/agents/heartbeat ./heartbeat.sh &

# task transitions (from wrapper scripts / CI steps)
./heartbeat.py working "archiving shim batch 5"
./heartbeat.py stop
```

Fail-soft guarantee: every network failure is swallowed (exit 0, warning on
stderr). Heartbeat is observability — it must never break a tool's work.

## Where the endpoint lives today

- **Preview dashboard (agent-11):** `src/app/api/agents/heartbeat/route.ts` (Next.js API route, Upstash Redis backend, 5-account fallback chain).
- **Production (recommended):** add the same route to the MCP control tower so MCP-connected agents can ping without a new HTTP client — tracked in #1402.

Full per-tool integration guide: [`docs/agents/heartbeat-integration.md`](../../docs/agents/heartbeat-integration.md).
