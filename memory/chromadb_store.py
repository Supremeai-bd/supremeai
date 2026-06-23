#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# file >> chromadb_store.py
# project >> SupremeAI 2.0
# purpose >> Database operations
# module >> memory
# ============================================================================
from __future__ import annotations

import os
import json
import math
import uuid
from typing import Any, Dict, List, Optional, Tuple

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False


class ChromaDBStore:
    """
    ChromaDB-backed vector store with local TF-IDF fallback.
    Provides add_document, add_documents, query, update, delete, and count APIs.
    """
    def __init__(self, db_path: str = None, collection_name: str = "supremeai_knowledge"):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base_dir, "data", "chromadb_store")
        self.db_path = db_path
        self.collection_name = collection_name
        self._fallback_docs: Dict[str, Dict[str, Any]] = {}
        self._client = None
        self._collection = None
        self._init_chroma()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------
    def _init_chroma(self) -> None:
        if not _CHROMA_AVAILABLE:
            self._load_fallback()
            return
        try:
            os.makedirs(self.db_path, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self.db_path)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception:
            self._client = None
            self._collection = None
            self._load_fallback()

    def _load_fallback(self) -> None:
        path = os.path.join(self.db_path, "fallback_docs.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._fallback_docs = json.load(f)
            except Exception:
                self._fallback_docs = {}

    def _save_fallback(self) -> None:
        if self.db_path == ":memory:":
            return
        os.makedirs(self.db_path, exist_ok=True)
        path = os.path.join(self.db_path, "fallback_docs.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._fallback_docs, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Tokenization / Similarity (fallback mode)
    # ------------------------------------------------------------------
    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [w.strip(".,!?;:()\"'").lower() for w in text.split() if w.strip()]

    @staticmethod
    def _get_vector(text: str) -> Dict[str, int]:
        tokens = ChromaDBStore._tokenize(text)
        vector: Dict[str, int] = {}
        for token in tokens:
            vector[token] = vector.get(token, 0) + 1
        return vector

    @staticmethod
    def _cosine_similarity(vec1: Dict[str, int], vec2: Dict[str, int]) -> float:
        intersection = set(vec1.keys()) & set(vec2.keys())
        numerator = sum(vec1[x] * vec2[x] for x in intersection)
        sum1 = sum(v ** 2 for v in vec1.values())
        sum2 = sum(v ** 2 for v in vec2.values())
        denominator = math.sqrt(sum1) * math.sqrt(sum2)
        return float(numerator) / denominator if denominator else 0.0

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def add_document(self, doc_id: str, text: str, metadata: Dict[str, Any] = None) -> None:
        self.add_documents([{"id": doc_id, "text": text, "metadata": metadata or {}}])

    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        if self._collection is not None:
            ids = []
            texts = []
            metadatas = []
            for doc in documents:
                doc_id = doc.get("id") or str(uuid.uuid4())
                text = doc.get("text") or doc.get("content") or ""
                metadata = doc.get("metadata") or {}
                metadata.setdefault("doc_id", doc_id)
                ids.append(doc_id)
                texts.append(text)
                metadatas.append(metadata)
            try:
                self._collection.upsert(ids=ids, documents=texts, metadatas=metadatas)
                return
            except Exception:
                pass
        for doc in documents:
            doc_id = doc.get("id") or str(uuid.uuid4())
            text = doc.get("text") or doc.get("content") or ""
            metadata = doc.get("metadata") or {}
            self._fallback_docs[doc_id] = {
                "text": text,
                "metadata": metadata,
                "vector": self._get_vector(text),
            }
        self._save_fallback()

    def query(self, query_text: str, n_results: int = 5, where: Dict[str, Any] = None) -> List[Tuple[str, float, Dict[str, Any]]]:
        if self._collection is not None:
            try:
                results = self._collection.query(query_texts=[query_text], n_results=n_results)
                matches: List[Tuple[str, float, Dict[str, Any]]] = []
                if results and results.get("ids") and results["ids"][0]:
                    for idx, doc_id in enumerate(results["ids"][0]):
                        distance = results["distances"][0][idx] if results.get("distances") else 0.0
                        score = float(1.0 - distance)
                        meta = results["metadatas"][0][idx] if results.get("metadatas") else {}
                        doc_text = results["documents"][0][idx] if results.get("documents") else ""
                        matches.append((doc_id, score, {"text": doc_text, "metadata": meta}))
                    return matches
            except Exception:
                pass
        query_vector = self._get_vector(query_text)
        scored = []
        for doc_id, doc_data in self._fallback_docs.items():
            score = self._cosine_similarity(query_vector, doc_data["vector"])
            scored.append((doc_id, score, doc_data))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:n_results]

    def delete(self, doc_id: str) -> None:
        if self._collection is not None:
            try:
                self._collection.delete(ids=[doc_id])
                return
            except Exception:
                pass
        self._fallback_docs.pop(doc_id, None)
        self._save_fallback()

    def count(self) -> int:
        if self._collection is not None:
            try:
                return self._collection.count()
            except Exception:
                pass
        return len(self._fallback_docs)

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        if self._collection is not None:
            try:
                result = self._collection.get(ids=[doc_id])
                if result and result.get("documents"):
                    return {
                        "id": doc_id,
                        "text": result["documents"][0],
                        "metadata": result["metadatas"][0] if result.get("metadatas") else {},
                    }
            except Exception:
                pass
        return self._fallback_docs.get(doc_id)
