from typing import Dict, Any, List
from loguru import logger
from config import settings
from core.admin_god import AdminGodLayer
from brain.model_router import ModelRouter


class AgentState:
    """Represents the execution state of a task."""
    def __init__(self, task: str):
        self.task = task
        self.history: List[Dict[str, Any]] = []
        self.current_step: str = "init"
        self.cost_accumulated: float = 0.0
        self.variables: Dict[str, Any] = {}
        self.completed: bool = False
        self.result: str = ""


class SupremeOrchestrator:
    """
    State-machine based master agent orchestrator.
    """
    def __init__(self, admin_god: AdminGodLayer | None = None, model_router: ModelRouter | None = None):
        self.admin_god = admin_god or AdminGodLayer()
        self.model_router = model_router or ModelRouter()

    def execute_task(self, task: str, task_type: str = "general") -> Dict[str, Any]:
        logger.info(f"Orchestrating task: {task} (type: {task_type})")
        state = AgentState(task)

        state.current_step = "admin_check"
        decision_context = {
            "task_type": task_type,
            "cost": state.cost_accumulated,
            "task_description": task,
        }

        validated_ctx = self.admin_god.enforce_rules(decision_context)
        if validated_ctx.get("blocked"):
            state.completed = True
            state.result = f"Blocked by Admin God: {validated_ctx.get('reason')}"
            logger.warning(f"Task blocked: {state.result}")
            return self._format_response(state)

        state.current_step = "reasoning"
        system_prompt = "You are SupremeAI 2.0, the universal self-learning agent."
        full_system_prompt = self.admin_god.inject_prompt_constraints(system_prompt)
        full_prompt = f"{full_system_prompt}\n\nTask: {task}"

        model_res = self.model_router.route_and_generate(
            prompt=full_prompt,
            task_type=task_type,
            max_cost=0.01,
        )

        state.cost_accumulated += model_res.get("cost", 0.0)
        state.result = model_res.get("text", "")
        state.completed = True
        state.current_step = "completed"
        return self._format_response(state)

    def _format_response(self, state: AgentState) -> Dict[str, Any]:
        return {
            "task": state.task,
            "completed": state.completed,
            "current_step": state.current_step,
            "cost": state.cost_accumulated,
            "result": state.result,
        }
