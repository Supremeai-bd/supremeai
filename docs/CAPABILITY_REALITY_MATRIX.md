# Capability Reality Matrix

> **What a user can actually ask SupremeAI to do today, and what only sounds possible.**
> Verified against the code at `main` @ `8e4280a` on 2026-11-24. Every row names the
> file that answers the request, so a claim can be re-checked instead of trusted.

This document exists because three surfaces describe capabilities differently:
the chat gateway (`gateway/service/app.py`), the voice socket
(`core/api/routes/websocket_voice.py`) and the browser automation API
(`core/api/routes/browser/_automation.py`). Nothing previously said, in one place,
which of them can *do* the thing rather than *talk about* it.

**The one-line summary:** SupremeAI is a chat-relay + scraper/browser-automation
platform. It is **not** an agent that executes a user's request end-to-end. The
chat model cannot call tools, so "log into X and do Y for me" cannot be answered
from a chat turn — no matter how confidently a reply is worded.

---

## 1. Works today

| Surface | What really happens | Evidence |
|---|---|---|
| **Chat (Studio / OpenAI-compatible)** | `/v1/chat/completions` streams real text through the stealth relay or a configured admin API slot. History persists per user/conversation. Guests and registered users both chat. **Text only — no tool calls.** | `gateway/service/app.py` (`_execute_chat_completion`) |
| **Speech-to-text** | Real cascade: Groq Whisper → OpenAI → Gemini → HuggingFace, with an honest `unavailable` status when no key exists. | `core/services/voice_service.py::speech_to_text` |
| **Text-to-speech** | Real: edge-tts → ElevenLabs. | `core/services/voice_service.py::text_to_speech` |
| **Browser automation (logged-in user)** | Create an isolated, owner-scoped Playwright session; `navigate / click / fill / type / screenshot / content / extract / back / forward / reload`; owner pause/resume; cookie+localStorage vault sync; HITL admin takeover. **The user drives it from the browser UI or the API** — not from chat. | `core/api/routes/browser/_automation.py`, `core/browser_session_manager.py` |
| **Scraping (admin/tenant)** | `/api/v1/scrape`, `/api/v1/browse`, `/api/v1/recipe` behind admin JWT with a per-process semaphore; core proxy routes with a 1 h cache; the standalone browser service exposes `/scrape`, `/browse`, `/recipe` behind a shared webhook secret with per-hop SSRF checks. | `core/api/routes/browser/_scraping.py`, `browser/main.py`, `browser/web_scraper.py` |
| **Deep research** | Multi-step research over SSE — **only** when the tenant has an active CrawlPolicy *and* a scout key. Otherwise it returns an honest empty result. | `core/api/routes/deep_research.py` |
| **Telegram bot** | `#gemini`, `/spark`, `!gemini` triggers answer questions (chunked, Markdown→plain fallback). Question answering only. | `core/integrations/telegram_bot.py` |
| **Image upload** | Validate (MIME + signature, fail-closed) and store per user; listing endpoint for the file explorer. **No grounded Q&A over the image in chat.** | `core/api/routes/chat_upload.py` |

## 2. Present in the API but not invocable from chat

These endpoints are real; the chat turn cannot reach them.

| Endpoint | Why it is not chat-reachable |
|---|---|
| `POST /api/browser/automation/*` | Requires an authenticated owner (`sub`) and is driven by explicit actions; chat has no tool loop and guests are rejected. |
| `POST /api/browser/autonomous/run` | Runs `AutonomousBrowserAgent` against a real ephemeral session, but only from this admin/tenant route. `MAX_STEPS` is bounded and no session → 503, never a fake success. |
| `POST /v1/capabilities/execute` | A **passthrough**, not an executor: it answers with chat text and reports `verified=false`, `mode=chat_passthrough`, `artifacts=[]`. | 
| `GET /api/v1/connections/my-workspace` | Reports `chatToolCalling: false`; every capability carries `invocableFromChat: false` and its real `invocationSurface` (`api`, `browser_ui`, `chat_text_only`). |

## 3. Not possible today (do not promise it)

1. **"Here is my password/PIN — log in and do the task."** No credential-ingest path
   in chat, and the vault (`core/browser_session_vault.py`) is only read by the
   automation API for saved cookie/storage sessions.
2. **Chat → browser ReAct loop.** No "tool call → page action → result back into the
   conversation" cycle exists.
3. **Voice-driven tasks.** The socket does real STT and TTS, then echoes the
   transcript. Every frame carries `simulated: true`; `HANDLE_INTENT_SIMULATED` in
   `core/api/routes/websocket_voice.py` is the flag to flip when a real router lands.
4. **"What is happening on this URL right now?" in chat.** No live fetch/browse from
   the chat path; answers come from model knowledge.
5. **Guest → browser automation.** Automation needs `sub` + `tenant_id`; a guest
   token cannot create a session.
6. **Deep research / scrape invoked by the model.** The routes exist; the model has
   no schema for them.
7. **Third-party actions (email, calendar, payments, orders, WhatsApp).** Adapters
   exist under `core/messaging/`, `core/tools/social/`; nothing wires them to chat.
8. **Multi-step unattended tasks with post-condition verification.** No
   screenshot/DOM assertion backs a "done" claim; truth is model text.
9. **Chat → HITL escalation.** HITL takeover exists for browser sessions only.
10. **Grounded questions over PDF/DOCX in chat.** Upload is image-only.

## 4. What would have to change (in order)

1. A tool-calling loop on the chat path (OpenAI `tools` semantics) with an identity-
   and allowlist-gated tool registry.
2. A chat-session ↔ ephemeral page binding that asks for consent before acting.
3. Credential ergonomics that never echo secrets into a prompt (client-side
   encrypted vault, injected at the transport layer).
4. Post-condition assertions (URL/DOM/screenshot diff) before any "done" claim.
5. Voice intent = allowlisted tool call; delete the canned echo when it lands
   (`tests/test_voice_intent_honesty.py` fails first, by design).

## 5. How to keep this honest

| Guard | What it pins |
|---|---|
| `tests/test_voice_intent_honesty.py` | Voice frames say `simulated: true`, `executed: false`; no execution primitives in the handler. |
| `gateway/tests/test_workspace_capability_honesty.py` | Workspace never advertises chat-invocable capabilities. |
| `gateway/tests/test_storage_and_endpoints.py` | `/v1/capabilities/execute` reports `verified=false`. |
| `core/tests/routes/test_browser_automation_contract.py` | Automation ownership, SSRF screening, pause gating and honest status codes. |

When any capability in §3 is implemented, update the row here **and** the guard that
pins it, in the same pull request.
