from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
import sys

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from tools.local_search_rag import LocalSearchRAG
except ImportError:
    LocalSearchRAG = None

try:
    import sqlite3
except ImportError:
    sqlite3 = None

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "knowledge_store.db")

class KnowledgeSearchRequest(BaseModel):
    query: str
    limit: int = 5
    use_fts: bool = True

class KnowledgeSearchResult(BaseModel):
    id: str
    title: str
    content: str
    score: Optional[float] = None
    source: Optional[str] = None

def _fts_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    if sqlite3 is None:
        raise RuntimeError("sqlite3 module is not available")
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, content, source, bm25(knowledge_fts) AS score FROM knowledge_fts WHERE knowledge_fts MATCH ? ORDER BY score LIMIT ?",
            [query, limit],
        )
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()

@router.post("/search", response_model=List[KnowledgeSearchResult])
def knowledge_search(request: KnowledgeSearchRequest) -> List[KnowledgeSearchResult]:
    results: List[Dict[str, Any]] = []
    if request.use_fts and sqlite3 is not None:
        try:
            results = _fts_search(request.query, request.limit)
        except Exception:
            results = []
    if not results and LocalSearchRAG is not None:
        try:
            rag = LocalSearchRAG()
            rag_results = rag.semantic_search(request.query, limit=request.limit)
            matches = rag_results.get("matches", []) if isinstance(rag_results, dict) else []
            for m in matches:
                results.append({
                    "id": m.get("doc_id"),
                    "title": m.get("title", ""),
                    "content": m.get("text", ""),
                    "score": m.get("score"),
                    "source": "chromadb",
                })
        except Exception:
            pass
    formatted: List[KnowledgeSearchResult] = []
    for row in results[: request.limit]:
        formatted.append(
            KnowledgeSearchResult(
                id=row.get("id", ""),
                title=row.get("title", ""),
                content=row.get("content", ""),
                score=row.get("score"),
                source=row.get("source"),
            )
        )
    return formatted
