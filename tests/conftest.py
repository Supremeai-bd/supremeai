# tests/conftest.py
"""Pytest configuration and shared fixtures for SupremeAI root test suite.

বাংলা: এই conftest শুধু root tests/ ফোল্ডারের জন্য।
গুরুত্বপূর্ণ: sys.modules['core'] = MagicMock() করা হয় না এখানে কারণ
backend/tests/conftest.py ইতিমধ্যে সঠিকভাবে sys.path সেটআপ করে।
এই blanket MagicMock টেস্টে settings-এর real value নষ্ট করে দিত।
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to sys.path so 'backend.*' imports resolve
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add backend/ to sys.path so 'core.*' imports resolve (same as backend/tests/conftest.py).
# বাংলা: আগে এখানে নির্দিষ্ট core.* সাবমডিউল (core.evolution, core.llm, ...) আলাদাভাবে
# sys.modules-এ MagicMock বসানো হয়েছিল "heavy dependency" এড়াতে, কিন্তু সেটা নিজেই একটা নতুন
# বাগ তৈরি করেছিল: core.llm_router-এর "from .llm.free_tier_tracker import get_tracker" লাইন
# ভেঙে পড়ত ("core.llm is not a package") কারণ sys.modules['core.llm']-এ বসানো MagicMock-এর
# কোনো real __path__ নেই, ফলে তার নিচে কোনো submodule ইম্পোর্ট করা যায় না। core/__init__.py-এর
# torch/aiohttp-নির্ভর ব্লকগুলো ইতিমধ্যে try/except দিয়ে গার্ড করা (দেখুন core/__init__.py), তাই
# আলাদা করে এই সাবমডিউলগুলো ব্লক করার আর দরকার নেই -- শুধু backend/ পাথে যোগ করাই যথেষ্ট।
backend_root = project_root / "backend"
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


# ---------------------------------------------------------------------------
# Fixtures shared across root tests/
# ---------------------------------------------------------------------------


# বাংলা মন্তব্য: BUG FIX - core/security/secret_vault.py-এর secret_vault singleton
# প্রতিটা secret key প্রথমবার fetch হওয়ার সময় নিজের ভেতরে cache করে রাখে এবং তারপর
# আর কখনো os.environ চেক করে না। ফলে test_core_config.py/test_core_config_comprehensive.py-র
# `with patch.dict(os.environ, {...}): settings = Settings()` প্যাটার্ন ব্যর্থ হতো যদি অন্য
# কোনো টেস্ট আগে থেকেই সেই একই key (যেমন GEMINI_API_KEY) fetch করে খালি/ভিন্ন মান cache
# করে রাখত -- পরবর্তী টেস্টের env var override-টা silently ignore হয়ে যেত। secret_vault
# আগে থেকেই invalidate_cache() মেথড এক্সপোজ করে, শুধু কোথাও কল করা হতো না।
@pytest.fixture(autouse=True)
def _reset_secret_vault_cache():
    def _invalidate_all():
        for module_name in ("core.config", "backend.core.config"):
            try:
                module = sys.modules.get(module_name)
                if module is not None and hasattr(module, "secret_vault"):
                    module.secret_vault.invalidate_cache()
            except Exception:
                pass

    _invalidate_all()
    yield
    _invalidate_all()


@pytest.fixture
def mock_docker_sandbox():
    """Mock DockerSandbox for testing without actual container runtime."""
    with patch("backend.agents.ephemeral_executor.DockerSandbox") as mock:
        instance = MagicMock()
        instance.run_quarantine_test.return_value = {
            "exit_code": 0,
            "stdout": "Success",
            "stderr": "",
        }
        mock.return_value = instance
        yield instance


@pytest.fixture
def mock_docker_sandbox_file_gate():
    """Mock DockerSandbox for FileIsolationGate tests."""
    with patch("backend.sandbox.file_isolation_gate.DockerSandbox") as mock:
        instance = MagicMock()
        instance.run_safe_container.return_value = {
            "exit_code": 0,
            "output": "File Size Processed inside Container: 52 bytes",
        }
        mock.return_value = instance
        yield instance


@pytest.fixture
def mock_genai():
    """Mock Google Gemini AI client."""
    with patch("backend.skills.core_knowledge_qa.genai") as mock_genai_module:
        mock_response = MagicMock()
        mock_response.text = "Test answer from AI"
        mock_response.candidates = []

        mock_genai_module.Client.return_value.models.generate_content.return_value = mock_response
        yield mock_genai_module


@pytest.fixture
def mock_firestore():
    """Mock Firestore client."""
    with patch("backend.api.dependencies.TenantAwareFirestore") as mock:
        instance = AsyncMock()
        mock.return_value = instance
        yield instance


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch("backend.core.config.settings") as mock:
        mock.gemini_api_key = "test-api-key"
        mock.supabase_url = "https://test.supabase.co"
        mock.supabase_key = "test-key"
        yield mock


@pytest.fixture
def mock_redis():
    """Mock Redis client for rate limiting and caching."""
    with patch("redis.asyncio.Redis") as mock:
        instance = AsyncMock()
        mock.return_value = instance
        yield instance


@pytest.fixture
def sample_skill_payload():
    """Sample skill payload for testing."""
    return {
        "name": "test_skill",
        "description": "A test skill for unit testing",
        "code": "def execute(payload): return {'result': payload}",
        "entry_file": "main.py",
    }


@pytest.fixture
def sample_bangla_text():
    """Sample Bangla text for testing language detection."""
    return "আমি সুপ্রিম এআই ব্যবহার করছি"


@pytest.fixture
def sample_user_context():
    """Sample user context for RBAC testing."""
    return {
        "user_id": "test-user-123",
        "user_role": "Admin",
        "tenant_id": "test-tenant-456",
    }
