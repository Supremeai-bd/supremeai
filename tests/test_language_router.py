import pytest

from core.language_router import LanguageRouter


@pytest.fixture
def router():
    return LanguageRouter()


@pytest.mark.parametrize("text,expected", [
    ("Hello how are you?", "english"),
    ("", "english"),
    ("   ", "english"),
    ("বাংলা", "bengali"),
    ("হ্যালো বাংলাদেশ", "bengali"),
    ("你好世界", "chinese"),
    ("こんにちは", "japanese"),
    ("مرحبا", "arabic"),
    ("नमस्ते", "hindi"),
    ("Hello世界", "chinese"),
])
def test_detect(router, text, expected):
    assert router.detect(text) == expected


@pytest.mark.parametrize("text,expected_provider", [
    ("Hello", "openrouter"),
    ("বাংলা টেক্সট", "deepseek"),
    ("你好", "openrouter"),
    ("こんにちは", "gemini"),
    ("مرحبا", "groq"),
    ("नमस्ते", "deepseek"),
])
def test_route_provider(router, text, expected_provider):
    result = router.route(text)
    assert result["language"] != "unknown"
    assert result["provider"] == expected_provider
    assert "reason" in result
    assert result["task_type"] == "general"


def test_route_task_type_override(router):
    result = router.route("Hello", task_type="code")
    assert result["task_type"] == "code"
    assert result["language"] == "english"
    assert result["provider"] == "openrouter"
