from typing import Dict, Any
from loguru import logger
import httpx
import asyncio

class TaskRouter:
    """
    Task Router for SupremeAI 2.0.
    Analyzes intent of user requests to map them to appropriate modules/agents.
    """
    def __init__(self):
        pass
        
    def analyze_and_route(self, task_description: str) -> Dict[str, Any]:
        """
        Analyzes intent and routes to either internal agents 
        or external automation webhooks (n8n/Make).
        """
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
            # Default to an automation workflow if no internal handler matches
            return {"task_type": "automation_workflow", "handler": "n8n_webhook", "cost_limit": 0.01}

    async def trigger_external_skill(self, webhook_url: str, payload: Dict[str, Any], retries: int = 3) -> Dict[str, Any]:
        """
        Triggers an external automation skill (like an n8n workflow).
        Includes basic retry logic for cloud stability.
        """
        async with httpx.AsyncClient() as client:
            for attempt in range(retries):
                try:
                    response = await client.post(webhook_url, json=payload, timeout=30.0)
                    response.raise_for_status()
                    logger.success(f"Skill triggered on attempt {attempt + 1}")
                    return response.json()
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt == retries - 1:
                        logger.error("All retry attempts failed.")
                        return {"success": False, "error": "External service unavailable"}
                    await asyncio.sleep(2 ** attempt) # Exponential backoff
