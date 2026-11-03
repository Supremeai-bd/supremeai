"""Issue #1442 — routing policy must never reference RETIRED models.

``registry._RETIRED_MODELS`` (verified-2026-09-13 set) skips retired models at
request time, so a stale entry in ``backend/config/routing_policy.json`` made
the *configured* chain head differ from the *effective* one — "easy" had no
working head at all and cost/latency planning from the JSON was wrong.

Layer 1 (import-free text guards, run in any env): retired model id substrings
must not appear in the live policy JSON, ``.env.example``, or the hardcoded
service fallbacks that were fixed alongside (#1442 follow-ups).

Layer 2 (needs the backend env): the parsed policy must contain zero entries
from ``registry._RETIRED_MODELS`` across ``complexity_rules``, ``task_overrides``
and ``fallback_chain`` — the exact walk the startup validator
(``LLMGatewayRoutingMixin._warn_retired_policy_models``) performs.
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
POLICY_PATH = BACKEND_DIR / "config" / "routing_policy.json"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
VISION_SERVICE = BACKEND_DIR / "services" / "vision_service.py"
VOICE_SERVICE = BACKEND_DIR / "services" / "voice_service.py"

# Layer-1 substrings: retired Gemini ids (also matches the "-exp" alias).
_RETIRED_SUBSTRINGS = ("gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash")
_POLICY_MODEL_KEYS = ("complexity_rules", "task_overrides", "fallback_chain")


def _walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)
    elif isinstance(value, dict):
        for v in value.values():
            yield from _walk_strings(v)


# ── Layer 1: import-free text guards ──────────────────────────────────────────


def test_routing_policy_json_has_no_retired_substrings():
    text = POLICY_PATH.read_text(encoding="utf-8")
    for sub in _RETIRED_SUBSTRINGS:
        assert sub not in text, f"routing_policy.json still references retired {sub!r}"


def test_env_example_gemini_model_is_served():
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    line = next((ln for ln in text.splitlines() if ln.startswith("GEMINI_MODEL_NAME=")), None)
    assert line is not None, "GEMINI_MODEL_NAME disappeared from .env.example"
    for sub in _RETIRED_SUBSTRINGS:
        assert sub not in line, f".env.example default is a retired model: {line!r}"


def test_service_fallbacks_not_retired():
    """vision_service / voice_service last-resort defaults must be served models."""
    for path in (VISION_SERVICE, VOICE_SERVICE):
        text = path.read_text(encoding="utf-8")
        for sub in _RETIRED_SUBSTRINGS:
            assert sub not in text, f"{path.name} still defaults to retired {sub!r}"


# ── Layer 2: registry-driven guards (backend env) ────────────────────────────


def _registry():
    return pytest.importorskip(
        "core.llm.llm_gateway.registry",
        reason="backend env required for registry._RETIRED_MODELS",
    )


def test_policy_entries_exist_in_registry_retirement_set():
    """Guard the guard: the retired ids we reject must be in _RETIRED_MODELS."""
    retired = _registry()._RETIRED_MODELS
    assert "gemini/gemini-2.0-flash" in retired
    assert "gemini/gemini-1.5-pro" in retired


def test_parsed_policy_has_zero_retired_models():
    """The exact walk the startup validator performs must find nothing."""
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    retired = _registry()._RETIRED_MODELS
    offenders = []
    for key in _POLICY_MODEL_KEYS:
        for model in _walk_strings(policy.get(key, {})):
            if model.lower() in retired:
                offenders.append(f"{key}:{model}")
    assert offenders == [], f"retired models still configured: {offenders}"
