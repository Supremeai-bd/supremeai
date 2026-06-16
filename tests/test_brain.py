import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add supremeai_2.0 to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain.model_router import ModelRouter
from brain.langgraph_agent import SupremeOrchestrator
from core.admin_god import AdminGodLayer
from core.universal_rules import UniversalRulesEngine

def test_model_router_fallback():
    # Test router fallback when API key is missing and Ollama fails/succeeds
    router = ModelRouter()
    router.openrouter_api_key = ""
    
    # Mock Ollama call to succeed
    with patch.object(router, '_call_ollama', return_value={"success": True, "provider": "ollama", "text": "local response", "cost": 0.0}):
        res = router.route_and_generate("hello", "coding")
        assert res["success"] is True
        assert res["provider"] == "ollama"
        assert res["text"] == "local response"

def test_orchestrator_admin_blocking():
    # Setup rules to block everything exceeding 0.01 cost
    rules_engine = UniversalRulesEngine()
    rules_engine.rules["image_generation"]["max_cost_per_image"] = 0.01
    
    admin_god = AdminGodLayer(rules_engine)
    orchestrator = SupremeOrchestrator(admin_god=admin_god)
    
    # A task with cost exceeding limits must be blocked
    # Let's test with a mock rule that sets blocked=True for high cost
    context = {"task_type": "image_generation", "cost": 0.05}
    res = rules_engine.apply(context)
    assert res["blocked"] is True

def test_orchestrator_execution_flow():
    # Mock model router
    mock_router = MagicMock()
    mock_router.route_and_generate.return_value = {
        "success": True,
        "provider": "openrouter",
        "text": "Sure, here is your code.",
        "cost": 0.002
    }
    
    orchestrator = SupremeOrchestrator(model_router=mock_router)
    res = orchestrator.execute_task("write a binary search in python", "coding")
    
    assert res["completed"] is True
    assert res["current_step"] == "completed"
    assert res["result"] == "Sure, here is your code."
    assert res["cost"] == 0.002
