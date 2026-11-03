"""Unit and regression tests for Vendor-Agnostic Dynamic AI Architecture (Issue #466).

Empirically verifies:
1. Zero-Key Resilience ($N = 0$): System operates cleanly without unhandled crashes.
2. Dynamic Discovery ($N >= 1$): System auto-activates whatever provider is present.
"""

import os

import pytest

from brain.model_router import ModelRouter
from services.voice_service import VoiceService
from tools.social.telegram_bot.ai_engine import AIEngineMixin


class DummyTelegramBot(AIEngineMixin):
    def __init__(self):
        self.processor = None


@pytest.mark.asyncio
async def test_voice_service_zero_key_resilience(monkeypatch):
    """When 0 keys are configured, voice_service must return honest unavailable status without crashing."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
    monkeypatch.delenv("HF_API_KEY", raising=False)

    from core.config import settings

    monkeypatch.setattr(settings, "groq_api_key", "", raising=False)
    monkeypatch.setattr(settings, "openai_api_key", "", raising=False)
    monkeypatch.setattr(settings, "hf_api_key", "", raising=False)

    voice = VoiceService()
    res = await voice.speech_to_text(b"mock_audio_bytes")
    assert res["status"] == "unavailable"
    assert res["reason"] == "STT_NOT_CONFIGURED"
    assert "awaiting" in res["message"].lower() or "not configured" in res["message"].lower()


@pytest.mark.asyncio
async def test_voice_service_dynamic_provider_cascade(monkeypatch):
    """When OpenAI key is configured (and Groq is absent), voice_service must route to OpenAI Whisper."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    from core.config import settings

    monkeypatch.setattr(settings, "groq_api_key", "", raising=False)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-mock-test")

    called_provider = []

    async def mock_openai(self, audio_bytes, filename, api_key):
        called_provider.append("openai")
        return {
            "status": "success",
            "transcript": "dynamic whisper transcript",
            "model": "whisper-1",
        }

    monkeypatch.setattr(VoiceService, "_transcribe_with_openai", mock_openai)

    voice = VoiceService()
    res = await voice.speech_to_text(b"mock_audio_bytes")
    assert res["status"] == "success"
    assert res["transcript"] == "dynamic whisper transcript"
    assert called_provider == ["openai"]


@pytest.mark.asyncio
async def test_model_router_zero_key_resilience(monkeypatch):
    """When no LLM keys are configured, ModelRouter returns a graceful structured response."""
    for key in [
        "GEMINI_API_KEY",
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "MISTRAL_API_KEY",
        "GROQ_API_KEY",
        "ANTHROPIC_API_KEY",
        "DEEPSEEK_API_KEY",
        "COHERE_API_KEY",
        "BYNARA_API_KEY",
        "BAI_API_KEY",
        "TOGETHER_API_KEY",
        "HF_API_KEY",
        "HUGGINGFACE_API_KEY",
        "OLLAMA_API_KEY",
        "OLLAMA_BASE_URL",
    ]:
        monkeypatch.delenv(key, raising=False)

    from core.config import settings

    for attr in [
        "gemini_api_key",
        "openrouter_api_key",
        "openai_api_key",
        "groq_api_key",
        "deepseek_api_key",
        "cohere_api_key",
        "hf_api_key",
    ]:
        if hasattr(settings, attr):
            monkeypatch.setattr(settings, attr, None, raising=False)

    router = ModelRouter()
    res = await router.async_route_and_generate("Hello", task_type="general")
    assert res["success"] is False
    assert res["error"] == "AWAITING_AI_PROVIDER_KEY"
    assert "awaiting" in res["text"].lower()


@pytest.mark.asyncio
async def test_telegram_bot_ai_engine_zero_key_resilience(monkeypatch):
    """When no AI keys are configured, Telegram Bot responds with a polite awaiting message."""
    for key in [
        "GEMINI_API_KEY",
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "GROQ_API_KEY",
        "MISTRAL_API_KEY",
        "ANTHROPIC_API_KEY",
        "DEEPSEEK_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)

    bot = DummyTelegramBot()
    reply = await bot._ai_response("Hello bot", "user_123")
    assert isinstance(reply, str)
    assert len(reply) > 10
    assert "বার্তাটি গ্রহণ করা হয়েছে" in reply or "SupremeAI" in reply


@pytest.mark.asyncio
async def test_voice_service_provider_error_auto_switch(monkeypatch):
    """Provider error must auto-switch to the next configured provider (Issue #466 fallback chain)."""
    monkeypatch.setenv("GROQ_API_KEY", "sk-mock-groq")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-mock-openai")
    monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
    monkeypatch.delenv("HF_API_KEY", raising=False)

    from core.config import settings

    for attr in ("groq_api_key", "openai_api_key", "hf_api_key"):
        if hasattr(settings, attr):
            monkeypatch.setattr(settings, attr, "", raising=False)

    call_order = []

    async def mock_groq_fail(self, audio_bytes, filename, api_key):
        call_order.append("groq")
        return {
            "status": "error",
            "transcript": "",
            "error": "STT_PROVIDER_ERROR",
            "provider_status": 500,
        }

    async def mock_openai_ok(self, audio_bytes, filename, api_key):
        call_order.append("openai")
        return {"status": "success", "transcript": "fallback transcript", "model": "whisper-1"}

    monkeypatch.setattr(VoiceService, "_transcribe_with_groq", mock_groq_fail)
    monkeypatch.setattr(VoiceService, "_transcribe_with_openai", mock_openai_ok)

    voice = VoiceService()
    res = await voice.speech_to_text(b"mock_audio_bytes")
    assert res["status"] == "success"
    assert res["transcript"] == "fallback transcript"
    assert call_order == ["groq", "openai"]


def test_get_voice_service_singleton():
    """websocket_voice route imports get_voice_service — must exist and be a stable singleton."""
    from services.voice_service import get_voice_service

    first = get_voice_service()
    second = get_voice_service()
    assert first is second
    assert isinstance(first, VoiceService)
