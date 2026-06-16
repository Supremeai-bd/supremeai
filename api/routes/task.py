from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class TaskRequest(BaseModel):
    task: str
    task_type: str = "general"
    max_cost: float = 0.01
    admin_token: str | None = None


class TaskResponse(BaseModel):
    success: bool
    result: str | None = None
    provider: str | None = None
    cost: float | None = None
    error: str | None = None


@router.post("/task/execute", response_model=TaskResponse)
def execute_task(req: TaskRequest):
    import core.app as app_mod
    admin_god = app_mod.admin_god
    model_router = app_mod.model_router
    intent_clf = app_mod.intent_clf

    try:
        admin_god.enforce("execute")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

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
        return TaskResponse(
            success=False,
            error=raw.get("error"),
            result=raw.get("text"),
            provider=raw.get("provider"),
            cost=raw.get("cost"),
        )

    return TaskResponse(
        success=True,
        result=raw.get("text"),
        provider=raw.get("provider"),
        cost=raw.get("cost", 0.0),
    )
