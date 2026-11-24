"""core.api.routes.agent_tools — governed tool surface for chat (audit item ⑯).

বাংলা: এটাই চ্যাটের টুল-সারফেস — কিন্তু লুপ এখানে নয়। নির্বাহ
``core.tool_loop``-এ, গেট তিনটি (flag → রেজিস্ট্রি → MCP পলিসি), আর
প্রতি-টেন্যান্ট দৃশ্যমানতা ``core.agent_tool_policy``-তে। এই রাউটার শুধু:

* ``GET  /api/agent/tools``       — OpenAI ``tools`` আকারে ম্যানিফেস্ট
  (flag বন্ধ থাকলে ``enabled: false``, ৪০৩ নয় — ক্লায়েন্ট সৎভাবে দেখাতে পারে);
* ``POST /api/agent/tool-calls``  — এক কল নির্বাহ, OpenAI ``tool`` মেসেজ আকারে ফলাফল।

গেটওয়ে (``gateway/service/app.py``) কিছুই ইমপোর্ট করে না — কেবল HTTP-তে
বহন করে (``gateway-no-core-private`` চুক্তি অটুট)। ডিফল্ট OFF।
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_current_user_token
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
        {"tool": payload.tool, "args": payload.arguments, "source": "http"}
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
