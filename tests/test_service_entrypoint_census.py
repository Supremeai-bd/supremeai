"""Census of `config/service_registry.yaml` entrypoints against the real tree.

The registry drives deploy planning and keepwarm, so an entry pointing at a
path that does not exist is not cosmetic — it makes the planner reason about a
service that cannot be built.

Two properties this suite protects, both of which the first version of the
guard got wrong:

* **ASGI targets are checked too.** `uvicorn gateway.service.app:app` was
  skipped entirely (no `.py` token to match), which left the two biggest live
  services unverified while the guard printed "all service entrypoints
  verified".
* **Unverified is reported, never rounded up to verified.** Services that
  declare no entrypoint at all are counted separately.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "service_entrypoint_census.py"
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))

import service_entrypoint_census as census  # noqa: E402


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=180, check=False,
    )


def test_self_test_matrix_passes():
    result = _run("--self-test")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "8/8 passed" in result.stdout


def test_live_registry_passes_and_reports_coverage():
    result = _run("--check")
    assert result.returncode == 0, result.stdout + result.stderr
    # Never the bare "all verified" claim: the line must carry counts.
    assert "verified " in result.stdout and "/" in result.stdout


def test_asgi_target_resolves_to_a_module_path():
    paths = census.candidate_paths({"entrypoint": "uvicorn gateway.service.app:app --port 8787"})
    assert "gateway/service/app.py" in paths


def test_docker_context_is_applied_to_module_resolution():
    paths = census.candidate_paths({"entrypoint": "uvicorn main:app", "docker_context": "browser"})
    assert "browser/main.py" in paths


def test_entrypoint_without_a_path_claim_is_not_verified():
    assert census.candidate_paths({"platform": "render"}) == []


def test_unknown_status_is_fail_closed(tmp_path):
    violations, _census_data = census.check_registry(
        {"services": {"x": {"status": "retird", "entrypoint": "x.py"}}}, tmp_path
    )
    assert len(violations) == 1 and "unknown status" in violations[0]


@pytest.mark.parametrize("status", ["live", "retired"])
def test_status_values_are_accepted(tmp_path, status):
    (tmp_path / "keep.py").write_text("", encoding="utf-8")
    spec = {"status": status, "entrypoint": "keep.py"}
    if status == "retired":
        spec["retired_evidence"] = "why"
        violations, _ = census.check_registry({"services": {"x": spec}}, tmp_path)
        assert len(violations) == 1 and "still exists" in violations[0]
    else:
        violations, _ = census.check_registry({"services": {"x": spec}}, tmp_path)
        assert violations == []
