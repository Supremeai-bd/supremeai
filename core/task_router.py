from typing import Dict, Any
from loguru import logger
import httpx
import asyncio

class TaskRouter:
    """
    Task Router for SupremeAI 2.0.
    Analyzes intent of user requests to map them to appropriate modules/agents.
    """

    def __init__(self) -> None:
        pass

    def process_requirement(self, task_description: str, max_cost: float = 0.01) -> Dict[str, Any]:
        logger.info(f"Processing requirement: '{task_description}' max_cost={max_cost}")
        desc_lower = task_description.lower()
        prompt_len = len(task_description)

        token_budget = "small" if prompt_len <= 500 else "medium" if prompt_len <= 2000 else "large"
        modality = "text"
        if any(w in desc_lower for w in ["image", "picture", "photo", "vision"]):
            modality = "image"
        if any(w in desc_lower for w in ["video", "voice", "audio", "speech"]):
            modality = "multimodal"

        if "code" in desc_lower or "program" in desc_lower or "script" in desc_lower:
            task_type = "coding"
        elif "image" in desc_lower or "picture" in desc_lower or "photo" in desc_lower or "draw" in desc_lower or "generate an image" in desc_lower:
            task_type = "image_generation"
        elif "scrape" in desc_lower or "crawl" in desc_lower:
            task_type = "web_scraping"
        elif "system" in desc_lower or "terminal" in desc_lower:
            task_type = "system_control"
        else:
            task_type = "general"

        reasoning_depth = "low"
        if any(w in desc_lower for w in ["math", "reasoning", "analyze", "research"]):
            reasoning_depth = "high"
        elif modality != "text":
            reasoning_depth = "medium"

        fallback_handler = "n8n_webhook"
        if task_type != "general":
            if task_type == "coding":
                fallback_handler = "crewai_agents"
            elif task_type == "web_scraping":
                fallback_handler = "browser_agent"
            elif task_type == "system_control":
                fallback_handler = "computer_agent"

        return {
            "task_type": task_type,
            "handler": fallback_handler,
            "cost_limit": max_cost,
            "token_budget": token_budget,
            "reasoning_depth": reasoning_depth,
            "modality": modality,
        }

    def analyze_and_route(self, task_description: str, max_cost: float = 0.01) -> Dict[str, Any]:
        return self.process_requirement(task_description, max_cost=max_cost)

    async def trigger_external_skill(self, webhook_url: str, payload: Dict[str, Any], retries: int = 3) -> Dict[str, Any]:
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
                    await asyncio.sleep(2 ** attempt)
