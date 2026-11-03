"""ERR-H02 regression tests — real skill install/uninstall state + blueprint deploy."""

from __future__ import annotations

import json

import anyio
import pytest
from fastapi import HTTPException

from api.routes import skills as skills_module


@pytest.fixture()
def isolated_dirs(tmp_path, monkeypatch: pytest.MonkeyPatch):
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    (manifests / "demo_skill.json").write_text(
        json.dumps({"skill_id": "demo_skill", "version": "2.1", "owner": "test"}), encoding="utf-8"
    )
    state = tmp_path / "installed.json"
    monkeypatch.setattr(skills_module, "MANIFEST_DIR", manifests)
    monkeypatch.setattr(skills_module, "INSTALLED_STATE_PATH", state)
    return manifests, state


def test_install_persists_real_state(isolated_dirs) -> None:
    _manifests, state = isolated_dirs
    resp = anyio.run(skills_module.install_skill, "demo_skill")
    assert resp["status"] == "installed"
    assert resp["version"] == "2.1"
    saved = json.loads(state.read_text(encoding="utf-8"))
    assert saved["demo_skill"]["version"] == "2.1"
    assert saved["demo_skill"]["installed_at"]


def test_install_unknown_skill_404(isolated_dirs) -> None:
    def _call():
        anyio.run(skills_module.install_skill, "nope")

    with pytest.raises(HTTPException) as excinfo:
        _call()
    assert excinfo.value.status_code == 404


def test_uninstall_round_trip(isolated_dirs) -> None:
    _manifests, state = isolated_dirs
    anyio.run(skills_module.install_skill, "demo_skill")
    resp = anyio.run(skills_module.uninstall_skill, "demo_skill")
    assert resp["status"] == "uninstalled"
    assert json.loads(state.read_text(encoding="utf-8")) == {}
    with pytest.raises(HTTPException) as excinfo:
        anyio.run(skills_module.uninstall_skill, "demo_skill")
    assert excinfo.value.status_code == 404  # not installed anymore


def test_installed_only_search_filters_for_real(isolated_dirs) -> None:
    _manifests, _state = isolated_dirs
    assert anyio.run(skills_module.search_skills, "demo", True) == []
    anyio.run(skills_module.install_skill, "demo_skill")
    results = anyio.run(skills_module.search_skills, "demo", True)
    assert [r["skill_id"] for r in results] == ["demo_skill"]


def test_deploy_blueprint_writes_real_manifest(isolated_dirs) -> None:
    manifests, _state = isolated_dirs
    resp = anyio.run(
        skills_module.deploy_blueprint,
        skills_module.BlueprintDeployRequest(
            name="My Forge Skill",
            description="built in the forge",
            agents=["scout"],
            nodes=[{"id": "a"}],
            edges=[],
            category="automation",
        ),
    )
    assert resp["status"] == "deployed"
    manifest_path = manifests / "my_forge_skill.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["skill_id"] == "my_forge_skill"
    assert manifest["source"] == "evolution_forge"
    # appears in the catalog like every other skill
    catalog = anyio.run(skills_module.get_active_skill_catalog)
    assert any(entry.get("skill_id") == "my_forge_skill" for entry in catalog)


def test_deploy_blueprint_collision_409(isolated_dirs) -> None:
    anyio.run(
        skills_module.deploy_blueprint, skills_module.BlueprintDeployRequest(name="Collide_Test")
    )
    with pytest.raises(HTTPException) as excinfo:
        anyio.run(
            skills_module.deploy_blueprint,
            skills_module.BlueprintDeployRequest(name="Collide_Test"),
        )
    assert excinfo.value.status_code == 409
