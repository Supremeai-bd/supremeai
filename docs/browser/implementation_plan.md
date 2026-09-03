# docs/browser — Implementation Plan

> **Source Plan:** [`SUPREME_BROWSER_MASTER_PLAN.md`](file:///f:/supremeai/docs/browser/SUPREME_BROWSER_MASTER_PLAN.md)  
> **Goal:** 6-Pillar Cognitive Autonomous Browser Suite সম্পূর্ণ করা।

---

## Pillar Status Overview

| Pillar | Description | Status |
| --- | --- | --- |
| 1 | In-App Live Preview Engine | ⚠️ Partial (CORS proxy exists) |
| 2 | Playwright MCP Automation | ✅ Exists (`services/browser/`) |
| 3 | Anti-Detection Stealth Shield | ⚠️ Partial (`browser_stealth.py`) |
| 4 | Vision Grounding & Semantic DOM | ⚠️ Partial (files exist, not wired) |
| 5 | Multi-Agent Swarm Browser | 🔴 Not Started |
| 6 | Live Screencast & HITL Takeover | 🔴 Not Started |

---

## 🚧 Pending Tasks

### Milestone 1 — Foundation (Pillar 1 + 2)

#### Step 1 — CORS Proxy API Route

- **কাজ:** `/api/browser/proxy` endpoint → server-side `httpx` দিয়ে target URL fetch + inject iframe-safe headers
- **ফাইল:** `backend/api/routes/browser.py` → `proxy_endpoint()` function
- **টেস্ট:** `curl http://localhost:8000/api/browser/proxy?url=https://example.com` → 200 OK

#### Step 2 — Playwright Pool Manager

- **কাজ:** Singleton Playwright Browser pool (max 3 headless instances) তৈরি করা
- **ফাইল:** `backend/services/browser/browser_pool.py` (new)
- **টেস্ট:** `pytest tests/services/browser/test_browser_pool.py`

#### Step 3 — Core Browser Action Executor

- **কাজ:** `navigate`, `click`, `type`, `screenshot` — unified executor
- **ফাইল:** `backend/services/browser/action_executor.py` (new)
- **API:** `POST /api/browser/browse` → `{action: "navigate", url: "..."}`

---

### Milestone 2 — Frontend Viewport (Pillar 1 continued)

#### Step 4 — Frontend Live Preview Shell

- **কাজ:** User Dashboard-এ sandboxed `<iframe>` + Device Viewport switcher (Desktop/Tablet/Mobile)
- **ফাইল:** `frontend/src/components/browser/LivePreview.tsx` (new)
- **টেস্ট:** একটি HTML কোড render করে দেখা

#### Step 5 — Console Error Trap (Self-Healing Feed)

- **কাজ:** iframe `postMessage` দিয়ে console errors ক্যাচ করে `ai_memory`-তে feed করা
- **ফাইল:** `frontend/src/components/browser/ConsoleErrorTrap.ts` (new)

---

### Milestone 3 — Cognitive Vision (Pillar 4)

#### Step 6 — Vision Grounding API Wire-up

- **কাজ:** `backend/browser/vision_grounding.py` (exists) → `/api/browser/vision-ground` endpoint-এ connect
- **ফাইল:** `backend/api/routes/browser.py` → `vision_ground_endpoint()` function
- **টেস্ট:** screenshot দিয়ে button coordinate detect করা

#### Step 7 — Semantic DOM Pruning API

- **কাজ:** `backend/browser/semantic_dom.py` (exists) → `/api/browser/semantic-dom` endpoint
- **ফাইল:** `backend/api/routes/browser.py` → `semantic_dom_endpoint()` function
- **টেস্ট:** 20K token HTML → 500 token pruned output

---

### Milestone 4 — Swarm & Screencast (Pillar 5 + 6)

#### Step 8 — WebSocket Screencast Stream

- **কাজ:** Playwright page `screenshot()` → 500ms interval → WebSocket JPEG stream
- **ফাইল:** `backend/api/routes/browser.py` → `/ws/browser/screencast` WebSocket handler
- **Security:** First-message token auth (no URL token)
- **টেস্ট:** WS connect → JPEG frames receive করা

#### Step 9 — 1-Click HITL Takeover

- **কাজ:** `POST /api/browser/takeover` → browser session কে user-controlled mode-এ switch করা
- **ফাইল:** `backend/services/browser/hitl_manager.py` (new)
- **টেস্ট:** AI session → takeover → user action → re-handoff

#### Step 10 — Multi-Agent Swarm Partitioner (Pillar 5)

- **কাজ:** `asyncio.gather()` দিয়ে ৩-৫টি parallel Playwright session → concurrent task partitioning
- **ফাইল:** `backend/services/browser/swarm_coordinator.py` (new)

---

## Implementation Priority Order

```
Priority 1 — Foundation (Milestone 1):
  Step 1 → CORS Proxy
  Step 2 → Browser Pool Manager
  Step 3 → Action Executor

Priority 2 — Frontend (Milestone 2):
  Step 4 → Live Preview Shell
  Step 5 → Console Error Trap

Priority 3 — Vision (Milestone 3):
  Step 6 → Vision Grounding API
  Step 7 → Semantic DOM API

Priority 4 — Advanced (Milestone 4):
  Step 8 → WebSocket Screencast
  Step 9 → HITL Takeover
  Step 10 → Swarm Partitioner
```

## Verification Gate

```bash
# Foundation check
curl -s http://localhost:8000/api/browser/status | jq .status
# → "ready"

# Playwright pool
cd backend && poetry run pytest tests/services/browser/ -v

# Vision grounding
curl -X POST http://localhost:8000/api/browser/vision-ground \
  -H "Content-Type: application/json" \
  -d '{"screenshot_base64": "..."}'
```
