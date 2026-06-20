import re
from typing import Dict, Any, Tuple

class LanguageRouter:
    BENGALI_RE = re.compile(r'[\u0980-\u09FF]')
    CHINESE_RE = re.compile(r'[\u4E00-\u9FFF]')
    JAPANESE_RE = re.compile(r'[\u3040-\u309F\u30A0-\u30FF]')
    ARABIC_RE = re.compile(r'[\u0600-\u06FF]')
    HINDI_RE = re.compile(r'[\u0900-\u097F]')

    PROVIDER_MAP = {
        "bengali": "deepseek",
        "chinese": "openrouter",
        "japanese": "gemini",
        "arabic": "groq",
        "hindi": "deepseek",
        "english": "openrouter",
    }

    def detect(self, text: str) -> str:
        if not text:
            return "english"
        if self.BENGALI_RE.search(text):
            return "bengali"
        if self.CHINESE_RE.search(text):
            return "chinese"
        if self.JAPANESE_RE.search(text):
            return "japanese"
        if self.ARABIC_RE.search(text):
            return "arabic"
        if self.HINDI_RE.search(text):
            return "hindi"
        return "english"

LANGUAGE_MODEL_MAP = {
    "zh": "01-ai/yi-34b-chat",
    "ja": "01-ai/yi-34b-chat",
    "ko": "01-ai/yi-34b-chat",
    "ar": "openai/gpt-4o",
    "bn": "supremeai/bangla-native",
    "en": "openrouter",
}

LANGUAGE_MODEL_FALLBACK = {
    "chinese": "01-ai/yi-34b-chat",
    "japanese": "01-ai/yi-34b-chat",
    "korean": "01-ai/yi-34b-chat",
    "arabic": "openai/gpt-4o",
    "bengali": "supremeai/bangla-native",
    "hindi": "deepseek",
    "english": "openrouter",
}

    def route(self, text: str, task_type: str = "general") -> Dict[str, Any]:
        language = self.detect(text)
        provider = self.PROVIDER_MAP.get(language, "openrouter")
        return {
            "language": language,
            "provider": provider,
            "task_type": task_type,
            "reason": f"Detected language '{language}', routed to provider '{provider}'",
        }

    def route_by_language(self, text: str, detected_lang: Optional[str] = None) -> Dict[str, Any]:
        language = detected_lang or self.detect(text)
        model = self.LANGUAGE_MODEL_MAP.get(language) or self.LANGUAGE_MODEL_FALLBACK.get(language) or "openrouter"
        return {
            "language": language,
            "model": model,
            "task_type": None,
            "reason": f"Detected language '{language}', routed to model '{model}'",
        }
