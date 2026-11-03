"""
Tests for services/project_context_service.py
"""

from __future__ import annotations

from pathlib import Path

from services.project_context_service import ContextType, ProjectContextService


def test_is_ignored_hidden_file():
    svc = ProjectContextService()
    assert svc._is_ignored(Path(".git/config")) is True


def test_is_ignored_normal_file():
    svc = ProjectContextService()
    assert svc._is_ignored(Path("src/main.py")) is False


def test_extract_definitions_finds_class_and_function():
    svc = ProjectContextService()
    content = "class Foo:\n    pass\ndef bar():\n    pass\n"
    entries = svc._extract_definitions(content, "src/app.py")
    types = [e.context_type for e in entries]
    assert ContextType.CLASS in types
    assert ContextType.FUNCTION in types
    assert any(e.name == "Foo" for e in entries)
    assert any(e.name == "bar" for e in entries)


def test_extract_routes_finds_fastapi_decorators():
    svc = ProjectContextService()
    content = '@router.get("/health")\n@router.post("/submit")\n'
    entries = svc._extract_routes(content, "src/routes.py")
    assert len(entries) == 2
    assert all(e.context_type == ContextType.ROUTE for e in entries)
    assert entries[0].name == "/health"
    assert entries[0].signature == "GET /health"
