import os
from unittest.mock import patch

import pytest

from core.config import Settings


def test_defaults():
    s = Settings()
    assert s.app_name == "SupremeAI 2.0"
    assert s.env == "local"
    assert s.debug is True
    assert s.port == 8000
    assert s.host == "0.0.0.0"
    assert s.supremeai_admin_password_hash is None
    assert s.ollama_url == "http://localhost:11434"
    assert s.gcp_project_id == "supremeai-a"
    assert s.gcp_region == "us-central1"
    assert s.max_cost_per_task == 0.01
    assert s.admin_rules_db == "data/constitutional_rules.db"
    assert s.memory_db_dir == "data/memory"
    assert s.skill_registry_path == "data/skill_registry.json"


@patch.dict(os.environ, {
    "PROJECT_NAME": "TestApp",
    "env": "production",
    "debug": "false",
    "port": "9000",
    "host": "0.0.0.0",
    "supremeai_admin_password_hash": "hashed123",
    "openrouter_api_key": "sk-openrouter",
    "hf_api_key": "sk-hf",
    "gemini_api_key": "sk-gemini",
    "deepseek_api_key": "sk-deepseek",
    "groq_api_key": "sk-groq",
    "nvidia_api_key": "sk-nvidia",
    "firecrawl_api_key": "sk-firecrawl",
    "sentry_dsn": "https://sentry.io/123",
    "ollama_url": "http://ollama:11434",
    "gcp_project_id": "test-project",
    "gcp_region": "europe-west1",
    "max_cost_per_task": "1.5",
    "admin_rules_db": "/tmp/rules.db",
    "memory_db_dir": "/tmp/memory",
    "skill_registry_path": "/tmp/skills.json",
}, clear=False)
def test_env_override():
    s = Settings()
    assert s.PROJECT_NAME == "TestApp"
    assert s.env == "production"
    assert s.debug is False
    assert s.port == 9000
    assert s.host == "0.0.0.0"
    assert s.supremeai_admin_password_hash == "hashed123"
    assert s.openrouter_api_key == "sk-openrouter"
    assert s.hf_api_key == "sk-hf"
    assert s.gemini_api_key == "sk-gemini"
    assert s.deepseek_api_key == "sk-deepseek"
    assert s.groq_api_key == "sk-groq"
    assert s.nvidia_api_key == "sk-nvidia"
    assert s.firecrawl_api_key == "sk-firecrawl"
    assert s.sentry_dsn == "https://sentry.io/123"
    assert s.ollama_url == "http://ollama:11434"
    assert s.gcp_project_id == "test-project"
    assert s.gcp_region == "europe-west1"
    assert s.max_cost_per_task == 1.5
    assert s.admin_rules_db == "/tmp/rules.db"
    assert s.memory_db_dir == "/tmp/memory"
    assert s.skill_registry_path == "/tmp/skills.json"


@patch.dict(os.environ, {"max_cost_per_task": "abc"}, clear=False)
def test_invalid_type_cast():
    with pytest.raises(Exception):
        Settings()
