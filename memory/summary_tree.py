from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from memory.sliding_window import SlidingWindowMemory


class SummaryTree:
    def build_hierarchical_summary(self, documents: List[str]) -> Dict[str, Any]:
        leaves: List[Dict[str, Any]] = []
        for idx, doc in enumerate(documents):
            leaves.append({"id": f"doc-{idx}", "text": doc, "summary": doc[:220]})
        return {"leaves": leaves, "root": {"summary": " ".join(item["summary"] for item in leaves)[:1000]}}

    def extract_key_concepts(self, text: str) -> List[str]:
        tokens = [t.strip() for t in text.replace("\n", " ").split(" ") if t.strip()]
        scored = {t: tokens.count(t) for t in set(tokens) if len(t) > 3}
        return sorted(scored, key=scored.get, reverse=True)[:12]

    def merge_summaries(self, summaries: List[str]) -> str:
        joined = "\n".join(summaries)
        if len(joined) <= 1200:
            return joined.strip()
        trimmed = []
        total = 0
        for summary in summaries:
            total += len(summary)
            if total > 1200:
                break
            trimmed.append(summary)
        return "\n".join(trimmed).strip()
