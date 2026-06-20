from unittest.mock import patch, MagicMock
from core.telemetry import setup_tracing, get_tracer, trace_span


def test_setup_tracing_sets_tracer():
    with patch('core.telemetry.otel_trace.set_tracer_provider') as mock_set:
        with patch('core.telemetry.OTLPSpanExporter') as mock_exporter:
            with patch('core.telemetry.BatchSpanProcessor') as mock_processor:
                setup_tracing(service_name='test-service', otlp_endpoint='http://localhost:4317')
                mock_set.assert_called_once()
                assert get_tracer() is not None


def test_trace_span_noop_when_no_tracer():
    with patch('core.telemetry.get_tracer', return_value=None):
        with trace_span('test-span') as span:
            assert span is not None


def test_trace_span_sets_attributes():
    with patch('core.telemetry.get_tracer') as mock_get_tracer:
        mock_tracer = MagicMock()
        mock_get_tracer.return_value = mock_tracer
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)
        with trace_span('test-span', attributes={'key': 'value'}) as span:
            pass
        mock_span.set_attribute.assert_called_once_with('key', 'value')
