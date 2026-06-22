from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VPNRotator:
    def __init__(self, endpoints: Optional[List[str]] = None, current_index: int = 0) -> None:
        self.endpoints = [item.strip() for item in (endpoints or []) if item.strip()]
        self.current_index = current_index
        self.history: List[Dict[str, Any]] = []
        self.max_history = int(os.getenv("VPN_ROTATOR_HISTORY", "100"))

    def _record(self, event: str, payload: Dict[str, Any]) -> None:
        entry = {"event": event, "ts": time.time(), **payload}
        self.history.append(entry)
        self.history = self.history[-self.max_history:]

    def rotate(self) -> Dict[str, Any]:
        reason = "ok"
        if not self.endpoints:
            return {"rotated": False, "endpoint": None, "reason": "No endpoints configured", "next_index": 0}

        endpoint = self.endpoints[self.current_index % len(self.endpoints)]
        previous = self.endpoints[(self.current_index - 1) % len(self.endpoints)]
        self.current_index = (self.current_index + 1) % len(self.endpoints)
        result = {"rotated": True, "endpoint": endpoint, "previous": previous, "next_index": self.current_index}
        if len(self.endpoints) <= 1 and previous == endpoint:
            reason = "single_endpoint_noop"
            result["reason"] = reason
            self._record(reason, result)
            return result
        self._record("rotate", result)
        return result

    def current(self) -> Optional[str]:
        if not self.endpoints:
            return None
        return self.endpoints[self.current_index % len(self.endpoints)]

    def rotate_agent(self, agent_id: str) -> Dict[str, Any]:
        previous = "auto"
        if self.endpoints:
            previous = self.endpoints[(self.current_index - 1) % len(self.endpoints)]
        rotation = self.rotate()
        result = {
            "agent_id": agent_id,
            "rotated": rotation.get("rotated", False),
            "endpoint": rotation.get("endpoint"),
            "previous": previous,
        }
        reason = rotation.get("reason")
        if reason:
            result["reason"] = reason
        logger.info("rotate_agent called agent=%s rotated=%s", agent_id, result["rotated"])
        return result

    def configure_endpoints(self, endpoints: List[str]) -> Dict[str, Any]:
        previous_count = len(self.endpoints)
        self.endpoints = [item.strip() for item in endpoints if item.strip()]
        self.current_index = 0
        result = {"configured": True, "count": len(self.endpoints), "previous_count": previous_count}
        self._record("configure", result)
        logger.info("VPN endpoints configured with %d endpoints", len(self.endpoints))
        return result

    def add_endpoint(self, endpoint: str) -> Dict[str, Any]:
        endpoint = endpoint.strip()
        if not endpoint:
            return {"added": False, "reason": "empty endpoint"}
        if endpoint in self.endpoints:
            return {"added": False, "reason": "duplicate endpoint", "endpoint": endpoint}
        self.endpoints.append(endpoint)
        result = {"added": True, "endpoint": endpoint, "count": len(self.endpoints)}
        self._record("add", result)
        logger.info("Added VPN endpoint: %s", endpoint)
        return result

    def history_since(self, since: Optional[float] = None) -> List[Dict[str, Any]]:
        if since is None:
            return list(self.history)
        return [entry for entry in self.history if entry.get("ts", 0.0) >= float(since)]

    def status(self) -> Dict[str, Any]:
        return {
            "configured": bool(self.endpoints),
            "count": len(self.endpoints),
            "current_index": self.current_index,
            "current_endpoint": self.current(),
            "history_count": len(self.history),
        }
