from __future__ import annotations

from unittest.mock import MagicMock
from brain.agent_departments import AgentDepartment, ROLE_PROMPTS


def _make_dept(model_router=None):
    if model_router is None:
        model_router = MagicMock()
    return AgentDepartment(model_router=model_router)


def test_list_roles_returns_all_defined_roles():
    dept = _make_dept()
    roles = dept.list_roles()
    assert "coder" in roles
    assert "code-reviewer" in roles
    assert "architect" in roles
    assert "qa" in roles
    assert "data" in roles
    assert "security" in roles
    assert len(roles) == 6


def test_execute_coder_success():
    mock_router = MagicMock()
    mock_router.route_and_generate.return_value = {
        "success": True,
        "text": "def hello(): pass",
        "cost": 0.003,
    }
    dept = _make_dept(mock_router)
    result = dept.execute("coder", "write a hello function", "Python context")
    assert result["success"] is True
    assert result["role"] == "coder"
    assert result["output"] == "def hello(): pass"
    assert result["cost"] == 0.003
    prompt = mock_router.route_and_generate.call_args.kwargs["prompt"]
    assert "write a hello function" in prompt
    assert "R-A-C-E" in prompt


def test_execute_code_reviewer_success():
    mock_router = MagicMock()
    mock_router.route_and_generate.return_value = {
        "success": True,
        "text": "Review: looks good",
        "cost": 0.002,
    }
    dept = _make_dept(mock_router)
    result = dept.execute("code-reviewer", "review this code", "code context")
    assert result["success"] is True
    assert result["role"] == "code-reviewer"
    assert "C-L-E-A-R" in mock_router.route_and_generate.call_args.kwargs["prompt"]


def test_execute_qa_success():
    mock_router = MagicMock()
    mock_router.route_and_generate.return_value = {
        "success": True,
        "text": "Test cases: 1, 2, 3",
        "cost": 0.001,
    }
    dept = _make_dept(mock_router)
    result = dept.execute("qa", "write test cases", "app context")
    assert result["success"] is True
    assert result["role"] == "qa"
    assert "S-T-A-R" in mock_router.route_and_generate.call_args.kwargs["prompt"]


def test_execute_architect_success():
    mock_router = MagicMock()
    mock_router.route_and_generate.return_value = {
        "success": True,
        "text": "Architecture plan",
        "cost": 0.004,
    }
    dept = _make_dept(mock_router)
    result = dept.execute("architect", "design system", "context")
    assert result["success"] is True
    assert result["role"] == "architect"
    assert "S-O-A-P" in mock_router.route_and_generate.call_args.kwargs["prompt"]


def test_execute_data_success():
    mock_router = MagicMock()
    mock_router.route_and_generate.return_value = {
        "success": True,
        "text": "Pipeline plan",
        "cost": 0.002,
    }
    dept = _make_dept(mock_router)
    result = dept.execute("data", "build pipeline", "context")
    assert result["success"] is True
    assert result["role"] == "data"
    assert "G-R-O-W" in mock_router.route_and_generate.call_args.kwargs["prompt"]


def test_execute_security_success():
    mock_router = MagicMock()
    mock_router.route_and_generate.return_value = {
        "success": True,
        "text": "Threat: SQLi, Mitigation: parameterized queries",
        "cost": 0.003,
    }
    dept = _make_dept(mock_router)
    result = dept.execute("security", "audit login flow", "context")
    assert result["success"] is True
    assert result["role"] == "security"
    assert result["output"] == "Threat: SQLi, Mitigation: parameterized queries"


def test_execute_unknown_role_falls_back_to_coder_prompt():
    mock_router = MagicMock()
    mock_router.route_and_generate.return_value = {
        "success": True,
        "text": "fallback output",
        "cost": 0.001,
    }
    dept = _make_dept(mock_router)
    result = dept.execute("unknown_role", "do something")
    assert result["success"] is True
    assert result["role"] == "unknown_role"
    assert "R-A-C-E" in mock_router.route_and_generate.call_args.kwargs["prompt"]


def test_execute_router_returns_text_without_success_flag():
    mock_router = MagicMock()
    mock_router.route_and_generate.return_value = {
        "success": False,
        "text": "fallback text output",
        "cost": 0.001,
    }
    dept = _make_dept(mock_router)
    result = dept.execute("coder", "generate code")
    assert result["success"] is True
    assert result["output"] == "fallback text output"


def test_execute_router_returns_neither_success_nor_text():
    mock_router = MagicMock()
    mock_router.route_and_generate.return_value = {
        "success": False,
        "error": "model unavailable",
        "cost": 0.0,
    }
    dept = _make_dept(mock_router)
    result = dept.execute("coder", "generate code")
    assert result["success"] is False
    assert result["error"] == "model unavailable"


def test_execute_exception_handling():
    mock_router = MagicMock()
    mock_router.route_and_generate.side_effect = RuntimeError("connection lost")
    dept = _make_dept(mock_router)
    result = dept.execute("coder", "generate code")
    assert result["success"] is False
    assert "connection lost" in result["error"]


def test_execute_case_insensitive_role():
    mock_router = MagicMock()
    mock_router.route_and_generate.return_value = {
        "success": True,
        "text": "output",
        "cost": 0.001,
    }
    dept = _make_dept(mock_router)
    result = dept.execute("CODER", "do task")
    assert result["role"] == "coder"


def test_execute_empty_context_defaults_to_none_string():
    mock_router = MagicMock()
    mock_router.route_and_generate.return_value = {
        "success": True,
        "text": "output",
        "cost": 0.001,
    }
    dept = _make_dept(mock_router)
    dept.execute("coder", "do task", context="")
    prompt = mock_router.route_and_generate.call_args.kwargs["prompt"]
    assert "Context: None" in prompt


def test_execute_with_context_includes_context():
    mock_router = MagicMock()
    mock_router.route_and_generate.return_value = {
        "success": True,
        "text": "output",
        "cost": 0.001,
    }
    dept = _make_dept(mock_router)
    dept.execute("coder", "do task", context="my context")
    prompt = mock_router.route_and_generate.call_args.kwargs["prompt"]
    assert "my context" in prompt
    assert "Context: my context" in prompt


def test_default_model_router_initialized():
    dept = _make_dept(None)
    assert dept.model_router is not None
