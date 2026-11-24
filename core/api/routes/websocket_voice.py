"""Voice WebSocket channel (``/ws/voice``).

Real STT (Groq Whisper → OpenAI → Gemini → HuggingFace cascade via
``core.services.voice_service``) in front of a **real** intent step: the
transcript is routed through the autonomous governed ReAct loop
(``core.agent_chat_loop.AgentChatLoop``) — the same loop that powers
``POST /api/agent/chat``. Tool calls stay inside the three governance gates
(flag → registry → MCP policy); the voice surface adds none of its own.

Honesty contract (audit items ⑤ / ⑱ — real-router revision, 2026-11-25):

* ``HANDLE_INTENT_SIMULATED`` is ``False``: every spoken turn goes through
  the same governed loop as chat. Nothing is echoed, nothing is canned.
* Every outbound frame still carries a literal ``simulated`` flag (now
  ``False``) plus ``surface="voice_agent"`` so the UI can audit the answer
  path frame-by-frame.
* The terminal ``response_complete`` frame reports ``executed`` truthfully —
  ``True`` only when the loop actually streamed a grounded reply — together
  with ``stepsUsed``, ``toolCalls`` and ``boundedStop``. A failed synthesis
  produces an honest error sentence, never a fabricated result.
``tests/test_voice_intent_honesty.py`` pins all of this.
"""

import asyncio
import json
import os
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from core.monitoring.logging_config import logger
from core.security import verify_token_async
from database.supabase_client import db
from models.voice_interaction import VoiceInteractionLog

router = APIRouter(prefix="/ws", tags=["Voice Engine Stream"])


class VoiceConnectionManager:
    # FIX (DoS): connection cap — unbounded list previously let memory grow
    # without limit (Render free tier has 512MB). Matches websocket_agent.py policy.
    MAX_CONNECTIONS = int(os.getenv("WS_MAX_CONNECTIONS", "50"))

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> bool:
        if len(self.active_connections) >= self.MAX_CONNECTIONS:
            await websocket.close(code=1013, reason="Too many connections")
            logger.warning(f"🛡️ [WS] Voice connection rejected: cap {self.MAX_CONNECTIONS} reached")
            return False
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("🟢 [WS] Voice Client Connected to SupremeAI Nexus.")
        return True

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("🔴 [WS] Voice Client Disconnected.")

    async def _authenticate(self, websocket: WebSocket) -> dict | None:
        try:
            auth_msg = await websocket.receive_json()
            token = auth_msg.get("token")
            if auth_msg.get("type") != "auth" or not token:
                return None
            return await verify_token_async(token)
        except Exception as e:
            import jwt

            if isinstance(e, jwt.ExpiredSignatureError):
                client_host = websocket.client.host if websocket.client else "unknown"
                logger.info(f"⚠️ [WS Auth] Expired token attempt from {client_host}")
            return None


manager = VoiceConnectionManager()


async def process_audio_dynamically(audio_bytes: bytes) -> str:
    """
    Sends audio buffer to dynamic VoiceService cascade (Groq -> OpenAI -> HF -> Graceful degradation).
    Vendor-agnostic STT (Issue #466).
    """
    try:
        from services.voice_service import get_voice_service

        voice = get_voice_service()
        res = await voice.speech_to_text(audio_bytes, filename="audio.webm")
        if res.get("status") == "success":
            return res.get("transcript", "")
        if res.get("status") == "unavailable":
            return res.get("message", "Speech-to-text is awaiting AI provider key configuration.")
        return res.get("message", "Unable to process audio.")
    except Exception as e:
        logger.error(f"❌ [Dynamic STT Error]: {e}")
        return f"Error processing audio: {e!s}"


# Backward-compatibility alias
process_audio_with_groq = process_audio_dynamically


# Honesty contract (real-router revision, 2026-11-25):
#
# The voice intent step no longer echoes. ``handle_intent`` routes every
# transcript through ``core.agent_chat_loop.AgentChatLoop`` — governed tool
# execution (three gates), grounded synthesis, honest failures. The flag stays
# as a *capability marker* for clients and is now ``False``; if the loop can
# not be built at all (import failure), the handler degrades to an honest
# "voice agent unavailable" sentence — it never falls back to a canned claim
# of work.
HANDLE_INTENT_SIMULATED = False

#: System note prepended to every voice turn — spoken style + language
#: mirroring, matching the blueprint's Adaptive Tone & Brevity pillar.
_VOICE_SYSTEM_NOTE = (
    "You are SupremeAI's voice interface (Aethel) — the user's personal "
    "executive. The user is SPEAKING, not typing: reply in short, spoken-style "
    "sentences unless they explicitly ask for detail. Mirror the user's "
    "language (বাংলা প্রশ্ন → খাঁটি বাংলা; English → professional English). "
    "Ground every claim in real tool observations; if a tool was blocked or "
    "failed, say so plainly."
)


def _voice_agent_loop():
    """Factory seam — tests inject a fake loop without touching core internals.

    Kept deliberately lazy: importing ``core.agent_chat_loop`` pulls the
    reasoning orchestrator and LLM gateway; a broken voice deployment must
    still answer honestly instead of dying at import time.
    """
    from core.agent_chat_loop import AgentChatLoop

    return AgentChatLoop()


async def _send_frame(websocket: WebSocket, payload: dict) -> None:
    """Send one auditable frame — every frame carries the honesty flags."""
    await websocket.send_json(
        {
            "simulated": False,
            "surface": "voice_agent",
            **payload,
        }
    )


async def handle_intent(transcript: str, websocket: WebSocket, start_time: float, user_id: str):
    """Route the transcript through the governed ReAct loop and stream the truth.

    Every frame carries ``simulated: False`` + ``surface: "voice_agent"``:

    * ``agent_event``   — loop progress (thought / tool_call / tool_result);
    * ``response_chunk`` — streamed answer deltas for Web Speech API TTS;
    * ``response_complete`` — terminal honesty: ``executed`` is ``True`` only
      when a grounded reply really streamed, plus ``stepsUsed``,
      ``toolCalls`` and ``boundedStop``.

    No execution primitive lives here — the loop's gates (flag → registry →
    MCP policy) are the only path to real work.
    """
    transcript_clean = (transcript or "").strip()
    intent = "agent"
    answer_parts: list[str] = []
    tool_calls: list[dict] = []
    bounded_stop = False
    failure: str | None = None

    if not transcript_clean:
        intent = "empty_audio"
        answer_parts = [
            "I couldn't hear anything in that recording — please try speaking again."
        ]
        for word in answer_parts[0].split(" "):
            await _send_frame(
                websocket,
                {"type": "response_chunk", "text": word + " ", "intent": intent},
            )
            await asyncio.sleep(0.03)
        await _send_frame(
            websocket,
            {
                "type": "response_complete",
                "intent": intent,
                "executed": False,
                "stepsUsed": 0,
                "toolCalls": [],
                "boundedStop": False,
                "error": "empty transcript",
            },
        )
        return

    try:
        loop = _voice_agent_loop()
        messages = [
            {"role": "system", "content": _VOICE_SYSTEM_NOTE},
            {"role": "user", "content": transcript_clean},
        ]
        async for event in loop.run_stream(messages=messages, tenant_id=user_id, model="auto"):
            etype = str(event.get("type") or "")
            if etype == "content_delta":
                delta = str(event.get("delta") or "")
                if not delta:
                    continue
                answer_parts.append(delta)
                await _send_frame(
                    websocket,
                    {"type": "response_chunk", "text": delta, "intent": intent},
                )
            elif etype in ("thought", "tool_call", "tool_result"):
                if etype == "tool_call":
                    tool_calls.append(
                        {"step": event.get("step"), "tool": event.get("tool")}
                    )
                # বাংলা: লুপ-অগ্রগতি সততার সাথে UI-তে — ভয়েস উত্তরের আগেই
                # "টুল চলছে" বোঝা যায়, ভান নয়।
                await _send_frame(websocket, {"type": "agent_event", "event": event})
            elif etype == "error":
                failure = str(event.get("message") or "agent error")
            elif etype == "final":
                if not answer_parts and event.get("answer"):
                    final_text = str(event.get("answer"))
                    answer_parts.append(final_text)
                    await _send_frame(
                        websocket,
                        {"type": "response_chunk", "text": final_text, "intent": intent},
                    )
                bounded_stop = bool(event.get("boundedStop"))
    except Exception as exc:
        failure = f"voice agent failed ({type(exc).__name__})"
        logger.error(f"❌ [WS Voice Agent] {type(exc).__name__}: {exc}")

    answer = "".join(answer_parts).strip()
    executed = bool(answer) and failure is None

    if not executed:
        # সততা: ব্যর্থতা বা শূন্য উত্তর — ভান নয়, স্পষ্ট ব্যর্থতার বাক্য।
        fallback = (
            "Voice agent could not complete this request"
            + (f" — {failure}." if failure else ".")
            + " Please try again, or ask in chat for a detailed answer."
        )
        answer = fallback
        for word in fallback.split(" "):
            await _send_frame(
                websocket,
                {"type": "response_chunk", "text": word + " ", "intent": intent},
            )
            await asyncio.sleep(0.03)

    # Log to database (best-effort — never blocks the voice path)
    if db.client:
        latency_ms = int((time.time() - start_time) * 1000)
        log_entry = VoiceInteractionLog(
            user_id=user_id,
            transcript=transcript_clean,
            supremeai_response=answer[:2000],
            latency_ms=latency_ms,
        )
        try:
            await (
                db.client.table("voice_interactions")
                .insert(log_entry.dict(exclude_none=True))
                .execute()
            )
        except Exception as db_err:
            logger.info(f"⚠️ [DB Logging Error]: {db_err}")

    await _send_frame(
        websocket,
        {
            "type": "response_complete",
            "intent": intent,
            "executed": executed,
            "stepsUsed": len(tool_calls),
            "toolCalls": tool_calls,
            "boundedStop": bounded_stop,
            **({"error": failure} if failure else {}),
        },
    )


@router.websocket("/voice")
async def websocket_voice_endpoint(
    websocket: WebSocket,
):
    """
    Real-time WebSocket for Voice-to-Voice Streaming.
    Receives binary audio chunks, uses Groq Whisper for STT, and returns the response.
    """
    auth_payload = await manager._authenticate(websocket)
    if not auth_payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    connected = await manager.connect(websocket)
    if not connected:
        return

    # Store audio chunks in memory
    audio_buffer = bytearray()
    start_time = time.time()

    try:
        while True:
            # We accept both text (commands like {"action": "process"}) and binary (audio chunks)
            message = await websocket.receive()

            if "bytes" in message:
                # Append binary chunk to buffer
                audio_buffer.extend(message["bytes"])
            elif "text" in message:
                try:
                    payload = json.loads(message["text"])
                    action = payload.get("action")

                    if action == "process":
                        if len(audio_buffer) == 0:
                            await websocket.send_json({"error": "Empty audio buffer"})
                            continue

                        # 1. Process STT using Dynamic VoiceService
                        logger.info(
                            f"🎙️ [WS] Processing audio buffer ({len(audio_buffer)} bytes)..."
                        )
                        transcript = await process_audio_dynamically(bytes(audio_buffer))
                        logger.info(f"🗣️ [User Voice]: {transcript}")

                        # Clear buffer for next recording
                        audio_buffer.clear()

                        # Send transcript to UI
                        await websocket.send_json({"type": "transcript", "text": transcript})

                        # 2. Intent Router
                        await handle_intent(
                            transcript,
                            websocket,
                            start_time,
                            auth_payload.get("sub", "anonymous"),
                        )
                        start_time = time.time()  # Reset timer

                    elif action == "text_chat":
                        transcript = payload.get("text", "")
                        logger.info(f"💬 [User Text]: {transcript}")

                        # Process text intent directly
                        await handle_intent(
                            transcript,
                            websocket,
                            start_time,
                            auth_payload.get("sub", "anonymous"),
                        )
                        start_time = time.time()  # Reset timer

                except json.JSONDecodeError:
                    logger.info("⚠️ [WS] Received invalid text message.")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.info(f"❌ [WS Voice Engine Error]: {e}")
        manager.disconnect(websocket)
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception as exc:
            logger.exception(f"WebSocket close failed after error: {exc}")
