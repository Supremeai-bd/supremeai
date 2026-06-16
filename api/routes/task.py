from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class TaskRequest(BaseModel):
    task: str
    task_type: str = "general"
    max_cost: float = 0.01
    admin_token: str | None = None
    schema_name: str | None = None


class TaskResponse(BaseModel):
    success: bool
    result: str | None = None
    provider: str | None = None
    cost: float | None = None
    error: str | None = None


class CompletionRequest(BaseModel):
    prefix: str
    suffix: str
    filePath: str
    language: str
    sessionId: str | None = None


class CompletionResponse(BaseModel):
    success: bool
    suggestions: list[str]


@router.post("/api/chat/completion", response_model=CompletionResponse)
def get_completion(req: CompletionRequest):
    import core.app as app_mod
    model_router = app_mod.model_router

    prompt = (
        f"You are a code completion assistant. Your task is to provide the code that fits between the prefix and suffix.\n"
        f"Do NOT wrap the response in code blocks, markdown, or explain it. Return ONLY the code to be inserted.\n\n"
        f"--- PREFIX ---\n{req.prefix}\n"
        f"--- SUFFIX ---\n{req.suffix}\n"
        f"--- COMPLETION ---"
    )

    raw = model_router.route_and_generate(
        prompt=prompt,
        task_type="completion",
        max_cost=0.005,
    )

    completion_text = raw.get("text", "")
    if completion_text.strip().startswith("```"):
        lines = completion_text.strip().splitlines()
        if len(lines) > 1:
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            completion_text = "\n".join(lines)

    suggestions = [completion_text] if completion_text else []
    return CompletionResponse(success=True, suggestions=suggestions)


from fastapi.responses import JSONResponse

class ProblemDetailsResponse(JSONResponse):
    def __init__(self, title: str, status: int, detail: str, type_url: str = "about:blank", instance: str = None, **kwargs):
        content = {
            "type": type_url,
            "title": title,
            "status": status,
            "detail": detail,
            "instance": instance or "",
        }
        content.update(kwargs)
        super().__init__(status_code=status, content=content, media_type="application/problem+json")


@router.post("/task/execute")
def execute_task(req: TaskRequest):
    import core.app as app_mod
    admin_god = app_mod.admin_god
    model_router = app_mod.model_router
    intent_clf = app_mod.intent_clf

    try:
        admin_god.enforce("execute")
    except PermissionError as exc:
        return ProblemDetailsResponse(
            title="Forbidden Access",
            status=403,
            detail=str(exc),
            type_url="https://supremeai.local/errors/forbidden",
            instance="/task/execute"
        )

    intent = intent_clf.classify(req.task)
    task_type = req.task_type
    if intent.task_type != "general" and req.task_type == "general":
        task_type = intent.task_type.value

    raw = model_router.route_and_generate(
        prompt=req.task,
        task_type=task_type,
        max_cost=req.max_cost,
    )

    if not raw.get("success"):
        return ProblemDetailsResponse(
            title="Task Execution Failed",
            status=502,
            detail=raw.get("error") or "Unknown upstream error",
            type_url="https://supremeai.local/errors/bad-gateway",
            instance="/task/execute",
            provider=raw.get("provider"),
            cost=raw.get("cost")
        )

    return TaskResponse(
        success=True,
        result=raw.get("text"),
        provider=raw.get("provider"),
        cost=raw.get("cost", 0.0),
    )

