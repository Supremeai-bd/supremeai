import inspect
import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

class ApiRouter:
    def __init__(self) -> None:
        self._handlers: Dict[str, Callable] = {}
        self._signatures: Dict[str, Any] = {}

    def register(self, capability: str, handler: Callable) -> None:
        self._handlers[capability] = handler
        try:
            self._signatures[capability] = inspect.signature(handler)
        except (ValueError, TypeError):
            self._signatures[capability] = None

    def capabilities(self) -> Dict[str, Optional[Any]]:
        return dict(self._signatures)

    def supports(self, capability: str) -> bool:
        return capability in self._handlers

    def dispatch(self, capability: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        handler = self._handlers.get(capability)
        if not handler:
            raise KeyError(f"No handler registered for capability '{capability}'")
        try:
            return handler(payload)
        except Exception as exc:
            logger.exception("Dispatch failed for capability=%s", capability)
            return {"success": False, "error": str(exc), "capability": capability}
