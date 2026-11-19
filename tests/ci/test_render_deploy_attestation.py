"""Offline release attestation contract. All provider and runtime I/O is stubbed."""

import io
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from scripts.ci import render_deploy_attestation as attestor
from scripts.ci.render_trigger_deploy import CANDIDATE_KEY_ENVS

SHA = "a" * 40
OTHER = "b" * 40


@pytest.fixture
def evidence(monkeypatch):
    for key in CANDIDATE_KEY_ENVS:
        monkeypatch.delenv(key, raising=False)
    for key, value in {
        "RENDER_API_KEY": "fixture-key",
        "RENDER_SERVICE_ID": "srv-fixture",
        "RENDER_DEPLOY_ID": "dep-fixture",
        "EXPECTED_SHA": SHA,
        "RELEASE_URL": "https://release.example.invalid/release",
    }.items():
        monkeypatch.setenv(key, value)
    for key in ("RENDER_SERVICE_SUSPENDED", "RENDER_AUXILIARY", "EXPECTED_CAPABILITY"):
        monkeypatch.delenv(key, raising=False)

    provider = Mock()
    provider.get_deploy.return_value = {"deploy": {"id": "dep-fixture", "status": "live", "commit": {"id": SHA}}}
    # A different deployment must never satisfy the requested deploy ID.
    provider.get_latest_deploy.return_value = {"status": "live", "commit": {"id": SHA}}
    monkeypatch.setattr(attestor, "RenderClient", Mock(return_value=provider))

    def runtime(payload):
        response = io.BytesIO(json.dumps(payload).encode())
        response.status = 200
        response.geturl = lambda: "https://release.example.invalid/release"
        return response

    release = Mock(side_effect=lambda *_args, **_kwargs: runtime({"commit": SHA}))
    monkeypatch.setattr(attestor.urllib.request, "urlopen", release)
    return provider, release, runtime


def _result(capsys):
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_verifies_only_the_triggered_live_deploy_and_runtime(evidence, capsys):
    provider, release, _ = evidence
    assert attestor.main() == 0
    assert _result(capsys)["status"] == "verified"
    provider.get_deploy.assert_called_once_with("dep-fixture", "srv-fixture")
    provider.get_latest_deploy.assert_not_called()
    release.assert_called_once()


@pytest.mark.parametrize("field,value", [
    ("status", "pre_live"), ("status", "build_failed"),
    ("id", "dep-other"), ("commit", {"id": OTHER}), ("commit", {}),
])
def test_provider_evidence_must_match_before_runtime_probe(evidence, capsys, field, value):
    provider, release, _ = evidence
    provider.get_deploy.return_value["deploy"][field] = value
    assert attestor.main() == 1
    assert _result(capsys)["status"] == "unverified"
    release.assert_not_called()


@pytest.mark.parametrize("runtime_sha", [OTHER, SHA[:7], "unknown", None])
def test_runtime_health_or_other_sha_cannot_attest(evidence, capsys, runtime_sha):
    _, release, runtime = evidence
    release.side_effect = lambda *_args, **_kwargs: runtime({"commit": runtime_sha})
    assert attestor.main() == 1
    assert _result(capsys)["status"] == "unverified"
    assert release.call_count == 1


@pytest.mark.parametrize("key", ["RENDER_DEPLOY_ID", "EXPECTED_SHA", "RELEASE_URL"])
def test_required_evidence_missing_is_not_verified(evidence, capsys, monkeypatch, key):
    provider, release, _ = evidence
    monkeypatch.delenv(key)
    assert attestor.main() == 1
    assert _result(capsys)["status"] == "unverified"
    provider.get_deploy.assert_not_called()
    release.assert_not_called()


@pytest.mark.parametrize("optional", [False, True])
def test_suspended_service_is_not_a_verified_release(evidence, capsys, monkeypatch, optional):
    provider, release, _ = evidence
    monkeypatch.setenv("RENDER_SERVICE_SUSPENDED", "1")
    monkeypatch.delenv("RENDER_DEPLOY_ID")
    if optional:
        monkeypatch.setenv("RENDER_AUXILIARY", "1")
    assert attestor.main() == (0 if optional else 1)
    result = _result(capsys)
    assert result["status"] == ("not_run" if optional else "unverified")
    assert "commit" not in result
    provider.get_deploy.assert_not_called()
    release.assert_not_called()


def test_ci_runner_without_release_url_is_metadata_only(evidence, capsys, monkeypatch):
    _, release, _ = evidence
    monkeypatch.delenv("RELEASE_URL")
    monkeypatch.setenv("RENDER_AUXILIARY", "1")
    assert attestor.main() == 0
    result = _result(capsys)
    assert result["status"] == "metadata_only"
    assert "commit" not in result
    release.assert_not_called()


def test_release_workflows_pin_the_deploy_id_and_keep_rollback_verifier_current():
    workflows = Path(__file__).resolve().parents[2] / ".github" / "workflows"
    unified = yaml.safe_load((workflows / "unified-pipeline.yml").read_text())
    rollback = yaml.safe_load((workflows / "deploy-rollback.yml").read_text())
    for job in (unified["jobs"]["deploy-render-services"], rollback["jobs"]["rollback"]):
        steps = job["steps"]
        trigger = next(step for step in steps if step.get("run") == "python scripts/ci/render_trigger_deploy.py")
        attest = next(step for step in steps if step.get("run") == "python scripts/ci/render_deploy_attestation.py")
        assert trigger["env"]["REQUIRE_EXPECTED_SHA"] == "1"
        assert attest["env"]["RENDER_DEPLOY_ID"] == f"${{{{ steps.{trigger['id']}.outputs.deploy_id }}}}"
    checkout = rollback["jobs"]["rollback"]["steps"][0]
    assert checkout["with"]["ref"] == "${{ github.sha }}"


def test_redirected_runtime_is_not_attestation(evidence, capsys):
    _, release, runtime = evidence
    redirected = runtime({"commit": SHA})
    redirected.geturl = lambda: "https://different.example.invalid/release"
    release.side_effect = None
    release.return_value = redirected
    assert attestor.main() == 1
    assert _result(capsys)["status"] == "unverified"


def test_production_release_dispatches_require_main_and_environment():
    workflows = Path(__file__).resolve().parents[2] / ".github/workflows"
    unified = yaml.safe_load((workflows / "unified-pipeline.yml").read_text(encoding="utf-8"))
    jobs = unified["jobs"]
    assert "refs/heads/main" in jobs["deploy-and-verify"]["if"]
    for job in ("deploy-render-services", "deploy-cloudflare", "deploy-vercel"):
        assert "refs/heads/main" in jobs[job]["if"]
        assert jobs[job]["environment"] == "production"
    rollback = yaml.safe_load((workflows / "deploy-rollback.yml").read_text(encoding="utf-8"))
    assert rollback["jobs"]["rollback"]["environment"] == "production"
    assert jobs["deploy-render-services"]["concurrency"]["group"] == rollback["jobs"]["rollback"]["concurrency"]["group"]
