"""Tests for MaintenancePipeline - System health monitoring and self-healing.

This module tests:
- Health score tracking
- Background monitoring loop
- Error event handling
- Health check execution
- Performance regression detection
- Auto-remediation with cooldown
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.maintenance_pipeline import MaintenancePipeline


class TestMaintenancePipeline:
    """Tests for MaintenancePipeline class."""

    def test_init(self):
        """Test pipeline initialization."""
        pipeline = MaintenancePipeline()

        assert pipeline.health_score == 100
        assert pipeline._monitor_task is None
        assert pipeline.last_recovery_time == 0

    def test_start_monitoring(self):
        """Test that monitoring starts background task."""
        pipeline = MaintenancePipeline()

        with patch("asyncio.create_task") as mock_create_task:
            pipeline.start_monitoring()

            mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_error_event_reduces_score(self):
        """Test that error events reduce health score."""
        pipeline = MaintenancePipeline()

        mock_event = MagicMock()
        mock_event.severity = "CRITICAL"
        mock_event.module = "test"
        mock_event.error_type = "test_error"
        mock_event.context = {}
        mock_event.message = "Test error"
        mock_event.structured_context = None

        with patch.object(pipeline, "auto_remediate", new_callable=AsyncMock):
            await pipeline._handle_error_event(mock_event)

            assert pipeline.health_score < 100

    @pytest.mark.asyncio
    async def test_handle_error_event_skips_low_severity(self):
        """Test that low severity events don't reduce score."""
        pipeline = MaintenancePipeline()
        initial_score = pipeline.health_score

        mock_event = MagicMock()
        mock_event.severity = "INFO"
        mock_event.module = "test"

        await pipeline._handle_error_event(mock_event)

        # Score should not have changed
        assert pipeline.health_score == initial_score

    @pytest.mark.asyncio
    async def test_run_health_check(self):
        """Test health check execution."""
        pipeline = MaintenancePipeline()

        with (
            patch("core.maintenance_pipeline.probe_redis", return_value={"status": "up"}),
            patch(
                "core.maintenance_pipeline.probe_database",
                return_value={"status": "up"},
            ),
            patch(
                "core.maintenance_pipeline.probe_external_api",
                return_value={"status": "up"},
            ),
        ):
            results = await pipeline.run_health_check()

            assert "redis" in results
            assert "database" in results
            assert "status" in results
            assert results["status"] == "HEALTHY"
            assert pipeline.health_score == 100

    @pytest.mark.asyncio
    async def test_run_health_check_degraded(self):
        """Test health check with degraded services."""
        pipeline = MaintenancePipeline()

        with (
            patch("core.maintenance_pipeline.probe_redis", return_value={"status": "down"}),
            patch(
                "core.maintenance_pipeline.probe_database",
                return_value={"status": "up"},
            ),
            patch(
                "core.maintenance_pipeline.probe_external_api",
                return_value={"status": "up"},
            ),
        ):
            results = await pipeline.run_health_check()

            assert pipeline.health_score < 100
            assert results["status"] in ["DEGRADED", "CRITICAL"]

    @pytest.mark.asyncio
    async def test_auto_remediate_cooldown(self):
        """Test that remediation respects cooldown period."""
        pipeline = MaintenancePipeline()
        pipeline.last_recovery_time = time.time()  # Recent recovery

        mock_event = MagicMock()
        mock_event.context = {}
        mock_event.error_type = "test_error"

        with patch("core.cache.redis_manager.redis_manager"):
            await pipeline.auto_remediate(mock_event)

            # Should have skipped due to cooldown
            assert pipeline.health_score == 100  # No change

    @pytest.mark.asyncio
    async def test_auto_remediate_gemini_degraded(self):
        """Test auto-remediation for Gemini API degraded."""
        pipeline = MaintenancePipeline()

        mock_event = MagicMock()
        mock_event.context = {"gemini": "down"}
        mock_event.error_type = "system.health.degraded"

        mock_redis = MagicMock()
        mock_redis.client = MagicMock()
        mock_redis.client.set = AsyncMock()

        with (
            patch("core.cache.redis_manager.redis_manager", mock_redis),
            patch("core.maintenance_pipeline.error_event_bus.emit"),
        ):
            await pipeline.auto_remediate(mock_event)

            mock_redis.client.set.assert_called()
            assert pipeline.last_recovery_time > 0

    @pytest.mark.asyncio
    async def test_auto_remediate_redis_degraded(self):
        """Test auto-remediation for Redis degraded."""
        pipeline = MaintenancePipeline()

        mock_event = MagicMock()
        mock_event.context = {"redis": "down"}
        mock_event.error_type = "redis_connection_lost"

        mock_redis = MagicMock()
        mock_redis.close = AsyncMock()

        with patch("core.cache.redis_manager.redis_manager", mock_redis):
            await pipeline.auto_remediate(mock_event)

            mock_redis.close.assert_called()

    @pytest.mark.asyncio
    async def test_detect_performance_regression_no_history(self):
        """Test regression detection with no latency history."""
        pipeline = MaintenancePipeline()

        with patch("api.routes.metrics.metrics_engine", None):
            # Should not raise
            await pipeline.detect_performance_regression()

    @pytest.mark.asyncio
    async def test_health_score_bounds(self):
        """Test that health score stays within bounds."""
        pipeline = MaintenancePipeline()

        # Reduce score multiple times
        for _ in range(30):
            mock_event = MagicMock()
            mock_event.severity = "CRITICAL"
            mock_event.context = {}
            mock_event.module = "test"
            mock_event.error_type = "test"
            mock_event.message = "test"
            mock_event.structured_context = None

            with patch.object(pipeline, "auto_remediate", new_callable=AsyncMock):
                await pipeline._handle_error_event(mock_event)

        # Should not go below 0
        assert pipeline.health_score >= 0


class TestMaintenancePipelineSingleton:
    """Tests for singleton pattern."""

    def test_singleton_exists(self):
        """Test that maintenance_pipeline singleton exists."""
        from core.maintenance_pipeline import maintenance_pipeline

        assert maintenance_pipeline is not None
        assert isinstance(maintenance_pipeline, MaintenancePipeline)
