import os
from typing import Any, Dict, Optional
from datetime import datetime, timezone

import httpx
from loguru import logger


class GCPCloudRunRouter:
    """Routes API calls to the GCP Cloud Run SupremeAI node."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        region: Optional[str] = None,
        service_name: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = (
            base_url
            or os.getenv("GCP_CLOUD_RUN_URL", "")
        ).rstrip("/")
        self.region = region or os.getenv("GCP_REGION", "us-central1")
        self.service_name = service_name or os.getenv("GCP_SERVICE_NAME", "supremeai-api")
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)

    def health_check(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        if not self.base_url:
            return {
                "success": False,
                "provider": "gcp_cloud_run",
                "region": self.region,
                "service_name": self.service_name,
                "status": "unconfigured",
                "error": "GCP_CLOUD_RUN_URL is not configured",
            }

        started = datetime.now(timezone.utc)
        try:
            with httpx.Client(timeout=timeout or self.timeout) as client:
                response = client.get(f"{self.base_url}/health")
            latency_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
            return {
                "success": 200 <= response.status_code < 300,
                "provider": "gcp_cloud_run",
                "region": self.region,
                "service_name": self.service_name,
                "status_code": response.status_code,
                "latency_ms": round(latency_ms, 2),
                "status": "active" if 200 <= response.status_code < 300 else "degraded",
                "data": self._safe_json(response),
            }
        except Exception as exc:
            logger.warning(f"GCP Cloud Run health check failed: {exc}")
            return {
                "success": False,
                "provider": "gcp_cloud_run",
                "region": self.region,
                "service_name": self.service_name,
                "status": "down",
                "error": str(exc),
            }

    def route(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        method: str = "POST",
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not self.base_url:
            return {
                "success": False,
                "provider": "gcp_cloud_run",
                "region": self.region,
                "service_name": self.service_name,
                "error": "GCP_CLOUD_RUN_URL is not configured",
            }

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        started = datetime.now(timezone.utc)
        try:
            with httpx.Client(timeout=timeout or self.timeout) as client:
                response = client.request(method, url, json=payload)
            latency_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
            data = self._safe_json(response)
            return {
                "success": 200 <= response.status_code < 300,
                "provider": "gcp_cloud_run",
                "region": self.region,
                "service_name": self.service_name,
                "status_code": response.status_code,
                "latency_ms": round(latency_ms, 2),
                "data": data,
            }
        except Exception as exc:
            logger.error(f"GCP Cloud Run route failed: {exc}")
            return {
                "success": False,
                "provider": "gcp_cloud_run",
                "region": self.region,
                "service_name": self.service_name,
                "error": str(exc),
            }

    def route_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.route("/api/v1/task/execute", payload)

    def get_config(self) -> Dict[str, Any]:
        return {
            "provider": "gcp_cloud_run",
            "base_url": self.base_url,
            "region": self.region,
            "service_name": self.service_name,
            "timeout": self.timeout,
            "configured": self.is_configured,
        }

    @staticmethod
    def _safe_json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except Exception:
            return {"text": response.text}
