# SupremeAI Mesh Node Daemon — `supreme-node`

> **MESH-3 (issue #941) — Phase A** — local daemon that connects PC-1 (Dev Rig) & PC-2 (Headless Tester) to the SupremeAI MCP Tower over WebSocket, sends periodic heartbeats, receives task assignments, executes them locally (bash / pytest / ollama / git), and posts results back.

---

## 📐 Architecture (1-minute overview)

```
 ┌────────────┐   WebSocket (wss)     ┌──────────────────────┐
 │  PC-1      │ ◄──────────────────► │   MCP Tower          │
 │  Dev Rig   │   60s heartbeat POST  │   (Render)           │
 │  (coder)   │   task dispatch       │   /api/v1/nodes/*    │
 └────────────┘                       └──────────────────────┘
                                              ▲
 ┌────────────┐   same protocol                 │
 │  PC-2      │ ◄─────────────────────────────┘
 │  Tester    │
 │  (tester)  │
 └────────────┘
```

* **Daemon**: `daemon.py` — single `asyncio` event loop.
* **Executors**: `local_executors.py` — real subprocess + HTTP (no mocks).
* **Config**: `config.yaml` — per-node (PC-1 vs PC-2) customization.
* **Service**: `systemd/` (Linux) or `launchd/` (macOS) — auto-start on boot.

---

## ✅ Prerequisites

| Item | PC-1 (Dev Rig) | PC-2 (Headless Tester) |
|------|----------------|------------------------|
| OS | Linux or macOS | Linux (headless) |
| Python | ≥ 3.10 | ≥ 3.10 |
| Internet | Required (for Tower WS) | Required |
| Ollama | Optional (local LLM) | Not required |
| Git | Required | Optional |
| Tower URL | `https://supremeai-mcp-tower.onrender.com` | same |

```bash
# সব OS-এ universal dependencies:
python3 --version  # >= 3.10
python3 -m pip install -r client/supreme-node/requirements.txt
```

---

## 🚀 Quick start (PC-1 — Dev Rig)

### 1. Clone + install
```bash
git clone https://github.com/SaifulHaqueNiloy/supremeai.git
cd supremeai/client/supreme-node
python3 -m pip install -r requirements.txt
```

### 2. Configure
```bash
cp config.yaml config.local.yaml
$EDITOR config.local.yaml
```

**Edit for PC-1:**
```yaml
node_id: pc-1-dev-rig    # অবশ্যই unique
node_type: local_pc
role: coder             # planner | coder | tester | gate | observer
capabilities:
  - file_edit
  - pytest
  - git_push
  - bash
  - ollama
tower_url: https://supremeai-mcp-tower.onrender.com
tower_ws_url: wss://supremeai-mcp-tower.onrender.com/ws/node
workspace_dir: /home/<you>/projects  # আপনার repo path
```

### 3. Smoke test (dry run — একবার heartbeat পাঠিরে exit)
```bash
python3 daemon.py --config config.local.yaml --dry-run
# Expected: "heartbeat ok — lease_active=True expires=..."
```

### 4. Run daemon (foreground — ডিবাগ করার জন্য)
```bash
python3 daemon.py --config config.local.yaml --log-level DEBUG
```

### 5. Install as systemd service (Linux)
```bash
sudo cp systemd/supreme-node.service /etc/systemd/system/
sudo mkdir -p /opt/supreme-node /etc/supreme-node
sudo cp -r ./* /opt/supreme-node/
sudo cp config.local.yaml /etc/supreme-node/config.yaml
sudo systemctl daemon-reload
sudo systemctl enable --now supreme-node
sudo systemctl status supreme-node
sudo journalctl -u supreme-node -f   # live logs
```

---

## 🚀 Quick start (PC-2 — Headless Tester)

PC-2 তে শুধু `node_id` ও `role` আলাদা হবে, বাকিসব একই।

```yaml
node_id: pc-2-headless
node_type: local_pc
role: tester                # tester role — pytest task assign হবে
capabilities:
  - pytest
  - bash
tower_url: https://supremeai-mcp-tower.onrender.com
tower_ws_url: wss://supremeai-mcp-tower.onrender.com/ws/node
workspace_dir: /opt/supreme-node/workspace
```

Install:
```bash
sudo cp systemd/supreme-node.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now supreme-node
```

---

## 🍎 macOS install (launchd)

```bash
sudo cp launchd/com.supremeai.node.plist /Library/LaunchDaemons/
sudo chown root:wheel /Library/LaunchDaemons/com.supremeai.node.plist
sudo chmod 644 /Library/LaunchDaemons/com.supremeai.node.plist
sudo mkdir -p /opt/supreme-node /etc/supreme-node /var/log/supreme-node
sudo cp -r ./* /opt/supreme-node/
sudo cp config.local.yaml /etc/supreme-node/config.yaml
sudo launchctl load -w /Library/LaunchDaemons/com.supremeai.node.plist

# Logs:
tail -f /var/log/supreme-node/stdout.log
tail -f /var/log/supreme-node/stderr.log
```

Per-user (no sudo):
```bash
cp launchd/com.supremeai.node.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.supremeai.node.plist
```

---

## 🔧 Configuration reference

| Key | Default | Description |
|-----|---------|-------------|
| `node_id` | — | **Required.** Mesh-এ unique। Convention: `<hostname>-<purpose>` |
| `node_type` | — | `local_pc` / `cloud_agent` / `web_ai` / `edge_device` / `external_mcp` |
| `role` | — | `planner` / `coder` / `tester` / `gate` / `observer` |
| `capabilities` | — | List — কোন executors সক্রিয়। Tower শুধু ঐ task-ই পাঠাবে। |
| `tower_url` | — | Tower REST base (MESH-1 heartbeat endpoint) |
| `tower_ws_url` | — | Tower WebSocket URL (`/ws/node` suffix) |
| `heartbeat_path` | `/api/v1/nodes/heartbeat` | Tower heartbeat POST endpoint (MESH-1 #939) |
| `heartbeat_interval` | `60` | Seconds between heartbeats |
| `reconnect_backoff_base` | `2` | Exponential backoff base (2, 4, 8, 16, …) |
| `reconnect_backoff_max` | `300` | Backoff cap (5 minutes) |
| `ollama_url` | `http://localhost:11434` | Ollama local server (optional) |
| `task_timeout_seconds` | `600` | Per-task hard timeout |
| `workspace_dir` | `./workspace` | যেখানে bash/git/pytest task চলবে |
| `tower_auth_token` | `""` | Optional Bearer token (env `TOWER_AUTH_TOKEN` overrides) |
| `log_level` | `INFO` | DEBUG/INFO/WARNING/ERROR |

---

## 📨 Task protocol

Tower থেকে WebSocket message আসবে এই format-এ:

```json
{
  "type": "task",
  "task_id": "abc-123",
  "task_type": "bash",
  "payload": {
    "cmd": "ls -la"
  },
  "timeout": 120
}
```

### Task types

| `task_type` | `payload` | Output |
|------------|----------|--------|
| `bash` | `{"cmd": "..."}` | `ExecResult{exit_code, stdout, stderr, duration}` |
| `pytest` | `{"test_path": "tests/test_x.py"}` | `TestResult{passed, failed, errors, skipped, total, raw_output}` |
| `ollama` | `{"prompt": "...", "model": "llama3.2"}` | `{"text": "..."}` |
| `git_push` | `{"branch": "feat/x", "files": ["a.py"], "message": "..."}` | `GitResult{commit_sha, pushed, files_staged}` |

Daemon তার result ফেরত পাঠায়:
```json
{
  "type": "result",
  "task_id": "abc-123",
  "status": "ok",
  "result": { ... },
  "duration_seconds": 1.23,
  "node_id": "pc-1-dev-rig"
}
```

Tower আরও পাঠাতে পারে:
- `{"type": "ping"}` → daemon `pong` দিয়ে reply করে।
- `{"type": "shutdown"}` → daemon graceful shutdown করে।

---

## 🔍 Troubleshooting

### Heartbeat পাঠাচ্ছে না / 401
```bash
# ১. Tower reachability check
curl -X POST https://supremeai-mcp-tower.onrender.com/api/v1/nodes/heartbeat \
  -H "Content-Type: application/json" \
  -d '{"node_id":"pc-1-dev-rig","node_type":"local_pc","role":"coder","capabilities":[],"timestamp":"2026-01-01T00:00:00Z","load":{"cpu":0,"mem":0,"active_tasks":0}}'

# ২. Config ঠিক আছে কিনা দেখুন
python3 -c "from daemon import load_config; print(load_config('config.local.yaml'))"

# ৩. Dry-run
python3 daemon.py --config config.local.yaml --dry-run
```

### WebSocket connect হচ্ছে না
- Tower-এ `/ws/node` endpoint চালু আছে কিনা যাচাই করুন (MESH-3 daemon-টির dependency হলো Tower-এর `/ws/node` route)।
- এই PR-এ শুধু client side আছে। Server side `/ws/node` route Tower PR-এ আলাদাভাবে যোগ করা হবে।
- ততক্ষণ পর্যন্ত daemon চালু থাকলে reconnect backoff দিয়ে চেষ্টা চালিয়ে যাবে।

### Ollama task fails
- PC-1 এ `ollama serve` চলছে কিনা যাচাই করুন: `curl http://localhost:11434/api/tags`
- Model আছে কিনা: `ollama list`
- Config থেকে `ollama` capability সরিয়ে দিলে daemon Ollama task পাঠাবে না।

### systemd restart হচ্ছে বারবার
```bash
journalctl -u supreme-node -n 100 --no-pager
# "config error" লেগে থাকলে /etc/supreme-node/config.yaml ঠিক করুন
# restart loop stop করতে:
sudo systemctl disable --now supreme-node
```

### Test চালানো
```bash
cd client/supreme-node
python3 -m pip install -r requirements.txt
python3 -m pytest tests/ -v
```

---

## 🧪 Tests (developer notes)

- `tests/test_daemon.py` — mock `websockets.connect` (acceptable for client-side; SERVER is real per env1.txt directive), test heartbeat loop, reconnect backoff, task dispatch, message routing.
- `tests/test_local_executors.py` — real subprocess tests (`run_bash("echo hello")`, `run_pytest` on a tiny test file, `git_commit_push` in temp dir).
- `tests/test_config.py` — config loading + validation + env override.

Mock শুধু WebSocket transport layer-এ — executors সব আসল subprocess (no fake mocks per env1.txt directive).

---

## 🔗 Related

- Issue: [#941 — MESH-3 Local daemon supreme-node](https://github.com/SaifulHaqueNiloy/supremeai/issues/941)
- Depends on: MESH-1 [#939](https://github.com/SaifulHaqueNiloy/supremeai/issues/939) — Tower heartbeat endpoint (PR #944)
- Blocks: Phase E (dynamic lease)
- Master plan: [`docs/plans/MULTI_AGENT_MESH_MASTER_PLAN.md`](../../docs/plans/MULTI_AGENT_MESH_MASTER_PLAN.md)
