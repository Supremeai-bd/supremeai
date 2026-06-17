from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VPNRotator:
    def __init__(self, endpoints: Optional[List[str]] = None, current_index: int = 0) -> None:
        self.endpoints = endpoints or []
        self.current_index = current_index

    def rotate(self) -> Dict[str, Any]:
        if not self.endpoints:
            return {"rotated": False, "endpoint": None, "reason": "No endpoints configured"}
        endpoint = self.endpoints[self.current_index % len(self.endpoints)]
        self.current_index += 1
        return {"rotated": True, "endpoint": endpoint, "next_index": self.current_index % len(self.endpoints)}

    def current(self) -> Optional[str]:
        if not self.endpoints:
            return None
        return self.endpoints[self.current_index % len(self.endpoints)]

    def rotate_agent(self, agent_id: str) -> Dict[str, Any]:
        rotation = self.rotate()
        result = {
            "agent_id": agent_id,
            "rotated": rotation.get("rotated", False),
            "endpoint": rotation.get("endpoint"),
        }
        reason = rotation.get("reason")
        if reason:
            result["reason"] = reason
        logger.info("rotate_agent called for agent=%s rotated=%s", agent_id, result["rotated"])
        return result
