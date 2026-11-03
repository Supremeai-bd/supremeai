from unittest.mock import mock_open, patch

import pytest

from tools.devops.coverage_auditor import CoverageAuditor, CoverageGap


@pytest.fixture
def auditor():
    """Provides an instance of the CoverageAuditor."""
    return CoverageAuditor()


@pytest.fixture
def mock_coverage_xml():
    """Provides a mock coverage.xml content."""
    return """<?xml version="1.0" ?>
<coverage lines-covered="85" lines-valid="100" branches-covered="80" branches-valid="100" complexity="0" version="6.5.0" timestamp="1678886400">
	<sources>
		<source>/app/src</source>
	</sources>
	<packages>
		<package name="my_app" line-rate="0.85" branch-rate="0.8">
			<classes>
				<class name="module1.py" filename="my_app/module1.py" complexity="0" line-rate="1" branch-rate="1">
					<methods/>
					<lines>
						<line number="1" hits="1"/>
						<line number="2" hits="1"/>
					</lines>
				</class>
				<class name="module2.py" filename="my_app/module2.py" complexity="0" line-rate="0.5" branch-rate="0.5">
					<methods/>
					<lines>
						<line number="1" hits="1"/>
						<line number="2" hits="0"/>
					</lines>
				</class>
                <class name="module3.py" filename="my_app/module3.py" complexity="0" line-rate="0.7" branch-rate="0.7">
					<methods/>
					<lines>
						<line number="1" hits="1"/>
                        <line number="2" hits="1"/>
						<line number="3" hits="0"/>
					</lines>
				</class>
			</classes>
		</package>
	</packages>
</coverage>
"""


@pytest.fixture
def mock_coverage_json():
    """Provides a mock coverage.json content (Istanbul format)."""
    return """
{
  "total": {"lines":{"total":10,"covered":7,"skipped":0,"pct":70}},
  "src/app.js": {"lines":{"total":5,"covered":5,"skipped":0,"pct":100}},
  "src/utils.js": {"lines":{"total":5,"covered":2,"skipped":0,"pct":40}, "uncovered_lines": [3, 4, 5]}
}
"""


def test_find_gaps_identifies_low_coverage_from_json(auditor, mock_coverage_json):
    """
    Tests that find_gaps correctly identifies low coverage files from a JSON report.
    """
    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=mock_coverage_json)),
    ):
        gaps = auditor.find_gaps("dummy/path/coverage.json", min_coverage=80)

    assert len(gaps) == 1
    assert gaps[0].file_path == "src/utils.js"
    assert gaps[0].coverage == 40.0
    assert gaps[0].uncovered_lines == [3, 4, 5]


def test_find_gaps_identifies_low_coverage_files(auditor, mock_coverage_xml):
    """
    Tests that find_gaps correctly identifies files below the coverage threshold.
    """
    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=mock_coverage_xml)),
    ):
        gaps = auditor.find_gaps("dummy/path/coverage.xml", min_coverage=80)

    assert len(gaps) == 2
    assert isinstance(gaps[0], CoverageGap)
    assert gaps[0].file_path == "my_app/module2.py"
    assert gaps[0].coverage == 50.0
    assert gaps[1].file_path == "my_app/module3.py"
    assert gaps[1].coverage == 70.0


def test_find_gaps_respects_min_coverage_threshold(auditor, mock_coverage_xml):
    """
    Tests that the min_coverage threshold is correctly applied.
    """
    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=mock_coverage_xml)),
    ):
        # With a lower threshold, module3 should not be included
        gaps = auditor.find_gaps("dummy/path/coverage.xml", min_coverage=60)

    assert len(gaps) == 1
    assert gaps[0].file_path == "my_app/module2.py"
    assert gaps[0].coverage == 50.0


def test_find_gaps_handles_file_not_found(auditor):
    """
    Tests that the auditor handles a missing coverage file gracefully.
    """
    with patch("builtins.open", side_effect=FileNotFoundError):
        gaps = auditor.find_gaps("non_existent_file.xml")
    assert gaps == []


def test_find_gaps_handles_invalid_xml(auditor):
    """
    Tests that the auditor handles a malformed XML file.
    """
    invalid_xml = "<coverage><invalid"
    with patch("builtins.open", mock_open(read_data=invalid_xml)):
        gaps = auditor.find_gaps("invalid.xml")
    assert gaps == []


def test_coverage_gap_dataclass():
    """Tests the CoverageGap dataclass."""
    gap = CoverageGap(file_path="src/main.py", coverage=75.5, uncovered_lines=[10, 15])
    assert gap.file_path == "src/main.py"
    assert gap.coverage == 75.5
    assert gap.uncovered_lines == [10, 15]
