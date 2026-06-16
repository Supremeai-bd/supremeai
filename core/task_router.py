from typing import Dict, Any
from loguru import logger

class TaskRouter:
    """
    Task Router for SupremeAI 2.0.
    Analyzes intent of user requests to map them to appropriate modules/agents.
    """
    def __init__(self):
        pass
        
    def analyze_and_route(self, task_description: str) -> Dict[str, Any]:
        logger.info(f"Analyzing task: '{task_description}'")
        desc_lower = task_description.lower()
        
        # Simple intent analysis
        if any(w in desc_lower for w in ["code", "python", "java", "script", "program", "develop"]):
            return {"task_type": "coding", "handler": "crewai_agents", "cost_limit": 0.05}
        elif any(w in desc_lower for w in ["image", "picture", "draw", "generate logo", "photograph"]):
            return {"task_type": "image_generation", "handler": "skill_marketplace", "cost_limit": 0.01}
        elif any(w in desc_lower for w in ["scrape", "crawl", "web page", "html"]):
            return {"task_type": "web_scraping", "handler": "browser_agent", "cost_limit": 0.02}
        elif any(w in desc_lower for w in ["system", "terminal", "run command", "files", "folder"]):
            return {"task_type": "system_control", "handler": "computer_agent", "cost_limit": 0.05}
        else:
            return {"task_type": "general", "handler": "langgraph_agent", "cost_limit": 0.01}
