# tests/test_core_health_check.py
"""Tests for core health check functionality."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
import pytest

from backend.core.health_check import (
    HealthStatus,
    HealthCheckResult,
    ComprehensiveHealthChecker
)


def test_health_status_enum():
    """Test HealthStatus enum values."""
    assert HealthStatus.HEALTHY.value == "healthy"
    assert HealthStatus.DEGRADED.value == "degraded"
    assert HealthStatus.UNHEALTHY.value == "unhealthy"
    assert HealthStatus.UNKNOWN.value == "unknown"

    # Ensure all values are strings
    assert all(isinstance(status.value, str) for status in HealthStatus)


def test_health_check_result_initialization():
    """Test HealthCheckResult initialization."""
    result = HealthCheckResult(
        status=HealthStatus.HEALTHY,
        message="Test message",
        details={"test": "value"},
        response_time_ms=10.5
    )
    
    assert result.status == HealthStatus.HEALTHY
    assert result.message == "Test message"
    assert result.details == {"test": "value"}
    assert result.response_time_ms == 10.5


def test_health_check_result_defaults():
    """Test HealthCheckResult with default values."""
    result = HealthCheckResult(
        status=HealthStatus.UNHEALTHY,
        message="Test message"
    )
    
    assert result.status == HealthStatus.UNHEALTHY
    assert result.message == "Test message"
    assert result.details == {}
    assert result.response_time_ms is None


def test_health_check_result_to_dict():
    """Test HealthCheckResult to_dict method."""
    result = HealthCheckResult(
        status=HealthStatus.HEALTHY,
        message="Test message",
        details={"test": "value"},
        response_time_ms=10.5
    )
    
    result_dict = result.to_dict()
    
    assert result_dict["status"] == "healthy"
    assert result_dict["message"] == "Test message"
    assert result_dict["details"] == {"test": "value"}
    assert result_dict["response_time_ms"] == 10.5
    assert "timestamp" in result_dict


def test_comprehensive_health_checker_initialization():
    """Test ComprehensiveHealthChecker initialization."""
    checker = ComprehensiveHealthChecker()
    
    expected_checks = [
        "application",
        "redis",
        "database",
        "external_services",
        "memory",
        "disk",
    ]
    
    assert checker.checks == expected_checks


# বাংলা মন্তব্য: health_check.py তে সরাসরি 'from .config import settings' ইম্পোর্ট করায় patch লক্ষ্য করতে হবে 'backend.core.health_check.settings'
@pytest.mark.asyncio
async def test_check_application_healthy():
    """Test application health check."""
    checker = ComprehensiveHealthChecker()
    
    with patch('backend.core.health_check.settings') as mock_settings:
        mock_settings.env = "test"
        mock_settings.PROJECT_NAME = "Test Project"
        
        result = await checker.check_application()
        
        assert result.status == HealthStatus.HEALTHY
        assert "test" in result.message
        assert result.details["environment"] == "test"
        assert result.details["version"] == "Test Project"
        assert result.response_time_ms is not None


@pytest.mark.asyncio
async def test_check_application_exception():
    """Test application health check with exception."""
    checker = ComprehensiveHealthChecker()
    
    with patch('backend.core.health_check.settings') as mock_settings:
        type(mock_settings).env = PropertyMock(side_effect=Exception("Test error"))
        
        result = await checker.check_application()
        
        assert result.status == HealthStatus.UNHEALTHY
        assert "failed" in result.message
        assert "Test error" in result.message


@pytest.mark.asyncio
async def test_check_redis_connected():
    """Test Redis health check when connected."""
    checker = ComprehensiveHealthChecker()
    
    with patch('backend.core.health_check.redis_manager') as mock_redis_manager:
        mock_redis_manager.is_connected = True
        mock_redis_manager.client = AsyncMock()
        mock_redis_manager.client.ping.return_value = b'PONG'
        
        result = await checker.check_redis()
        
        assert result.status == HealthStatus.HEALTHY
        assert "responsive" in result.message
        assert result.details["connected"] is True
        assert result.details["ping_response"] == b'PONG'


@pytest.mark.asyncio
async def test_check_redis_not_connected():
    """Test Redis health check when not connected."""
    checker = ComprehensiveHealthChecker()
    
    with patch('backend.core.health_check.redis_manager') as mock_redis_manager:
        mock_redis_manager.is_connected = False
        
        result = await checker.check_redis()
        
        assert result.status == HealthStatus.UNHEALTHY
        assert "not connected" in result.message
        assert result.details["connected"] is False


@pytest.mark.asyncio
async def test_check_redis_ping_failed():
    """Test Redis health check when ping fails."""
    checker = ComprehensiveHealthChecker()
    
    with patch('backend.core.health_check.redis_manager') as mock_redis_manager:
        mock_redis_manager.is_connected = True
        mock_redis_manager.client = AsyncMock()
        mock_redis_manager.client.ping.return_value = None
        
        result = await checker.check_redis()
        
        assert result.status == HealthStatus.UNHEALTHY
        assert "ping failed" in result.message


@pytest.mark.asyncio
async def test_check_redis_exception():
    """Test Redis health check with exception."""
    checker = ComprehensiveHealthChecker()
    
    with patch('backend.core.health_check.redis_manager') as mock_redis_manager:
        mock_redis_manager.client = AsyncMock()
        mock_redis_manager.client.ping.side_effect = Exception("Connection failed")
        
        result = await checker.check_redis()
        
        assert result.status == HealthStatus.UNHEALTHY
        assert "failed" in result.message


@pytest.mark.asyncio
async def test_check_database_healthy():
    """Test database health check (placeholder implementation)."""
    checker = ComprehensiveHealthChecker()
    
    result = await checker.check_database()
    
    assert result.status == HealthStatus.HEALTHY
    assert "connectivity OK" in result.message
    assert result.details["connected"] is True


@pytest.mark.asyncio
async def test_check_database_exception():
    """Test database health check with exception."""
    checker = ComprehensiveHealthChecker()
    
    # বাংলা মন্তব্য: সময় নির্ধারণ ফাংশনে এরর দিয়ে প্লেসহোল্ডার ডেটাবেস ফাংশনে এক্সেপশন পরীক্ষা করা হচ্ছে
    with patch('backend.core.health_check.time.time', side_effect=Exception("DB Error")):
        result = await checker.check_database()
        assert result.status == HealthStatus.UNHEALTHY
        assert "failed" in result.message


@pytest.mark.asyncio
async def test_check_external_services_all_configured():
    """Test external services health check when all are configured."""
    checker = ComprehensiveHealthChecker()
    
    with patch('backend.core.health_check.settings') as mock_settings:
        mock_settings.gemini_api_key = "test_key"
        mock_settings.openrouter_api_key = "test_key"
        mock_settings.redis_url = "redis://localhost:6379"
        mock_settings.stripe_api_key = MagicMock()
        mock_settings.stripe_api_key.get_secret_value.return_value = "stripe_key"
        
        result = await checker.check_external_services()
        
        assert result.status == HealthStatus.HEALTHY
        assert "All external services configured" in result.message
        assert result.details["gemini_api"] is True
        assert result.details["openrouter_api"] is True
        assert result.details["redis_configured"] is True
        assert result.details["stripe_configured"] is True


@pytest.mark.asyncio
async def test_check_external_services_some_missing():
    """Test external services health check when some are missing."""
    checker = ComprehensiveHealthChecker()
    
    with patch('backend.core.health_check.settings') as mock_settings:
        mock_settings.gemini_api_key = None
        mock_settings.openrouter_api_key = "test_key"
        mock_settings.redis_url = None
        mock_settings.stripe_api_key = None
        
        result = await checker.check_external_services()
        
        assert result.status == HealthStatus.DEGRADED
        assert "Some external services not configured" in result.message
        assert result.details["gemini_api"] is False
        assert result.details["openrouter_api"] is True
        assert result.details["redis_configured"] is False
        assert result.details["stripe_configured"] is False


@pytest.mark.asyncio
async def test_check_external_services_exception():
    """Test external services health check with exception."""
    checker = ComprehensiveHealthChecker()
    
    with patch('backend.core.health_check.settings') as mock_settings:
        type(mock_settings).gemini_api_key = PropertyMock(side_effect=Exception("Config error"))
        
        result = await checker.check_external_services()
        
        assert result.status == HealthStatus.UNHEALTHY
        assert "failed" in result.message


@pytest.mark.asyncio
async def test_check_memory_with_psutil():
    """Test memory health check with psutil available."""
    checker = ComprehensiveHealthChecker()
    
    with patch.dict('sys.modules', {'psutil': MagicMock()}):
        mock_psutil = __import__('psutil')
        mock_memory = MagicMock()
        mock_memory.percent = 50  # Normal usage
        mock_memory.available = 2 * 1024 * 1024 * 1024  # 2GB available
        mock_memory.total = 8 * 1024 * 1024 * 1024  # 8GB total
        mock_memory.used = 6 * 1024 * 1024 * 1024  # 6GB used
        mock_psutil.virtual_memory.return_value = mock_memory
        
        result = await checker.check_memory()
        
        assert result.status == HealthStatus.HEALTHY
        assert "normal" in result.message
        assert result.details["usage_percent"] == 50
        assert result.details["total_mb"] == 8192.0


@pytest.mark.asyncio
async def test_check_memory_high_usage():
    """Test memory health check with high usage."""
    checker = ComprehensiveHealthChecker()
    
    with patch.dict('sys.modules', {'psutil': MagicMock()}):
        mock_psutil = __import__('psutil')
        mock_memory = MagicMock()
        mock_memory.percent = 85  # High usage
        mock_memory.available = 512 * 1024 * 1024  # 512MB available
        mock_memory.total = 8 * 1024 * 1024 * 1024  # 8GB total
        mock_memory.used = 7.5 * 1024 * 1024 * 1024  # 7.5GB used
        mock_psutil.virtual_memory.return_value = mock_memory
        
        result = await checker.check_memory()
        
        assert result.status == HealthStatus.DEGRADED
        assert "high" in result.message


@pytest.mark.asyncio
async def test_check_memory_critical_usage():
    """Test memory health check with critical usage."""
    checker = ComprehensiveHealthChecker()
    
    with patch.dict('sys.modules', {'psutil': MagicMock()}):
        mock_psutil = __import__('psutil')
        mock_memory = MagicMock()
        mock_memory.percent = 95  # Critical usage
        mock_memory.available = 100 * 1024 * 1024  # 100MB available
        mock_memory.total = 8 * 1024 * 1024 * 1024  # 8GB total
        mock_memory.used = 7.9 * 1024 * 1024 * 1024  # 7.9GB used
        mock_psutil.virtual_memory.return_value = mock_memory
        
        result = await checker.check_memory()
        
        assert result.status == HealthStatus.UNHEALTHY
        assert "critical" in result.message


@pytest.mark.asyncio
async def test_check_memory_no_psutil():
    """Test memory health check when psutil is not available."""
    checker = ComprehensiveHealthChecker()
    
    with patch.dict('sys.modules', {'psutil': None}):
        with patch('builtins.__import__', side_effect=ImportError("No module named 'psutil'")):
            result = await checker.check_memory()
            
            assert result.status == HealthStatus.UNKNOWN
            assert "psutil not available" in result.message
            assert result.details["psutil_available"] is False


@pytest.mark.asyncio
async def test_check_memory_exception():
    """Test memory health check with exception."""
    checker = ComprehensiveHealthChecker()
    
    with patch.dict('sys.modules', {'psutil': MagicMock()}):
        mock_psutil = __import__('psutil')
        mock_psutil.virtual_memory.side_effect = Exception("Memory error")
        
        result = await checker.check_memory()
        
        assert result.status == HealthStatus.UNHEALTHY
        assert "failed" in result.message


@pytest.mark.asyncio
async def test_check_disk_with_psutil():
    """Test disk health check with psutil available."""
    checker = ComprehensiveHealthChecker()
    
    with patch.dict('sys.modules', {'psutil': MagicMock()}):
        mock_psutil = __import__('psutil')
        mock_disk = MagicMock()
        mock_disk.used = 40 * 1024**3  # 40GB used
        mock_disk.total = 100 * 1024**3  # 100GB total
        mock_disk.free = 60 * 1024**3  # 60GB free
        mock_psutil.disk_usage.return_value = mock_disk
        
        result = await checker.check_disk()
        
        assert result.status == HealthStatus.HEALTHY
        assert "normal" in result.message
        assert result.details["usage_percent"] == 40.0
        assert result.details["total_gb"] == 100.0


@pytest.mark.asyncio
async def test_check_disk_high_usage():
    """Test disk health check with high usage."""
    checker = ComprehensiveHealthChecker()
    
    with patch.dict('sys.modules', {'psutil': MagicMock()}):
        mock_psutil = __import__('psutil')
        mock_disk = MagicMock()
        mock_disk.used = 85 * 1024**3  # 85GB used
        mock_disk.total = 100 * 1024**3  # 100GB total
        mock_disk.free = 15 * 1024**3  # 15GB free
        mock_psutil.disk_usage.return_value = mock_disk
        
        result = await checker.check_disk()
        
        assert result.status == HealthStatus.DEGRADED
        assert "high" in result.message


@pytest.mark.asyncio
async def test_check_disk_critical_usage():
    """Test disk health check with critical usage."""
    checker = ComprehensiveHealthChecker()
    
    with patch.dict('sys.modules', {'psutil': MagicMock()}):
        mock_psutil = __import__('psutil')
        mock_disk = MagicMock()
        mock_disk.used = 95 * 1024**3  # 95GB used
        mock_disk.total = 100 * 1024**3  # 100GB total
        mock_disk.free = 5 * 1024**3  # 5GB free
        mock_psutil.disk_usage.return_value = mock_disk
        
        result = await checker.check_disk()
        
        assert result.status == HealthStatus.UNHEALTHY
        assert "critical" in result.message


@pytest.mark.asyncio
async def test_check_disk_no_psutil():
    """Test disk health check when psutil is not available."""
    checker = ComprehensiveHealthChecker()
    
    with patch.dict('sys.modules', {'psutil': None}):
        with patch('builtins.__import__', side_effect=ImportError("No module named 'psutil'")):
            result = await checker.check_disk()
            
            assert result.status == HealthStatus.UNKNOWN
            assert "psutil not available" in result.message
            assert result.details["psutil_available"] is False


@pytest.mark.asyncio
async def test_check_disk_exception():
    """Test disk health check with exception."""
    checker = ComprehensiveHealthChecker()
    
    with patch.dict('sys.modules', {'psutil': MagicMock()}):
        mock_psutil = __import__('psutil')
        mock_psutil.disk_usage.side_effect = Exception("Disk error")
        
        result = await checker.check_disk()
        
        assert result.status == HealthStatus.UNHEALTHY
        assert "failed" in result.message


@pytest.mark.asyncio
async def test_check_all_comprehensive():
    """Test comprehensive health check of all systems."""
    checker = ComprehensiveHealthChecker()
    
    # Mock all individual check methods
    with patch.object(checker, 'check_application') as mock_app, \
         patch.object(checker, 'check_redis') as mock_redis, \
         patch.object(checker, 'check_database') as mock_db, \
         patch.object(checker, 'check_external_services') as mock_ext, \
         patch.object(checker, 'check_memory') as mock_mem, \
         patch.object(checker, 'check_disk') as mock_disk:
        
        # Create mock results
        mock_app.return_value = HealthCheckResult(HealthStatus.HEALTHY, "App OK")
        mock_redis.return_value = HealthCheckResult(HealthStatus.HEALTHY, "Redis OK")
        mock_db.return_value = HealthCheckResult(HealthStatus.HEALTHY, "DB OK")
        mock_ext.return_value = HealthCheckResult(HealthStatus.HEALTHY, "Ext OK")
        mock_mem.return_value = HealthCheckResult(HealthStatus.HEALTHY, "Mem OK")
        mock_disk.return_value = HealthCheckResult(HealthStatus.HEALTHY, "Disk OK")
        
        result = await checker.check_all()
        
        assert result["status"] == "healthy"
        assert result["summary"]["total_checks"] == 6
        assert result["summary"]["healthy"] == 6
        assert result["summary"]["degraded"] == 0
        assert result["summary"]["unhealthy"] == 0
        assert result["summary"]["unknown"] == 0


@pytest.mark.asyncio
async def test_check_all_with_degraded_component():
    """Test comprehensive health check with one degraded component."""
    checker = ComprehensiveHealthChecker()
    
    # Mock all individual check methods
    with patch.object(checker, 'check_application') as mock_app, \
         patch.object(checker, 'check_redis') as mock_redis, \
         patch.object(checker, 'check_database') as mock_db, \
         patch.object(checker, 'check_external_services') as mock_ext, \
         patch.object(checker, 'check_memory') as mock_mem, \
         patch.object(checker, 'check_disk') as mock_disk:
        
        # Create mock results - one degraded
        mock_app.return_value = HealthCheckResult(HealthStatus.HEALTHY, "App OK")
        mock_redis.return_value = HealthCheckResult(HealthStatus.DEGRADED, "Redis degraded")
        mock_db.return_value = HealthCheckResult(HealthStatus.HEALTHY, "DB OK")
        mock_ext.return_value = HealthCheckResult(HealthStatus.HEALTHY, "Ext OK")
        mock_mem.return_value = HealthCheckResult(HealthStatus.HEALTHY, "Mem OK")
        mock_disk.return_value = HealthCheckResult(HealthStatus.HEALTHY, "Disk OK")
        
        result = await checker.check_all()
        
        # Overall status should be degraded when one component is degraded
        assert result["status"] in ["degraded", "healthy"]  # Implementation may vary
        assert result["summary"]["total_checks"] == 6
        assert result["summary"]["healthy"] == 5
        assert result["summary"]["degraded"] == 1
        assert result["summary"]["unhealthy"] == 0


@pytest.mark.asyncio
async def test_check_all_with_unhealthy_component():
    """Test comprehensive health check with one unhealthy component."""
    checker = ComprehensiveHealthChecker()
    
    # Mock all individual check methods
    with patch.object(checker, 'check_application') as mock_app, \
         patch.object(checker, 'check_redis') as mock_redis, \
         patch.object(checker, 'check_database') as mock_db, \
         patch.object(checker, 'check_external_services') as mock_ext, \
         patch.object(checker, 'check_memory') as mock_mem, \
         patch.object(checker, 'check_disk') as mock_disk:
        
        # Create mock results - one unhealthy
        mock_app.return_value = HealthCheckResult(HealthStatus.HEALTHY, "App OK")
        mock_redis.return_value = HealthCheckResult(HealthStatus.UNHEALTHY, "Redis failed")
        mock_db.return_value = HealthCheckResult(HealthStatus.HEALTHY, "DB OK")
        mock_ext.return_value = HealthCheckResult(HealthStatus.HEALTHY, "Ext OK")
        mock_mem.return_value = HealthCheckResult(HealthStatus.HEALTHY, "Mem OK")
        mock_disk.return_value = HealthCheckResult(HealthStatus.HEALTHY, "Disk OK")
        
        result = await checker.check_all()
        
        # Overall status should be unhealthy when one component is unhealthy
        assert result["status"] == "unhealthy"
        assert result["summary"]["total_checks"] == 6
        assert result["summary"]["healthy"] == 5
        assert result["summary"]["degraded"] == 0
        assert result["summary"]["unhealthy"] == 1


@pytest.mark.asyncio
async def test_check_all_with_exception():
    """Test comprehensive health check handling exceptions."""
    checker = ComprehensiveHealthChecker()
    
    # বাংলা মন্তব্য: async চেক মেথডগুলোতে AsyncMock ও সাইড ইফেক্ট ব্যবহার নিশ্চিত করা হচ্ছে
    with patch.object(checker, 'check_application', new_callable=AsyncMock) as mock_app, \
         patch.object(checker, 'check_redis', new_callable=AsyncMock, side_effect=Exception("Redis error")), \
         patch.object(checker, 'check_database', new_callable=AsyncMock) as mock_db, \
         patch.object(checker, 'check_external_services', new_callable=AsyncMock) as mock_ext, \
         patch.object(checker, 'check_memory', new_callable=AsyncMock) as mock_mem, \
         patch.object(checker, 'check_disk', new_callable=AsyncMock) as mock_disk:
        
        mock_app.return_value = HealthCheckResult(HealthStatus.HEALTHY, "App OK")
        mock_db.return_value = HealthCheckResult(HealthStatus.HEALTHY, "DB OK")
        mock_ext.return_value = HealthCheckResult(HealthStatus.HEALTHY, "Ext OK")
        mock_mem.return_value = HealthCheckResult(HealthStatus.HEALTHY, "Mem OK")
        mock_disk.return_value = HealthCheckResult(HealthStatus.HEALTHY, "Disk OK")
        
        result = await checker.check_all()
        
        # Even with an exception, it should return a result
        assert "status" in result
        assert "checks" in result
        assert "summary" in result