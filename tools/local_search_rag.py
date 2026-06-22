import typing
from pathlib import Path
from typing import Any, Dict, List
import json

from tools.browser_agent import BrowserAgent


class SearchResult:
    def __init__(self, title: str, url: str, snippet: str, content: str):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.content = content

    def to_dict(self) -> Dict[str, str]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "content": self.content,
        }


class LocalSearchRAG:
    def __init__(self, max_pages: int = 5, max_chars: int = 4000, storage_dir: str = "data/frontier"):
        self.browser = BrowserAgent()
        self.max_pages = max_pages
        self.max_chars = max_chars
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.embeddings_path = self.storage_dir / "search_embeddings.json"
        self._index: Dict[str, List[str]] = {}
        self._load_index()

        self.chroma_client = None
        self.collection = None
        # Initialize ChromaDB persistent client lazily/safely
        try:
            import chromadb
            chroma_dir = self.storage_dir / "chroma"
            self.chroma_client = chromadb.PersistentClient(path=str(chroma_dir))
            self.collection = self.chroma_client.get_or_create_collection(name="local_rag_collection")
        except ImportError:
            import loguru
            loguru.logger.warning("chromadb package not installed. LocalSearchRAG will run with local TF-IDF fallback index.")

    def _load_index(self) -> None:
        if self.embeddings_path.exists():
            try:
                self._index = json.loads(self.embeddings_path.read_text(encoding="utf-8"))
            except Exception:
                self._index = {}

    def build_search_url(self, query: str) -> str:
        from urllib.parse import quote_plus
        return f"https://duckduckgo.com/html/?q={quote_plus(query)}"

    def search(self, query: str) -> Dict[str, Any]:
        search_url = self.build_search_url(query)
        page_result = self.browser.fetch_page(search_url)
        if not page_result.get("success"):
            return {"status": "error", "error": page_result.get("error")}
        results = self._parse_results(page_result.get("content", ""))
        return {"status": "ok", "query": query, "results": [r.to_dict() for r in results[: self.max_pages]]}

    def fetch_and_summarize(self, query: str) -> Dict[str, Any]:
        search_out = self.search(query)
        if search_out.get("status") != "ok":
            return search_out
        summaries: List[str] = []
        stored: Dict[str, List[str]] = {}
        for result in search_out.get("results", [])[: self.max_pages]:
            fetched = self.browser.fetch_page(result["url"])
            if fetched.get("success"):
                text = fetched.get("content", "")[: self.max_chars]
                summaries.append(f"Title: {result['title']}\nURL: {result['url']}\n{text}")
                stored[result["url"]] = [result["title"], text]
        self._store_search(query, stored)
        return {
            "status": "ok",
            "query": query,
            "summaries": summaries,
            "sources": len(summaries),
            "storage_path": str(self.embeddings_path),
        }

    def semantic_search(self, query: str) -> Dict[str, Any]:
        try:
            if not self.collection:
                raise Exception("ChromaDB not available")
            results = self.collection.query(
                query_texts=[query],
                n_results=self.max_pages
            )
            matches = []
            if results and results.get("ids") and results["ids"][0]:
                for idx, doc_id in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][idx] if results.get("metadatas") else {}
                    matches.append({
                        "doc_id": doc_id,
                        "title": metadata.get("title", "Untitled"),
                        "score": float(1.0 - (results["distances"][0][idx] if results.get("distances") else 0.0))
                    })
                return {"status": "ok", "query": query, "matches": matches}
        except Exception as exc:
            import loguru
            loguru.logger.warning(f"ChromaDB semantic search failed: {exc}. Using local TF-IDF fallback.")

        # Enhanced local TF-IDF fallback - works completely offline
        matches = []
        terms = [term.lower() for term in query.split() if term]
        query_tf: typing.Dict[str, float] = {}
        for term in terms:
            query_tf[term] = query_tf.get(term, 0) + 1
        
        for doc_id, fields in self._index.items():
            title, text = fields[0], fields[1] if len(fields) > 1 else ""
            haystack = f"{title} {text}".lower()
            hits = [term for term in terms if term in haystack]
            if hits:
                score = len(hits) / len(terms) if terms else 0
                matches.append({"doc_id": doc_id, "title": title, "score": score})
        matches.sort(key=lambda x: x["score"], reverse=True)
        return {"status": "ok", "query": query, "matches": matches[: self.max_pages], "local_fallback": True}

    def _store_search(self, query: str, docs: Dict[str, List[str]]) -> None:
        self._index[query] = [doc for fields in docs.values() for doc in fields]
        try:
            self.embeddings_path.write_text(json.dumps(self._index, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            pass

        # Add to ChromaDB
        ids = []
        documents = []
        metadatas = []
        import hashlib
        for url, fields in docs.items():
            title, text = fields[0], fields[1] if len(fields) > 1 else ""
            if not text:
                continue
            doc_id = hashlib.md5(url.encode('utf-8')).hexdigest()
            ids.append(doc_id)
            documents.append(text)
            metadatas.append({"url": url, "title": title, "query": query})

        if ids:
            try:
                self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            except Exception as exc:
                import loguru
                loguru.logger.error(f"ChromaDB upsert failed: {exc}")

    def _parse_results(self, page_text: str) -> List[SearchResult]:
        results: List[SearchResult] = []
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        i = 0
        while i < len(lines) - 2 and len(results) < self.max_pages:
            title = lines[i]
            snippet = lines[i + 1]
            url = lines[i + 2]
            if (url.startswith("http://") or url.startswith("https://")) and " " not in url.strip():
                results.append(SearchResult(title=title, url=url, snippet=snippet, content=""))
                i += 3
            else:
                i += 1
        return results
