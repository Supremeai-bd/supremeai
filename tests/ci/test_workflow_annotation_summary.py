import json
from pathlib import Path

import pytest
import yaml

from scripts.ci import workflow_annotation_summary as summary

SHA = "a" * 40


def test_report_counts_all_pages_and_excludes_untrusted_messages():
    def fetch(path, _token):
        if "/attempts/" in path:
            yield {"jobs": [{"id": 10}, {"id": 11}]}
        elif "/commits/" in path:
            yield {"check_runs": [{"id": 12, "name": "CodeQL", "app": {"slug": "github-advanced-security"}}]}
        elif "/10/" in path:
            yield [{"annotation_level": "warning", "message": "PRIVATE_FIXTURE"}]
            yield [{"annotation_level": "failure", "message": "PRIVATE_FIXTURE"}]
        elif "/11/" in path:
            yield []
        else:
            yield [{"annotation_level": "failure", "message": "PRIVATE_FIXTURE"}]
    result = summary.report("org/repo", "5", "2", SHA, "token", fetch)
    assert "**Total:** 1 warning, 2 failure" in result
    assert "Same-SHA CodeQL `12`" in result
    assert "PRIVATE_FIXTURE" not in result and "token" not in result
    assert "attempts/2" in result


def test_failure_does_not_report_clean_or_leak_exception(tmp_path, monkeypatch):
    out = tmp_path / "summary"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(out))
    monkeypatch.setattr(summary, "report", lambda *a: (_ for _ in ()).throw(RuntimeError("PRIVATE_FIXTURE")))
    assert summary.main() == 1
    text = out.read_text()
    assert "INCOMPLETE" in text and "PRIVATE_FIXTURE" not in text
    assert "0 warning" not in text


def test_empty_or_invalid_source_cannot_be_reported_as_success():
    with pytest.raises(ValueError):
        summary.report("org/repo", "1", "1", SHA, "token", lambda *_: iter([{"jobs": []}]))
    with pytest.raises(ValueError):
        summary.report("org/repo/unsafe", "1", "1", SHA, "token", lambda *_: iter([]))




def test_unfinished_jobs_mark_snapshot_incomplete():
    def fetch(path, _token):
        if "/attempts/" in path:
            yield {"jobs": [{"id": 10, "status": "in_progress"}, {"id": 11, "status": "completed", "conclusion": "skipped"}]}
        elif "/commits/" in path:
            yield {"check_runs": []}
        else:
            yield []
    result = summary.report("org/repo", "5", "2", SHA, "token", fetch)
    assert "INCOMPLETE SNAPSHOT" in result and "1 job(s)" in result
    assert "skipped: 1" in result


def test_reporter_uses_trusted_default_branch_for_fork_prs():
    path = Path(__file__).resolve().parents[2] / ".github/workflows/unified-pipeline.yml"
    jobs = yaml.safe_load(path.read_text())["jobs"]
    reporter = jobs["warning-summary"]
    checkout = next(step for step in reporter["steps"] if step.get("name") == "Checkout trusted default branch")
    assert checkout["with"]["ref"] == "${{ github.event.repository.default_branch }}"
    assert checkout["with"]["persist-credentials"] is False
    assert all(value == "read" for value in reporter["permissions"].values())
