"""A SARIF upload without `security-events: write` fails on main only.

Real instance (2026-11-19): `gateway-image.yml` uploaded Trivy SARIF with
`permissions: {contents: read, packages: write}`. The image built, the scan ran,
the summary printed — only the upload failed, and only on `main`, because the
step never runs for pull requests. Two merges in a row produced a red main run
while every PR check was green.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import sarif_permission_guard as guard  # noqa: E402

BAD = """name: img
permissions:
  contents: read
  packages: write
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: github/codeql-action/upload-sarif@v4
        with:
          sarif_file: trivy.sarif
"""

GOOD_JOB = """name: img
permissions:
  contents: read
jobs:
  build:
    permissions:
      contents: read
      security-events: write
    runs-on: ubuntu-latest
    steps:
      - uses: github/codeql-action/upload-sarif@v4
"""


def test_missing_permission_is_reported_once():
    problems = guard.audit_text(BAD, "wf.yml")
    assert len(problems) == 1, problems
    assert "wf.yml:" in problems[0]
    assert "security-events: write" in problems[0]


def test_job_level_permission_passes():
    assert guard.audit_text(GOOD_JOB, "wf.yml") == []


def test_workflow_level_permission_passes():
    text = BAD.replace("  packages: write", "  security-events: write")
    assert guard.audit_text(text, "wf.yml") == []


def test_other_jobs_permission_does_not_cover_the_upload():
    text = GOOD_JOB.replace("  build:", "  scan:").replace(
        "      - uses: github/codeql-action/upload-sarif@v4",
        "      - run: echo noop",
    ) + "  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: github/codeql-action/upload-sarif@v4\n"
    assert guard.audit_text(text, "wf.yml")


def test_files_without_sarif_are_ignored():
    assert guard.audit_text("name: x\njobs:\n  a:\n    runs-on: x\n", "wf.yml") == []


def test_live_workflows_grant_the_permission():
    """The repository itself must be clean — this is the regression lock."""
    assert guard.audit_surface(REPO_ROOT) == []


def test_empty_surface_is_not_a_pass(tmp_path):
    assert any("SURFACE_EMPTY" in p for p in guard.audit_surface(tmp_path))
