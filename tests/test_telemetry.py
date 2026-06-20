from unittest.mock import patch, MagicMock
from core.telemetry import setup_tracing, get_tracer, trace_span, _RealSpan, _NoOpSpan


def test_setup_tracing_noop():
    with patch("core.telemetry.otel_trace") as mock_trace:
        setup_tracing("test-service")
        assert mock_trace.set_tracer_provider.called
        assert mock_trace.get_tracer.called
        assert get_tracer() is not None


def test_setup_tracing_with_endpoint():
    with patch("core.telemetry.OTLPSpanExporter") as mock_exporter, \
         patch("core.telemetry.BatchSpanProcessor") as mock_processor, \
         patch("core.telemetry.TracerProvider") as mock_provider_class:

        mock_provider = MagicMock()
        mock_provider_class.return_value = mock_provider

        setup_tracing("test-service", "http://localhost:4317")

        mock_exporter.assert_called_once_with(endpoint="http://localhost:4317", insecure=True)
        mock_processor.assert_called_once_with(mock_exporter.return_value)
        mock_provider.add_span_processor.assert_called_once_with(mock_processor.return_value)


def test_setup_tracing_without_endpoint_no_exporter():
    with patch("core.telemetry.OTLPSpanExporter") as mock_exporter, \
         patch("core.telemetry.TracerProvider") as mock_provider_class:
        mock_provider = MagicMock()
        mock_provider_class.return_value = mock_provider

        setup_tracing("test-service")

        mock_exporter.assert_not_called()
        mock_provider.add_span_processor.assert_not_called()


def test_trace_span_no_tracer():
    with patch("core.telemetry.get_tracer", return_value=None):
        with trace_span("test-span") as span:
            assert isinstance(span, _NoOpSpan)


def test_trace_span_with_tracer():
    mock_tracer = MagicMock()
    mock_span = MagicMock()

    mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

    with patch("core.telemetry.get_tracer", return_value=mock_tracer):
        with trace_span("test-span", attributes={"key": "val"}) as span:
            assert isinstance(span, _RealSpan)
            mock_span.set_attribute.assert_called_with("key", "val")

        mock_tracer.start_as_current_span.assert_called_once()


def test_trace_span_sets_ok_status_on_success():
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

    with patch("core.telemetry.get_tracer", return_value=mock_tracer):
        with trace_span("ok-span"):
            pass
        from opentelemetry.trace import Status, StatusCode
        mock_span.set_status.assert_called_once()
        status_arg = mock_span.set_status.call_args[0][0]
        assert status_arg.status_code == StatusCode.OK


def test_trace_span_records_exception_on_error():
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

    with patch("core.telemetry.get_tracer", return_value=mock_tracer):
        try:
            with trace_span("error-span"):
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        from opentelemetry.trace import Status, StatusCode
        mock_span.set_status.assert_called()
        status_call = mock_span.set_status.call_args[0][0]
        assert status_call.status_code == StatusCode.ERROR
        mock_span.record_exception.assert_called()


def test_trace_span_unknown_kind_defaults_to_internal():
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

    with patch("core.telemetry.get_tracer", return_value=mock_tracer):
        with trace_span("span", kind="unknown"):
            pass
        from opentelemetry import trace as otel_trace
        call_kwargs = mock_tracer.start_as_current_span.call_args
        assert call_kwargs.kwargs["kind"] == otel_trace.SpanKind.INTERNAL


def test_trace_span_sets_attributes_multiple():
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span

    with patch("core.telemetry.get_tracer", return_value=mock_tracer):
        with trace_span("span", attributes={"a": 1, "b": "two"}):
            pass
        assert mock_span.set_attribute.call_count == 2


def test_noop_span_methods_are_silent():
    span = _NoOpSpan()
    span.set_attribute("key", "val")
    span.record_exception(Exception("x"))


def test_real_span_delegates_set_attribute():
    mock_span = MagicMock()
    real = _RealSpan(mock_span)
    real.set_attribute("k", "v")
    mock_span.set_attribute.assert_called_once_with("k", "v")


def test_real_span_delegates_record_exception():
    mock_span = MagicMock()
    real = _RealSpan(mock_span)
    exc = ValueError("v")
    real.record_exception(exc)
    mock_span.record_exception.assert_called_once_with(exc)


def test_tracer_shared_globally_after_setup():
    with patch("core.telemetry.OTLPSpanExporter"), \
         patch("core.telemetry.BatchSpanProcessor"), \
         patch("core.telemetry.TracerProvider"):
        setup_tracing("svc-a")
        t1 = get_tracer()
        assert t1 is not None
        setup_tracing("svc-b")
        t2 = get_tracer()
        assert get_tracer() is t2
