from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from memory.chromadb_store import ChromaDBStore
from tools.local_search_rag import LocalSearchRAG


class KnowledgeBaseIndexer:
    def __init__(self, chroma: Optional[ChromaDBStore] = None, rag: Optional[LocalSearchRAG] = None) -> None:
        self.chroma = chroma or ChromaDBStore()
        self.rag = rag or LocalSearchRAG()

    def index_seed_data(self, seed_dir: str = "tools/seed_data/") -> Dict[str, Any]:
        if not os.path.isdir(seed_dir):
            return {"indexed": False, "reason": f"seed directory not found: {seed_dir}"}
        indexed = 0
        for root, dirs, files in os.walk(seed_dir):
            for name in files:
                path = os.path.join(root, name)
                try:
                    text = self._read_text(path)
                    if text:
                        self.chroma.add_documents([text])
                        indexed += 1
                except Exception:
                    pass
        return {"indexed": indexed, "seed_dir": seed_dir}

    def search_knowledge(self, query: str) -> List[Dict[str, Any]]:
        try:
            result = self.rag.semantic_search(query, limit=5)
            matches = result.get("matches", []) if isinstance(result, dict) else []
            return [{"doc_id": m.get("doc_id"), "text": m.get("text"), "score": m.get("score")} for m in matches]
        except Exception:
            return []

    def update_knowledge(self, new_data: Dict[str, Any]) -> Dict[str, Any]:
        text = new_data.get("text") or new_data.get("content") or ""
        if not text:
            return {"updated": False, "reason": "missing text/content"}
        try:
            self.chroma.add_documents([text])
            return {"updated": True}
        except Exception as exc:
            return {"updated": False, "reason": str(exc)}

    @staticmethod
    def _read_text(path: str) -> str:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
