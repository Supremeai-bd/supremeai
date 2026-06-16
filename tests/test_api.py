import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("OPENROUTER_API_KEY", "")
os.environ.setdefault("HF_API_KEY", "")
os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")

import core.app as app_mod
from core.app import app

client = TestClient(app)


def test_health_returns_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["orchestrator"] == "online"


def test_task_execute_enforces_admin_block():
    from admin.god import AdminGodLayer
    import tempfile, pathlib

    db = pathlib.Path(tempfile.gettempdir()) / "supremeai_test_rules.db"
    admin = AdminGodLayer(str(db))
    admin.set_rule("admin_authorized", "false")

    previous = app_mod.admin_god
    app_mod.admin_god = admin
    try:
        resp = client.post("/task/execute", json={"task": "do anything", "task_type": "general"})
        assert resp.status_code == 403
    finally:
        app_mod.admin_god = previous


def test_task_execute_allowed_and_success():
    from admin.god import AdminGodLayer
    import tempfile, pathlib
    from core.intent import IntentClassifier, TaskType

    db = pathlib.Path(tempfile.gettempdir()) / "supremeai_test_rules2.db"
    admin = AdminGodLayer(str(db))
    admin.set_rule("admin_authorized", "true")

    fake_router = MagicMock()
    fake_router.route_and_generate.return_value = {
        "success": True,
        "provider": "openrouter",
        "model": "fake-model",
        "text": "ok",
        "cost": 0.0,
    }
    fake_intent = MagicMock()
    fake_intent.classify.return_value = type("Intent", (), {"task_type": TaskType.general, "confidence": 0.5})()

    previous_admin = app_mod.admin_god
    previous_router = app_mod.model_router
    previous_intent = app_mod.intent_clf
    app_mod.admin_god = admin
    app_mod.model_router = fake_router
    app_mod.intent_clf = fake_intent
    try:
        resp = client.post("/task/execute", json={"task": "hello", "task_type": "general"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["result"] == "ok"
        fake_router.route_and_generate.assert_called_once_with(
            prompt="hello", task_type="general", max_cost=0.01
        )
    finally:
        app_mod.admin_god = previous_admin
        app_mod.model_router = previous_router
        app_mod.intent_clf = previous_intent
