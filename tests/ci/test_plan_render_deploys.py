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
    ],
    ids=["copied-bootstrap", "missing-api-id", "other-runtime-file", "gateway-only", "docs-only"],
)
def test_changed_paths_emit_expected_matrix(monkeypatch, tmp_path, capsys, path, api_registered, services, unregistered):
    for service, (id_env, _, _, _) in planner.SERVICE_RULES.items():
        for alias in planner.SERVICE_ID_ALIASES.get(id_env, ()):
            monkeypatch.delenv(alias, raising=False)
        if service == "api" and not api_registered:
            monkeypatch.delenv(id_env, raising=False)
        else:
            monkeypatch.setenv(id_env, f"fixture-{service}")

    output = tmp_path / "github_output"
    monkeypatch.setattr(planner, "changed_files", lambda _base, _head: [path])
    monkeypatch.setattr(sys, "argv", ["plan_render_deploys.py", "--base", "base", "--head", "head", "--output", str(output)])

    assert planner.main() == 0
    outputs = dict(line.split("=", 1) for line in output.read_text().splitlines())
    matrix = json.loads(outputs["matrix"])["include"]
    assert {item["service"]: item["service_id"] for item in matrix} == {svc: f"fixture-{svc}" for svc in services}
    assert outputs["has_services"] == ("true" if services else "false")
    assert json.loads(outputs["unregistered"]) == unregistered
    assert ("::warning::api changed" in capsys.readouterr().err) == bool(unregistered)
