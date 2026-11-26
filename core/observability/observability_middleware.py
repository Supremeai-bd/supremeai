from __future__ import annotations

import os
import time
import uuid

from core.monitoring.logging_config import logger
from core.observability.metrics_registry import normalize_route_path, record_error, record_request, record_request_duration
from core.observability.telemetry import trace_span


# বাংলা মন্তব্য: লাইভনেস/রেডিনেস প্রোব (Render health check, uptime monitor) প্রতি ~৪ সেকেন্ডে আসে।
# এগুলো evolution_logs-এ লিখলে দিনে ~২০k অর্থহীন সারি জমে (২০২৬-১১-২৬ প্রোড ডেটা: ৪৭,১৬১ সারির
# ৯৬.৭%-ই "GET /health/live - 200")। সফল (<400) প্রোব শুধু Prometheus মেট্রিকে থাকবে;
# ব্যর্থ প্রোব (>=400) আগের মতোই অডিট লগ ও PostHog-এ যাবে — যাতে আউটেজ সিগন্যাল হারিয়ে না যায়।
_PROBE_PATHS = frozenset(
    {
        "/health",
        "/healthz",
        "/health/live",
        "/health/ready",
        "/api/v1/health",
        "/api/v1/health/live",
        "/api/v1/health/ready",
    }
)


def should_persist_request_log(path: str, status_code: int) -> bool:
    """Return False for successful health-probe hits (metrics-only), True otherwise."""
    # বাংলা মন্তব্য: query string ও শেষের '/' বাদ দিয়ে তুলনা, যাতে "/health/live/" বা "?x=1" ফসকে না যায়
    clean = (path or "").split("?", 1)[0].rstrip("/") or "/"
    return not (clean in _PROBE_PATHS and status_code < 400)


class ObservabilityMiddleware:
    def __init__(self, app) -> None:
        self.app = app

        # Redis traffic monitoring is expensive. We sample and bound background tasks.
        # Long-run safety: avoid cardinality/cost explosions and unbounded task growth.
        self._redis_traffic_sampling_rate = float(
            os.getenv("REDIS_TRAFFIC_METRICS_SAMPLING_RATE", "0.05")
        )
        self._redis_traffic_max_background_tasks = int(
            os.getenv("REDIS_TRAFFIC_MAX_BACKGROUND_TASKS") or "50"
        )
        self._redis_metric_fail_count = 0

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path == "/metrics":
            await self.app(scope, receive, send)
            return

        headers = scope.get("headers", [])
        trace_id = ""
        user_id = "anonymous_api_user"
        tenant_id = "unknown"

        for k, v in headers:
            if k.lower() in (b"x-trace-id", b"traceparent"):
                trace_id = v.decode("utf-8", errors="replace")
            elif k.lower() == b"x-user-id":
                user_id = v.decode("utf-8", errors="replace")
            elif k.lower() in (b"x-tenant-id", b"x-workspace-id"):
                tenant_id = v.decode("utf-8", errors="replace")

        from starlette.requests import Request

        request = Request(scope)
        authenticated_user = (
            getattr(request.state, "user", None) if hasattr(request, "state") else None
        )
        if not authenticated_user and "user" in scope and isinstance(scope["user"], dict):
            authenticated_user = scope["user"]
        if authenticated_user:
            user_id = authenticated_user.get("sub") or authenticated_user.get("user_id") or user_id
            if not tenant_id or tenant_id == "unknown":
                tenant_id = authenticated_user.get("tenant_id") or tenant_id

        # Use OpenTelemetry trace_id if available, otherwise generate or use header
        try:
            from opentelemetry import trace as otel_trace

            current_span = otel_trace.get_current_span()
            if current_span and current_span.get_span_context().is_valid:
                trace_id = f"{current_span.get_span_context().trace_id:032x}"
        except ImportError:
            import logging

            logging.getLogger(__name__).warning("Silenced error in except-pass block")

        if not trace_id:
            trace_id = f"00-{uuid.uuid4().hex}-0000000000000001-01"

        if not hasattr(self.app, "_background_tasks"):
            self.app._background_tasks = set()

        method = scope.get("method", "GET")
        started = time.perf_counter()
        status_code = 500
        error_type = None

        async def custom_send(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                start_headers = list(message.get("headers", []))
                start_headers.append((b"X-Trace-ID", trace_id.encode("utf-8")))
                start_headers.append((b"traceparent", trace_id.encode("utf-8")))
                message["headers"] = start_headers
            await send(message)

        norm_path = normalize_route_path(path)

        try:
            with trace_span(
                f"{method} {norm_path}",
                attributes={
                    "http.method": method,
                    "http.route": norm_path,
                    "http.url": f"{scope.get('scheme', 'http')}://{scope.get('server', ('localhost', 80))[0]}{path}",
                    "trace_id": trace_id,
                    "enduser.id": user_id,
                    "tenant.id": tenant_id,
                },
                kind="server",
            ):
                await self.app(scope, receive, custom_send)
        except Exception as exc:
            error_type = type(exc).__name__
            record_error(error_type, path)
            raise
        finally:
            duration = time.perf_counter() - started

            record_request(method, path, status_code)
            record_request_duration(method, path, duration)

            # বাংলা মন্তব্য: সফল হেলথ-প্রোব হলে PostHog ও evolution_logs দুটোই স্কিপ —
            # Prometheus মেট্রিক (record_request/record_request_duration) উপরে আগেই রেকর্ড হয়েছে।
            persist_request_log = should_persist_request_log(path, status_code)

            if persist_request_log:
                try:
                    from core.observability.posthog_client import posthog_client

                    posthog_client.capture(
                        distinct_id=user_id,
                        event="api_request",
                        properties={
                            "path": path,
                            "method": method,
                            "status_code": status_code,
                            "duration": duration,
                        },
                    )
                except Exception as exc:
                    logger.debug(f"PostHog capture failed in observability middleware: {exc}")

            # --- START REDIS TRAFFIC MONITORING ---
            try:
                import asyncio
                import json

                # Sampling: every Nth request will be written to Redis.
                if self._redis_traffic_sampling_rate <= 0:
                    redis_enabled = False
                else:
                    threshold = int(self._redis_traffic_sampling_rate * 10000)
                    redis_enabled = (uuid.uuid4().int % 10000) < threshold

                if redis_enabled:
                    from core.cache.redis_manager import redis_manager

                if redis_enabled and redis_manager and redis_manager.client:
                    # Bound background tasks count to avoid memory pressure.
                    bg_tasks = len(getattr(self.app, "_background_tasks", set()))
                    if bg_tasks < self._redis_traffic_max_background_tasks:
                        now = int(time.time())
                        minute_key = f"traffic:live:{now // 60}"

                        async def push_traffic() -> None:
                            try:
                                payload = {
                                    "method": method,
                                    "path": path,
                                    "status": status_code,
                                    "duration": duration,
                                    "error": error_type,
                                }
                                await redis_manager.client.lpush(minute_key, json.dumps(payload))
                                await redis_manager.client.expire(
                                    minute_key, 86400
                                )  # 24 hours retention
                            except Exception as redis_err:
                                self._redis_metric_fail_count += 1
                                if (
                                    self._redis_metric_fail_count == 1
                                    or self._redis_metric_fail_count % 10 == 0
                                ):
                                    logger.warning(
                                        "[Observability] Redis traffic metric write failed "
                                        "(total failures: %s): %r",
                                        self._redis_metric_fail_count,
                                        redis_err,
                                    )

                        task = asyncio.create_task(push_traffic())
                        self.app._background_tasks.add(task)
                        task.add_done_callback(self.app._background_tasks.discard)
            except Exception as e:
                logger.debug(f"Redis traffic monitoring failed: {e}")
            # --- END REDIS TRAFFIC MONITORING ---

            try:
                from core.database.supabase_client import db

                if persist_request_log and db.client:
                    db.append_evolution_log(
                        {
                            "event_type": "api_request",
                            "description": f"{method} {path} - {status_code}",
                            "metadata": {
                                "tenant_id": tenant_id,
                                "user_id": user_id,
                                "trace_id": trace_id,
                                "path": path,
                                "method": method,
                                "status_code": status_code,
                                "duration": duration,
                            },
                        }
                    )
            except Exception as exc:
                logger.debug(f"Evolution log persistence failed in observability middleware: {exc}")

            # --- START SENTINEL AGENT EVENT TRIGGER ---
            from core.utils.environment import is_test_environment

            if not is_test_environment() and (status_code >= 500 or duration > 3.0):
                try:
                    import asyncio

                    from core.sentinel_agent import sentinel

                    event_type = "high_latency" if duration > 3.0 else "internal_server_error"
                    details = (
                        f"Endpoint {method} {path} resulted in {status_code} in {duration:.2f}s."
                    )
                    if error_type:
                        details += f" Exception: {error_type}"

                    task = asyncio.create_task(sentinel.trigger_event(event_type, details))
                    self.app._background_tasks.add(task)
                    task.add_done_callback(self.app._background_tasks.discard)
                except Exception as e:
                    logger.debug(f"Sentinel Agent event trigger failed: {e}")
            # --- END SENTINEL AGENT EVENT TRIGGER ---
