"""বাংলা মন্তব্য: scripts/ci/workflow_annotation_summary.py-এর জন্য হার্মেটিক ইউনিট টেস্ট (test_parity_guard পরিপূরক)।"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "workflow_annotation_summary.py"
_SPEC = importlib.util.spec_from_file_location("workflow_annotation_summary", SCRIPT_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)

VALID_SHA = "a" * 40


def test_report_summarizes_counts_without_leaking_messages():
    # বাংলা মন্তব্য: অ্যানোটেশনের কাঁচা বার্তা বা গোপন তথ্য কখনোই সামারিতে কপি হবে না
    secret_text = "SECRET_LEAK_DO_NOT_ECHO_12345"

    def fake_fetch(path: str, _token: str):
        if path.endswith("/jobs"):
            yield {
                "jobs": [
                    {"id": 101, "status": "completed", "conclusion": "success"},
                    {"id": 102, "status": "in_progress", "conclusion": None},
                ]
            }
        elif path.endswith("/check-runs"):
            yield {
                "check_runs": [
                    {
                        "id": 555,
                        "name": "CodeQL",
                        "status": "completed",
                        "app": {"slug": "github-advanced-security"},
                    }
                ]
            }
        elif "/check-runs/101/annotations" in path:
            yield [
                {"annotation_level": "warning", "message": secret_text},
                {"annotation_level": "notice", "message": "ignored"},
            ]
        elif "/check-runs/102/annotations" in path:
            yield []
        elif "/check-runs/555/annotations" in path:
            yield [{"annotation_level": "failure", "message": secret_text}]
        else:
            raise AssertionError(f"Unexpected path: {path}")

    summary = mod.report(
        "Supremeai-bd/supremeai",
        "24570001",
        "1",
        VALID_SHA,
        "tok_readonly",
        fetch=fake_fetch,
    )
    assert "| Actions job `101` | 1 | 0 |" in summary
    assert "| Same-SHA CodeQL `555` | 0 | 1 |" in summary
    assert "**INCOMPLETE SNAPSHOT:** 1 job(s) and 0 CodeQL check(s)" in summary
    assert "**Total:** 1 warning, 1 failure annotations" in summary
    assert secret_text not in summary


@pytest.mark.parametrize(
    "repo,run,attempt,sha,token",
    [
        ("bad repo", "1", "1", VALID_SHA, "tok"),
        ("Supremeai-bd/supremeai", "0", "1", VALID_SHA, "tok"),
        ("Supremeai-bd/supremeai", "1", "abc", VALID_SHA, "tok"),
        ("Supremeai-bd/supremeai", "1", "1", "shortsha", "tok"),
        ("Supremeai-bd/supremeai", "1", "1", VALID_SHA, ""),
    ],
)
def test_report_rejects_invalid_parameters(repo, run, attempt, sha, token):
    with pytest.raises(ValueError):
        mod.report(repo, run, attempt, sha, token, fetch=lambda *_a: iter(()))


def test_report_fails_closed_when_jobs_list_is_empty():
    with pytest.raises(ValueError, match="No source jobs returned"):
        mod.report(
            "Supremeai-bd/supremeai",
            "12",
            "1",
            VALID_SHA,
            "tok",
            fetch=lambda *_a: iter([{"jobs": []}]),
        )


def test_main_fails_when_summary_env_missing(monkeypatch):
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert mod.main() == 1
