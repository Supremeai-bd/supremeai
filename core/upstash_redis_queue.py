from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
from loguru import logger


class UpstashRedisQueue:
    def __init__(
        self,
        rest_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        self.rest_url = (rest_url or os.getenv("UPSTASH_REDIS_REST_URL", "")).rstrip("/")
        self.token = token or os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
        self.timeout = timeout
        self._client = httpx.Client(timeout=self.timeout) if self.rest_url and self.token else None

    @property
    def configured(self) -> bool:
        return bool(self._client)

    def _request(self, *args: str) -> Dict[str, Any]:
        if not self._client:
            raise RuntimeError("UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN are not configured")
        response = self._client.post(
            self.rest_url,
            headers={"Authorization": f"Bearer {self.token}"},
            json=list(args),
        )
        response.raise_for_status()
        return response.json()

    def get(self, key: str) -> Optional[str]:
        if not self.configured:
            return None
        try:
            return self._request("GET", key).get("result")
        except Exception as exc:
            logger.error(f"Upstash Redis GET failed: {exc}")
            return None

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        if not self.configured:
            return False
        try:
            command: list[Any] = ["SET", key, value]
            if ex:
                command.extend(["EX", ex])
            self._request(*command)
            return True
        except Exception as exc:
            logger.error(f"Upstash Redis SET failed: {exc}")
            return False

    def incr(self, key: str) -> Optional[int]:
        if not self.configured:
            return None
        try:
            result = self._request("INCR", key).get("result")
            return int(result) if result is not None else None
        except Exception as exc:
            logger.error(f"Upstash Redis INCR failed: {exc}")
            return None

    def decr(self, key: str) -> Optional[int]:
        if not self.configured:
            return None
        try:
            result = self._request("DECR", key).get("result")
            return int(result) if result is not None else None
        except Exception as exc:
            logger.error(f"Upstash Redis DECR failed: {exc}")
            return None

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
