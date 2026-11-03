import sys
from unittest.mock import MagicMock

sys.modules["psutil"] = MagicMock()
sys.modules["prometheus_client"] = MagicMock()

import asyncio
import time
from unittest.mock import patch

import pytest

from core.health.health_monitor import HealthMonitor


@pytest.fixture
def monitor():
    with (
        patch.object(HealthMonitor, "_setup_metrics"),
        patch("core.health.health_monitor.start_http_server", create=True),
    ):
        return HealthMonitor(metrics_port=9090)


def test_health_monitor_initialization(monitor):
    assert monitor.start_time > 0
    assert monitor.cpu_threshold == 85.0
    assert monitor.mem_threshold == 90.0
    assert monitor.metrics_port == 9090


def test_health_monitor_initialization_without_prometheus():
    with patch("core.health.health_monitor._PROMETHEUS_AVAILABLE", False):
        monitor = HealthMonitor(metrics_port=9090)
    assert not hasattr(monitor, "uptime_seconds")


@pytest.mark.anyio
async def test_get_system_metrics_structure(monitor):
    with patch("psutil.cpu_percent", return_value=50.0), patch("psutil.virtual_memory") as mock_vm:
        mock_vm.return_value.percent = 40.0
        mock_vm.return_value.available = 1024 * 1024 * 1024
        metrics = await monitor.get_system_metrics()
    assert "status" in metrics
    assert "uptime_seconds" in metrics
    assert "cpu_usage_percent" in metrics
    assert "memory_usage_percent" in metrics
    assert "memory_available_mb" in metrics
    assert "active_tasks" in metrics
    assert metrics["status"] == "healthy"
    assert metrics["cpu_usage_percent"] == 50.0
    assert metrics["memory_usage_percent"] == 40.0


@pytest.mark.anyio
async def test_get_system_metrics_degraded(monitor):
    with patch("psutil.cpu_percent", return_value=95.0), patch("psutil.virtual_memory") as mock_vm:
        mock_vm.return_value.percent = 95.0
        mock_vm.return_value.available = 1024 * 1024
        metrics = await monitor.get_system_metrics()
    assert metrics["status"] == "degraded"


@pytest.mark.anyio
async def test_get_system_metrics_degraded_memory(monitor):
    with patch("psutil.cpu_percent", return_value=10.0), patch("psutil.virtual_memory") as mock_vm:
        mock_vm.return_value.percent = 95.0
        mock_vm.return_value.available = 1024 * 1024
        metrics = await monitor.get_system_metrics()
    assert metrics["status"] == "degraded"


@pytest.mark.anyio
async def test_get_system_metrics_prometheus_update(monitor):
    monitor.uptime_seconds = MagicMock()
    monitor.cpu_usage_percent = MagicMock()
    monitor.memory_usage_percent = MagicMock()
    monitor.memory_available_mb = MagicMock()
    monitor.active_tasks = MagicMock()
    monitor.status = MagicMock()
    with patch("psutil.cpu_percent", return_value=50.0), patch("psutil.virtual_memory") as mock_vm:
        mock_vm.return_value.percent = 40.0
        mock_vm.return_value.available = 1024 * 1024 * 1024
        await monitor.get_system_metrics()
    monitor.uptime_seconds.set.assert_called_once()
    monitor.cpu_usage_percent.set.assert_called_once_with(50.0)
    monitor.memory_usage_percent.set.assert_called_once_with(40.0)
    monitor.status.set.assert_called_once_with(1)


@pytest.mark.anyio
async def test_get_system_metrics_prometheus_update_failure(monitor):
    monitor.uptime_seconds = MagicMock()
    monitor.uptime_seconds.set.side_effect = Exception("Prometheus error")
    with patch("psutil.cpu_percent", return_value=50.0), patch("psutil.virtual_memory") as mock_vm:
        mock_vm.return_value.percent = 40.0
        mock_vm.return_value.available = 1024 * 1024
        metrics = await monitor.get_system_metrics()
    assert metrics["status"] == "healthy"


@pytest.mark.anyio
async def test_is_ready(monitor):
    with patch.object(
        monitor,
        "get_system_metrics",
        return_value={"status": "healthy", "uptime_seconds": 10},
    ):
        result = await monitor.is_ready()
    assert result is True


@pytest.mark.anyio
async def test_is_ready_degraded(monitor):
    with patch.object(
        monitor,
        "get_system_metrics",
        return_value={"status": "degraded", "uptime_seconds": 10},
    ):
        result = await monitor.is_ready()
    assert result is True


@pytest.mark.anyio
async def test_is_live(monitor):
    result = await monitor.is_live()
    assert result is True


def test_record_request_duration_with_prometheus(monitor):
    monitor.request_duration_seconds = MagicMock()
    monitor.record_request_duration(0.5)
    monitor.request_duration_seconds.observe.assert_called_once_with(0.5)


def test_record_request_duration_prometheus_error(monitor):
    monitor.request_duration_seconds = MagicMock()
    monitor.request_duration_seconds.observe.side_effect = Exception("fail")
    monitor.record_request_duration(0.5)


def test_health_monitor_uptime_increases():
    with (
        patch.object(HealthMonitor, "_setup_metrics"),
        patch("core.health.health_monitor.start_http_server", create=True),
    ):
        m = HealthMonitor(metrics_port=9091)
    time.sleep(0.01)
    with patch("psutil.cpu_percent", return_value=0.0), patch("psutil.virtual_memory") as mock_vm:
        mock_vm.return_value.percent = 0.0
        mock_vm.return_value.available = 1024 * 1024 * 1024
        loop = asyncio.new_event_loop()
        try:
            metrics = loop.run_until_complete(m.get_system_metrics())
        finally:
            loop.close()
    assert metrics["uptime_seconds"] >= 0


def test_health_monitor_reports_elapsed_process_time_not_cpu_time():
    # FIX (final-test hardening-2): the old mock patched time.time with a
    # two-entry side_effect list. health_monitor.time IS the global time
    # module, so any other time.time() consumer during the patch window
    # (structured-logging timestamps, pytest internals) burned an entry and
    # raised StopIteration — the test could never pass reliably in CI.
    # A controlled fake clock keeps the contract under test intact:
    # uptime_seconds must be ELAPSED WALL TIME (start→now), independent of
    # the CPU-usage sample reported alongside it.
    fake_clock = {"now": 100.0}

    def _fake_time() -> float:
        return fake_clock["now"]

    with (
        patch.object(HealthMonitor, "_setup_metrics"),
        patch("core.health.health_monitor.start_http_server", create=True),
        patch("core.health.health_monitor.time.time", side_effect=_fake_time),
    ):
        monitor = HealthMonitor(metrics_port=9092)  # start_time = 100.0
        fake_clock["now"] = 112.9  # advance the wall clock by 12.9s

        with (
            patch("psutil.cpu_percent", return_value=73.0),
            patch("psutil.virtual_memory") as mock_vm,
        ):
            mock_vm.return_value.percent = 20.0
            mock_vm.return_value.available = 1024 * 1024 * 1024
            loop = asyncio.new_event_loop()
            try:
                metrics = loop.run_until_complete(monitor.get_system_metrics())
            finally:
                loop.close()

    assert metrics["uptime_seconds"] == 12
    assert metrics["cpu_usage_percent"] == 73.0
