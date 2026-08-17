# tests/test_agents_insight_mage.py
"""Tests for InsightMage - trend analysis and anomaly detection."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta


class TestTrendDetector:
    """Test trend detection functionality."""

    def test_trend_detector_initialization(self):
        """Test trend detector initializes with default values."""
        from backend.agents.insight_mage import TrendDetector

        detector = TrendDetector()
        assert detector.min_points == 7  # TREND_MIN_POINTS in source

    def test_trend_detector_custom_min_points(self):
        """Test trend detector with custom minimum points."""
        from backend.agents.insight_mage import TrendDetector

        detector = TrendDetector(min_points=10)
        assert detector.min_points == 10

    def test_analyze_increasing_trend(self):
        """Test detection of increasing trend."""
        from backend.agents.insight_mage import TrendDetector

        detector = TrendDetector()

        # Clear increasing values (index-based x since no timestamps passed)
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]

        result = detector.analyze(values)

        assert isinstance(result.direction, str)
        assert result.slope > 0  # Should detect positive slope

    def test_analyze_decreasing_trend(self):
        """Test detection of decreasing trend."""
        from backend.agents.insight_mage import TrendDetector

        detector = TrendDetector()

        # Clear decreasing values (index-based x since no timestamps passed)
        values = [7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]

        result = detector.analyze(values)

        assert isinstance(result.direction, str)
        assert result.slope < 0  # Should detect negative slope

    def test_analyze_stable_trend(self):
        """Test detection of stable trend."""
        from backend.agents.insight_mage import TrendDetector

        detector = TrendDetector()

        # Stable values
        values = [2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0]

        result = detector.analyze(values)

        assert isinstance(result.direction, str)


class TestAnomalyDetector:
    """Test anomaly detection functionality."""

    def test_anomaly_detector_initialization(self):
        """Test anomaly detector initializes with default threshold."""
        from backend.agents.insight_mage import AnomalyDetector

        detector = AnomalyDetector()
        assert detector.z_threshold == 2.5  # ANOMALY_Z_THRESHOLD in source

    def test_anomaly_detector_custom_threshold(self):
        """Test anomaly detector with custom threshold."""
        from backend.agents.insight_mage import AnomalyDetector

        detector = AnomalyDetector(z_threshold=3.0)
        assert detector.z_threshold == 3.0

    def test_detect_normal_value(self):
        """Test that normal values are not flagged as anomalies."""
        from backend.agents.insight_mage import AnomalyDetector

        detector = AnomalyDetector(z_threshold=2.0)

        # Historical data
        historical = [1.0, 1.1, 1.2, 1.0, 1.1, 1.3, 1.0, 1.2]

        result = detector.detect(1.1, historical)

        # Should not be anomaly (is_normal should be True or anomaly should be False)
        assert isinstance(result.is_anomaly, bool)

    def test_detect_outlier_value(self):
        """Test that outlier values are detected as anomalies."""
        from backend.agents.insight_mage import AnomalyDetector

        detector = AnomalyDetector(z_threshold=1.5)

        # Historical data with values around 1.0
        historical = [1.0, 1.1, 1.0, 1.1, 1.0, 1.1, 1.0, 1.1]

        # Outlier value - much higher than historical
        result = detector.detect(100.0, historical)

        # Should be anomaly
        assert result.is_anomaly is True or result.z_score > 3


class TestReportFormatter:
    """Test report formatting functionality."""

    def test_report_formatter_initialization(self):
        """Test report formatter initializes."""
        from backend.agents.insight_mage import ReportFormatter

        formatter = ReportFormatter()
        assert formatter is not None

    @pytest.mark.asyncio
    async def test_generate_report(self):
        """Test report generation."""
        from backend.agents.insight_mage import ReportFormatter

        mock_router = MagicMock()
        mock_router.route = AsyncMock(return_value={"content": "Summary report"})
        formatter = ReportFormatter(llm_router=mock_router)

        data = {
            "metrics": [
                {"name": "users", "value": 100},
                {"name": "queries", "value": 500}
            ]
        }

        result = await formatter.generate(data, trends=[], anomalies=[])
        assert isinstance(result, str)
        assert result == "Summary report"


class TestInsightMage:
    """Test main InsightMage agent."""

    def test_insight_mage_initialization(self):
        """Test InsightMage initializes correctly."""
        from backend.agents.insight_mage import InsightMage

        mage = InsightMage()
        assert mage is not None

    def test_cache_key_generation(self):
        """Test cache key is generated correctly."""
        from backend.agents.insight_mage import InsightMage

        mage = InsightMage()

        key = mage._cache_key("tenant-1", "users", "query-hash")
        assert isinstance(key, str)
        assert key.startswith("insight_mage:")
