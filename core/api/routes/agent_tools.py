"""core.api.routes.agent_tools — governed tool surface for chat (audit item ⑯).

বাংলা: এটাই চ্যাটের টুল-সারফেস — কিন্তু লুপ এখানে নয়। নির্বাহ
``core.tool_loop``-এ, গেট তিনটি (flag → রেজিস্ট্রি → MCP পলিসি), আর
প্রতি-টেন্যান্ট দৃশ্যমানতা ``core.agent_tool_policy``-তে। এই রাউটার শুধু:

* ``GET  /api/agent/tools``       — OpenAI ``tools`` আকারে ম্যানিফেস্ট
  (flag বন্ধ থাকলে ``enabled: false``, ৪০৩ নয় — ক্লায়েন্ট সৎভাবে দেখাতে পারে);
* ``POST /api/agent/tool-calls``  — এক কল নির্বাহ, OpenAI ``tool`` মেসেজ আকারে ফলাফল;
* ``POST /api/agent/chat``        — সম্পূর্ণ ReAct টার্ন (``core.agent_chat_loop``), JSON ফল;
* ``POST /api/agent/stream``      — একই টার্নের SSE ইভেন্ট-স্ট্রিম (``data: {json}`` … ``[DONE]``)।

গেটওয়ে (``gateway/service/app.py``) কিছুই ইমপোর্ট করে না — কেবল HTTP-তে
বহন করে (``gateway-no-core-private`` চুক্তি অটুট)। ডিফল্ট OFF।
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.deps import get_current_user_token
from core.agent_chat_loop import DEFAULT_MAX_STEPS, HARD_MAX_STEPS, AgentChatLoop
from core.agent_tool_policy import tenant_tool_view
from core.agent_tool_specs import SPECS_BY_NAME
from core.monitoring.logging_config import logger
from core.tool_loop import agent_tools_enabled, execute_tool_decision

router = APIRouter(
    prefix="/api/agent",
    tags=["AI-Orchestration"],
    dependencies=[Depends(get_current_user_token)],
)

UserToken = Annotated[dict, Depends(get_current_user_token)]


class ToolCallPayload(BaseModel):
    """One OpenAI-style tool call, already chosen by the model."""

    tool: str = Field(min_length=1, max_length=64)
    arguments: dict[str, Any] = Field(default_factory=dict)
    tool_call_id: str | None = Field(default=None, max_length=128)


def _tenant_of(token: dict) -> str:
    return str(token.get("tenant_id") or token.get("sub") or "").strip()


def _new_agent_chat_loop() -> AgentChatLoop:
    """Factory seam — tests stub the loop without touching heavy collaborators."""
    return AgentChatLoop()


def _missing_required(tool: str, arguments: dict[str, Any]) -> list[str]:
    spec = SPECS_BY_NAME.get(tool)
    if spec is None:
        return []
    required = spec["parameters"].get("required", [])
    return [key for key in required if key not in arguments]


@router.get("/tools")
async def list_agent_tools(token: UserToken) -> dict[str, Any]:
    """Return the tenant's tool manifest in OpenAI ``tools`` shape.

    ``enabled=false`` (flag off) is a normal, honest answer with an empty list —
    not an error — so the client can render "tool calling is off" instead of a
    broken surface.
    """
    view = tenant_tool_view(_tenant_of(token))
    payload = view.as_dict()
    payload["availableCount"] = len(view.available_names())
    return payload


@router.post("/tool-calls")
async def call_agent_tool(payload: ToolCallPayload, token: UserToken) -> dict[str, Any]:
    """Execute one tool call through the governed loop and return a tool message.

    Status codes:
      * ``403`` — the surface is off (flag), or the tenant's allowlist does not
        include this tool. Configuration/authorisation errors, not recoverable
        by the model.
      * ``400`` — malformed call (missing required argument).
      * ``200`` — executed, or refused *at runtime* (``policy_blocked``,
        ``unknown_tool``, ``error``). The refusal text is the tool result so the
        model can recover; ``executed`` is false and ``status`` says why.
    """
    if not agent_tools_enabled():
        raise HTTPException(
            status_code=403,
            detail=(
                "agent tool calling is disabled — set SUPREMEAI_AGENT_TOOLS=true "
                "to expose it (default OFF, fail-safe)"
            ),
        )

    view = tenant_tool_view(_tenant_of(token))
    declared = {item["function"]["name"]: item for item in view.tools}
    if view.allowlist_error:
        raise HTTPException(
            status_code=403,
            detail=f"agent tool allowlist misconfigured — denying all tools: {view.allowlist_error}",
        )
    if payload.tool not in declared:
        raise HTTPException(
            status_code=403,
            detail=(
                f"tool '{payload.tool}' is not in this tenant's allowlist "
                f"(source={view.allowlist_source})"
            ),
        )

    missing = _missing_required(payload.tool, payload.arguments)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"tool '{payload.tool}' is missing required argument(s): {', '.join(missing)}",
        )

    logger.info(
        f"[agent_tools] tenant={view.tenant_id or '<unknown>'} tool={payload.tool} "
        f"args={sorted(payload.arguments)}"
    )
    result = await execute_tool_decision(
        {
            "tool": payload.tool,
            "args": payload.arguments,
            "source": "http",
            "tenant_id": view.tenant_id,
        }
    )

    content = (
        result.get("observation")
        if result.get("executed")
        else result.get("reason") or result.get("error") or "tool did not execute"
    )
    response: dict[str, Any] = {
        "role": "tool",
        "tool_call_id": payload.tool_call_id,
        "name": payload.tool,
        "content": content,
        "executed": bool(result.get("executed")),
        "status": result.get("status"),
        "policy": result.get("policy"),
        "risk": result.get("risk"),
        "tenantId": view.tenant_id or None,
    }
    if result.get("error"):
        response["error"] = result["error"]
    return response


# ── Autonomous ReAct chat turn (M09 P-C) ─────────────────────────────────────
#
# বাংলা: লুপ ``core.agent_chat_loop.AgentChatLoop``-এ; রাউটার কেবল চুক্তি-
# যাচাই, টেন্যান্ট-অ্যাট্রিবিউশন ও পরিবহন করে। flag-off মানে সাদামাটা চ্যাট
# মোড — সৎ মেটা ইভেন্ট সহ 200 (টুল-সারফেসের ``enabled: false`` চুক্তির মতোই),
# 403 নয়: চ্যাট টুল ছাড়াও সত্যিই উত্তর দিতে পারে।


class AgentChatMessage(BaseModel):
    """One OpenAI-shaped conversation message."""

    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class AgentChatPayload(BaseModel):
    """A bounded ReAct chat turn request."""

    messages: list[AgentChatMessage] = Field(min_length=1, max_length=64)
    model: str = Field(default="auto", max_length=64)
    max_steps: int = Field(default=DEFAULT_MAX_STEPS, ge=1, le=HARD_MAX_STEPS)


@router.post("/chat")
async def agent_chat(payload: AgentChatPayload, token: UserToken) -> dict[str, Any]:
    """Run one full autonomous ReAct turn and return the collected result.

    The loop lives in core (``core.agent_chat_loop``): tenant-scoped tool
    filtering, governed execution via ``core.tool_loop`` and a streamed final
    synthesis. ``errors`` carries honest failure notes instead of fabricated
    answers.
    """
    loop = _new_agent_chat_loop()
    result = await loop.run(
        messages=[m.model_dump() for m in payload.messages],
        tenant_id=_tenant_of(token),
        model=payload.model,
        max_steps=payload.max_steps,
    )
    logger.info(
        f"[agent_chat] tenant={_tenant_of(token) or '<unknown>'} "
        f"steps={result.get('stepsUsed')} errors={len(result.get('errors') or [])}"
    )
    return result


@router.post("/stream")
async def agent_chat_stream(payload: AgentChatPayload, token: UserToken) -> StreamingResponse:
    """Stream one autonomous ReAct turn as SSE events.

    Frames: ``data: {json event}\\n\\n`` for each loop event (meta / thought /
    tool_call / tool_result / content_delta / error / final), then a terminal
    ``data: [DONE]\\n\\n`` — the same framing the client already knows from
    ``/api/chat/stream_chat``.
    """

    async def event_stream() -> AsyncIterator[str]:
        loop = _new_agent_chat_loop()
        try:
            async for event in loop.run_stream(
                messages=[m.model_dump() for m in payload.messages],
                tenant_id=_tenant_of(token),
                model=payload.model,
                max_steps=payload.max_steps,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        except Exception as exc:
            logger.error(f"[agent_stream] broken: {type(exc).__name__}: {exc}")
            yield "data: {\"type\": \"error\", \"message\": \"agent stream failed internally\"}\n\n"
        yield "data: [DONE]\n\n"

    # বাংলা: SSE হেডার — proxy/CDN বাফারিং রোধে ক্রিটিক্যাল (chat.py-র সাথে একই)।
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Encoding": "identity",
        },
    )
