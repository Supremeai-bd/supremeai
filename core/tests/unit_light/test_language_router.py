"""Tests for core.language_router — pure script/language detection and routing."""

from core.language_router import LanguageRouter


def test_detect_english_default():
    assert LanguageRouter().detect("Hello world") == "english"


def test_detect_empty():
    assert LanguageRouter().detect("") == "english"


def test_detect_bengali():
    assert LanguageRouter().detect("আজকের আবহাওয়া কেমন?") == "bengali"


def test_detect_chinese():
    assert LanguageRouter().detect("你好世界") == "chinese"


def test_detect_japanese():
    assert LanguageRouter().detect("こんにちは") == "japanese"


def test_detect_arabic():
    assert LanguageRouter().detect("مرحبا بالعالم") == "arabic"


def test_detect_hindi():
    assert LanguageRouter().detect("नमस्ते दुनिया") == "hindi"


def test_route_uses_provider_map():
    result = LanguageRouter().route("আজকের আবহাওয়া")
    assert result["language"] == "bengali"
    assert result["provider"] == "deepseek"
    assert "bengali" in result["reason"]


from core.config import settings


def test_route_by_language_explicit():
    result = LanguageRouter().route_by_language("text", detected_lang="japanese")
    assert result["language"] == "japanese"
    assert result["model"] == settings.model_multilingual


def test_route_by_language_fallback():
    result = LanguageRouter().route_by_language("text", detected_lang="korean")
    assert result["model"] == settings.model_multilingual


def test_route_by_language_unknown_fallback():
    result = LanguageRouter().route_by_language("text", detected_lang="klingon")
    assert result["model"] == settings.model_multilingual
