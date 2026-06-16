from typing import List, Dict, Any, Callable
from loguru import logger
from .model_router import ModelRouter

class CrewAgent:
    """Represents a specialized agent with a role, goal, and backstory."""
    def __init__(self, role: str, goal: str, backstory: str, model_router: ModelRouter = None):
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.model_router = model_router or ModelRouter()
        
    def execute(self, task_description: str, context: str = "") -> str:
        prompt = (
            f"You are a member of a crew working towards a goal.\n"
            f"Your Role: {self.role}\n"
            f"Your Goal: {self.goal}\n"
            f"Backstory: {self.backstory}\n"
            f"Previous Context: {context}\n"
            f"Current Task: {task_description}\n"
            f"Deliver your best professional response."
        )
        logger.info(f"Crew Agent '{self.role}' executing task...")
        # Routes coding tasks to coding models, general tasks to general models
        task_type = "coding" if "code" in task_description or "program" in task_description else "general"
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
