"""Task execution endpoints for SupremeAI.

বাংলা: কাজ এক্সিকিউশন এন্ডপয়েন্ট।
"""

import datetime
import json
import re

# বাংলা মন্তব্য: টাইপিং এরর এড়ানোর জন্য Any ইমপোর্ট করা হলো
from typing import Any

import anyio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, model_validator

# --- Local Imports ---
# Moved imports to the top of the file to improve performance by avoiding repeated imports inside functions.
from api.dependencies import get_current_user_token

# STABILIZE FIX: PromptAction now lives in core.intent_router_v2 (canonical).
# core.intent_router re-exports it for backwards compat.
from core.intent_router import PromptAction
from core.monitoring.logging_config import logger
from core.prompt_handler import format_unified_chat_prompt

router = APIRouter(dependencies=[Depends(get_current_user_token)])

# --- Agentic Security & Context: Task Request Schema ---
# Added messages and session_id parameters on 2026-06-21 to prevent context loss.
class TaskRequest(BaseModel):
    task: str
    task_type: str = "general"
    max_cost: float = 0.01
    admin_token: str | None = None
    schema_name: str | None = None
    messages: list[dict] | None = None
    session_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def harmonize_fields(cls, data: Any) -> Any:
        """বাংলা: ফ্রন্টএন্ড কনট্র্যাক্ট হারমোনাইজ — message→task, history→messages।

        FIX (API-contract audit): chatService.sendMessage() ঐতিহাসিকভাবে
        ``{message, history}`` পাঠাত, অথচ canonical TaskRequest ফিল্ড হলো
        ``task``/``messages`` — ফলে প্রতিটি কল Pydantic 422 খাত। এখন দুই
        শেপই গ্রহণযোগ্য (ChatStreamRequest.harmonize_fields-এর একই প্যাটার্ন)।
        """
        if isinstance(data, dict):
            if not data.get("task") and data.get("message"):
                data["task"] = data["message"]
            if not data.get("messages") and data.get("history"):
                data["messages"] = data["history"]
            if not data.get("task"):
                raise ValueError("Either 'task' or 'message' must be provided.")
        return data


class TaskResponse(BaseModel):
    success: bool
    result: str | None = None
    provider: str | None = None
    cost: float | None = None
    error: str | None = None
    action: dict[str, Any] | None = None
    intent: dict[str, Any] | None = None


class CompletionRequest(BaseModel):
    prefix: str
    suffix: str
    filePath: str  # -- camelCase required to match frontend JSON API contract
    language: str
    sessionId: str | None = None  # -- camelCase required to match frontend JSON API contract


class CompletionResponse(BaseModel):
    success: bool
    suggestions: list[str]


class ChatStreamRequest(BaseModel):
    message: str | None = None
    prompt: str | None = None
    sessionId: str | None = None  # -- camelCase required to match frontend JSON API contract
    session_id: str | None = None
    messages: list[dict] | None = None
    context: dict | None = None

    @model_validator(mode="before")
    @classmethod
    def harmonize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("message") and data.get("prompt"):
                data["message"] = data["prompt"]
            elif not data.get("prompt") and data.get("message"):
                data["prompt"] = data["message"]
            if not data.get("sessionId") and data.get("session_id"):
                data["sessionId"] = data["session_id"]
            elif not data.get("session_id") and data.get("sessionId"):
                data["session_id"] = data["sessionId"]
            if not data.get("message"):
                raise ValueError("Either 'message' or 'prompt' must be provided.")
        return data


class ActionStreamRequest(BaseModel):
    message: str
    messages: list[dict] | None = None


def _build_completion_prompt(prefix: str, suffix: str) -> str:
    return (
        f"You are a code completion assistant. Your task is to provide the code that fits between the prefix and suffix.\n"
        f"Do NOT wrap the response in code blocks, markdown, or explain it. Return ONLY the code to be inserted.\n\n"
        f"--- PREFIX ---\n{prefix}\n"
        f"--- SUFFIX ---\n{suffix}\n"
        f"--- COMPLETION ---"
    )


def _build_chat_prompt(req: ChatStreamRequest) -> str:
    context = req.context or {}
    text_content = req.message or req.prompt or ""
    parts = [f"User: {text_content}"]
    if context.get("codeSnippet"):
        parts.append(f"Code snippet:\n{context['codeSnippet']}")
    if context.get("filePath"):
        parts.append(f"File: {context['filePath']}")
    if context.get("language"):
        parts.append(f"Language: {context['language']}")
    parts.append("Assistant:")
    return "\n".join(parts)


@router.post("/api/chat/completion", response_model=CompletionResponse)
async def get_completion(req: CompletionRequest):
    import core.services as app_mod

    model_router = app_mod.model_router

    prompt = _build_completion_prompt(req.prefix, req.suffix)

    raw = await model_router.async_route_and_generate(
        prompt=prompt,
        task_type="completion",
        max_cost=0.005,
    )

    from utils.text_helpers import strip_markdown_code_block

    completion_text = strip_markdown_code_block(raw.get("text", ""))

    suggestions = [completion_text] if completion_text else []
    return CompletionResponse(success=True, suggestions=suggestions)


@router.post("/api/chat/stream")
async def stream_chat(req: ChatStreamRequest):
    import core.services as app_mod

    model_router = app_mod.model_router
    prompt = _build_chat_prompt(req)

    async def event_generator():
        async for chunk in model_router.async_route_and_stream(
            prompt=prompt,
            task_type="general",
            max_cost=0.01,
        ):
            token = chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)
            yield f"data: {json.dumps({'token': token, 'delta': token})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class ProblemDetailsResponse(JSONResponse):
    def __init__(
        self,
        title: str,
        status: int,
        detail: str,
        type_url: str = "about:blank",
        instance: str | None = None,
        **kwargs,
    ):
        content = {
            "type": type_url,
            "title": title,
            "status": status,
            "detail": detail,
            "instance": instance or "",
        }
        content.update(kwargs)
        super().__init__(status_code=status, content=content, media_type="application/problem+json")


# --- Action Cards Helpers ---
# Formats output as structured action card JSON.
def format_chat_history(messages: list[dict]) -> str:
    lines = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, str) and content.strip().startswith("{"):
            try:
                data = json.loads(content)
                if isinstance(data, dict) and "content" in data:
                    content = data["content"]
            except Exception as e:
                logger.warning(f"Exception suppressed: {e}")
        role_label = "User" if role == "user" else "Assistant"
        lines.append(f"{role_label}: {content}")
    return "\n".join(lines)


def format_response(text: str, task_type: str) -> str:
    def extract_code(t: str) -> str:
        from utils.text_helpers import strip_markdown_code_block

        return strip_markdown_code_block(t)

    def detect_language(t: str) -> str:
        if "```" in t:
            lang = t.split("```")[1].splitlines()[0].strip()
            if lang:
                return lang
        return "javascript"

    if "```" in text or task_type in ["code", "completion"]:
        return json.dumps(
            {
                "type": "code",
                "content": extract_code(text),
                "metadata": {
                    "language": detect_language(text),
                    "filename": (
                        "index.html" if "html" in detect_language(text) else "component.tsx"
                    ),
                    "actions": [
                        {"id": "preview", "label": "👁️ Preview", "type": "preview"},
                        {"id": "save", "label": "💾 Save to Project", "type": "save"},
                        {"id": "run", "label": "▶️ Run Code", "type": "run"},
                        {"id": "deploy", "label": "🚀 Deploy", "type": "deploy"},
                    ],
                },
            },
            ensure_ascii=False,
        )

    # বাংলা: লজিক্যাল অপারেটর ঠিক করা হয়েছে - and ব্যবহার করা হয়েছে
    if task_type == "image" or ("generate image" in text.lower()):
        urls = re.findall(
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
            text,
        )
        image_url = urls[0] if urls else text
        return json.dumps(
            {
                "type": "image",
                "content": image_url,
                "metadata": {
                    "actions": [
                        {"id": "download", "label": "⬇️ Download", "type": "save"},
                        {"id": "share", "label": "🔗 Share", "type": "share"},
                    ]
                },
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "type": "text",
            "content": text,
            "metadata": {
                "actions": [
                    {"id": "copy", "label": "📋 Copy", "type": "copy"},
                    {"id": "share", "label": "🔗 Share", "type": "share"},
                ]
            },
        },
        ensure_ascii=False,
    )


# বাংলা মন্তব্য: টেস্ট ও ক্লায়েন্ট উভয়ের সামঞ্জস্যের জন্য /task/execute এবং /api/task/execute উভয় রুটই সাপোর্ট করা হলো
@router.post("/task/execute")
@router.post("/api/task/execute")
async def execute_task(req: TaskRequest):
    import core.services as app_mod

    admin_god = app_mod.admin_god
    model_router = app_mod.model_router
    intent_clf = app_mod.intent_clf

    try:
        admin_god.enforce("execute")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    # --- Prompt-to-Action: Intent Routing ---
    # বাংলা মন্তব্য: ইনপুটকে ক্যাটাগরি রূপে চিহ্নিত করে ফ্রন্টএন্ডকে ডাইনামিক অ্যাকশন টিপ দিচ্ছে
    # R1 FIX: Use LLM-based IntentRouterV2 with regex fallback (env INTENT_ROUTER_MODE=regex to disable)
    from core.intent_router_v2 import intent_router_v2

    prompt_action: PromptAction = await intent_router_v2.route(req.task)

    intent = await anyio.to_thread.run_sync(intent_clf.classify, req.task)

    task_type = req.task_type
    if intent.task_type != "general" and req.task_type == "general":
        task_type = (
            intent.task_type.value if hasattr(intent.task_type, "value") else str(intent.task_type)
        )

    # Build prompt context if chat messages are provided
    prompt = format_unified_chat_prompt(req.task, req.messages)

    # A request's session ID is not an owner. Do not inject shared past
    # experiences or return their responses on this authenticated task route.
    raw = await model_router.async_route_and_generate(
        prompt=prompt,
        task_type=task_type,
        max_cost=req.max_cost,
    )

    if not raw.get("success"):
        return ProblemDetailsResponse(
            title="Task Execution Failed",
            status=502,
            detail=raw.get("error") or "Unknown upstream error",
            type_url="https://supremeai.local/errors/bad-gateway",
            instance="/api/task/execute",
            provider=raw.get("provider"),
            cost=raw.get("cost"),
        )

    # Format output as Action-Oriented JSON string
    formatted_result = format_response(raw.get("text", ""), task_type)

    return TaskResponse(
        success=True,
        result=formatted_result,
        provider=raw.get("provider"),
        cost=raw.get("cost", 0.0),
        action={
            "type": prompt_action.action_type,
            "target": prompt_action.target_module,
            "label": prompt_action.label,
            "icon": prompt_action.icon,
            "confidence": prompt_action.confidence,
            "requires_confirmation": prompt_action.requires_confirmation,
            "payload": prompt_action.payload,
        },
        intent={
            "task_type": (
                intent.task_type.value
                if hasattr(intent.task_type, "value")
                else str(intent.task_type)
            ),
            "confidence": intent.confidence,
        },
    )


@router.get("/api/task/stream")
async def task_stream():
    async def keepalive():
        import asyncio

        try:
            while True:
                yield f"data: {json.dumps({'status': 'alive', 'timestamp': datetime.datetime.now(datetime.UTC).isoformat()})}\n\n"

                await asyncio.sleep(15)
        except asyncio.CancelledError:
            logger.debug("Task stream keepalive cancelled (client disconnected)")
            raise

    return StreamingResponse(
        keepalive(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/chat/prompt-action")
async def prompt_action(req: ActionStreamRequest):
    from core.intent import IntentClassifier
    from core.intent_router_v2 import intent_router_v2

    # R1 FIX: LLM-based intent router (async) with regex fallback
    action = await intent_router_v2.route(req.message)
    intent_clf = IntentClassifier()
    intent = intent_clf.classify(req.message)

    return JSONResponse(
        {
            "action": {
                "type": action.action_type,
                "target": action.target_module,
                "label": action.label,
                "icon": action.icon,
                "confidence": action.confidence,
                "requires_confirmation": action.requires_confirmation,
                "payload": action.payload,
            },
            "intent": {
                "task_type": intent.task_type.value,
                "confidence": intent.confidence,
            },
        }
    )
