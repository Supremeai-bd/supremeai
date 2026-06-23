#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# file >> rag_pipeline.py
# project >> SupremeAI 2.0
# purpose >> RAG retrieval
# module >> memory
# ============================================================================
from typing import List, Dict, Any
from .chromadb_store import ChromaDBStore

class RAGPipeline:
    """Retrieval-Augmented Generation Pipeline."""
    def __init__(self, vector_store: ChromaDBStore = None):
        self.vector_store = vector_store or ChromaDBStore()
        
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
        words = text.split()
        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
            i += chunk_size - overlap
            if i + chunk_size >= len(words) and i < len(words):
                chunks.append(" ".join(words[i:]))
                break
        return chunks
        
    def ingest_document(self, doc_id: str, content: str, metadata: Dict[str, Any] = {}):
        chunks = self.chunk_text(content)
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{idx}"
            chunk_meta = {**metadata, "chunk_index": idx, "document_id": doc_id}
            self.vector_store.add_document(chunk_id, chunk, chunk_meta)
            
    def retrieve_context(self, query: str, limit: int = 3) -> str:
        results = self.vector_store.query(query, n_results=limit)
        context_parts = []
        for doc_id, score, doc_data in results:
            if score > 0.05: # threshold
                context_parts.append(doc_data["text"])
        return "\n---\n".join(context_parts)
