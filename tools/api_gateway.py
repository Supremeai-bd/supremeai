import httpx
from typing import Dict, Any, Optional
from loguru import logger

class APIGateway:
    """
    Universal API Gateway connecting SupremeAI 2.0 to n8n, Make.com, and Zapier.
    """
    def __init__(self):
        self.n8n_url = "http://localhost:5678"
        
    def trigger_n8n_workflow(self, webhook_path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.n8n_url}/{webhook_path.lstrip('/')}"
        logger.info(f"Triggering n8n workflow at {url}")
        try:
            response = httpx.post(url, json=payload, timeout=10.0)
            return {
                "success": response.is_success,
                "status_code": response.status_code,
                "data": response.json() if response.is_success else response.text
            }
        except Exception as e:
            logger.error(f"n8n trigger failed: {e}")
            return {"success": False, "error": str(e)}

    def trigger_make_webhook(self, webhook_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Triggering Make.com webhook")
        try:
            response = httpx.post(webhook_url, json=payload, timeout=10.0)
            return {"success": response.is_success, "response": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}
