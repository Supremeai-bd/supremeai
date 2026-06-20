import pytest
from unittest.mock import MagicMock
from brain.agent_department import AgentDepartment, CodingAgent, ReviewAgent, QAAgent

def test_agent_department_coding_success():
    mock_router = MagicMock()
    mock_router.route_and_generate.return_value = {
        "success": True,
        "text": "def test(): pass",
        "provider": "gemini",
        "cost": 0.002
    }
    
    dept = AgentDepartment(mock_router)
    res = dept.run("coding", "write code for addition")
    assert res["success"]
    assert res["output"] == "def test(): pass"
    assert res["provider"] == "gemini"

def test_agent_department_review_failure():
    mock_router = MagicMock()
    mock_router.route_and_generate.return_value = {
        "success": False,
        "error": "rate limit reached"
    }
    
    dept = AgentDepartment(mock_router)
    res = dept.run("review", "review this code")
    assert not res["success"]
    assert res["error"] == "rate limit reached"

def test_agent_department_qa_exception():
    mock_router = MagicMock()
    mock_router.route_and_generate.side_effect = Exception("connection failed")
    
    dept = AgentDepartment(mock_router)
    res = dept.run("qa", "write tests")
    assert not res["success"]
    assert "connection failed" in res["error"]

def test_agent_department_unknown():
    mock_router = MagicMock()
    dept = AgentDepartment(mock_router)
    res = dept.run("unknown_dept", "do task")
    assert not res["success"]
    assert "Unknown department" in res["error"]
