# tests/test_services_internet_monitor.py
"""Tests for the internet monitor service."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.internet_monitor_service import (
    InternetMonitorService,
    get_internet_monitor_service,
    initialize_internet_monitor_service,
    internet_monitor_service,
    start_internet_monitoring,
    stop_internet_monitoring,
)


def test_internet_monitor_service_initialization():
    """Test InternetMonitorService initialization."""
    service = InternetMonitorService()
    assert service.agent is not None
    assert service.monitoring_task is None
    assert service.is_running is False


@pytest.mark.asyncio
async def test_initialize_service_success():
    """Test successful initialization of the service."""
    service = InternetMonitorService()
    service.agent.initialize = AsyncMock()
    await service.initialize()
    service.agent.initialize.assert_called_once()


@pytest.mark.asyncio
async def test_initialize_service_failure():
    """Test initialization failure of the service."""
    service = InternetMonitorService()
    service.agent.initialize = AsyncMock(side_effect=Exception("Initialization failed"))
    with pytest.raises(Exception, match="Initialization failed"):
        await service.initialize()


@pytest.mark.asyncio
async def test_start_monitoring_first_time():
    """Test starting monitoring when not already running."""
    service = InternetMonitorService()
    service.agent.start_monitoring_loop = AsyncMock(return_value=AsyncMock())
    await service.start_monitoring()
    assert service.is_running is True
    assert service.monitoring_task is not None
    assert isinstance(service.monitoring_task, asyncio.Task)


@pytest.mark.asyncio
async def test_start_monitoring_already_running():
    """Test starting monitoring when already running."""
    service = InternetMonitorService()
    service.is_running = True
    with patch("backend.services.internet_monitor_service.logger") as mock_logger:
        await service.start_monitoring()
        mock_logger.warning.assert_called_once_with("Internet monitoring is already running")


@pytest.mark.asyncio
async def test_start_monitoring_exception():
    """Test starting monitoring with exception."""
    service = InternetMonitorService()
    service.agent.start_monitoring_loop = MagicMock(side_effect=Exception("Start failed"))
    with pytest.raises(Exception, match="Start failed"):
        await service.start_monitoring()


@pytest.mark.asyncio
async def test_stop_monitoring_when_running():
    """Test stopping monitoring when it's running."""
    service = InternetMonitorService()
    service.is_running = True
    mock_task = asyncio.Future()
    mock_task.set_result(None)
    mock_task.cancel = MagicMock()
    service.monitoring_task = mock_task
    with patch.object(asyncio, "wait_for", side_effect=asyncio.CancelledError()):
        await service.stop_monitoring()
    assert service.is_running is False
    mock_task.cancel.assert_called_once()


@pytest.mark.asyncio
async def test_stop_monitoring_when_not_running():
    """Test stopping monitoring when it's not running."""
    service = InternetMonitorService()
    service.is_running = False
    with patch("backend.services.internet_monitor_service.logger") as mock_logger:
        await service.stop_monitoring()
        mock_logger.warning.assert_called_once_with("Internet monitoring is not running")


@pytest.mark.asyncio
async def test_stop_monitoring_with_task():
    """Test stopping monitoring with active task."""
    service = InternetMonitorService()
    service.is_running = True
    mock_task = asyncio.Future()
    mock_task.set_result(None)
    mock_task.cancel = MagicMock()
    service.monitoring_task = mock_task
    with patch("asyncio.wait_for", side_effect=asyncio.CancelledError):
        await service.stop_monitoring()
    assert service.is_running is False
    mock_task.cancel.assert_called_once()


@pytest.mark.asyncio
async def test_get_status():
    """Test getting the service status."""
    service = InternetMonitorService()
    service.is_running = True
    service.agent.session = "active_session"
    service.agent.check_interval = 30
    service.agent.name = "test_agent"
    status = await service.get_status()
    assert status["is_running"]
    assert status["is_initialized"]
    assert status["check_interval"] == 30
    assert status["name"] == "test_agent"


@pytest.mark.asyncio
async def test_get_latest_updates():
    """Test getting latest updates."""
    service = InternetMonitorService()
    expected_updates = {"update1": "data1", "update2": "data2"}
    service.agent.get_latest_updates = AsyncMock(return_value=expected_updates)
    updates = await service.get_latest_updates()
    assert updates == expected_updates
    service.agent.get_latest_updates.assert_called_once()


@pytest.mark.asyncio
async def test_get_update_summary():
    """Test getting update summary."""
    service = InternetMonitorService()
    expected_summary = {"total_updates": 10, "last_updated": "2023-01-01"}
    service.agent.get_update_summary = AsyncMock(return_value=expected_summary)
    summary = await service.get_update_summary()
    assert summary == expected_summary
    service.agent.get_update_summary.assert_called_once()


@pytest.mark.asyncio
async def test_get_update_history():
    """Test getting update history."""
    service = InternetMonitorService()
    expected_history = [{"id": 1, "data": "update1"}, {"id": 2, "data": "update2"}]
    service.agent.get_update_history = AsyncMock(return_value=expected_history)
    history = await service.get_update_history()
    assert history == expected_history
    service.agent.get_update_history.assert_called_once()


def test_global_service_instance():
    """Test that the global service instance exists."""
    assert internet_monitor_service is not None
    assert isinstance(internet_monitor_service, InternetMonitorService)


@pytest.mark.asyncio
async def test_initialize_global_service():
    """Test initializing the global service."""
    with patch.object(internet_monitor_service, "initialize") as mock_initialize:
        await initialize_internet_monitor_service()
        mock_initialize.assert_called_once()


@pytest.mark.asyncio
async def test_start_global_monitoring():
    """Test starting monitoring via global function."""
    with patch.object(internet_monitor_service, "start_monitoring") as mock_start:
        await start_internet_monitoring()
        mock_start.assert_called_once()


@pytest.mark.asyncio
async def test_stop_global_monitoring():
    """Test stopping monitoring via global function."""
    with patch.object(internet_monitor_service, "stop_monitoring") as mock_stop:
        await stop_internet_monitoring()
        mock_stop.assert_called_once()


def test_get_global_service():
    """Test getting the global service instance."""
    service = get_internet_monitor_service()
    assert service is internet_monitor_service
    assert isinstance(service, InternetMonitorService)


@pytest.mark.asyncio
async def test_service_lifecycle():
    """Test the complete lifecycle of the service."""
    service = InternetMonitorService()
    service.agent.initialize = AsyncMock()
    await service.initialize()
    service.agent.initialize.assert_called_once()
    service.agent.start_monitoring_loop = AsyncMock(return_value=AsyncMock())
    await service.start_monitoring()
    assert service.is_running is True
    service.agent.session = "session"
    service.agent.check_interval = 60
    service.agent.name = "lifecycle_test"
    status = await service.get_status()
    assert status["is_running"] is True
    if service.monitoring_task:
        service.monitoring_task.cancel()
        try:
            await service.monitoring_task
        except asyncio.CancelledError:
            import logging

            logging.getLogger(__name__).warning(
                "Silenced error in except-pass block"
            )  # FIX: CancelledError handled correctly now
        except Exception as e:
            import logging

            logging.getLogger(__name__).exception(f"Silenced error: {e}")
    service.monitoring_task = None
    service.is_running = False
    final_status = await service.get_status()
    assert final_status["is_running"] is False


@pytest.mark.asyncio
async def test_concurrent_operations():
    """Test concurrent operations on the service."""
    service = InternetMonitorService()
    service.agent.initialize = AsyncMock()
    service.agent.start_monitoring_loop = AsyncMock(return_value=AsyncMock())
    await service.initialize()
    await service.start_monitoring()
    tasks = [service.get_status() for _ in range(5)]
    results = await asyncio.gather(*tasks)
    for result in results:
        assert result["is_running"] is True
    if service.monitoring_task:
        service.monitoring_task.cancel()
        try:
            await service.monitoring_task
        except asyncio.CancelledError:
            import logging

            logging.getLogger(__name__).warning(
                "Silenced error in except-pass block"
            )  # FIX: CancelledError handled correctly now
        except Exception as e:
            import logging

            logging.getLogger(__name__).exception(f"Silenced error: {e}")
    service.monitoring_task = None
    service.is_running = False


@pytest.mark.asyncio
async def test_exception_handling_in_status():
    """Test that exceptions in agent properties are handled gracefully."""
    service = InternetMonitorService()
    service.is_running = True
    service.agent.session = None
    service.agent.check_interval = 30
    service.agent.name = "test_agent"
    status = await service.get_status()
    assert "is_running" in status
    assert "is_initialized" in status
    assert "check_interval" in status
    assert "name" in status
    assert status["is_initialized"] is False
