"""Unit tests for Script Sprawl Guard (Loop 1 of Continuous Maintenance)."""

import pytest
from scripts.ci.sprawl_guard import (
    BASELINE_ROOT_SCRIPTS,
    check_changed_files,
    is_root_sprawl_path,
)


def test_is_root_sprawl_path():
    assert is_root_sprawl_path("scripts/test.py") is True
    assert is_root_sprawl_path("scripts\\test.py") is True
    assert is_root_sprawl_path("./scripts/test.py") is True
    assert is_root_sprawl_path("scripts/ci/sprawl_guard.py") is False
    assert is_root_sprawl_path("backend/main.py") is False
    assert is_root_sprawl_path("scripts/supremeai_toolkit/tools.py") is False


def test_check_changed_files_detects_new_root_script():
    files = [
        {"filename": "scripts/new_random_script.py", "status": "added"},
        {"filename": "scripts/ci/new_tool.py", "status": "added"},
    ]
    ok, offenders = check_changed_files(files)
    assert ok is False
    assert offenders == ["scripts/new_random_script.py"]


def test_check_changed_files_allows_baseline_scripts():
    first_baseline = next(iter(BASELINE_ROOT_SCRIPTS))
    files = [
        {"filename": f"scripts/{first_baseline}", "status": "modified"},
        {"filename": "scripts/ci/good_script.py", "status": "added"},
    ]
    ok, offenders = check_changed_files(files)
    assert ok is True
    assert offenders == []


def test_check_changed_files_allows_subdirectories():
    files = [
        {"filename": "scripts/supremeai_toolkit/runner.py", "status": "added"},
        {"filename": "scripts/agents/planner.py", "status": "added"},
        {"filename": "scripts/ci/test_runner.py", "status": "added"},
    ]
    ok, offenders = check_changed_files(files)
    assert ok is True
    assert offenders == []
