import os
import sys
import sentry_sdk
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
from loguru import logger

from config import settings
from core.universal_rules import UniversalRulesEngine
from core.admin_god import AdminGodLayer
from brain.model_router import ModelRouter
from brain.langgraph_agent import SupremeOrchestrator

logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add(
    os.path.join(os.path.dirname(__file__), "logs", "app.log"),
    rotation="10 MB",
    level="DEBUG",
    encoding="utf-8",
)

if settings.sentry_dsn:
    logger.info("Initializing Sentry SDK...")
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        send_default_pii=True,
        traces_sample_rate=1.0,
    )

app = FastAPI(
    title="SupremeAI 2.0 Master Server",
    description="Universal Self-Learning AI Agent Orchestrator",
    version="2.0.0",
)


@app.get("/sentry-debug")
def trigger_error():
    logger.info("Triggering division by zero for Sentry testing")
    division_by_zero = 1 / 0


rules_engine = UniversalRulesEngine()
admin_god = AdminGodLayer(rules_engine)
model_router = ModelRouter()
orchestrator = SupremeOrchestrator(admin_god, model_router)


class DecisionContext(BaseModel):
    task_type: str
    cost: float
    additional_data: Dict[str, Any] = {}


class TaskRequest(BaseModel):
    task: str
    task_type: str = "general"


class RuleUpdate(BaseModel):
    rules: Dict[str, Any]


def get_admin_auth(authorization: Optional[str] = Header(None)) -> bool:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid token format")
    password = parts[1]
    if not admin_god.verify_admin(password):
        raise HTTPException(status_code=403, detail="Forbidden: Admin validation failed")
    return True


@app.get("/", response_class=HTMLResponse)
def get_customer_ui():
    logger.info("Serving Customer Portal Web UI")
    ui_path = os.path.join(os.path.dirname(__file__), "interfaces", "web_chat", "customer.html")
    if os.path.exists(ui_path):
        with open(ui_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>SupremeAI 2.0 Customer UI file not found.</h3>"


@app.get("/admin/dashboard", response_class=HTMLResponse)
def get_admin_ui():
    logger.info("Serving Admin Dashboard Web UI")
    ui_path = os.path.join(os.path.dirname(__file__), "interfaces", "web_chat", "admin.html")
    if os.path.exists(ui_path):
        with open(ui_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>SupremeAI 2.0 Admin UI file not found.</h3>"


@app.get("/health")
def health_check():
    logger.info("Health check endpoint hit")
    return {
        "status": "online",
        "service": "SupremeAI 2.0",
        "admin_rules_loaded": True,
    }


@app.post("/decision/evaluate")
def evaluate_decision(context: DecisionContext):
    logger.info(f"Evaluating decision context for task: {context.task_type}")
    raw_ctx = {
        "task_type": context.task_type,
        "cost": context.cost,
        **context.additional_data,
    }

    if "direction" in context.task_type or "space" in context.task_type:
        raw_ctx["direction"] = True

    result = admin_god.enforce_rules(raw_ctx)
    return result


@app.get("/admin/rules")
def get_rules(is_admin: bool = Depends(get_admin_auth)):
    logger.info("Admin retrieving rules config")
    return rules_engine.rules


@app.get("/skills")
def list_skills():
    from skills.registry import SkillRegistry

    registry = SkillRegistry()
    return registry.skills.get("skills", {})


@app.post("/admin/rules")
def update_rules(update: RuleUpdate, is_admin: bool = Depends(get_admin_auth)):
    logger.info("Admin updating rules config")
    success = rules_engine.save_rules(update.rules)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save rules")
    return {"message": "Rules updated successfully", "rules": rules_engine.rules}


@app.post("/task/execute")
def execute_task(request: TaskRequest):
    logger.info(f"Executing task endpoint: {request.task}")
    result = orchestrator.execute_task(request.task, request.task_type)
    return result
