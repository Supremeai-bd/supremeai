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

    def route(self, text: str, task_type: str = "general") -> Dict[str, Any]:
        language = self.detect(text)
        provider = self.PROVIDER_MAP.get(language, "openrouter")
        return {
            "language": language,
            "provider": provider,
            "task_type": task_type,
            "reason": f"Detected language '{language}', routed to provider '{provider}'",
        }
