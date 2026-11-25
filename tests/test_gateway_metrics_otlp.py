"""Tests for gateway /metrics endpoint and Grafana OTLP metrics exporter."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from gateway.metrics_exporter import push_otlp_metrics_once, record_request, reset_for_tests
from gateway.service.app import app


def test_gateway_metrics_endpoint_exposes_prometheus_text():
    """GET /metrics should return 200 and Prometheus-formatted gateway counters."""
    reset_for_tests()
    client = TestClient(app)
    health_resp = client.get("/healthz")
    assert health_resp.status_code == 200

    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert "gateway_http_requests_total" in metrics_resp.text


def test_gateway_metrics_token_guard(monkeypatch):
    """GET /metrics should enforce METRICS_SCRAPE_TOKEN when configured."""
    monkeypatch.setenv("METRICS_SCRAPE_TOKEN", "secret-scrape-token")
    client = TestClient(app)

    assert client.get("/metrics").status_code == 403
    assert client.get("/metrics", headers={"x-metrics-token": "secret-scrape-token"}).status_code == 200


def test_push_otlp_metrics_once_sends_valid_payload(monkeypatch):
    """push_otlp_metrics_once should POST valid OTLP JSON to /v1/metrics."""
    reset_for_tests()
    record_request("GET", "/healthz", 200, 0.012)

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://otlp.example.com/otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "Authorization=Basic dGVzdDp0b2tlbg==")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "supremeai-api")

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
        ok = push_otlp_metrics_once()

    assert ok is True
    req = mock_open.call_args.args[0]
    assert req.full_url == "https://otlp.example.com/otlp/v1/metrics"
    assert req.headers.get("Authorization") == "Basic dGVzdDp0b2tlbg=="
    payload = json.loads(req.data.decode("utf-8"))
    metrics = payload["resourceMetrics"][0]["scopeMetrics"][0]["metrics"]
    names = {m["name"] for m in metrics}
    assert "gateway_http_requests_total" in names
    assert "gateway_http_request_duration_seconds_sum" in names
    assert "gateway_http_request_duration_seconds_count" in names
