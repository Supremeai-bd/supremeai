from typing import Any, Dict, Optional
from loguru import logger

from brain.model_router import ModelRouter
from admin.god import AdminGodLayer
from core.intent import IntentClassifier


class SupremeOrchestrator:
    def __init__(
        self,
        admin: Optional[AdminGodLayer] = None,
        model_router: Optional[ModelRouter] = None,
        intent_clf: Optional[IntentClassifier] = None,
        admin_god: Optional[AdminGodLayer] = None,
    ):
        self.admin = admin or admin_god
        self.model_router = model_router or ModelRouter()
        self.intent_clf = intent_clf or IntentClassifier()

    def execute_task(self, task: str, task_type: str = "general") -> Dict[str, Any]:
        try:
            if self.admin:
                self.admin.enforce("execute")
        except PermissionError as exc:
            return {"success": False, "result": f"Blocked: {exc}", "cost": 0.0}

        intent = self.intent_clf.classify(task)
        effective_type = task_type
        if intent.task_type != "general" and task_type == "general":
            effective_type = intent.task_type.value

        raw = self.model_router.route_and_generate(
            prompt=task,
            task_type=effective_type,
            max_cost=0.01,
        )

        if not raw.get("success"):
            return {
                "success": False,
                "result": raw.get("error", "Unknown upstream error"),
                "cost": raw.get("cost", 0.0),
                "provider": raw.get("provider"),
            }

        return {
            "success": True,
            "completed": True,
            "current_step": "completed",
            "result": raw.get("text", ""),
            "cost": raw.get("cost", 0.0),
            "provider": raw.get("provider"),
        }
