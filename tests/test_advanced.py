import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.task_router import TaskRouter
from core.evolution_engine import EvolutionEngine
from skills.registry import SkillRegistry
from skills.installer import SkillInstaller
from skills.marketplace import SkillMarketplace
from memory.sqlite_store import SQLiteMemoryStore
from memory.chromadb_store import ChromaDBStore
from memory.rag_pipeline import RAGPipeline
from tools.browser_agent import BrowserAgent
from tools.computer_agent import ComputerAgent
from tools.api_gateway import APIGateway
from interfaces.telegram_bot import TelegramBotHandler
from evolution.daily_learner import DailyLearner
from evolution.self_updater import SelfUpdater

def test_task_router():
    router = TaskRouter()
    r = router.analyze_and_route("write a python script to search a list")
    assert r["task_type"] == "coding"
    
    r = router.analyze_and_route("generate an image of a red square")
    assert r["task_type"] == "image_generation"

def test_evolution_engine():
    engine = EvolutionEngine()
    history = [{"success": True}, {"success": False}]
    report = engine.run_daily_evolution(history)
    assert report["total_tasks_processed"] == 2
    assert report["success_rate"] == 50.0

def test_sqlite_memory_store():
    # Use in-memory SQLite for testing
    store = SQLiteMemoryStore(":memory:")
    store.log_task("Write code", "coding", True, 0.01, "Code written")
    history = store.get_task_history()
    assert len(history) == 1
    assert history[0]["task_description"] == "Write code"

def test_chromadb_local_vector_db():
    db = ChromaDBStore(":memory:")
    db.add_document("doc1", "apple fruit red sweet")
    db.add_document("doc2", "banana yellow long fruit")
    
    res = db.query("red apple", n_results=1)
    assert len(res) == 1
    assert res[0][0] == "doc1"

def test_rag_pipeline():
    db = ChromaDBStore(":memory:")
    pipeline = RAGPipeline(db)
    pipeline.ingest_document("test_doc", "The secret passcode is 12345.")
    ctx = pipeline.retrieve_context("passcode")
    assert "12345" in ctx

def test_browser_agent():
    agent = BrowserAgent()
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = "<html><title>Sample Site</title><body>Hello world</body></html>"
        mock_resp.is_success = True
        mock_get.return_value = mock_resp
        
        res = agent.fetch_page("http://example.com")
        assert res["success"] is True
        assert res["title"] == "Sample Site"

def test_computer_agent_security():
    agent = ComputerAgent()
    res = agent.execute_command("rm -rf /")
    assert res["success"] is False
    assert "Security block" in res["error"]

def test_api_gateway():
    gateway = APIGateway()
    with patch("httpx.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok"}
        mock_post.return_value = mock_resp
        
        res = gateway.trigger_n8n_workflow("webhook/test", {"test": "val"})
        assert res["success"] is True
        assert res["data"] == {"status": "ok"}

def test_telegram_bot_handler():
    handler = TelegramBotHandler()
    res = handler.handle_message("/rules", "user1")
    assert "5 directions" in res
