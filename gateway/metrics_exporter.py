"""gateway/metrics_exporter.py — Prometheus metrics exporter (#1934).

Stdlib + optional prometheus_client. Exposes gateway HTTP status and request
latency for Prometheus scraping at /metrics. Falls back to a minimal
text format when prometheus_client is unavailable (never raises).
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.request
from collections import defaultdict

_log = logging.getLogger(__name__)
_START_TIME_NS = str(int(time.time() * 1_000_000_000))
_OTLP_THREAD_STARTED = False
_OTLP_LOCK = threading.Lock()

try:
    from core.observability.metrics_registry import normalize_route_path
except ImportError:
    _UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
    _NUM_RE = re.compile(r"/(?:\d+)(?=/|$|\?)")

    def normalize_route_path(path: str) -> str:
        if not path:
            return "/"
        clean = path.split("?")[0]
        clean = _UUID_RE.sub("{id}", clean)
        clean = _NUM_RE.sub("/{id}", clean)
        return clean

try:
    from prometheus_client import (  # type: ignore[import-not-found]
        CONTENT_TYPE_LATEST,
        Counter,
        Histogram,
        generate_latest,
    )

    _PROM_AVAILABLE = True
    _REQUESTS = Counter(
        "gateway_http_requests_total",
        "Total HTTP requests handled by the gateway",
        ["method", "path", "status"],
    )
    _LATENCY = Histogram(
        "gateway_http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "path"],
    )
except Exception:  # pragma: no cover - prometheus_client absent
    _PROM_AVAILABLE = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    _REQUESTS = None  # type: ignore[assignment]
    _LATENCY = None  # type: ignore[assignment]
    generate_latest = None  # type: ignore[assignment]


# In-process fallback counters (used when prometheus_client is absent).
_FALLBACK_COUNTS: dict[tuple[str, str, str], int] = defaultdict(int)
_FALLBACK_LATENCY_SUM: dict[tuple[str, str], float] = defaultdict(float)
_FALLBACK_LATENCY_COUNT: dict[tuple[str, str], int] = defaultdict(int)


def record_request(method: str, path: str, status: int, duration_s: float) -> None:
    """Record a single request. Safe to call from middleware."""
    try:
        norm_path = normalize_route_path(path)
        if _PROM_AVAILABLE:
            _REQUESTS.labels(method=method, path=norm_path, status=str(status)).inc()
            _LATENCY.labels(method=method, path=norm_path).observe(duration_s)
        else:
            _FALLBACK_COUNTS[(method, norm_path, str(status))] += 1
            _FALLBACK_LATENCY_SUM[(method, norm_path)] += duration_s
            _FALLBACK_LATENCY_COUNT[(method, norm_path)] += 1
    except Exception:  # pragma: no cover - never break request path
        pass


def render_metrics() -> tuple[str, str]:
    """Return (body, content_type) for the /metrics endpoint."""
    if _PROM_AVAILABLE:
        try:
            return generate_latest().decode("utf-8", "replace"), CONTENT_TYPE_LATEST
        except Exception:
            pass
    # Minimal text exposition fallback
    lines: list[str] = []
    lines.append("# HELP gateway_http_requests_total Total HTTP requests")
    lines.append("# TYPE gateway_http_requests_total counter")
    for (method, path, status), count in _FALLBACK_COUNTS.items():
        lines.append(
            'gateway_http_requests_total{method="%s",path="%s",status="%s"} %d'
            % (method, path, status, count)
        )
    lines.append("# HELP gateway_http_request_duration_seconds_sum Latency sum (s)")
    lines.append("# TYPE gateway_http_request_duration_seconds summary")
    for (method, path), s in _FALLBACK_LATENCY_SUM.items():
        c = _FALLBACK_LATENCY_COUNT[(method, path)]
        lines.append(
            'gateway_http_request_duration_seconds_sum{method="%s",path="%s"} %.6f'
            % (method, path, s)
        )
        lines.append(
            'gateway_http_request_duration_seconds_count{method="%s",path="%s"} %d'
            % (method, path, c)
        )
    return "\n".join(lines) + "\n", CONTENT_TYPE_LATEST


def reset_for_tests() -> None:
    """Clear in-process fallback state (tests only)."""
    _FALLBACK_COUNTS.clear()
    _FALLBACK_LATENCY_SUM.clear()
    _FALLBACK_LATENCY_COUNT.clear()


def _parse_otlp_headers(raw: str) -> dict[str, str]:
    """Parse comma-separated `Key=Value` OTLP header string."""
    headers: dict[str, str] = {}
    for part in (raw or "").split(","):
        item = part.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            if k.strip():
                headers[k.strip()] = v.strip()
    return headers


def _snapshot_counts_and_latency() -> tuple[list[tuple[str, str, str, int]], list[tuple[str, str, float, int]]]:
    """Read current request counts and latency totals from prometheus_client or fallback."""
    counts: list[tuple[str, str, str, int]] = []
    latencies: list[tuple[str, str, float, int]] = []
    if _PROM_AVAILABLE and _REQUESTS is not None and _LATENCY is not None:
        try:
            for metric in _REQUESTS.collect():
                for sample in metric.samples:
                    if sample.name == "gateway_http_requests_total":
                        lbl = sample.labels
                        counts.append((lbl.get("method", ""), lbl.get("path", ""), lbl.get("status", ""), int(sample.value)))
            sums: dict[tuple[str, str], float] = {}
            cnts: dict[tuple[str, str], int] = {}
            for metric in _LATENCY.collect():
                for sample in metric.samples:
                    key = (sample.labels.get("method", ""), sample.labels.get("path", ""))
                    if sample.name == "gateway_http_request_duration_seconds_sum":
                        sums[key] = float(sample.value)
                    elif sample.name == "gateway_http_request_duration_seconds_count":
                        cnts[key] = int(sample.value)
            for key, s_val in sums.items():
                latencies.append((key[0], key[1], s_val, cnts.get(key, 0)))
            return counts, latencies
        except Exception:
            pass
    for (method, path, status), cnt in list(_FALLBACK_COUNTS.items()):
        counts.append((method, path, status, int(cnt)))
    for (method, path), s_val in list(_FALLBACK_LATENCY_SUM.items()):
        latencies.append((method, path, float(s_val), int(_FALLBACK_LATENCY_COUNT.get((method, path), 0))))
    return counts, latencies


def push_otlp_metrics_once(timeout: float = 5.0) -> bool:
    """Push current gateway HTTP metrics to Grafana Cloud / OTLP HTTP JSON endpoint.

    # বাংলা মন্তব্য: Render বা লোকাল গেটওয়ে থেকে স্ট্যান্ডার্ড লাইব্রেরি দিয়েই Grafana Cloud OTLP-তে মেট্রিক্স পাঠানো হয়।
    """
    endpoint = (os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or "").strip().rstrip("/")
    if not endpoint:
        return False

    counts, latencies = _snapshot_counts_and_latency()
    if not counts and not latencies:
        return False

    now_ns = str(int(time.time() * 1_000_000_000))
    service_name = (os.getenv("OTEL_SERVICE_NAME") or "supremeai-api").strip()

    def _attrs(pairs: list[tuple[str, str]]) -> list[dict[str, object]]:
        return [{"key": k, "value": {"stringValue": v}} for k, v in pairs]

    metrics_payload: list[dict[str, object]] = []
    if counts:
        metrics_payload.append({
            "name": "gateway_http_requests_total",
            "description": "Total HTTP requests handled by the gateway",
            "unit": "1",
            "sum": {
                "aggregationTemporality": 2,
                "isMonotonic": True,
                "dataPoints": [
                    {
                        "attributes": _attrs([("method", m), ("path", p), ("status", st)]),
                        "startTimeUnixNano": _START_TIME_NS,
                        "timeUnixNano": now_ns,
                        "asInt": str(c),
                    }
                    for m, p, st, c in counts
                ],
            },
        })
    if latencies:
        metrics_payload.append({
            "name": "gateway_http_request_duration_seconds_sum",
            "description": "HTTP request latency sum in seconds",
            "unit": "s",
            "sum": {
                "aggregationTemporality": 2,
                "isMonotonic": True,
                "dataPoints": [
                    {
                        "attributes": _attrs([("method", m), ("path", p)]),
                        "startTimeUnixNano": _START_TIME_NS,
                        "timeUnixNano": now_ns,
                        "asDouble": s_val,
                    }
                    for m, p, s_val, _ in latencies
                ],
            },
        })
        metrics_payload.append({
            "name": "gateway_http_request_duration_seconds_count",
            "description": "HTTP request latency observation count",
            "unit": "1",
            "sum": {
                "aggregationTemporality": 2,
                "isMonotonic": True,
                "dataPoints": [
                    {
                        "attributes": _attrs([("method", m), ("path", p)]),
                        "startTimeUnixNano": _START_TIME_NS,
                        "timeUnixNano": now_ns,
                        "asInt": str(c_val),
                    }
                    for m, p, _, c_val in latencies
                ],
            },
        })

    body = json.dumps({
        "resourceMetrics": [{
            "resource": {
                "attributes": _attrs([
                    ("service.name", service_name),
                    ("deployment.environment", os.getenv("ENV", "production")),
                ])
            },
            "scopeMetrics": [{
                "scope": {"name": "supremeai.gateway.metrics_exporter", "version": "1.0.0"},
                "metrics": metrics_payload,
            }],
        }]
    }).encode("utf-8")

    headers = {"Content-Type": "application/json", **_parse_otlp_headers(os.getenv("OTEL_EXPORTER_OTLP_HEADERS") or "")}
    target = endpoint if endpoint.endswith("/v1/metrics") else f"{endpoint}/v1/metrics"
    req = urllib.request.Request(target, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception as exc:
        _log.debug("OTLP metrics push skipped/failed: %s", exc)
        return False


def start_otlp_metrics_background_pusher(interval_s: float = 60.0) -> bool:
    """Start daemon thread to periodically flush OTLP metrics when configured."""
    global _OTLP_THREAD_STARTED
    if os.getenv("PYTEST_CURRENT_TEST") or not (os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or "").strip():
        return False
    with _OTLP_LOCK:
        if _OTLP_THREAD_STARTED:
            return True
        _OTLP_THREAD_STARTED = True

    def _loop() -> None:
        while True:
            time.sleep(max(5.0, interval_s))
            push_otlp_metrics_once()

    t = threading.Thread(target=_loop, name="otlp-metrics-pusher", daemon=True)
    t.start()
    return True
