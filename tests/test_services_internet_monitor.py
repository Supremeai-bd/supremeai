# tests/test_services_internet_monitor.py
"""Tests for the internet monitor service."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, create_autospec
import pytest

from backend.services.internet_monitor_service import (
    InternetMonitorService,
    internet_monitor_service,
    initialize_internet_monitor_service,
    start_internet_monitoring,
    stop_internet_monitoring,
    get_internet_monitor_service
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
    
    # Mock the agent's initialize method
    service.agent.initialize = AsyncMock()
    
    await service.initialize()
    
    service.agent.initialize.assert_called_once()


@pytest.mark.asyncio
async def test_initialize_service_failure():
    """Test initialization failure of the service."""
    service = InternetMonitorService()
    
    # Mock the agent's initialize method to raise an exception
    service.agent.initialize = AsyncMock(side_effect=Exception("Initialization failed"))
    
    with pytest.raises(Exception, match="Initialization failed"):
        await service.initialize()


@pytest.mark.asyncio
async def test_start_monitoring_first_time():
    """Test starting monitoring when not already running."""
    service = InternetMonitorService()
    
    # Mock the agent's start_monitoring_loop method
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
    
    # Capture log messages to verify warning
    with patch('backend.services.internet_monitor_service.logger') as mock_logger:
        await service.start_monitoring()
        
        # Verify that a warning was logged
        mock_logger.warning.assert_called_once_with("Internet monitoring is already running")


@pytest.mark.asyncio
async def test_start_monitoring_exception():
    """Test starting monitoring with exception."""
    service = InternetMonitorService()
    
    # Mock the agent's start_monitoring_loop method to raise an exception
    service.agent.start_monitoring_loop = MagicMock(side_effect=Exception("Start failed"))
    
    with pytest.raises(Exception, match="Start failed"):
        await service.start_monitoring()


@pytest.mark.asyncio
async def test_stop_monitoring_when_running():
    """Test stopping monitoring when it's running."""
    service = InternetMonitorService()
    service.is_running = True
    
    # Create a mock task using asyncio.Future
    mock_task = asyncio.Future()
    mock_task.set_result(None)
    mock_task.cancel = MagicMock()
    service.monitoring_task = mock_task

    # Mock waiting for the task with CancelledError
    with patch.object(asyncio, 'wait_for', side_effect=asyncio.CancelledError()):
        await service.stop_monitoring()
    
    assert service.is_running is False
    mock_task.cancel.assert_called_once()


@pytest.mark.asyncio
async def test_stop_monitoring_when_not_running():
    """Test stopping monitoring when it's not running."""
    service = InternetMonitorService()
    service.is_running = False
    
    # Capture log messages to verify warning
    with patch('backend.services.internet_monitor_service.logger') as mock_logger:
        await service.stop_monitoring()
        
        # Verify that a warning was logged
        mock_logger.warning.assert_called_once_with("Internet monitoring is not running")


@pytest.mark.asyncio
async def test_stop_monitoring_with_task():
    """Test stopping monitoring with active task."""
    service = InternetMonitorService()
    service.is_running = True

    # Create a mock task using asyncio.Future
    mock_task = asyncio.Future()
    mock_task.set_result(None)
    mock_task.cancel = MagicMock()
    service.monitoring_task = mock_task

    with patch('asyncio.wait_for', side_effect=asyncio.CancelledError):
        await service.stop_monitoring()
    
    assert service.is_running is False
    mock_task.cancel.assert_called_once()


@pytest.mark.asyncio
async def test_get_status():
    """Test getting the service status."""
    service = InternetMonitorService()
    service.is_running = True
    
    # Mock the agent properties
    service.agent.session = "active_session"
    service.agent.check_interval = 30
    service.agent.name = "test_agent"
    
    status = await service.get_status()
    
    assert status["is_running"] == True
    assert status["is_initialized"] == True  # Because session is not None
    assert status["check_interval"] == 30
    assert status["name"] == "test_agent"


@pytest.mark.asyncio
async def test_get_latest_updates():
    """Test getting latest updates."""
    service = InternetMonitorService()
    
    # Mock the agent's get_latest_updates method
    expected_updates = {"update1": "data1", "update2": "data2"}
    service.agent.get_latest_updates = AsyncMock(return_value=expected_updates)
    
    updates = await service.get_latest_updates()
    
    assert updates == expected_updates
    service.agent.get_latest_updates.assert_called_once()


@pytest.mark.asyncio
async def test_get_update_summary():
    """Test getting update summary."""
    service = InternetMonitorService()
    
    # Mock the agent's get_update_summary method
    expected_summary = {"total_updates": 10, "last_updated": "2023-01-01"}
    service.agent.get_update_summary = AsyncMock(return_value=expected_summary)
    
    summary = await service.get_update_summary()
    
    assert summary == expected_summary
    service.agent.get_update_summary.assert_called_once()


@pytest.mark.asyncio
async def test_get_update_history():
    """Test getting update history."""
    service = InternetMonitorService()
    
    # Mock the agent's get_update_history method
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
    # Mock the global service's initialize method
    with patch.object(internet_monitor_service, 'initialize') as mock_initialize:
        await initialize_internet_monitor_service()
        
        mock_initialize.assert_called_once()


@pytest.mark.asyncio
async def test_start_global_monitoring():
    """Test starting monitoring via global function."""
    # Mock the global service's start_monitoring method
    with patch.object(internet_monitor_service, 'start_monitoring') as mock_start:
        await start_internet_monitoring()
        
        mock_start.assert_called_once()


@pytest.mark.asyncio
async def test_stop_global_monitoring():
    """Test stopping monitoring via global function."""
    # Mock the global service's stop_monitoring method
    with patch.object(internet_monitor_service, 'stop_monitoring') as mock_stop:
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
    
    # Initialize
    service.agent.initialize = AsyncMock()
    await service.initialize()
    service.agent.initialize.assert_called_once()
    
    # Start monitoring
    service.agent.start_monitoring_loop = AsyncMock(return_value=AsyncMock())
    await service.start_monitoring()
    assert service.is_running is True
    
    # Check status
    service.agent.session = "session"
    service.agent.check_interval = 60
    service.agent.name = "lifecycle_test"
    status = await service.get_status()
    assert status["is_running"] is True
    
    # Stop monitoring
    if service.monitoring_task:
        service.monitoring_task.cancel()
        # Suppress the CancelledError for this test
        try:
            await service.monitoring_task
        except asyncio.CancelledError:
            pass
    service.monitoring_task = None
    service.is_running = False
    
    # Final status check
    final_status = await service.get_status()
    assert final_status["is_running"] is False


@pytest.mark.asyncio
async def test_concurrent_operations():
    """Test concurrent operations on the service."""
    service = InternetMonitorService()
    
    # Mock methods
    service.agent.initialize = AsyncMock()
    service.agent.start_monitoring_loop = AsyncMock(return_value=AsyncMock())
    
    # Initialize
    await service.initialize()
    
    # Start monitoring
    await service.start_monitoring()
    
    # Run multiple status queries concurrently
    tasks = [service.get_status() for _ in range(5)]
    results = await asyncio.gather(*tasks)
    
    # All results should be consistent
    for result in results:
        assert result["is_running"] is True
    
    # Stop monitoring
    if service.monitoring_task:
        service.monitoring_task.cancel()
        try:
            await service.monitoring_task
        except asyncio.CancelledError:
            pass
    service.monitoring_task = None
    service.is_running = False


@pytest.mark.asyncio
async def test_exception_handling_in_status():
    """Test that exceptions in agent properties are handled gracefully."""
    service = InternetMonitorService()
    service.is_running = True
    
    # Mock the agent with problematic properties
    service.agent.session = None
    service.agent.check_interval = 30
    service.agent.name = "test_agent"
    
    status = await service.get_status()
    
    # Should still return a valid status dict even if agent properties cause issues
    assert "is_running" in status
    assert "is_initialized" in status
    assert "check_interval" in status
    assert "name" in status
    assert status["is_initialized"] is False  # Because session is None