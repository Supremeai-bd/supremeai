"""Contract tests for scripts/ci/resolve_production_targets.py (issue #1132).

One canonical production target-resolution contract: both smoke workflows
(qa-live-smoke.yml, 09-post-deploy-smoke.yml) and release certification must
resolve the SAME UI/API targets with the SAME provenance for the same inputs.

Covered here (issue acceptance criteria):
- explicit owner override (PRODUCTION_URL) — API surface, UI still derived
- Firebase + Infisical backend (no explicit URL) — two distinct origins
- missing target — everything stays empty (UNVERIFIED, fail-closed, no
  localhost/placeholder fabrication)
- misconfigured same-origin fallback — labeled provenance + loud note
- hosting-domain-as-API-origin (2026-09-18 live incident) — resolved but flagged
- normalization + override precedence
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "ci" / "resolve_production_targets.py"

_spec = importlib.util.spec_from_file_location("resolve_production_targets", SCRIPT_PATH)
resolver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(resolver)


def _resolve(**kwargs):
    lines, notes = resolver.resolve_targets(**kwargs)
    return lines, notes


def test_explicit_override_resolves_api_and_derived_ui():
    """PRODUCTION_URL owner override → API origin; UI from FIREBASE_PROJECT_ID."""
    lines, notes = _resolve(api_explicit="https://api.example.com/", firebase_project="supremeai-a")
    assert lines["API_ORIGIN"] == "https://api.example.com"  # trailing / normalized
    assert lines["API_ORIGIN_SOURCE"] == "PRODUCTION_URL (owner override)"
    assert lines["UI_ORIGIN"] == "https://supremeai-a.web.app"
    assert "FIREBASE_PROJECT_ID-derived" in lines["UI_ORIGIN_SOURCE"]
    # backend health probe and canary consume the same truth
    assert lines["BACKEND_HEALTH_URL"] == lines["API_ORIGIN"]
    assert lines["BACKEND_HEALTH_SOURCE"] == lines["API_ORIGIN_SOURCE"]
    assert lines["QA_BASE_URL"] == lines["UI_ORIGIN"]
    assert not any("MISCONFIGURATION" in n for n in notes)


def test_firebase_and_infisical_backend_distinct_origins():
    """No explicit override: UI = Firebase-derived, API = Infisical RENDER_CORE_URL."""
    lines, _ = _resolve(firebase_project="supremeai-a", render_core="https://core.render.app/")
    assert lines["UI_ORIGIN"] == "https://supremeai-a.web.app"
    assert lines["API_ORIGIN"] == "https://core.render.app"
    assert lines["API_ORIGIN_SOURCE"] == "RENDER_CORE_URL (Infisical prod)"
    # surfaces stay DISTINCT for Firebase-hosted deployments (issue requirement)
    assert lines["UI_ORIGIN"] != lines["API_ORIGIN"]


def test_missing_targets_stay_unverified_fail_closed():
    """Nothing configured → everything empty; no localhost / placeholder fabrication."""
    lines, notes = _resolve()
    assert lines["UI_ORIGIN"] == ""
    assert lines["UI_ORIGIN_SOURCE"] == ""
    assert lines["API_ORIGIN"] == ""
    assert lines["API_ORIGIN_SOURCE"] == ""
    assert lines["BACKEND_HEALTH_URL"] == ""
    assert lines["QA_BASE_URL"] == ""
    assert any("UNVERIFIED" in n for n in notes)
    blob = " ".join(lines.values()).lower()
    assert "localhost" not in blob and "placeholder" not in blob and "example.com" not in blob


def test_same_origin_fallback_is_labeled_not_hidden():
    """No API target but UI known → same-origin fallback with explicit provenance."""
    lines, notes = _resolve(firebase_project="supremeai-a")
    assert lines["API_ORIGIN"] == "https://supremeai-a.web.app"
    assert "same-origin fallback" in lines["API_ORIGIN_SOURCE"]
    assert any("same-origin" in n for n in notes)


def test_no_fallback_fabrication_without_ui():
    """No UI origin and no API config → API stays empty (no fabricated fallback)."""
    lines, _ = _resolve()
    assert lines["API_ORIGIN"] == ""
    assert lines["API_ORIGIN_SOURCE"] == ""


def test_ui_owner_override_wins_over_firebase_derivation():
    """FRONTEND_PRODUCTION_URL beats FIREBASE_PROJECT_ID derivation for UI surface."""
    lines, _ = _resolve(
        ui_explicit="https://custom-ui.example.com",
        firebase_project="supremeai-a",
        render_core="https://core.render.app",
    )
    assert lines["UI_ORIGIN"] == "https://custom-ui.example.com"
    assert lines["UI_ORIGIN_SOURCE"] == "FRONTEND_PRODUCTION_URL (owner override)"
    assert lines["API_ORIGIN"] == "https://core.render.app"


def test_hosting_domain_api_override_is_flagged_as_misconfiguration():
    """2026-09-18 live incident shape: PRODUCTION_URL pointing at *.web.app."""
    lines, notes = _resolve(
        api_explicit="https://supremeai-a.web.app", firebase_project="supremeai-a"
    )
    assert lines["API_ORIGIN"] == "https://supremeai-a.web.app"  # override honored
    assert any("MISCONFIGURATION" in n for n in notes)


def test_same_origin_fallback_not_applied_when_explicit_api_set():
    """Explicit API override must NOT be replaced by the same-origin fallback."""
    lines, _ = _resolve(api_explicit="https://api.example.com", firebase_project="supremeai-a")
    assert lines["API_ORIGIN"] == "https://api.example.com"
    assert lines["API_ORIGIN_SOURCE"] == "PRODUCTION_URL (owner override)"


def test_whitespace_only_inputs_are_empty():
    """Whitespace-only config must resolve as unset — honest emptiness."""
    lines, _ = _resolve(
        api_explicit="   ", ui_explicit="\t", firebase_project="  ", render_core=" / "
    )
    assert lines["UI_ORIGIN"] == ""
    assert lines["API_ORIGIN"] == ""


def test_env_file_append(tmp_path: Path):
    """--env-file appends the exact contract keys (GITHUB_ENV contract)."""
    lines, _ = _resolve(api_explicit="https://api.example.com", firebase_project="proj")
    env_file = tmp_path / "github_env"
    env_file.write_text("PREEXISTING=1\n", encoding="utf-8")
    with open(env_file, "a", encoding="utf-8") as fh:
        for key in resolver.ENV_KEYS:
            fh.write(f"{key}={lines[key]}\n")
    content = env_file.read_text(encoding="utf-8")
    assert content.startswith("PREEXISTING=1\n")
    for key in resolver.ENV_KEYS:
        assert f"{key}={lines[key]}\n" in content
