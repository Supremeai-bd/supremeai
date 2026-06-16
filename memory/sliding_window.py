from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger

@dataclass
class SlidingWindowConfig:
    max_tokens: int = 4000
    overlap_ratio: float = 0.15
    summarize: bool = True

class SlidingWindowMemory:
    """
    Splits large text/documents into overlapping windows for manageable processing.
    Optionally summarizes each window to keep context compact.
    """
    def __init__(self, config: SlidingWindowConfig = None):
        self.config = config or SlidingWindowConfig()

    def _token_count(self, text: str) -> int:
        return max(1, len(text.split()))

    def _make_windows(self, text: str) -> List[str]:
        max_tokens = self.config.max_tokens
        words = text.split()
        if len(words) <= max_tokens:
            return [text]
        overlap = int(max_tokens * self.config.overlap_ratio)
        step = max(1, max_tokens - overlap)
        windows = []
        start = 0
        while start < len(words):
            chunk = words[start:start + max_tokens]
            windows.append(" ".join(chunk))
            start += step
        return windows

    def chunk(self, text: str) -> List[Dict[str, Any]]:
        windows = self._make_windows(text)
        items = []
        for idx, win in enumerate(windows):
            item = {
                "window_index": idx,
                "text": win,
                "token_count": self._token_count(win),
            }
            if self.config.summarize:
                item["summary"] = win[:120].replace("\n", " ")
            items.append(item)
        logger.info(f"SlidingWindow: created {len(items)} windows from {self._token_count(text)} tokens")
        return items

    def build_context(self, documents: List[str], query: str = "") -> str:
        chunks: List[str] = []
        for doc in documents:
            for w in self.chunk(doc):
                chunks.append(w["text"])
        if not chunks:
            return ""
        budget = self.config.max_tokens
        selected: List[str] = []
        total = 0
        if query:
            first, rest = chunks[0], chunks[1:]
            chunks = [first] + sorted(rest, key=lambda x: len(x))
        for part in chunks:
            tc = self._token_count(part)
            if total + tc <= budget:
                selected.append(part)
                total += tc
        return "\n---\n".join(selected)
