from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from core.monitoring.logging_config import logger
from core.orchestration.agent_orchestrator import async_task_manager

# AUDIT FIX (2026-11-13, HIGH — task results readable by anyone):
# /api/task/{task_id} and /api/task/_stats had no auth dependency — any caller
# (even anonymous) could poll arbitrary task ids and read their results, and
# _stats exposed pool internals. Router-level token auth restored. Note:
# per-task OWNERSHIP still needs the TaskRecord user linkage (tracked as
# follow-up in the audit report, E10) — this change stops anonymous reads.
try:
    from core.api.deps import get_current_admin, get_current_user_token
except ImportError:
    try:
        from api.deps import get_current_admin, get_current_user_token
    except ImportError:  # pragma: no cover — CI bootstrap only
        async def get_current_user_token() -> str:
            return "mock-token"

        async def get_current_admin() -> str:
            return "mock-admin"


router = APIRouter(
    prefix="/api/task",
    tags=["async-task"],
    dependencies=[Depends(get_current_user_token)],
)


class TaskResponse(BaseModel):
    task_id: str
    status: str
    progress: int = 0
    result: str | None = None
    error: str | None = None


@router.get("/{task_id}")
def get_task_status(task_id: str, request: Request) -> TaskResponse:
    # Issue #685 (Domain 15): high-traffic polling router — log lookups with the
    # request correlation id (also auto-injected into loguru records by
    # SupremeContextMiddleware's contextualize scope).
    correlation_id = getattr(request.state, "correlation_id", "")
    task = async_task_manager.get_task(task_id)
    if task:
        logger.info(
            "[task.status] task_id=%s status=%s correlation_id=%s",
            task_id,
            task["status"],
            correlation_id,
        )
        return TaskResponse(
            task_id=task["task_id"],
            status=task["status"],
            progress=task.get("progress", 0),
            result=task.get("result"),
            error=task.get("error"),
        )
    logger.warning("[task.status] task_id=%s not_found correlation_id=%s", task_id, correlation_id)
    return TaskResponse(task_id=task_id, status="not_found", progress=0)


@router.get("/_stats")
def get_task_stats(_: dict = Depends(get_current_admin)) -> dict[str, Any]:
    """Pool statistics — admin-only (AUDIT FIX 2026-11-13: was unauthenticated)."""
    return async_task_manager.get_stats()
