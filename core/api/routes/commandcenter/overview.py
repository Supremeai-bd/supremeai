from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.dependencies import get_current_admin
from core.monitoring.logging_config import logger

router = APIRouter(
    prefix="",
    tags=["Command Center"],
    dependencies=[Depends(get_current_admin)],
)


class OverviewResponse(BaseModel):
    active_agents: Optional[int] = None
    active_tasks: Optional[int] = None
    requests_per_second: Optional[float] = None
    latency_p95_ms: Optional[float] = None
    error_rate: Optional[float] = None
    cost_per_hour: Optional[float] = None
    health_percent: Optional[float] = None
    status: str = "stub"
    note: str = (
        "Command Center overview is not yet backed by live telemetry; "
        "all numeric fields are intentionally null rather than fabricated zeros."
    )


@router.get("/overview", response_model=OverviewResponse)
async def get_overview():
    try:
        return OverviewResponse(status="stub")
    except Exception as exc:
        logger.error(f"Command center overview failed: {exc}")
        raise HTTPException(status_code=503, detail="Overview unavailable") from exc
