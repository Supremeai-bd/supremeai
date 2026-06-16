import os
from typing import Dict, Any
from loguru import logger
from brain.langgraph_agent import SupremeOrchestrator

class TelegramBotHandler:
    """
    Handles Telegram interactions.
    Binds Telegram update payloads to SupremeAI Orchestrator calls.
    """
    def __init__(self, orchestrator: SupremeOrchestrator = None):
        self.orchestrator = orchestrator or SupremeOrchestrator()
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "mock_token")
        
    def handle_message(self, message_text: str, user_id: str) -> str:
        logger.info(f"Telegram Bot received message from {user_id}: '{message_text}'")
        
        # Check command pattern
        if message_text.startswith("/admin"):
            return "Admin command menu: /rules /limit /block /unblock"
        elif message_text.startswith("/rules"):
            return "Current constitutional rules: 5 directions (North, South, East, West, Center)"
        
        # Default fallback: Execute via Master Orchestrator
        task_type = "coding" if "code" in message_text.lower() else "general"
        result = self.orchestrator.execute_task(message_text, task_type)
        return result.get("result", "Sorry, I encountered an error executing that request.")
