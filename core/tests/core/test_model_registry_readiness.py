from brain.model_registry import ModelRegistry


def test_provider_model_id_uses_provider_native_identifier():
    assert ModelRegistry.provider_model_id("gemini-3.1-pro") == "google/gemini-2.5-pro-preview"


def test_readiness_snapshot_is_safe_and_explicit():
    snapshot = ModelRegistry.readiness_snapshot()
    entry = snapshot["gemini-3.1-pro"]
    assert entry["status"] == "UNVALIDATED"
    assert "api_key" not in entry
    assert "provider_model_id" in entry


def test_registry_validation_detects_missing_provider_ids():
    original = ModelRegistry.MODELS["gemini-3.1-pro"]
    ModelRegistry.MODELS["gemini-3.1-pro"] = {**original, "openrouter_id": None}
    try:
        assert any("missing provider model id" in issue for issue in ModelRegistry.validate())
    finally:
        ModelRegistry.MODELS["gemini-3.1-pro"] = original
