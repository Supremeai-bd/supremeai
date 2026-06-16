import os
import sys
import types
import pytest
from unittest.mock import patch, MagicMock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _bootstrap():
    os.environ.setdefault("OPENROUTER_API_KEY", "")
    os.environ.setdefault("HF_API_KEY", "")
    os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")


_bootstrap()

from brain.model_router import ModelRouter
from brain.langgraph_agent import SupremeOrchestrator
from core.admin_god import AdminGodLayer
from core.universal_rules import UniversalRulesEngine


def test_model_router_fallback():
    router = ModelRouter()
    router.openrouter_api_key = ""

    with patch.object(router, '_call_ollama', return_value={"success": True, "provider": "ollama", "text": "local response", "cost": 0.0}):
        res = router.route_and_generate("hello", "coding")
        assert res["success"] is True
        assert res["provider"] == "ollama"
        assert res["text"] == "local response"


def test_orchestrator_admin_blocking():
    rules_engine = UniversalRulesEngine()
    rules_engine.rules["image_generation"]["max_cost_per_image"] = 0.01

    admin_god = AdminGodLayer(rules_engine)
    orchestrator = SupremeOrchestrator(admin_god=admin_god)

    context = {"task_type": "image_generation", "cost": 0.05}
    res = rules_engine.apply(context)
    assert res["blocked"] is True


def test_orchestrator_execution_flow():
    mock_router = MagicMock()
    mock_router.route_and_generate.return_value = {
        "success": True,
        "provider": "openrouter",
        "text": "Sure, here is your code.",
        "cost": 0.002,
    }

    orchestrator = SupremeOrchestrator(model_router=mock_router)
    res = orchestrator.execute_task("write a binary search in python", "coding")

    assert res["completed"] is True
    assert res["current_step"] == "completed"
    assert res["result"] == "Sure, here is your code."
    assert res["cost"] == 0.002


def test_route_and_generate_with_cot():
    from tools.cot_reasoner import ChainOfThoughtReasoner
    router = ModelRouter()
    router.cot_reasoner = MagicMock()
    router.cot_reasoner.refine_loop.return_value = {
        "status": "ok",
        "iterations": 1,
        "thoughts": [{"type": "thought", "content": "step one", "reasoning_depth": 0}],
        "final_answer": "42",
        "last_output": {},
    }
    router.cot_reasoner.verify.return_value = {"matches": True}

    def fake_route(self, prompt, task_type="general", max_cost=0.01):
        return {
            "success": True,
            "provider": "openrouter",
            "text": "<answer>42</answer>",
            "cost": 0.0,
        }

    router.route_and_generate = types.MethodType(fake_route, router)
    result = router.route_and_generate_with_cot("1+1?", task_type="math")

    assert result["success"] is True
    assert "reasoning" in result
    assert result["reasoning"]["iterations"] == 1
    assert result["reasoning"]["final_answer"] == "42"
    assert "cot_verification" in result
    assert result["text"] == "<answer>42</answer>"


def test_query_local_rag():
    router = ModelRouter()

    class FakeRAG:
        def semantic_search(self, query):
            return {
                "status": "ok",
                "query": query,
                "matches": [
                    {"doc_id": "doc1", "title": "Python Guide", "score": 1},
                    {"doc_id": "doc2", "title": "Advanced Python", "score": 0},
                ],
            }

    router._local_rag = FakeRAG()
    result = router.query_local_rag("python tutorial")

    assert result["status"] == "ok"
    assert len(result.get("matches", [])) == 2

def test_route_and_stream():
    router = ModelRouter()
    # Mock _stream_ollama
    def mock_stream(prompt, model):
        yield "chunk1"
        yield "chunk2"
    router._stream_ollama = mock_stream
    
    with patch.object(router, '_pick_provider', return_value=("ollama", "qwen")):
        chunks = list(router.route_and_stream("test prompt", "general"))
        assert chunks == ["chunk1", "chunk2"]
