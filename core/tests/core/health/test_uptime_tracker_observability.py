from __future__ import annotations

from unittest.mock import patch

from core.health import uptime_tracker


def test_record_check_logs_persistence_failure(caplog):
    with patch.object(uptime_tracker, "_connect", side_effect=OSError("disk unavailable")):
        with caplog.at_level("ERROR", logger=uptime_tracker._LOGGER.name):
            uptime_tracker.record_check("api", "healthy", 12.5)

    assert "Failed to persist uptime check" in caplog.text
    assert "disk unavailable" in caplog.text


def test_get_uptime_percentage_logs_read_failure(caplog):
    with patch.object(uptime_tracker, "_connect", side_effect=OSError("database unavailable")):
        with caplog.at_level("ERROR", logger=uptime_tracker._LOGGER.name):
            result = uptime_tracker.get_uptime_percentage("api", 24)

    assert result is None
    assert "Failed to calculate uptime percentage" in caplog.text
    assert "database unavailable" in caplog.text


def test_get_history_logs_read_failure(caplog):
    with patch.object(uptime_tracker, "_connect", side_effect=OSError("database unavailable")):
        with caplog.at_level("ERROR", logger=uptime_tracker._LOGGER.name):
            result = uptime_tracker.get_history("api")

    assert result == []
    assert "Failed to read uptime history" in caplog.text
    assert "database unavailable" in caplog.text
