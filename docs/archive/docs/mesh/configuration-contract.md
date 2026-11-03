# Mesh Node — Configuration & Endpoint Contract

> Status: canonical · Established by #2255 (Phase-0 of
> `docs/audit_reports/full-architecture-audit-2026-09-27/FULL_ARCHITECTURE_AUDIT_BN.md`)

## 1. Who hosts what (today)

| Capability | Hosted by | Endpoint(s) | Notes |
|---|---|---|---|
| Node heartbeat / presence / lease | **SupremeAI backend** — `backend/api/routes/mesh.py`, router `prefix="/api/v1/nodes"` (mounted with registry prefix `""`) | `POST /api/v1/nodes/heartbeat` | Registers presence + grants/refreshes a 10-min lease; response carries `assigned_tasks` |
| Node list / detail / role patch | **SupremeAI backend** (same router) | `GET /api/v1/nodes`, `GET /api/v1/nodes/{node_id}`, `PATCH /api/v1/nodes/{node_id}` | MESH-2 dashboard consumers |
| Tower-native task queue | **SupremeAI backend** — `backend/api/routes/mesh_tasks.py` | `POST /api/v1/tasks/*` | CAS claim + lease + zombie reap (`backend/core/task_router.py`) |
| MCP tools (policy, registry, audit, …) | **MCP Control Tower** — `infrastructure/mcp-control-plane/` | MCP protocol only: stdio, `POST /mcp` (streamable HTTP), SSE | Tower is **not** a REST API; it hosts **no** node REST routes and **no** `/ws/node` |
| Node task WebSocket (`/ws/node`) | **Nothing yet** | — | Planned channel. The daemon treats an empty `tower_ws_url` as *heartbeat-only mode*; today task assignment rides the heartbeat response (`assigned_tasks`) |

## 2. `config.yaml` keys (as implemented by `client/supreme-node/daemon.py`)

| Key | Meaning | Contract |
|---|---|---|
| `backend_url` | **Canonical** control-plane base URL — the SupremeAI **backend** API (hosts `/api/v1/nodes/*`, `/api/v1/tasks/*`). Pointing this at the MCP Tower 404s every heartbeat: the Tower serves MCP protocol only. | `${VAR}`/`$VAR` env references are expanded by `load_config` |
| `tower_url` | **Legacy alias** for `backend_url`. Still accepted with a warning so already-deployed configs keep working; `load_config` derives `backend_url` from it. | Do not use in new configs |
| `heartbeat_path` | Path appended to the base URL for the heartbeat POST. | Default `"/api/v1/nodes/heartbeat"` (matches the backend router) |
| `tower_ws_url` | WebSocket URL for the (planned) push channel. | **Empty string = disabled** → heartbeat-only mode; the run loop skips `connect()` and `listen_for_tasks()` entirely |
| `tower_auth_token` | Optional bearer token. | `TOWER_AUTH_TOKEN` env var overrides |

Fail-fast rule: if neither `backend_url` nor `tower_url` yields a non-empty URL, `load_config` raises `ConfigError` — a daemon never builds a garbage URL.

## 3. Heartbeat contract (MESH-1, #939)

Request body (`POST {backend_url}/api/v1/nodes/heartbeat`):

```json
{
  "node_id": "pc-1-dev-rig",
  "node_type": "local_pc",
  "role": "coder",
  "capabilities": ["file_edit", "pytest", "git_push", "bash"],
  "timestamp": "<iso8601>",
  "load": {"cpu": 0.0, "mem": 0.0, "active_tasks": 0}
}
```

Response (`HeartbeatResult`):

```json
{
  "status": "ok",
  "lease_active": true,
  "lease_expires_at": "<iso8601>",
  "assigned_tasks": []
}
```

Semantics:

- Every heartbeat registers presence and **grants/refreshes a 10-minute lease** (`backend/core/presence_registry.py`).
- An expired lease marks the record `lease_active=false`; the record is not removed.
- `assigned_tasks` carries any tasks dispatched to this node — execute locally, report results per the MESH-3 daemon contract.

## 4. Change discipline

The mesh node contract lives in exactly three synchronized places: this document, `client/supreme-node/config.yaml`, and the `daemon.py` defaults — plus the tests in `client/supreme-node/tests/` that pin them. If the mesh control plane ever moves (e.g., the Tower grows node REST routes or the `/ws/node` channel ships), update **all of them in the same PR**. This issue (#2255) exists because the template, the daemon default, the tests, and reality disagreed.
