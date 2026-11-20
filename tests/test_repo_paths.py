"""Tests for the repo path resolver.

The resolver exists because 101 tracked scripts referenced a top-level
``backend/`` directory that has never existed in this repository
(``git log --all -- backend/`` is empty). Guards built on that dead path crash
with ``FileNotFoundError`` instead of returning a verdict, and a crash read as
an exit code looks identical to a finding.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "ci"))

import repo_paths  # noqa: E402
from repo_paths import (  # noqa: E402
    BACKEND_ALIAS,
    REPO_ROOT,
    RepoPathError,
    candidates,
    require,
    resolve,
)


class TestRoot:
    def test_root_is_a_repository(self):
        assert (REPO_ROOT / "scripts" / "ci").is_dir()

    def test_root_is_found_by_walking_not_counting(self):
        # `.git` is the same rule git itself uses; counting parents breaks when
        # this module moves.
        assert (REPO_ROOT / ".git").exists() or (REPO_ROOT / "pyproject.toml").exists()


class TestAliasIsJustifiedByTheTree:
    """The backend -> core alias must describe reality, not opinion."""

    def test_backend_directory_does_not_exist(self):
        assert not (REPO_ROOT / "backend").exists()

    def test_measured_evidence_rows(self):
        rows = repo_paths.alias_evidence()
        assert rows, "alias evidence must not be empty"
        for sub, under_backend, under_core in rows:
            assert under_core, f"{BACKEND_ALIAS}/{sub} should exist"
            assert not under_backend, f"backend/{sub} unexpectedly exists"

    def test_alias_target_exists(self):
        assert (REPO_ROOT / BACKEND_ALIAS).is_dir()

    def test_history_never_contained_backend(self):
        """Guards against someone "fixing" this by recreating backend/."""
        out = subprocess.run(
            ["git", "log", "--oneline", "--all", "--", "backend/"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        ).stdout.strip()
        assert out == "", f"backend/ unexpectedly has history: {out[:200]}"


class TestResolution:
    def test_resolves_existing_path(self):
        assert resolve("scripts/ci") is not None

    def test_returns_none_for_missing(self):
        assert resolve("no_such_dir_xyz/deeper") is None

    def test_literal_path_is_preferred(self):
        """If backend/ ever returns, it must win over the alias."""
        tops = [c.relative_to(REPO_ROOT).parts[0] for c in candidates("backend/api")]
        assert tops[0] == "backend"
        assert tops[1] == BACKEND_ALIAS

    def test_alias_resolves_real_subpath(self):
        assert resolve("backend/api/routes") is not None

    def test_non_backend_paths_get_no_alias(self):
        assert len(candidates("scripts/ci")) == 1

    def test_empty_path_has_no_candidates(self):
        assert candidates("") == []

    def test_require_returns_resolved_path(self):
        assert require("backend/api").name == "api"

    def test_require_raises_with_actionable_message(self):
        try:
            require("backend/definitely_not_here_xyz")
        except RepoPathError as exc:
            assert "never existed" in str(exc)
            assert "Tried:" in str(exc)
        else:
            raise AssertionError("require() did not raise")

    def test_repo_path_error_is_a_filenotfound(self):
        # Callers that catch FileNotFoundError keep working.
        assert issubclass(RepoPathError, FileNotFoundError)


class TestDeadReferenceReport:
    def test_reports_the_measured_count(self):
        """The count must match what grep sees, not a number in the source."""
        out = subprocess.run(
            ["git", "grep", "-l", "backend/", "--", "scripts"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        ).stdout.strip().splitlines()
        expected = [line for line in out if line.endswith(".py")]
        count, files = repo_paths._dead_reference_report()
        assert count == len(expected), f"reported {count}, grep sees {len(expected)}"
        assert sorted(files) == sorted(expected)
