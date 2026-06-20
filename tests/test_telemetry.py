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
