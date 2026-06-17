from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["metrics"])

try:
    from prometheus_client import Counter as _Counter, Histogram as _Histogram, generate_latest as _generate_latest

    http_requests_total = _Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
    )
    http_request_duration_seconds = _Histogram(
        "http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "path"],
        buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
    )
    error_total = _Counter(
        "error_total",
        "Total errors by type",
        ["error_type", "endpoint"],
    )
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False


def record_request(method: str, path: str, status: int) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    http_requests_total.labels(method=method, path=path, status=str(status)).inc()


def record_error(error_type: str, endpoint: str) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    error_total.labels(error_type=error_type, endpoint=endpoint).inc()


def record_request_duration(method: str, path: str, duration: float) -> None:
    if not _PROMETHEUS_AVAILABLE:
        return
    http_request_duration_seconds.labels(method=method, path=path).observe(duration)


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    if not _PROMETHEUS_AVAILABLE:
        return PlainTextResponse("# prometheus_client not installed\n", status_code=200)
    return PlainTextResponse(_generate_latest().decode("utf-8"))
