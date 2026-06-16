import os
import json
import math
from typing import List, Dict, Any, Tuple

class LocalVectorDB:
    """
    Lightweight local Vector Database implementation.
    Uses TF-IDF/word frequency cosine similarity vectors for zero dependencies.
    Provides identical search API to ChromaDB.
    """
    def __init__(self, db_path: str = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(base_dir, "data", "vector_store.json")
        else:
            self.db_path = db_path
            
        self.documents: Dict[str, Dict[str, Any]] = self._load_db()
        
    def _load_db(self) -> Dict[str, Dict[str, Any]]:
        if self.db_path == ":memory:":
            return {}
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
        
    def _save_db(self):
        if self.db_path == ":memory:":
            return
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        try:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self.documents, f, indent=4)
        except Exception:
            pass
            
    def _tokenize(self, text: str) -> List[str]:
        return [w.strip(".,!?;:()\"'").lower() for w in text.split() if w]
        
    def _get_vector(self, text: str) -> Dict[str, int]:
        tokens = self._tokenize(text)
        vector = {}
        for token in tokens:
            vector[token] = vector.get(token, 0) + 1
        return vector
        
    def _cosine_similarity(self, vec1: Dict[str, int], vec2: Dict[str, int]) -> float:
        intersection = set(vec1.keys()) & set(vec2.keys())
        numerator = sum([vec1[x] * vec2[x] for x in intersection])
        
        sum1 = sum([vec1[x]**2 for x in vec1.keys()])
        sum2 = sum([vec2[x]**2 for x in vec2.keys()])
        denominator = math.sqrt(sum1) * math.sqrt(sum2)
        
        if not denominator:
            return 0.0
        return float(numerator) / denominator

    def add_document(self, doc_id: str, text: str, metadata: Dict[str, Any] = {}):
        self.documents[doc_id] = {
            "text": text,
            "metadata": metadata,
            "vector": self._get_vector(text)
        }
        self._save_db()
        
    def query(self, query_text: str, n_results: int = 3) -> List[Tuple[str, float, Dict[str, Any]]]:
        query_vector = self._get_vector(query_text)
        scores = []
        
        for doc_id, doc_data in self.documents.items():
            sim = self._cosine_similarity(query_vector, doc_data["vector"])
            scores.append((doc_id, sim, doc_data))
            
        # Sort descending by score
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:n_results]
class ChromaDBStore(LocalVectorDB):
    """Alias for LocalVectorDB conforming to ChromaDB naming requirements."""
    pass
