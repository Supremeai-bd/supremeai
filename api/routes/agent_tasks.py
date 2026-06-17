from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
from loguru import logger

from brain.agent_departments import AgentDepartment
from brain.model_router import ModelRouter
from brain.langgraph_agent import SupremeOrchestrator
from brain.autonomous_agent import AutonomousAgent
from core.rbac import RoleBasedAccessControl
from core.generation_monitor import GenerationMonitor

agent_router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

model_router = ModelRouter()
orchestrator = SupremeOrchestrator()
autonomous_agent = AutonomousAgent()
agent_department = AgentDepartment(model_router)
rbac = RoleBasedAccessControl()
monitor = GenerationMonitor()


class AgentExecuteRequest(BaseModel):
    task: str
    task_type: str = "general"
    role: Optional[str] = None
    department: Optional[str] = None
    autonomous: bool = False
    user_context: Optional[Dict[str, Any]] = None


class AgentExecuteResponse(BaseModel):
    success: bool
    output: Optional[str] = None
    role: Optional[str] = None
    provider: Optional[str] = None
    cost: Optional[float] = None
    errors: Optional[list] = None


def _user_context(request: Request) -> Dict[str, Any]:
    return {
        "ip": request.client.host if request.client else None,
        "source": request.headers.get("X-Source"),
    }


@agent_router.post("/execute", response_model=AgentExecuteResponse)
async def execute_agent(request: Request, body: AgentExecuteRequest):
    user = _user_context(request)
    if body.autonomous:
        run = autonomous_agent.run(body.task, body.task_type)
        monitor.track_agent_call(prompt=body.task, provider="autonomous")
        return AgentExecuteResponse(
            success=run.get("run", {}).get("success", False),
            output=run.get("run", {}).get("output"),
            role="autonomous",
            cost=0.0,
            errors=run.get("run", {}).get("errors") or [],
        )

    if body.department:
        result = agent_department.execute(body.department, body.task, body.task_type)
        monitor.track_agent_call(prompt=body.task, provider=result.get("provider", "unknown"))
        return AgentExecuteResponse(
            success=result.get("success", False),
            output=result.get("output"),
            role=result.get("role"),
            provider=result.get("provider"),
            cost=result.get("cost"),
            errors=[result.get("error")] if result.get("error") else [],
        )

    result = orchestrator.execute_task(body.task, body.task_type)
    monitor.track_agent_call(prompt=body.task, provider=result.get("provider", "unknown"))
    return AgentExecuteResponse(
        success=result.get("success", False),
        output=result.get("result"),
        role="orchestrator",
        provider=result.get("provider"),
        cost=result.get("cost"),
        errors=[result.get("result")] if not result.get("success") else [],
    )


@agent_router.get("/roles")
async def list_agent_roles():
    return {"roles": agent_department.list_roles()}


@agent_router.get("/monitor/latency")
async def agent_latency_summary():
    summary = monitor.latency_summary()
    return JSONResponse(content=summary)
