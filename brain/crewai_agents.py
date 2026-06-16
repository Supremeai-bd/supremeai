from typing import List, Dict, Any, Callable
from loguru import logger
from .model_router import ModelRouter

from core.admin_god import AdminGodLayer

class CrewAgent:
    """Represents a specialized agent with a role, goal, and backstory."""
    def __init__(self, role: str, goal: str, backstory: str, model_router: ModelRouter = None, admin_god: AdminGodLayer = None):
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.model_router = model_router or ModelRouter()
        self.admin_god = admin_god or AdminGodLayer()
        
    def execute(self, task_description: str, context: str = "") -> str:
        # Routes coding tasks to coding models, general tasks to general models
        task_type = "coding" if "code" in task_description or "program" in task_description else "general"
        
        # Enforce rules check
        decision_context = {
            "task_type": task_type,
            "cost": 0.0,
            "task_description": task_description,
        }
        validated_ctx = self.admin_god.enforce_rules(decision_context)
        if validated_ctx.get("blocked"):
            logger.warning(f"Crew Agent '{self.role}' blocked: {validated_ctx.get('reason')}")
            return f"Blocked by Admin: {validated_ctx.get('reason')}"
            
        backstory_with_rules = self.admin_god.inject_prompt_constraints(self.backstory)
        
        prompt = (
            f"You are a member of a crew working towards a goal.\n"
            f"Your Role: {self.role}\n"
            f"Your Goal: {self.goal}\n"
            f"Backstory: {backstory_with_rules}\n"
            f"Previous Context: {context}\n"
            f"Current Task: {task_description}\n"
            f"Deliver your best professional response."
        )
        logger.info(f"Crew Agent '{self.role}' executing task...")
        res = self.model_router.route_and_generate(prompt, task_type=task_type)
        return res.get("text", "")

class CrewTask:
    """Represents a specific task to be performed by a CrewAgent."""
    def __init__(self, description: str, agent: CrewAgent):
        self.description = description
        self.agent = agent
        self.output: str = ""

class SupremeCrew:
    """Orchestrates a collaborative crew of agents executing tasks sequentially."""
    def __init__(self, agents: List[CrewAgent], tasks: List[CrewTask]):
        self.agents = agents
        self.tasks = tasks
        
    def kickoff(self) -> str:
        context = ""
        logger.info(f"Starting Crew execution with {len(self.agents)} agents and {len(self.tasks)} tasks.")
        for i, task in enumerate(self.tasks):
            logger.info(f"Running task {i+1}/{len(self.tasks)}: {task.description[:50]}...")
            task.output = task.agent.execute(task.description, context)
            context += f"\n[Task Output from {task.agent.role}]: {task.output}\n"
        return context
