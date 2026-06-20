import os
import types
from unittest.mock import MagicMock

import pytest


def _bootstrap():
    os.environ.setdefault("OPENROUTER_API_KEY", "")
    os.environ.setdefault("HF_API_KEY", "")
    os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")


_bootstrap()


def test_intent_classifier_general():
    from core.intent import IntentClassifier
    clf = IntentClassifier()
    intent = clf.classify("what is the capital of france?")
    assert intent.task_type.value == "general"
    assert intent.confidence >= 0.0


def test_intent_classifier_coding():
    from core.intent import IntentClassifier
    clf = IntentClassifier()
    intent = clf.classify("write a python function to sort a list")
    assert intent.task_type.value == "coding"


def test_intent_classifier_admin():
    from core.intent import IntentClassifier
    clf = IntentClassifier()
    intent = clf.classify("run admin shutdown command now")
    assert intent.task_type.value == "admin"


def test_intent_classifier_translation():
    from core.intent import IntentClassifier
    clf = IntentClassifier()
    intent = clf.classify("translate this to bengali")
    assert intent.task_type.value == "translation"


def test_model_router_fallback_chain(monkeypatch):
    import types
    from brain.model_router import ModelRouter
    mr = ModelRouter()
    mr.openrouter_api_key = "x"
    mr.hf_api_key = ""
    mr.ollama_url = "http://localhost:11434"
    mr.default_model = "m"
    mr.local_model = "l"

    def boom(self, p, m): raise RuntimeError("down")
    monkeypatch.setattr(mr, "_call_openrouter", boom, raising=True)
    monkeypatch.setattr(mr, "_call_huggingface", boom, raising=True)
    monkeypatch.setattr(mr, "_call_ollama", boom, raising=True)

    out = mr.route_and_generate("ping", task_type="general")
    assert out["success"] is False
    assert "unavailable" in out.get("text", "").lower()


def test_model_router_uses_registry_for_tier_selection(monkeypatch):
    import types
    from brain.model_router import ModelRouter
    mr = ModelRouter()
    mr.openrouter_api_key = "test-key"

    async def fake_call(p, m):
        return {"success": True, "provider": "openrouter", "text": "ok", "cost": 0.0}

    monkeypatch.setattr(mr, "_call_openrouter", fake_call)
    result = mr.route_and_generate("simple prompt", task_type="general")
    assert result["success"] is True


def test_admin_rules_db_roundtrip():
    import tempfile, pathlib
    from admin.god import AdminGodLayer
    db = pathlib.Path(tempfile.gettempdir()) / "supremeai_admin_test.db"
    admin = AdminGodLayer(str(db))
    assert admin.get_rule("missing") is None
    admin.set_rule("x", "1")
    assert admin.get_rule("x") == "1"
    admin.set_rule("admin_authorized", "false")
    assert admin.is_admin_action_allowed("execute") is False
    admin.set_rule("admin_authorized", "true")
    assert admin.is_admin_action_allowed("execute") is True


def test_schema_validator_retry_on_validation_fail():
    from pydantic import BaseModel
    from core.schema_validator import SchemaValidator
    validator = SchemaValidator()

    class TestSchema(BaseModel):
        name: str
        value: int

    validator.register("test", TestSchema)

    # Test validation passes on first attempt
    result = validator.validate("test", {"name": "foo", "value": 42})
    assert result["status"] == "ok"
    assert result["data"]["name"] == "foo"

    # Test validation retry logic with invalid payload
    result = validator.validate_with_retry("test", {"name": "bar"}, max_attempts=2)
    assert result["status"] == "error"
    assert result["schema"] == "test"
