from unittest.mock import AsyncMock, patch

import pytest

from tools.devops.auto_coverage_improver import AutoCoverageImprover
from tools.devops.coverage_auditor import CoverageGap


@pytest.fixture
def improver():
    """Provides an instance of AutoCoverageImprover with mocked dependencies."""
    with (
        patch("tools.devops.auto_coverage_improver.CoverageAuditor") as MockAuditor,
        patch("tools.devops.auto_coverage_improver.AutoTestGenerator") as MockGenerator,
    ):
        improver_instance = AutoCoverageImprover()
        improver_instance.auditor = MockAuditor()
        improver_instance.generator = MockGenerator()
        yield improver_instance


@pytest.mark.anyio
async def test_run_with_gaps(improver):
    """
    Tests the run method when coverage gaps are found and tests are generated successfully.
    """
    mock_gaps = [
        CoverageGap(file_path="src/module1.py", coverage=50.0, uncovered_lines=[10]),
        CoverageGap(file_path="src/module2.py", coverage=75.0, uncovered_lines=[5]),
    ]
    improver.auditor.find_gaps.return_value = mock_gaps
    improver.generator.generate_and_save = AsyncMock(return_value={"status": "success"})

    with patch("os.path.exists", return_value=True):
        report = await improver.run("coverage.xml", min_coverage_target=80.0)

    assert report["status"] == "completed"
    assert report["gaps_found"] == 2
    assert report["tests_generated"] == 2
    improver.auditor.find_gaps.assert_called_once_with("coverage.xml", min_coverage=80.0)
    assert improver.generator.generate_and_save.call_count == 2


@pytest.mark.anyio
async def test_run_no_gaps_found(improver):
    """
    Tests the run method when the auditor finds no coverage gaps.
    """
    improver.auditor.find_gaps.return_value = []

    report = await improver.run("coverage.xml")

    assert report["status"] == "success"
    assert report["message"] == "No coverage gaps found."
    assert improver.generator.generate_and_save.call_count == 0


@pytest.mark.anyio
async def test_run_skips_non_existent_files(improver):
    """
    Tests that files that don't exist on disk are skipped.
    """
    mock_gaps = [CoverageGap(file_path="src/non_existent.py", coverage=40.0, uncovered_lines=[1])]
    improver.auditor.find_gaps.return_value = mock_gaps

    with patch("os.path.exists", return_value=False):
        report = await improver.run("coverage.xml")

    assert report["status"] == "completed"
    assert report["gaps_found"] == 1
    assert report["tests_generated"] == 0
    assert improver.generator.generate_and_save.call_count == 0


@pytest.mark.anyio
async def test_run_with_dry_run_enabled(improver):
    """
    Tests that `run_tests` is False when `dry_run` is True.
    """
    mock_gaps = [CoverageGap(file_path="src/module1.py", coverage=50.0, uncovered_lines=[10])]
    improver.auditor.find_gaps.return_value = mock_gaps
    improver.generator.generate_and_save = AsyncMock(return_value={"status": "success"})

    with patch("os.path.exists", return_value=True):
        await improver.run("coverage.xml", dry_run=True)

    # Check that generate_and_save was called with run_tests=False
    improver.generator.generate_and_save.assert_called_once_with("src/module1.py", run_tests=False)
