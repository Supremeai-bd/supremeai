"""
Tests for services/sandbox_service.py
"""

from __future__ import annotations

from unittest.mock import patch

from services.sandbox_service import SandboxService


def test_create_sandbox_returns_id():
    svc = SandboxService()
    with patch.object(svc, "active_sandboxes", {}):
        sandbox_id = svc.create_sandbox("task_1", "python")
    assert isinstance(sandbox_id, str)


def test_execute_returns_result_dict():
    svc = SandboxService()
    with patch.object(svc, "active_sandboxes", {"sb1": {}}):
        result = svc.execute("sb1", "print('hello')")
    assert isinstance(result, dict)


def test_destroy_removes_sandbox():
    svc = SandboxService()
    sb = {"id": "sb1"}
    with patch.object(svc, "active_sandboxes", {"sb1": sb}):
        ok = svc.destroy("sb1")
    assert ok is True


def test_list_sandboxes_returns_list():
    svc = SandboxService()
    with patch.object(svc, "active_sandboxes", {"a": {}, "b": {}}):
        result = svc.list_sandboxes()
    assert isinstance(result, list)


def test_get_sandbox_returns_dict_or_none():
    svc = SandboxService()
    with patch.object(svc, "active_sandboxes", {"sb1": {"lang": "python"}}):
        assert svc.get_sandbox("sb1") is not None
        assert svc.get_sandbox("missing") is None
