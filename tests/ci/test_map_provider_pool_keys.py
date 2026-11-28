"""Offline tests for the Infisical alias -> LLM_PROVIDER_KEYS mapping step."""

from __future__ import annotations

import json

from scripts.ci.map_provider_pool_keys import build_pool


def test_alias_values_map_into_pool_with_verified_model(monkeypatch):
    for name in (
        "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_AI_API_KEY", "GEMINI_TOKEN",
        "JULES_API_KEY", "SUPREMEAI_PROVIDER_KEY_GEMINI", "GEMINI_API_KEYS",
        "GROQ_API_KEY", "GROQ_API_KEYS", "GEMINI_MODEL", "EVALUATOR_GEMINI_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GEMINI_TOKEN", "g" * 24)
    monkeypatch.setenv("GROQ_API_KEY", "q" * 24)
    pool = build_pool()
    assert [e["key"] for e in pool["gemini"]] == ["g" * 24]
    assert pool["gemini"][0]["model"] == "gemini-flash-lite-latest"
    assert "gemini-flash-lite-latest" in pool["gemini"][0]["url"]
    assert pool["groq"][0]["model"] == "llama-3.3-70b-versatile"


def test_comma_pool_values_are_split(monkeypatch):
    for name in ("GROQ_API_KEY", "SUPREMEAI_PROVIDER_KEY_GROQ", "GROQ_API_KEYS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SUPREMEAI_PROVIDER_KEY_GROQ", f"{'a' * 20},{'b' * 20}")
    pool = build_pool()
    assert sorted(e["key"] for e in pool["groq"]) == ["a" * 20, "b" * 20]


def test_placeholders_and_short_values_are_rejected(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "changeme")
    assert "openai" not in build_pool()
    monkeypatch.setenv("OPENAI_API_KEY", "short")
    assert "openai" not in build_pool()
    monkeypatch.setenv("OPENAI_API_KEY", "o" * 32)
    assert [e["key"] for e in build_pool()["openai"]] == ["o" * 32]


def test_gemini_model_env_override_is_respected(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "g" * 24)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")
    pool = build_pool()
    assert pool["gemini"][0]["model"] == "gemini-2.0-flash"
    assert "gemini-2.0-flash" in pool["gemini"][0]["url"]


def test_pool_output_is_valid_llm_provider_keys_json(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "q" * 24)
    payload = json.dumps(build_pool(), separators=(",", ":"))
    data = json.loads(payload)
    assert data["groq"][0]["url"] == "https://api.groq.com/openai/v1/chat/completions"
