"""Offline checks of the deploy planner used by the unified workflow."""

import json
import sys

import pytest

from scripts.ci import plan_render_deploys as planner


_RUNTIME_SERVICES = {"core", "scraper", "mcp", "worker"}
_BOOTSTRAP = "scripts/runtime/infisical_bootstrap.py"


@pytest.mark.parametrize(
    ("path", "api_registered", "services", "unregistered"),
    [
        (_BOOTSTRAP, True, _RUNTIME_SERVICES | {"api"}, []),
        (_BOOTSTRAP, False, _RUNTIME_SERVICES, ["api:RENDER_API_SERVICE_ID"]),
        ("scripts/runtime/other.py", True, _RUNTIME_SERVICES, []),
        ("gateway/service/app.py", True, {"api"}, []),
        ("docs/INDEX.md", True, set(), []),
        ("scripts/lib/render_client.py", True, set(), []),
    ],
    ids=["copied-bootstrap", "missing-api-id", "other-runtime-file", "gateway-only", "docs-only", "ci-client-only"],
)
def test_changed_paths_emit_expected_matrix(monkeypatch, tmp_path, capsys, path, api_registered, services, unregistered):
    for service, spec in planner.render_services().items():
        id_env = spec["canonical_service_id_env"]
        for name in (id_env, *spec.get("service_id_aliases", ())):
            monkeypatch.delenv(name, raising=False)
        if service != "api" or api_registered:
            monkeypatch.setenv(id_env, f"srv-{service}")

    output = tmp_path / "github_output"
    monkeypatch.setattr(planner, "changed_files", lambda _base, _head: [path])
    monkeypatch.setattr(sys, "argv", ["plan_render_deploys.py", "--base", "base", "--head", "head", "--output", str(output)])

    assert planner.main() == 0
    outputs = dict(line.split("=", 1) for line in output.read_text().splitlines())
    matrix = json.loads(outputs["matrix"])["include"]
    assert {item["service"]: item["service_id"] for item in matrix} == {svc: f"srv-{svc}" for svc in services}
    assert outputs["has_services"] == ("true" if services else "false")
    assert json.loads(outputs["unregistered"]) == unregistered
    assert ("::warning::api:" in capsys.readouterr().err) == bool(unregistered)


@pytest.mark.parametrize("force", [False, True], ids=["push", "rollback"])
def test_mcp_cutover_uses_the_same_target_and_only_paykari_key(monkeypatch, tmp_path, force):
    monkeypatch.setenv("RENDER_MCP_SERVICE_ID", "srv-replacement")
    monkeypatch.setenv("RENDER_MCP_SVC_ID", "srv-retired")
    monkeypatch.setenv("RENDER_MCP_URL", "https://stale.onrender.com")
    monkeypatch.setattr(planner, "changed_files", lambda *_: ["infrastructure/mcp-control-plane/src/index.ts"])
    out = tmp_path / "matrix"
    args = ["plan_render_deploys.py", "--targets", "mcp", "--output", str(out)]
    if force:
        args += ["--force", "--require-configured"]
    monkeypatch.setattr(sys, "argv", args)
    assert planner.main() == 0
    outputs = dict(line.split("=", 1) for line in out.read_text().splitlines())
    assert json.loads(outputs["matrix"])["include"] == [{
        "service": "mcp", "service_id": "srv-replacement", "api_key_env": "RENDER_API_PAYKARI",
        "api_key_alias_env": "RENDER_API_KEY_PAYKARI", "health_path": "/health",
    }]


def test_mcp_rollback_does_not_fall_back_to_the_old_id(monkeypatch, capsys):
    monkeypatch.delenv("RENDER_MCP_SERVICE_ID", raising=False)
    monkeypatch.setenv("RENDER_MCP_SVC_ID", "srv-retired")
    monkeypatch.setattr(sys, "argv", ["plan_render_deploys.py", "--force", "--targets", "mcp", "--require-configured"])
    with pytest.raises(SystemExit, match="2"):
        planner.main()
    assert "mcp:RENDER_MCP_SERVICE_ID" in capsys.readouterr().err


def test_production_push_does_not_deploy_ci_runner(monkeypatch, tmp_path):
    out = tmp_path / "matrix"
    monkeypatch.setenv("RENDER_CI_RUNNER_SERVICE_ID", "srv-inactive")
    monkeypatch.setattr(planner, "changed_files", lambda *_: ["scripts/ci/render_trigger_deploy.py"])
    monkeypatch.setattr(sys, "argv", ["plan_render_deploys.py", "--output", str(out)])
    assert planner.main() == 0
    assert "matrix={\"include\":[]}" in out.read_text()


def test_cutover_must_not_reuse_inactive_auxiliary_runner(monkeypatch, capsys):
    monkeypatch.setenv("RENDER_MCP_SERVICE_ID", "srv-cirunner")
    monkeypatch.setenv("RENDER_CI_RUNNER_SERVICE_ID", "srv-cirunner")
    monkeypatch.setattr(sys, "argv", ["plan_render_deploys.py", "--force", "--targets", "mcp"])
    with pytest.raises(SystemExit, match="2"):
        planner.main()
    assert "registered to another role" in capsys.readouterr().err
