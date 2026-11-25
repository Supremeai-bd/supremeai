"""OTLP traces endpoint resolution (pattern audit P2.1, 2026-11-25).

gateway/metrics_exporter.py appends /v1/metrics to the OTEL_EXPORTER_OTLP_ENDPOINT
base (pinned by tests/test_gateway_metrics_otlp.py). The trace exporter in
core/observability/telemetry.py must apply the same spec rule for /v1/traces —
OTLPSpanExporter(endpoint=...) uses its value verbatim, so a bare base URL
POSTs to the wrong path and Grafana's OTLP gateway drops every span.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.observability.telemetry import resolve_otlp_traces_endpoint


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        # Grafana Cloud OTLP convention: base endpoint, signal path appended.
        (
            "https://otlp-gateway.grafana.net/otlp",
            "https://otlp-gateway.grafana.net/otlp/v1/traces",
        ),
        # Trailing slash must not produce a double slash.
        ("https://otlp.example.com/otlp/", "https://otlp.example.com/otlp/v1/traces"),
        # An explicit full signal path passes through untouched.
        ("https://otlp.example.com/v1/traces", "https://otlp.example.com/v1/traces"),
        # Whitespace tolerance.
        (
            "  https://otlp.example.com/otlp  ",
            "https://otlp.example.com/otlp/v1/traces",
        ),
    ],
)
def test_base_endpoint_gets_signal_path(base: str, expected: str) -> None:
    assert resolve_otlp_traces_endpoint(base, None) == expected


def test_signal_specific_env_is_used_verbatim() -> None:
    assert (
        resolve_otlp_traces_endpoint("https://base.example.com/otlp", "https://custom.example.com/traces")
        == "https://custom.example.com/traces"
    )


def test_blank_traces_env_falls_back_to_base() -> None:
    assert (
        resolve_otlp_traces_endpoint("https://base.example.com/otlp", "   ")
        == "https://base.example.com/otlp/v1/traces"
    )


@pytest.mark.parametrize(
    ("base", "traces"),
    [(None, None), ("", None), ("   ", ""), (None, ""), ("", "  ")],
)
def test_missing_configuration_resolves_to_none(base: str | None, traces: str | None) -> None:
    assert resolve_otlp_traces_endpoint(base, traces) is None


def test_init_telemetry_passes_resolved_endpoint_to_exporter(monkeypatch) -> None:
    """init_telemetry must hand OTLPSpanExporter the FULL /v1/traces URL."""
    pytest.importorskip("opentelemetry.sdk.trace")
    import core.observability.telemetry as telemetry_module

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://otlp.example.com/otlp")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.setattr(telemetry_module, "_tracer", None)

    fake_tracer = MagicMock()
    with (
        patch(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter"
        ) as mock_exporter_cls,
        patch.object(telemetry_module.trace, "set_tracer_provider"),
        patch.object(telemetry_module.trace, "get_tracer", return_value=fake_tracer),
    ):
        telemetry_module.init_telemetry("supremeai-test-svc")

    assert mock_exporter_cls.call_args.kwargs["endpoint"] == "https://otlp.example.com/otlp/v1/traces"

    # The singleton must be reset so other tests start from a clean slate.
    monkeypatch.setattr(telemetry_module, "_tracer", None)
