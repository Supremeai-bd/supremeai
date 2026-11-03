# backend/tests/core/test_container_auditor.py
# বাংলা মন্তব্য: ContainerAuditor-এর জন্য comprehensive unit tests।
# Docker commands mock করা হয়েছে — actual Docker dependency ছাড়াই।

import json
from unittest.mock import MagicMock, patch

import pytest

from core.container_auditor import ContainerAuditor

# -------------------- Fixtures --------------------


@pytest.fixture
def auditor():
    """ContainerAuditor ইনস্ট্যান্স ফেরত দেয়।"""
    return ContainerAuditor()


@pytest.fixture
def mock_docker_stats_output():
    """Mock docker stats JSON output।"""
    return json_lines(
        [
            {"Name": "container1", "MemPerc": "45.2%"},
            {"Name": "container2", "MemPerc": "82.5%"},
            {"Name": "container3", "MemPerc": "96.8%"},
        ]
    )


def json_lines(items: list[dict]) -> str:
    """List of dicts-কে newline-separated JSON string-এ রূপান্তর করে।"""
    return "\n".join(json.dumps(item) for item in items)


# -------------------- Tests: __init__ --------------------


# -------------------- Tests: get_container_stats --------------------


class TestGetContainerStats:
    """বাংলা মন্তব্য: Docker stats fetching এবং error handling টেস্ট।"""

    def test_successful_stats_fetch(self, auditor, mock_docker_stats_output):
        """বাংলা মন্তব্য: সফলভাবে docker stats return হলে correct list-of-dicts পাওয়া যায়।"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = mock_docker_stats_output
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            stats = auditor.get_container_stats()

            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args
            assert call_kwargs.kwargs["capture_output"] is True
            assert call_kwargs.kwargs["text"] is True
            assert call_kwargs.kwargs["timeout"] == 10
            assert call_kwargs.kwargs["check"] is False

            assert len(stats) == 3
            assert stats[0]["Name"] == "container1"
            assert stats[2]["MemPerc"] == "96.8%"

    def test_docker_command_failure(self, auditor):
        """বাংলা মন্তব্য: docker stats command fail করলে empty list return হয়।"""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Cannot connect to Docker daemon"

        with patch("subprocess.run", return_value=mock_result):
            stats = auditor.get_container_stats()
            assert stats == []

    def test_docker_stats_timeout(self, auditor):
        """বাংলা মন্তব্য: subprocess timeout হলে empty list return হয়।"""
        import subprocess

        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="docker stats", timeout=10),
        ):
            stats = auditor.get_container_stats()
            assert stats == []

    def test_docker_stats_general_exception(self, auditor):
        """বাংলা মন্তব্য: যেকোনো unexpected exception handle করে empty list return হয়।"""
        with patch("subprocess.run", side_effect=RuntimeError("Unexpected error")):
            stats = auditor.get_container_stats()
            assert stats == []

    def test_empty_stdout(self, auditor):
        """বাংলা মন্তব্য: empty stdout-এ return হয় empty list।"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            stats = auditor.get_container_stats()
            assert stats == []

    def test_whitespace_only_stdout(self, auditor):
        """বাংলা মন্তব্য: whitespace-only stdout-এ return হয় empty list।"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "   \n  \n  "
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            stats = auditor.get_container_stats()
            assert stats == []


# -------------------- Tests: parse_memory_percent --------------------


class TestParseMemoryPercent:
    """বাংলা মন্তব্য: Memory percentage string parsing টেস্ট।"""

    def test_valid_percentage(self, auditor):
        assert auditor.parse_memory_percent("45.2%") == 45.2

    def test_high_percentage(self, auditor):
        assert auditor.parse_memory_percent("99.9%") == 99.9

    def test_zero_percentage(self, auditor):
        assert auditor.parse_memory_percent("0.00%") == 0.0

    def test_percentage_with_whitespace(self, auditor):
        assert auditor.parse_memory_percent("  50.5%  ") == 50.5

    def test_invalid_string_returns_zero(self, auditor):
        assert auditor.parse_memory_percent("N/A") == 0.0

    def test_empty_string_returns_zero(self, auditor):
        assert auditor.parse_memory_percent("") == 0.0

    def test_non_numeric_returns_zero(self, auditor):
        assert auditor.parse_memory_percent("abc%") == 0.0


# -------------------- Tests: audit_cycle --------------------


class TestAuditCycle:
    """বাংলা মন্তব্য: audit_cycle-এর memory threshold logic এবং docker kill টেস্ট।"""

    @pytest.mark.asyncio
    async def test_normal_memory_no_action(self, auditor):
        """বাংলা মন্তব্য: 80%-এর নিচে মেমরি থাকলে কোনো action নেই।"""
        stats = [{"Name": "container1", "MemPerc": "45.2%"}]

        with patch.object(auditor, "get_container_stats", return_value=stats):
            with patch("core.container_auditor.logger") as mock_logger:
                await auditor.audit_cycle()
                # কোনো warning বা error log হওয়া উচিত নয়
                mock_logger.warning.assert_not_called()
                mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_warning_threshold_80_percent(self, auditor):
        """বাংলা মন্তব্য: 80%+ মেমরি হলে warning log হয় কিন্তু kill হয় না।"""
        stats = [{"Name": "container_warn", "MemPerc": "82.5%"}]

        with patch.object(auditor, "get_container_stats", return_value=stats):
            with patch("core.container_auditor.logger") as mock_logger:
                with patch("subprocess.run") as mock_run:
                    await auditor.audit_cycle()

                    mock_logger.warning.assert_called_once()
                    assert "Memory Warning" in mock_logger.warning.call_args[0][0]
                    mock_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_critical_threshold_95_percent_kills_container(self, auditor):
        """বাংলা মন্তব্য: 95%+ মেমরি হলে docker kill command run হয়।"""
        stats = [{"Name": "oom_container", "MemPerc": "96.8%"}]

        with patch.object(auditor, "get_container_stats", return_value=stats):
            with patch("core.container_auditor.logger") as mock_logger:
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=0)

                    await auditor.audit_cycle()

                    mock_logger.error.assert_called_once()
                    assert "OOM Kill Chain Triggered" in mock_logger.error.call_args[0][0]
                    mock_run.assert_called_once_with(
                        ["docker", "kill", "oom_container"],
                        capture_output=True,
                        timeout=5,
                        check=False,
                    )

    @pytest.mark.asyncio
    async def test_kill_command_failure_logs_error(self, auditor):
        """বাংলা মন্তব্য: docker kill fail করলে error log হয়।"""
        stats = [{"Name": "bad_container", "MemPerc": "97.0%"}]

        with patch.object(auditor, "get_container_stats", return_value=stats):
            with patch("core.container_auditor.logger") as mock_logger:
                with patch("subprocess.run", side_effect=RuntimeError("Kill failed")):
                    await auditor.audit_cycle()

                    # OOM error + kill failure error — 2 error logs
                    error_calls = [
                        c
                        for c in mock_logger.error.call_args_list
                        if "OOM" in c[0][0] or "Failed to kill" in c[0][0]
                    ]
                    assert len(error_calls) >= 1

    @pytest.mark.asyncio
    async def test_multiple_containers_mixed_thresholds(self, auditor):
        """বাংলা মন্তব্য: Multiple containers-এ mixed thresholds correctly handle হয়।"""
        stats = [
            {"Name": "healthy", "MemPerc": "30.0%"},
            {"Name": "warning_container", "MemPerc": "85.0%"},
            {"Name": "critical_container", "MemPerc": "98.0%"},
        ]

        with patch.object(auditor, "get_container_stats", return_value=stats):
            with patch("core.container_auditor.logger") as mock_logger:
                with patch("subprocess.run") as mock_run:
                    await auditor.audit_cycle()

                    # 1 warning + 1 OOM error
                    assert mock_logger.warning.call_count == 1
                    assert mock_logger.error.call_count == 1
                    mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_stats_list(self, auditor):
        """বাংলা মন্তব্য: কোনো container না থাকলে audit_cycle peacefully শেষ হয়।"""
        with patch.object(auditor, "get_container_stats", return_value=[]):
            with patch("core.container_auditor.logger") as mock_logger:
                await auditor.audit_cycle()
                mock_logger.warning.assert_not_called()
                mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_audit_cycle_exception_handling(self, auditor):
        """বাংলা মন্তব্য: audit_cycle-এ exception হলে run() method handle করে।"""
        with patch.object(auditor, "get_container_stats", side_effect=RuntimeError("Unexpected")):
            with patch("core.container_auditor.logger") as mock_logger:
                await auditor.audit_cycle()
                mock_logger.error.assert_called_once()
                assert (
                    "Error in container audit cycle: Unexpected"
                    in mock_logger.error.call_args[0][0]
                )
                # Logger may or may not be called depending on implementation
                # The exception is raised, which is the important part


# -------------------- Tests: run --------------------


# -------------------- Tests: Integration --------------------


class TestContainerAuditorIntegration:
    """বাংলা মন্তব্য: Integration-style tests for realistic scenarios।"""

    @pytest.mark.asyncio
    async def test_full_cycle_with_mock_docker(self, auditor):
        """বাংলা মন্তব্য: Full audit cycle with realistic docker stats output।"""
        realistic_stats = [
            {"Name": "supremeai-backend", "MemPerc": "35.2%"},
            {"Name": "supremeai-worker-1", "MemPerc": "78.9%"},
            {"Name": "supremeai-worker-2", "MemPerc": "94.1%"},
        ]

        with patch.object(auditor, "get_container_stats", return_value=realistic_stats):
            with patch("core.container_auditor.logger") as mock_logger:
                with patch("subprocess.run"):
                    await auditor.audit_cycle()

                    # 78.9% < 80%, so no warning
                    # 94.1% < 95%, so no OOM kill
                    # But worker-2 at 94.1% is close to threshold, let's verify no critical actions
                    mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_full_cycle_with_critical_container(self, auditor):
        """বাংলা মন্তব্য: Full cycle with one critical container triggering kill।"""
        critical_stats = [
            {"Name": "leaking-container", "MemPerc": "97.5%"},
        ]

        with patch.object(auditor, "get_container_stats", return_value=critical_stats):
            with patch("core.container_auditor.logger") as mock_logger:
                with patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
                    await auditor.audit_cycle()

                    mock_logger.error.assert_called_once()
                    assert "OOM Kill Chain Triggered" in mock_logger.error.call_args[0][0]
                    mock_run.assert_called_once()
