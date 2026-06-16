from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger
from .crewai_agents import CrewAgent, CrewTask

class SwarmOrchestrator:
    """
    Orchestrates a large swarm of agents executing tasks concurrently.
    Complements SupremeCrew by running independent tasks in parallel.
    """
    def __init__(self, agents: List[CrewAgent], max_workers: int = 5):
        self.agents = agents
        self.max_workers = max_workers

    def execute_swarm(self, tasks: List[CrewTask]) -> Dict[str, str]:
        """Runs tasks concurrently using a ThreadPoolExecutor."""
        logger.info(f"Swarm initiated with {len(self.agents)} agents and {len(tasks)} tasks.")
        results: Dict[str, str] = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {}
            for idx, task in enumerate(tasks):
                # Round robin assignment if tasks exceed agents
                agent = self.agents[idx % len(self.agents)]
                logger.info(f"Assigning task '{task.description[:30]}...' to agent {agent.role}")
                future = executor.submit(agent.execute, task.description, "")
                future_to_task[future] = task

            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    output = future.result()
                    task.output = output
                    results[task.description] = output
                except Exception as exc:
                    logger.error(f"Task '{task.description[:30]}' failed in swarm: {exc}")
                    results[task.description] = f"Error: {exc}"
                    
        return results
