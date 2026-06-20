import os
import pytest
from core.rbac import RoleBasedAccessControl

_TEST_ENV_DEFAULTS = {
    "ENV": "test",
    "OPENROUTER_API_KEY": "",
    "HF_API_KEY": "",
    "GEMINI_API_KEY": "",
    "DEEPSEEK_API_KEY": "",
    "GROQ_API_KEY": "",
    "NVIDIA_API_KEY": "",
    "FIRECRAWL_API_KEY": "",
    "OLLAMA_URL": "http://localhost:11434",
    "SUPREMEAI_API_TOKEN": "",
    "SENTRY_DSN": "",
    "GCP_PROJECT_ID": "",
    "GCP_REGION": "",
}


@pytest.fixture
def rbac():
    return RoleBasedAccessControl()


@pytest.fixture(autouse=False)
def isolate_env(monkeypatch: pytest.MonkeyPatch):
    for key, value in _TEST_ENV_DEFAULTS.items():
        monkeypatch.setenv(key, value)
