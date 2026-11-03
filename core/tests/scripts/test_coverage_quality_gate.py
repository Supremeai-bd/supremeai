"""Tests for scripts/ci/coverage_quality_gate.py — the tiered coverage gate.

BACKGROUND (final-test hardening-2, 2026-09-14): the gate's path matcher
compared "backend/..."-prefixed policy globs against coverage.json paths
("core/...", relative to the backend root). Nothing ever matched, both tiers
accumulated zero files, and the divide-by-zero guard reported a vacuous
100.00% pass — the gate never enforced anything. These tests lock in the
fixed, fail-closed contract:

1. Path normalization: bare and "backend/"-prefixed forms both match.
2. dir/** semantics: any depth below the directory.
3. Fail-closed: a tier matching ZERO files must FAIL (policy/scope drift).
4. Honest thresholds: below-threshold coverage fails, at/above passes.
5. Exit codes: 0 on pass, 1 on any failure.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_GATE = _REPO_ROOT / "scripts" / "ci" / "coverage_quality_gate.py"

if not _GATE.is_file():
    pytest.skip(
        f"scripts/ci/coverage_quality_gate.py not found at {_GATE} — the CI "
        "tooling appears to have been moved or removed. Restore it or update "
        "this test's path.",
        allow_module_level=True,
    )


def _run_gate(cov_payload: dict, policy_path: Path, tiers: str) -> subprocess.CompletedProcess:
    cov_file = policy_path.parent / "_gate_test_coverage.json"
    cov_file.write_text(json.dumps(cov_payload))
    try:
        completed = subprocess.run(
            [sys.executable, str(_GATE), str(cov_file), str(policy_path), "--tiers", tiers],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # loguru logs to stderr; fold both streams so assertions read one field.
        completed.stdout = completed.stdout + completed.stderr
        return completed
    finally:
        cov_file.unlink(missing_ok=True)


@pytest.fixture(scope="module")
def policy_file(tmp_path_factory) -> Path:
    policy = tmp_path_factory.mktemp("policy") / "coverage_policy.yaml"
    policy.write_text(
        """
version: 1
thresholds:
  overall:
    pr: 25
  critical:
    pr: 37
  important:
    pr: 27
critical:
  - core/llm/**
  - core/security/**
  - api/routes/billing*
important:
  - services/**
  - api/routes/**
"""
    )
    return policy


def _file(stmts: int, covered: int) -> dict:
    return {"summary": {"num_statements": stmts, "covered_lines": covered}}


class TestPathNormalization:
    """The vacuous-pass regression: policy globs must match real coverage paths."""

    def test_bare_policy_glob_matches_bare_coverage_path(self, policy_file):
        cov = {
            "totals": {"percent_covered": 100.0},
            "files": {"core/llm/router.py": _file(10, 10)},
        }
        result = _run_gate(cov, policy_file, "critical")
        assert result.returncode == 0, result.stderr
        assert "1 files" in result.stdout

    def test_backend_prefixed_coverage_path_also_matches(self, policy_file):
        cov = {
            "totals": {"percent_covered": 100.0},
            "files": {"backend/core/llm/router.py": _file(10, 10)},
        }
        result = _run_gate(cov, policy_file, "critical")
        assert result.returncode == 0, result.stderr
        assert "1 files" in result.stdout

    def test_dir_glob_matches_any_depth(self, policy_file):
        cov = {
            "totals": {"percent_covered": 100.0},
            "files": {"core/llm/gateway/deep/nested/module.py": _file(10, 10)},
        }
        result = _run_gate(cov, policy_file, "critical")
        assert result.returncode == 0, result.stderr
        assert "1 files" in result.stdout

    def test_fnmatch_prefix_pattern(self, policy_file):
        cov = {
            "totals": {"percent_covered": 100.0},
            "files": {"api/routes/billing_api.py": _file(10, 10)},
        }
        result = _run_gate(cov, policy_file, "critical")
        assert result.returncode == 0, result.stderr
        assert "1 files" in result.stdout


class TestFailClosed:
    """A vacuous 100% is forbidden: zero matched files must fail the gate."""

    def test_zero_matched_critical_files_fails(self, policy_file):
        cov = {
            "totals": {"percent_covered": 90.0},
            "files": {"unrelated/module.py": _file(10, 9)},
        }
        result = _run_gate(cov, policy_file, "critical")
        assert result.returncode == 1
        assert "matched 0 files" in result.stdout
        assert "drift" in result.stdout

    def test_zero_matched_important_files_fails(self, policy_file):
        cov = {
            "totals": {"percent_covered": 90.0},
            "files": {"core/llm/router.py": _file(10, 9)},  # critical, not important
        }
        result = _run_gate(cov, policy_file, "important")
        assert result.returncode == 1
        assert "matched 0 files" in result.stdout

    def test_empty_coverage_file_fails(self, policy_file):
        cov = {"totals": {"percent_covered": 50.0}, "files": {}}
        result = _run_gate(cov, policy_file, "overall,critical,important")
        assert result.returncode == 1

    def test_below_threshold_critical_fails(self, policy_file):
        cov = {
            "totals": {"percent_covered": 10.0},
            "files": {"core/llm/router.py": _file(100, 10)},
        }
        result = _run_gate(cov, policy_file, "critical")
        assert result.returncode == 1
        assert "10.00%" in result.stdout
        assert "below" in result.stdout


class TestHonestReporting:
    def test_exact_threshold_passes(self, policy_file):
        # 37% is the policy threshold: 37/100 covered must pass.
        cov = {
            "totals": {"percent_covered": 37.0},
            "files": {"core/llm/router.py": _file(100, 37)},
        }
        result = _run_gate(cov, policy_file, "critical")
        assert result.returncode == 0, result.stdout

    def test_evidence_logs_worst_offenders(self, policy_file):
        cov = {
            "totals": {"percent_covered": 50.0},
            "files": {
                "core/llm/big.py": _file(100, 10),
                "core/llm/small.py": _file(10, 9),
            },
        }
        result = _run_gate(cov, policy_file, "critical")
        assert "core/llm/big.py" in result.stdout
        assert "90 missed" in result.stdout

    def test_mixed_tiers_aggregate_across_files(self, policy_file):
        cov = {
            "totals": {"percent_covered": 60.0},
            "files": {
                "core/llm/a.py": _file(100, 50),
                "core/security/b.py": _file(100, 70),
                "services/c.py": _file(100, 30),
            },
        }
        result = _run_gate(cov, policy_file, "critical,important")
        assert result.returncode == 0, result.stdout
        # critical: (50+70)/200 = 60%; important: 30/100 = 30%
        assert "60.00%" in result.stdout
        assert "30.00%" in result.stdout
