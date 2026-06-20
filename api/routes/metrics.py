from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["metrics"])

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest

    http_requests_total = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
    )
    request_duration_seconds = Histogram(
        "request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "endpoint"],
        buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
    )
    error_total = Counter(
        "error_total",
        "Total errors by type",
        ["error_type", "endpoint"],
    )
    active_requests = Gauge(
        "active_requests",
        "Number of active requests",
        ["method", "endpoint"],
    )
    model_calls_total = Counter(
        "supremeai_model_calls_total",
        "Model API calls",
        ["provider", "model"],
    )
    supremeai_requests_total = Counter(
        "supremeai_requests_total",
        "Total requests",
        ["method", "endpoint"],
    )
    supremeai_response_seconds = Histogram(
        "supremeai_response_seconds",
        "Response time",
        ["method", "endpoint"],
        buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10],
    )
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False


def record_request(method: str, path: str, status: int) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    http_requests_total.labels(method=method, endpoint=path, status=str(status)).inc()
    supremeai_requests_total.labels(method=method, endpoint=path).inc()


def record_error(error_type: str, endpoint: str) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    error_total.labels(error_type=error_type, endpoint=endpoint).inc()


def record_request_duration(method: str, path: str, duration: float) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    request_duration_seconds.labels(method=method, endpoint=path).observe(duration)
    supremeai_response_seconds.labels(method=method, endpoint=path).observe(duration)


def record_model_call(provider: str, model: str) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    model_calls_total.labels(provider=provider, model=model).inc()


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    if not _PROMETHEUS_AVAILABLE:
        return PlainTextResponse("# prometheus_client not installed\n", status_code=200)
    return PlainTextResponse(generate_latest().decode("utf-8"))
